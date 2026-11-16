"""Object storage for product images.

What it does: defines the storage interface, a Supabase implementation and an
in-memory fake, plus the validation every upload must survive.
Where it fits: used by services/admin_image.py; the fake is what the test suite
runs against, so image handling is fully covered without credentials.

Why a public bucket: signed URLs expire. A storefront page would start showing
broken images, and worse, order items snapshot the image URL - an expired link
in a two-year-old order is not recoverable.
"""

from __future__ import annotations

import io
import re
import uuid
from typing import Protocol

import httpx
from PIL import Image, JpegImagePlugin, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import AppError, ValidationError

#: Only these three. SVG is deliberately absent: it is a document format that
#: can carry scripts, and it would be served from the same origin as the site.
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

#: The `ftyp` brands of an HEVC-coded HEIF: the HEIC an iPhone saves a photo as.
#: Pillow has no decoder for it and cannot even name it, so without this check
#: the admin was told the file is not an image, with nothing about the format.
_HEIC_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs"})


def _is_heic(data: bytes) -> bool:
    """Whether the leading `ftyp` box names an HEIC brand, major or compatible.

    Compatible brands too, because a file whose major brand is the generic
    `mif1` can still be HEVC inside. The box is read no further than 64 bytes:
    its declared size comes from the file and is not evidence of anything.
    """
    if data[4:8] != b"ftyp":
        return False
    end = min(int.from_bytes(data[:4], "big"), len(data), 64)
    brands = [data[8:12], *(data[i : i + 4] for i in range(16, end - 3, 4))]
    return any(brand in _HEIC_BRANDS for brand in brands)


def _announced_format(data: bytes) -> str | None:
    """The Pillow format, other than an allowed one, that the first bytes announce.

    A signature check only: it asks each plugin's own `accept` function about the
    16-byte prefix and never calls the plugin's parser. That is the point. A
    plain `Image.open` hands an upload to every parser Pillow has until one
    takes it, so the GIF, TIFF, EPS, PPM, MSP... parsers - where most of
    Pillow's published vulnerabilities live - ran on bytes from the network
    only to find out the file was not JPEG, PNG or WebP. `validate_image` now
    opens with `formats=` the allowed three, and this is how a file that
    Pillow could have opened as something else is still told apart from one
    that is not an image: the panel tells the admin which format to export.

    What still holds: a file whose prefix also matches an allowed format is not
    "another format" - it is an allowed one that failed to parse (MPO shares
    JPEG's signature), so the answer is None and it stays INVALID_IMAGE.
    """
    Image.init()  # registers every plugin (imports only; no file is parsed)
    prefix = data[:16]
    announced: list[str] = []
    for name, (_factory, accept) in Image.OPEN.items():
        if accept is None:
            continue
        try:
            matched = accept(prefix) is True
        except Exception:  # noqa: S112 - a probe must never turn a refusal into a 500
            continue
        if not matched:
            continue
        if name in ALLOWED_FORMATS:
            return None
        announced.append(name)
    return announced[0] if announced else None


def _unsupported_format(detected: str, declared_type: str | None) -> ValidationError:
    return ValidationError(
        "Only JPEG, PNG and WebP images are accepted",
        code="UNSUPPORTED_IMAGE_FORMAT",
        details={"detected": detected, "declared": declared_type},
    )


_MIB = 1024 * 1024

