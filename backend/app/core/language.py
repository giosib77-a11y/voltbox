"""The storefront language a catalogue read is answered in.

What it does: names the two languages, declares the `lang` query parameter
every catalogue read takes, and picks the English or the Georgian text of a
name or description.
Where it fits: the storefront's catalogue, search and cart routes take
`LanguageQuery`; the mappers and services that build their answers call
`localized`. The admin panel is Georgian and never sends it.

Why a query parameter and not Accept-Language: the language is then part of
the URL, so anything that ever caches these answers - a browser, a CDN - keys
the two languages apart without a `Vary` header, and a browser's own
Accept-Language, which it sends on every request, cannot pick the language
instead of the page. A Georgian page sends nothing, so its requests are the
ones it made before English existed.

English is optional for every name. An empty one falls back to the Georgian,
so an untranslated product still shows - never a blank card.
"""

from typing import Annotated, Literal

from fastapi import Query

Language = Literal["ka", "en"]

DEFAULT_LANGUAGE: Language = "ka"

LanguageQuery = Annotated[
    Language,
    Query(
        description=(
            "Language of the names and descriptions in the answer. `en` gives the "
            "English text where there is one and the Georgian where there is not."
        ),
    ),
]


def localized(georgian: str, english: str, lang: Language) -> str:
    """The English text on an English page when there is some, else the Georgian.

    Blank counts as missing: the admin form trims what it saves, but a value
    typed into the database by hand may be a lone space, and that would show as
    an empty name.
    """
    if lang == "en" and english.strip():
        return english
    return georgian