#: What one upload costs to verify, decode and shrink, as `(fixed, per pixel)`.
#:
#: Measured, not derived: `validate_image` + `shrink_to_fit` on one image per
#: case in a fresh process, peak RSS in the production image. Sized on Pillow
#: 12.3; re-checked on 13.0.0 (python:3.14.7-slim-trixie, the locked wheels, the
#: four cases of TestDecodeMemoryIsBounded, three runs each): the worst-case
#: peaks came out at 90.2-91.1 MiB against 90.4-91.4 on 12.3, within the 0.5 MiB
#: the runs differ by among themselves, so nothing below was changed. The
#: audit that asked for this limit assumed one number for every format - 50M
#: pixels x 4 bytes, around 200 MB - where a WebP at that resolution actually
#: peaks at 812 MB. That spread is why the limit cannot be a single pixel count:
#: it would be either unsafe for a WebP or useless for a photo.
#:
#: Linux is what these are sized on, because production is Linux and the two
#: platforms do not agree: at the same pixel count libwebp costs about 8 MiB more
#: here than on Windows. The earlier numbers were Windows ones - the Linux
#: measurement was reading a broken counter at the time and could not contradict
#: them - which is how WebP came to be under-priced.
#:
#: JPEG's and PNG's pairs are the most expensive variant of their path, because
#: the ceiling is set by the worst file the validation accepts, not by the
#: average upload. WEBP's was set from the most expensive variant measured at
#: the time and is known not to cover alpha made of noise (see the WEBP entry).
#: The fixed part is mostly the re-encode of the 1600px result, which is why WebP -
#: saved with `method=5` - carries most of it. The WEBP pair was measured with
#: `method=6`, which holds more while it encodes (on Windows the same WebP case
#: fell from 90 to 58 MiB and a lossy RGBA one from 97 to 82 on the switch), and
#: was re-measured with `method=5` on Linux (the production image, Docker
#: Desktop's WSL2 VM, Pillow 13.0.0, libwebp 1.6.0): the limit stayed. See the
#: WEBP entry for the numbers and why a lower cost was not justified. It is also
#: rounded up well past the measurement on purpose: the peak does not grow
#: smoothly with the pixel count.
#: Measured on Linux, a 2250x1688 WebP peaks 9 MiB above a 2190x1643 one, which
#: is the allocator handing out whole blocks. The margin lives in the fixed part
#: because that is where such a jump is largest relative to the total.
#:
#: The shape matters as much as the count, and the worst one is the squarest:
#: a source only just above MAX_STORED_EDGE is barely reduced, so the bitmap and
#: an almost equally large result are alive together. Every number here is
#: measured on that shape. An image at or below the edge with Orientation 1 is
#: never costed at all - `validate_image` applies the budget only to an image
#: that is decoded - so these limits are free to sit below 1600x1600, and WebP's
#: now does. One at or below the edge that must be rotated is decoded, so it is
#: costed like the rest.
DECODE_COST = {
    # The bitmap (4 bytes per pixel even for RGB), reduce()'s half-size copy on
    # the way to MAX_STORED_EDGE, and a coefficient buffer. Admits 13.3
    # megapixels, which covers every phone's default photo; 3651x3651 peaks at
    # 90.4 MiB. Both JPEG paths are nearly shape-blind - the coefficient buffer
    # and the bitmap follow the source, not the reduction - so re-measuring them
    # on the worst shape moved neither by more than 0.5 MiB.
    "JPEG": (11 * _MIB, 7),
    # Full-resolution chroma (4:4:4, 4:2:2) or four components (CMYK) make that
    # coefficient buffer two to four times bigger. Cameras do not write these;
    # image editors exporting at high quality do. 2797x2797 peaks at 90.4 MiB.
    "JPEG_FULL_CHROMA": (3 * _MIB, 13),
    # RGBA is the worst case: resize() premultiplies into a second full-size copy
    # (RGBa) and skips reduce() while both are alive, which is also why the shape
    # moves this path so much - on the squarest shape the old limit peaked at
    # 95.9 MiB where the 4:3 image of the same size peaked at 91.2. The fixed
    # part absorbs that: 8.27 megapixels, and 2876x2876 peaks at 90.9 MiB.
    "PNG": (29 * _MIB, 9),
    # libwebp's animation decoder - the only WebP path Pillow has - holds a
    # current and a previous canvas, Pillow copies the frame out as `bytes`, and
    # only then fills its own bitmap. Several times a JPEG's pixel for the same
    # picture, which is why a WebP is held to 1.9 megapixels and a photo to 13.3.
    # The fixed part carries the whole correction: on Linux, on the squarest
    # shape, the old 2.62 megapixel limit peaked at 120.0 MiB. 1601x1187 peaked
    # at 91.4 with `method=6`.
    #
    # Re-measured with `method=5`, on Linux, 1601x1187 (the largest the budget
    # admits; three runs, within 0.5 MiB of each other):
    #   RGBA flat, lossless (TestDecodeMemoryIsBounded's case)  51 MiB
    #   RGBA flat, lossy 52 - RGB flat, lossy 40
    #   RGBA photo with a soft-edged cut-out mask               82.5
    #   RGBA with noise in the alpha channel                    109
    #   RGBA noise, lossless                                    113
    # The flat figure alone would admit about 3.7 megapixels, but it is not what
    # sets the limit: decoding takes 47-55 MiB whatever the file holds, and the
    # re-encode adds 4 MiB for a flat picture, 36 for a cut-out and 58 for noise,
    # because libwebp's alpha encoder allocates by what it finds in the plane.
    # A cut-out reaches the budget between 2.3 and 2.6 megapixels (98.5 MiB at
    # 2.3, 107.8 at 2.6), so there is no room to admit more, and the pair is
    # kept. What still holds: a cut-out like that stays 17 MiB under the budget
    # at 1.9 megapixels, and an RGB one 31-60 MiB under (flat lossy 40.1, photo
    # 39.5, noise 62.1 lossy and 68.9 lossless, at 1601x1187). What does not:
    # alpha made of noise is over the budget on both paths that decode. Measured
    # on Linux, the resize path (1601x1187) peaks at 108.8-113.4 MiB with noise
    # in alpha; the only-turning path (EXIF orientation 6, 1378x1378 and
    # 1600x1187) at 107.9-108.1 with noise in alpha and 112.5-112.8 for RGBA
    # noise, lossless. That is accepted by the owner as a risk (PROJECT.md
    # Accepted Risks, AUDIT.md A-103), and the flat test fixture cannot show it.
    "WEBP": (71 * _MIB, 16),
}


def _decode_cost(probe: Image.Image, image_format: str) -> tuple[int, int]:
    """The `(fixed, per pixel)` cost of decoding this particular image.

    Everything read here comes from the header: `Image.open` parses the format,
    the mode and the JPEG sampling factors without materialising a pixel, which
    is what lets the cost be checked before anything is allocated.

    JPEG is split in two because a progressive file makes libjpeg hold every DCT
    coefficient of the image at once, and how much that is depends on the chroma
    sampling. A baseline single-scan file needs none of it, but the header cannot
    promise that a file is single-scan - the scan count is only known once the
    whole file has been read - so both classes are priced as if the buffer were
    there. Grayscale and 4:2:0 are the cheap class, and they are also what every
    phone camera writes.
    """
    if image_format != "JPEG":
        return DECODE_COST[image_format]
    subsampled = probe.mode == "L" or JpegImagePlugin.get_sampling(probe) == 2
    return DECODE_COST["JPEG" if subsampled else "JPEG_FULL_CHROMA"]


def _max_pixels(probe: Image.Image, image_format: str) -> int:
    """How many pixels of this image fit in the decode budget.

    Never negative: a budget below the fixed cost leaves room for nothing, and
    the answer is then zero rather than a negative limit that would accept
    everything.
    """
    fixed, per_pixel = _decode_cost(probe, image_format)
    return max(0, (settings.max_image_decode_bytes - fixed) // per_pixel)


_ORIENTATION_TAG = 0x0112


def _png_exif(data: bytes) -> bytes | None:
    """The payload of the first `eXIf` chunk of a PNG, wherever it sits, or None.

    Pillow only has a PNG's EXIF at open when the chunk precedes the pixel data;
    one placed after IDAT (the PNG spec allows either) is read only by `load()`,
    which decodes the whole image. So the chunk list is walked here, the way
    `_strip_png` walks it: length and type of each chunk, no CRC, no pixels. Cost:
    one pass over the chunk headers, the same order of work as Pillow's own
    `verify()`, which walks every chunk of the file (and checks its CRC); it
    stops at IEND or at the first chunk that does not fit, and a file that is
    broken is refused later by `verify()`, not here.
    """
    size = len(data)
    pos = 8  # past the signature, which Pillow has already matched
    while pos + 12 <= size:
        end = pos + 12 + int.from_bytes(data[pos : pos + 4], "big")
        if end > size:
            return None
        kind = data[pos + 4 : pos + 8]
        if kind == b"eXIf":
            return data[pos + 8 : end - 4]
        if kind == b"IEND":
            return None
        pos = end
    return None


def _exif_orientation(probe: Image.Image, data: bytes) -> int:
    """The EXIF Orientation of a just-opened image, 1 (upright) when there is none.

    `data` is the file `probe` was opened from. Header-only on purpose, and the
    one function both `validate_image` and `shrink_to_fit` ask, so they agree on
    which images are decoded: it reads the raw EXIF and parses only that.
    `getexif()` is avoided because on a PNG whose `eXIf` chunk follows the pixel
    data it calls `load()`, which decodes the whole image before the budget has
    been checked. A PNG's EXIF is therefore always taken from its chunk list
    (`_png_exif`) and never from `info["exif"]`, so an `eXIf` before the pixel
    data and one after it turn the picture the same way.

    Only EXIF counts. A browser turns a picture upright by EXIF Orientation and
    ignores the XMP one, and XMP is removed from what is stored anyway.

    What still holds: a PNG with several `eXIf` chunks (the spec allows one) is
    read from the first. A value outside 2..8 (0, 9, garbage, a non-integer) is
    not a rotation, and unreadable EXIF is not a reason to refuse a picture.
    """
    raw = _png_exif(data) if probe.format == "PNG" else probe.info.get("exif")
    if not raw:
        return 1
    exif = Image.Exif()
    try:
        exif.load(raw)
        value = exif.get(_ORIENTATION_TAG, 1)
    except Exception:  # damaged EXIF must never turn an upload into a 500
        return 1
    return value if isinstance(value, int) and 2 <= value <= 8 else 1


class StorageBackend(Protocol):
    """What the image service needs from storage."""

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Store the object and return its public URL."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object. Missing objects are not an error."""
        ...


def validate_image(data: bytes, declared_type: str | None) -> tuple[str, str]:
    """Decode the bytes and return `(format_name, extension)`.

    The filename extension and the client-declared MIME type are both supplied
    by the caller and neither is evidence of anything, so the file is actually
    decoded. `Image.verify()` parses the structure without materialising the
    pixels, which is what makes the checks below meaningful before any
    allocation: both the resolution and what it will cost to decode are known
    while the bitmap still does not exist.
    """
    if not data:
        raise ValidationError("The file is empty", code="EMPTY_FILE")
    if len(data) > settings.max_image_bytes:
        limit_mb = settings.max_image_bytes // (1024 * 1024)
        raise ValidationError(
            f"The image must be at most {limit_mb} MB",
            code="IMAGE_TOO_LARGE",
            # The panel turns this into advice. A photo straight off a phone is
            # the ordinary way to meet this limit, and "too large" on its own
            # reads like the feature is broken.
            details={"maxBytes": settings.max_image_bytes},
        )

    try:
        # `formats=` is a security boundary, not an optimisation: only the three
        # parsers we accept ever see the bytes. Anything else is answered below
        # from its signature (`_announced_format`).
        with Image.open(io.BytesIO(data), formats=list(ALLOWED_FORMATS)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            # While the header is still open: verify() releases it, and the
            # sampling factors are only readable from the probe.
            allowed = image_format in ALLOWED_FORMATS
            pixel_budget = _max_pixels(probe, image_format) if allowed else 0
            orientation = _exif_orientation(probe, data)
            # Read at open, like the size: Pillow takes an APNG's from its `acTL`
            # and a WebP's from the demuxer's header, and no frame is decoded.
            # JPEG has no such attribute - one picture.
            frames = getattr(probe, "n_frames", 1)
            probe.verify()
    except Image.DecompressionBombError as exc:
        # Pillow has a guard of its own: it warns above MAX_IMAGE_PIXELS
        # (89,478,485) and raises above twice that, inside open(), before the
        # size above is ever read. DecompressionBombError is a plain Exception -
        # not an OSError, not a ValueError - so it used to pass straight through
        # the handler below and reach the client as a 500 for an image that was
        # merely too big. The budget here is far stricter than Pillow's limit at
        # any sane setting, so the two guards now agree on the answer as well as
        # on the verdict.
        raise ValidationError(
            "The image resolution is too large", code="IMAGE_TOO_MANY_PIXELS"
        ) from exc
    # SyntaxError is Pillow's own answer for a PNG that ends inside a chunk
    # header ("broken PNG file"; 5 or 8 bytes cut off the end of the file - any
    # other cut is an OSError) and it is neither an OSError nor a ValueError, so
    # a partly downloaded upload used to reach the client as a 500. The tuple
    # stays closed: anything Pillow raises that is not a statement about these
    # bytes is still a bug, not a refusal.
    #
    # IndexError is Pillow's answer to two files whose headers contradict
    # themselves, both raised after `_open` (which converts it to a SyntaxError
    # only while it runs): a JPEG whose SOF declares three components and lists
    # fewer (`get_sampling`, called from `_decode_cost`, reads `layer[0..2]`) and
    # a PNG with no IDAT between IHDR and IEND (`verify()` seeks to `tile[0]`).
    # The try holds nothing of ours that indexes: `_max_pixels` is arithmetic and
    # a dict lookup, `_png_exif` only slices, and `_exif_orientation` catches
    # everything itself - so an IndexError here is Pillow's, about these bytes.
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, IndexError) as exc:
        if _is_heic(data):
            raise _unsupported_format("HEIC", declared_type) from exc
        if (announced := _announced_format(data)) is not None:
            raise _unsupported_format(announced, declared_type) from exc
        raise ValidationError("This file is not a readable image", code="INVALID_IMAGE") from exc

    if not allowed:
        raise _unsupported_format(image_format or "unknown", declared_type)

    # A product photo does not move, and animation was the one thing the two ways
    # of storing an image disagreed about: one that fits kept every frame (the
    # byte-level strip), one that was reduced became its first frame (the
    # re-encode). Refused rather than reconciled.
    #
    # After `verify()` and the format check, so a file that is not a whole image
    # is still INVALID_IMAGE and HEIC (never opened here) still names its format;
    # before the pixel limit, because an animation is refused at any size - telling
    # the admin to export a smaller one would only lead to this refusal next.
    #
    # What still holds: one frame is accepted, including an APNG whose `acTL` says
    # one and a `VP8X`-animated WebP with one `ANMF`. An APNG is stored as a static
    # PNG: `_PNG_KEPT` has no acTL/fcTL/fdAT, because a second `acTL` makes Pillow
    # drop the animation and count one frame whatever the first said, so such a
    # file passes this check at one. Whatever the file carried, the stored one is
    # the IDAT picture. An APNG whose default image is not frame 0 is still refused
    # here (Pillow counts two frames). The WebP is different and unchanged: `_WEBP_KEPT` still
    # lists ANIM/ANMF, so a one-frame animated WebP keeps them and the WebP walker
    # has to hold for exactly these files.
    if frames > 1:
        raise ValidationError("Animated images are not accepted", code="IMAGE_ANIMATED")

    # A decompression bomb is small on disk and enormous once decoded, and the
    # decode is what allocates - so the limit is memory, converted into a pixel
    # count at this file's own cost. A WebP buys roughly a seventh of the pixels a
    # phone's JPEG (4:2:0) does for the same memory: at the default 100 MiB, 13.3
    # megapixels against 1.9 (`DECODE_COST` above).
    #
    # Only an image that will actually be decoded pays it: one that is resized
    # (longest side above the edge) or turned upright (EXIF Orientation other
    # than 1). `shrink_to_fit` strips the metadata of any other image at the byte
    # level, without materialising a pixel, so there is no allocation to bound -
    # measured, a 1600x1600 WebP peaks at 4.9 MiB where a 1601x1599 one, one
    # pixel wider and the same megapixels, peaks at 120.6 MiB. A cost in pixels
    # alone cannot tell those two apart, and charging the cheap one as though it
    # decoded is what used to pin the WebP limit at 2,560,000 pixels.
    #
    # What is unchecked is exactly: at most 1600x1600 AND Orientation 1, which is
    # never decoded. That is the 4.9 MiB case. The same 1600x1600 with an
    # Orientation of 6 is decoded to be rotated, so it is costed like any other.
    # Orientation is read by the same function `shrink_to_fit` uses, so the two
    # cannot disagree about which images get decoded.
    if (max(width, height) > MAX_STORED_EDGE or orientation != 1) and width * height > pixel_budget:
        # The largest version of *this* image that would fit, so the panel can
        # name a size to export instead of only refusing one.
        scale = (pixel_budget / (width * height)) ** 0.5
        raise ValidationError(
            "The image resolution is too large",
            code="IMAGE_TOO_MANY_PIXELS",
            details={
                "width": width,
                "height": height,
                "maxWidth": max(1, int(width * scale)),
                "maxHeight": max(1, int(height * scale)),
            },
        )

    return image_format, ALLOWED_FORMATS[image_format]


#: The longest side an image is stored at.
#:
#: Nothing used to resize an upload: the bytes a phone camera produced were the
#: bytes a shopper downloaded into a 200-pixel card. Measured on a 12MP photo,
#: 2277 KB became 527 KB at this size - the same picture, four times cheaper on
#: a mobile connection, and the largest product image on screen is around 800px
#: wide even on a desktop.
#:
#: Load-bearing a second way, which is not obvious from the name: `validate_image`
#: applies the decode budget only to an image that is decoded, and one at or below
#: this edge with Orientation 1 is not - only its bytes are stripped. So this
#: constant is also the size of the upload that is admitted without being costed,
#: and raising it widens that path - at 1600 the most an unchecked image can cost
#: is a measured 4.9 MiB, but the cost of a decode grows with the square of the
#: edge. Anything that raises this for a larger gallery image has to re-measure
#: that number, not just this one.
MAX_STORED_EDGE = 1600

#: JPEG quality for a re-encode. 82 is the point where the file stops shrinking
#: much and the eye stops noticing.
JPEG_QUALITY = 82

#: What undoes each EXIF Orientation 2..8; 1 is upright and not in the table.
#: The same mapping as `ImageOps.exif_transpose`, applied from the orientation
#: `_exif_orientation` read, so the decision and the rotation cannot disagree.
_UPRIGHT = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def _unreadable() -> ValidationError:
    return ValidationError("This file is not a readable image", code="INVALID_IMAGE")


#: What Pillow raises while decoding bytes that are not a picture, measured on
#: damaged files of all three formats: OSError for JPEG ("image file is
#: truncated", "broken data stream"), PNG pixel data and WebP ("failed to read next
#: frame"); for a PNG chunk after the pixel data - which Pillow parses only when it
#: decodes - ValueError (a chunk too short for its type), SyntaxError (an APNG chunk
#: out of sequence) and IndexError (an `iCCP` with no name, an unguarded index in
#: Pillow). A closed list on purpose: anything else is not a statement about the
#: bytes and stays a 500.
_BAD_PIXEL_DATA = (OSError, ValueError, SyntaxError, IndexError)


# Lossless metadata removal. Each function below walks the container of one
# format byte by byte - no Pillow, no decode, so no allocation to budget - and
# copies everything except the metadata verbatim. Pixels are never touched. A
# file whose structure does not hold together is refused rather than decoded:
# these run on images the decode budget does not cover.


#: An 0xFF that is not a stuffed byte (FF 00) or a restart marker (FF D0-D7): the
#: first thing in entropy-coded data that can end it.
_SCAN_END = re.compile(rb"\xff(?!\x00|[\xd0-\xd7])")

#: A run of 0xFF fill bytes in front of a marker's code.
_FILL = re.compile(rb"\xff+")

#: The most markers one walk consumes before the file is refused. Inside a scan the
#: stuffed bytes and restart markers are copied in bulk by `_SCAN_END`, so the loop
#: turns only for real markers, and a legitimate JPEG has a few dozen: measured, a
#: 4000x3000 progressive file with EXIF and ICC has 27, a baseline one 12, one
#: with a restart marker after every block 13. But JPEG `verify()` checks nothing
#: after SOS, so a 5 MiB file of `FF 01` (a standalone marker, two bytes) or
#: `FF FF 00` (three) would otherwise cost 2.5 M iterations - measured 1.1 s and
#: 1.5 s of CPU per upload. At this cap the walk is bounded whatever the file size:
#: measured 35 ms for 5 MiB of `FF 01` and 84 ms for 5 MiB of `FF FF 00` (each
#: iteration there also searches for the end of the scan), with 65 536 markers
#: costing 27 ms - three orders of magnitude above what any real file needs.
_MAX_JPEG_MARKERS = 65_536


#: The bytes of a JFIF APP0 payload up to and including the thumbnail's width and
#: height: `JFIF\0` (5), version (2), units (1), densities (4), size (2).
_JFIF_HEADER = 14

#: The bytes of an Adobe APP14 payload that mean something: `Adobe` (5), version
#: (2), flags0 (2), flags1 (2), transform (1).
_ADOBE_HEADER = 12


def _strip_jpeg(data: bytes) -> bytes:
    """A JPEG without EXIF, XMP, IPTC, comments, thumbnails or anything after the
    image.

    Walks the segments from SOI to EOI. Kept, each only when its payload says what
    it is: APP0 starting `JFIF\\0` (the density and aspect), APP2 starting
    `ICC_PROFILE\\0`, APP14 starting `Adobe` (it says how to read the colours); and
    every segment that is not an APPn or a comment (tables, frame and scan
    headers). Dropped: every other APPn - APP0 `JFXX` (an extension that carries
    a thumbnail), APP1 (EXIF and XMP, extended XMP too), APP11 (C2PA), APP13
    (IPTC/Photoshop) - an APP0 or APP14 under another identifier, and COM.
    A kept JFIF or Adobe segment is cut to the header decoders read: JFIF's
    14 bytes with the thumbnail size set to 0x0 (after them the segment may carry
    an uncompressed RGB thumbnail, 3*X*Y bytes), Adobe's 12. A segment that
    already is that - what libjpeg and so Pillow write - is copied unchanged, and
    one shorter than that (no thumbnail size, so no thumbnail) is kept as it is.
    Entropy-coded data is copied untouched, and the walk ends at the first EOI:
    phones, Samsung among them, append metadata trailers after it, and an MPO's
    second picture sits there too.

    What still holds: the PNG and WebP walkers drop by the same rule - a chunk is
    kept because it is known to be harmless, not dropped because it is known to be
    harmful - so an identifying chunk nobody has named yet does not get through in
    any of the three formats.

    Entropy data is not searched for `FF D9` but walked marker by marker: a
    progressive file has segments between its scans, and their bytes can be
    anything. Inside a scan an `FF` is followed by 00 (a stuffed byte), RSTn, or
    a marker that ends the scan.
    """
    size = len(data)
    if data[:2] != b"\xff\xd8":
        raise _unreadable()
    out = bytearray(b"\xff\xd8")
    pos = 2
    in_scan = False
    seen_scan = False
    markers = 0
    while pos < size:
        if in_scan:
            # Entropy-coded bytes up to the next marker, copied in one piece
            # (stuffed bytes and restart markers go along with them).
            ends_scan = _SCAN_END.search(data, pos)
            if ends_scan is None:
                raise _unreadable()
            out += data[pos : ends_scan.start()]
            pos = ends_scan.start()
        if data[pos] != 0xFF:
            # Between header segments, padding or junk before the next marker:
            # not a broken structure, so it is stepped over. It is not copied.
            pos = data.find(b"\xff", pos)
            if pos < 0:
                raise _unreadable()
        # Any number of 0xFF fill bytes may precede a marker's code (skipped in C,
        # not a byte at a time: a file of nothing but 0xFF is 5 M iterations).
        pos += 1  # data[pos] is the 0xFF that starts the marker
        if pos < size and data[pos] == 0xFF:  # the rare case: more fill bytes
            fill = _FILL.match(data, pos)
            if fill is None:  # cannot happen, data[pos] is 0xFF
                raise _unreadable()
            pos = fill.end()
        if pos >= size:
            raise _unreadable()
        marker = data[pos]
        pos += 1
        markers += 1
        if markers > _MAX_JPEG_MARKERS:
            raise _unreadable()
        if in_scan and (marker == 0x00 or 0xD0 <= marker <= 0xD7):
            out += bytes((0xFF, marker))  # a stuffed 0xFF, or a restart marker
            continue
        if marker == 0xD9:
            if not seen_scan:
                raise _unreadable()
            out += b"\xff\xd9"
            return bytes(out)
        if marker == 0x00 or marker == 0xD8:
            raise _unreadable()
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # standalone, no length
            out += bytes((0xFF, marker))
            in_scan = False
            continue
        if pos + 2 > size:
            raise _unreadable()
        length = int.from_bytes(data[pos : pos + 2], "big")
        end = pos + length
        if length < 2 or end > size:
            raise _unreadable()
        payload = data[pos + 2 : end]
        is_app = 0xE0 <= marker <= 0xEF
        if marker == 0xE0 and payload.startswith(b"JFIF\x00"):
            if len(payload) >= _JFIF_HEADER:
                # Only the header, and the thumbnail declared 0x0: what follows
                # the two size bytes is 3*X*Y bytes of uncompressed RGB - a small
                # copy of the whole frame, taken before any crop. A decoder that
                # reads no thumbnail reads nothing else from there.
                payload = payload[: _JFIF_HEADER - 2] + b"\x00\x00"
            # A shorter payload has no thumbnail size and so no thumbnail; it is
            # kept as it is, not refused - Pillow reads such a file.
            out += b"\xff\xe0" + (len(payload) + 2).to_bytes(2, "big") + payload
        elif marker == 0xEE and payload.startswith(b"Adobe"):
            # The 12 bytes decoders use - version, flags, and the transform that
            # says how to read CMYK/YCCK. Anything after them is nobody's.
            payload = payload[:_ADOBE_HEADER]
            out += b"\xff\xee" + (len(payload) + 2).to_bytes(2, "big") + payload
        elif not (is_app or marker == 0xFE) or (
            marker == 0xE2 and payload.startswith(b"ICC_PROFILE\x00")
        ):
            out += bytes((0xFF, marker)) + data[pos:end]
        in_scan = marker == 0xDA
        seen_scan = seen_scan or in_scan
        pos = end
    raise _unreadable()  # no EOI


#: The PNG chunks that are stored: the ones that say how to decode or show the
#: picture, never who made it. An allowlist, because the set of chunks that can
#: carry an identity is open - `caBX` (C2PA, which may name the author), `exIf`
#: and `zxIf` (EXIF under other spellings), `iDOT` (an Apple one), `sPLT`, `tIME`
#: and any private chunk a tool invents - and a denylist only ever removes the ones
#: someone has already named.
#:
#: Critical: IHDR, PLTE, IDAT, IEND. Colour and transparency: tRNS, gAMA, cHRM,
#: sRGB, iCCP (the ICC profile - it changes how the colours look), sBIT, bKGD,
#: cICP, mDCV, cLLI. Size on screen: pHYs. What is not here is dropped,
#: including text (tEXt, zTXt, iTXt), eXIf, tIME and every chunk this list has
#: not heard of.
#:
#: The APNG chunks (acTL, fcTL, fdAT) are deliberately NOT kept. Every APNG
#: `validate_image` accepts has one frame as Pillow counts it, and the stored
#: file is the IDAT picture in every case - the default image Pillow decodes -
#: so dropping them leaves a static PNG. Keeping them was a hole: a second `acTL`
#: makes Pillow drop the animation and count one frame whatever the first said,
#: so a file could pass the one-frame check and still carry frames a browser
#: would animate.
_PNG_KEPT = frozenset(
    {
        b"IHDR",
        b"PLTE",
        b"IDAT",
        b"IEND",
        b"tRNS",
        b"gAMA",
        b"cHRM",
        b"sRGB",
        b"iCCP",
        b"sBIT",
        b"bKGD",
        b"pHYs",
        b"cICP",
        b"mDCV",
        b"cLLI",
    }
)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _strip_png(data: bytes) -> bytes:
    """A PNG with only the chunks in `_PNG_KEPT`.

    Every chunk is length, type, data, CRC, and a kept one is copied whole - the
    CRC with it, so nothing is recomputed. The walk ends after IEND, and what
    follows it is dropped. What still holds: the pixel data is never touched, so
    the result decodes to the same pixels, and a file made only of kept chunks
    comes back byte for byte. An APNG loses its animation chunks (acTL, fcTL,
    fdAT) and becomes a static PNG showing its IDAT frame - the default image,
    which is the only frame `validate_image` lets through.
    """
    size = len(data)
    if data[:8] != _PNG_SIGNATURE:
        raise _unreadable()
    out = bytearray(_PNG_SIGNATURE)
    pos = 8
    while pos + 12 <= size:
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > size:
            raise _unreadable()
        if kind in _PNG_KEPT:
            out += data[pos:end]
        if kind == b"IEND":
            return bytes(out)
        pos = end
    raise _unreadable()  # no IEND


#: The WebP chunks that are stored, by FourCC (`VP8 ` has a trailing space): the
#: image data (VP8, VP8L, ALPH), the header that announces what follows (VP8X),
#: the animation (ANIM, ANMF - `validate_image` accepts an animated WebP only with
#: one frame) and the ICC profile (ICCP - it changes how the colours look). An
#: allowlist for the same reason as `_PNG_KEPT`: EXIF and `XMP ` are the two
#: chunks the format names as metadata, but `C2PA` and any other FourCC a tool
#: invents would have passed a list of those two.
_WEBP_KEPT = frozenset({b"VP8X", b"VP8 ", b"VP8L", b"ALPH", b"ANIM", b"ANMF", b"ICCP"})

#: What an `ANMF` frame may contain after its 16-byte frame header: the frame's own
#: image data. The spec lets a frame carry unknown chunks as well, and they are
#: dropped like any other.
_WEBP_FRAME_KEPT = frozenset({b"VP8 ", b"VP8L", b"ALPH"})
_WEBP_FRAME_HEADER = 16

#: In a WebP `VP8X` header: the EXIF and XMP bits of the feature flags. These are
#: the only flags that announce a chunk this module drops (the others announce ICC,
#: alpha and animation, all kept), so nothing is left announcing what is gone.
_WEBP_EXIF_FLAG = 0x08
_WEBP_XMP_FLAG = 0x04

#: The most chunks one walk consumes - the file's and those inside its `ANMF` frames
#: together - before the file is refused. A legitimate WebP has a handful (measured:
#: 1 for a plain lossless one, 3 with alpha, 5 for a three-frame animation, and an
#: animation costs about 3 per frame, so one of 2 000 frames is about 6 000). But a
#: file may be padded with zero-length unknown chunks of 8 bytes each, and libwebp
#: accepts that after the image data and inside a frame, with no limit of its own:
#: measured, 5 MiB of them (655 000 chunks) passes `validate_image` in 3-65 ms
#: (`Image.open` + `verify()` costs the same, the demuxer is C), while this walk
#: took 285 ms - up to 90 times what validation paid, on every such upload. At this
#: cap the walk is bounded whatever the file size: 33 ms for 5 MiB of them, as 65 000
#: chunks cost before the cap (32 ms). That is the same ceiling as
#: `_MAX_JPEG_MARKERS`, and about 21 000 frames of animation at 3 chunks each -
#: more than 5 MiB of real frames can hold.
_MAX_WEBP_CHUNKS = 65_536


def _webp_chunks(
    data: bytes, pos: int, end: int, left: list[int], *, in_frame: bool = False
) -> bytes:
    """The allowlisted chunks in `data[pos:end]`, each padded to an even length.

    The chunk list of the file, or - with `in_frame` - of one `ANMF` payload after
    its frame header. Only the file level contains frames, so the recursion is one
    level deep and every byte is walked once. `left` is the one-element budget of
    chunks the whole file may still consume (`_MAX_WEBP_CHUNKS` at the start), shared
    by both levels and by every frame, so a file cannot split its chunks between
    them to stay under the cap.
    """
    kept = _WEBP_FRAME_KEPT if in_frame else _WEBP_KEPT
    body = bytearray()
    while pos < end:
        left[0] -= 1
        if left[0] < 0 or pos + 8 > end:
            raise _unreadable()
        fourcc = data[pos : pos + 4]
        length = int.from_bytes(data[pos + 4 : pos + 8], "little")
        payload_end = pos + 8 + length
        if payload_end > end:
            raise _unreadable()
        next_pos = payload_end + length % 2  # the source's padding, whatever is kept
        if fourcc in kept:
            payload = bytearray(data[pos + 8 : payload_end])
            if fourcc == b"VP8X" and payload:
                payload[0] &= ~(_WEBP_EXIF_FLAG | _WEBP_XMP_FLAG)
            elif fourcc == b"ANMF":
                if length < _WEBP_FRAME_HEADER:
                    raise _unreadable()
                frame = _webp_chunks(
                    data, pos + 8 + _WEBP_FRAME_HEADER, payload_end, left, in_frame=True
                )
                payload = payload[:_WEBP_FRAME_HEADER] + frame
                length = len(payload)
            body += fourcc + length.to_bytes(4, "little") + payload
            if length % 2:
                body += b"\x00"  # chunks are padded to an even length
        pos = next_pos
    return bytes(body)


def _strip_webp(data: bytes) -> bytes:
    """A WebP with only the chunks in `_WEBP_KEPT`.

    A RIFF file: `RIFF`, a little-endian size, `WEBP`, then chunks of FourCC,
    little-endian size and data padded to an even length. The `VP8X` header
    announces which metadata chunks exist, so its EXIF and XMP bits are cleared
    with them; the ICC, alpha and animation bits stay, because their chunks do.
    An `ANMF` frame holds chunks of its own, and the ones that are not image data
    (ALPH, VP8, VP8L) are dropped from inside it, with the frame's size rewritten.
    The RIFF size is rewritten too, and what lies beyond the declared size is
    dropped. What still holds: image data is copied byte for byte, so the result
    decodes to the same pixels.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise _unreadable()
    riff_end = 8 + int.from_bytes(data[4:8], "little")
    if riff_end > len(data):
        raise _unreadable()
    body = _webp_chunks(data, 12, riff_end, [_MAX_WEBP_CHUNKS])
    return b"RIFF" + (4 + len(body)).to_bytes(4, "little") + b"WEBP" + body


_STRIP_METADATA = {"JPEG": _strip_jpeg, "PNG": _strip_png, "WEBP": _strip_webp}


def _profile_for(info_profile: object, saved_as_gray: bool) -> bytes | None:
    """The embedded ICC profile, when it still describes what is being saved.

    The profile is part of how the picture looks, so a re-encode carries it:
    Pillow's JPEG and WebP writers drop it unless it is passed. But a profile
    describes a colour space, and a CMYK or greyscale source is saved as RGB
    here - a CMYK profile on RGB pixels would colour them wrongly - so it is
    kept only when its space (bytes 16-19 of the header) is the one being saved.
    """
    if not isinstance(info_profile, bytes) or len(info_profile) < 20:
        return None
    wanted = b"GRAY" if saved_as_gray else b"RGB "
    return info_profile if info_profile[16:20] == wanted else None


def shrink_to_fit(data: bytes, image_format: str) -> bytes:
    """The same image, upright, with no metadata and its longest side at most
    MAX_STORED_EDGE.

    Metadata is removed from every file that is stored: EXIF, GPS, XMP, IPTC,
    comments, thumbnails and trailing data. The bucket is public, so what a phone
    wrote into a photo - where it was taken, with what - would be published with
    it. The ICC profile stays; it changes how the colours look.

    Losslessly whenever nothing has to be decoded: an image that fits and is
    already upright is stripped at the byte level, pixel for pixel the file that
    arrived. A re-encode happens for only two reasons, and loses quality only
    then: the image is too large, or its EXIF Orientation is not 1. The latter
    cannot be left alone - the tag is metadata and goes, so the picture has to
    be turned upright for good or it would show sideways. The reduction comes
    before the rotation, because the box is square so the result is the same
    size either way, and rotating a reduced bitmap copies at most 1600x1600
    pixels instead of the full-resolution one.

    The format is preserved rather than normalised to JPEG: a PNG product shot
    on a transparent background turns into one on a black background otherwise,
    which is a worse picture than a large one.

    What still holds: nothing is decoded that `validate_image` did not cost
    (it reads the orientation the same way, from the same bytes - a PNG's `eXIf`
    counts wherever it sits, before or after the pixel data), and a file with
    nothing to strip is returned byte for byte. A file whose structure cannot be
    walked raises INVALID_IMAGE rather than being decoded, because that path is
    unbudgeted. So does a file whose pixel data cannot be decoded (a JPEG whose
    EOI was cut, a PNG whose zlib stream is broken): `validate_image` does not read
    that far, and the decode is where it shows. Only Pillow's own errors for bad
    bytes are turned into it (`_BAD_PIXEL_DATA`), and only around the two calls
    that decode; a bug anywhere else is still an error, not a refusal.
    """
    # The one parser `validate_image` already accepted the file for, so a caller
    # that skips validation cannot reach another one through this call.
    with Image.open(io.BytesIO(data), formats=[image_format]) as image:
        orientation = _exif_orientation(image, data)
        if max(image.size) <= MAX_STORED_EDGE and orientation == 1:
            return _STRIP_METADATA[image_format](data)

        # Nothing is lost by taking these before the pixels are touched.
        saved_as_gray = image_format == "PNG" and image.mode in ("L", "LA")
        profile = _profile_for(image.info.get("icc_profile"), saved_as_gray)

        # Where the pixels are decoded - `thumbnail` for a large image, `transpose`
        # for one that only has to be turned - and so the only place damage that
        # `validate_image` cannot see (it parses structure, and for a JPEG nothing
        # after the scan header) surfaces. Only these two calls are covered: the
        # encoder below works on a bitmap that is already in memory, and an error
        # there is ours, not the upload's.
        try:
            image.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
            if orientation != 1:
                upright = image.transpose(_UPRIGHT[orientation])
                # The source bitmap is not needed again, and the encoder below is
                # the most expensive step: keeping both alive through it measured
                # 97.7 MiB for the largest WebP the budget admits, releasing the
                # source 89.8.
                image.close()
            else:
                upright = image
        except _BAD_PIXEL_DATA as exc:
            raise _unreadable() from exc
        buffer = io.BytesIO()
        # No `exif=` anywhere: a writer given none writes none.
        if image_format == "JPEG":
            # `comment=b""` because Pillow's JPEG writer otherwise copies the
            # source's COM segment across.
            upright.convert("RGB").save(
                buffer,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                icc_profile=profile,
                comment=b"",
            )
        elif image_format == "PNG":
            # No `optimize=True`: it searches for the smallest encoding and costs
            # seconds of CPU. Measured on a 2800x2100 PNG, 6.5 s against 0.52 s
            # for a file about 10% larger - not worth the seconds a worker
            # spends on one upload.
            upright.save(buffer, format="PNG", icc_profile=profile)
        else:
            # `method=5`, not libwebp's slowest (6). Measured on Windows 11, AMD
            # Ryzen 7 4700U, Python 3.14.5, Pillow 13.0.0 (libwebp 1.6.0), best of
            # 3-7, quality 82, a 1600x1186 result - the largest WebP the budget
            # admits is 1601x1187:
            #   photo RGB    m4 344 ms / 163.6 kB   m5 361 / 162.2   m6 431 / 159.9
            #   RGBA product m4 498 ms /  101.8 kB  m5 376 / 102.1   m6 3615 / 98.3
            # Across five alpha shapes m6 took 2.2-4.0 s where m4 and m5 took
            # 0.18-0.73 s: any partly transparent pixel makes m6 8-14x slower, for
            # a file 2-4% smaller than m5's. The encoder runs under Semaphore(1),
            # so that is seconds in which every other upload waits. On a WebP with
            # no transparency m5 is 16% faster than m6 for a file 1.4% larger, so
            # m5 keeps nearly all of m6's size win and none of its worst case; m4
            # is only 5% faster than m5 on photos and no faster on RGBA. What still
            # holds: the encode is the largest part of a WebP upload's time (about
            # 80%), so its cost is still a few hundred ms - not free. Linux
            # timings were not taken; libwebp is the same code on both.
            upright.save(buffer, format="WEBP", quality=JPEG_QUALITY, method=5, icc_profile=profile)
        shrunk = buffer.getvalue()

    # The re-encode is always what is stored once the code gets here. Reaching it
    # means the image was decoded for one of two reasons - its longest side is over
    # MAX_STORED_EDGE, or its Orientation is not 1 - and in neither case would the
    # stripped original do: an over-edge one breaks the edge, a turned one would
    # show sideways. It used to be compared with the stripped original when the
    # Orientation was 1 and the smaller won (A-105); that comparison could only
    # ever be about an image over the edge, and a synthetic 1700x50 `I;16` PNG
    # whose re-encode was larger was stored at 1700 px because of it. So a
    # re-encode may be larger in bytes than the file that arrived, and the edge
    # holds. What still holds: an image at or below the edge and upright is never
    # decoded - it is stripped at the byte level above, so a file the walk cannot
    # read still raises INVALID_IMAGE there; and the walk is no longer run on an
    # image that was decoded, so one it cannot read (a JPEG whose tail is not an
    # EOI - Pillow stops after the last MCU) is stored as its clean re-encode,
    # which carries no metadata: no `exif=` is passed and the ICC profile is the
    # only thing copied across.
    return shrunk


def object_key(product_id: uuid.UUID, extension: str) -> str:
    """`products/<product id>/<uuid>.<ext>` - never the uploaded filename.

    A caller-supplied name would carry path separators, unicode look-alikes and
    collisions into the bucket.
    """
    return f"products/{product_id}/{uuid.uuid4().hex}.{extension}"


class InMemoryStorage:
    """Test and offline backend. Keeps objects in a dict."""

    def __init__(self, base_url: str = "https://storage.test/voltbox") -> None:
        self.base_url = base_url.rstrip("/")
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self.objects[key] = data
        return f"{self.base_url}/{key}"

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def url_for(self, key: str) -> str:
        return f"{self.base_url}/{key}"


class SupabaseStorage:
    """Supabase Storage over its REST API.

    httpx rather than the supabase client: this needs two calls, and the client
    would pull in a much larger dependency for them.
    """

    def __init__(self, project_ref: str, service_key: str, bucket: str) -> None:
        self.base = f"https://{project_ref}.supabase.co/storage/v1"
        self.bucket = bucket
        self.headers = {
            "Authorization": f"Bearer {service_key}",
            # The service role key must never reach the browser; it lives only
            # in the backend process.
            "apikey": service_key,
        }

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/object/{self.bucket}/{key}",
                content=data,
                headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
            )
        if response.status_code >= 400:
            raise ValidationError(
                "The image could not be stored",
                code="STORAGE_UPLOAD_FAILED",
                details={"status": response.status_code},
            )
        return f"{self.base}/object/public/{self.bucket}/{key}"

    async def delete(self, key: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(
                f"{self.base}/object/{self.bucket}/{key}", headers=self.headers
            )
        # A missing object is not an error: deletion has to be idempotent so
        # a retry after a timeout does not fail.
        if response.is_success or _is_missing_object(response):
            return
        # Anything else - a rejected key, a missing policy, an outage - means the
        # file is still public at its URL, so the admin must not be told it went.
        # Only the status travels: the request carried the service role key.
        raise AppError(
            "The image could not be removed from storage",
            code="STORAGE_DELETE_FAILED",
            status_code=502,
            details={"status": response.status_code},
        )


def _is_missing_object(response: httpx.Response) -> bool:
    """A 404, or the 400 whose body says 404 that Supabase Storage has used for it."""
    if response.status_code == 404:
        return True
    if response.status_code != 400:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and str(body.get("statusCode")) == "404"


#: Where the in-memory fake is an acceptable stand-in. Anywhere else, an
#: unconfigured bucket is a misconfiguration rather than a mode to run in.
LOCAL_ENVS = {"development", "test"}


def get_storage() -> StorageBackend:
    """The configured backend; the in-memory one only outside a deployment.

    Falling back rather than failing keeps the whole feature testable and lets
    the panel run locally before any bucket exists. It must not survive into a
    deployment: uploads would land in one worker's memory, the saved URL would
    point at `storage.test` (a reserved name that resolves nowhere), and the
    order items that snapshot that URL keep it forever. Nothing raises, so the
    panel reports success and the breakage only shows on the storefront.

    A test run never gets the real bucket, whatever the environment holds. The
    credentials are read from `.env`, and a developer's `.env` points at the
    live project - so anything that uploads without overriding this dependency
    writes into production storage while pointed at a local database. Those
    files are orphaned the moment they are written: no row here refers to them,
    nothing cleans them up, and they are indistinguishable from real ones
    afterwards except by size.
    """
    if settings.app_env == "test":
        return InMemoryStorage()

    if settings.supabase_project_ref and settings.supabase_service_role_key.get_secret_value():
        return SupabaseStorage(
            settings.supabase_project_ref,
            settings.supabase_service_role_key.get_secret_value(),
            settings.supabase_storage_bucket,
        )

    if settings.app_env not in LOCAL_ENVS:
        raise RuntimeError(
            f"Object storage is not configured and APP_ENV is {settings.app_env!r}. "
            "Set SUPABASE_PROJECT_REF and SUPABASE_SERVICE_ROLE_KEY; without them "
            "uploaded images would be written to process memory and lost."
        )

    return InMemoryStorage()
