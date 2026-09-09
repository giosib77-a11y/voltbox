"""ძებნის ტექსტის ნორმალიზაცია — ერთადერთი ადგილი, სადაც ეს წესები ცხოვრობს.

ქართულს Postgres-ის full-text ლექსიკონი არ აქვს, ამიტომ FTS-ის ნაცვლად
ნორმალიზებულ ტექსტზე ტოკენების დამთხვევასა და trigram-მსგავსებაზე ვდგავართ.

მილსადენი (იგივე თანმიმდევრობა, რაც frontend-ის `utils/search.js`-ში, რომ ორივე
მხარემ ერთი და იგივე შედეგი დააბრუნოს):
  1. lowercase + პუნქტუაციის მოცილება
  2. ათასეულების გამყოფები: "20 000" → "20000",  "20,000" → "20000"
  3. ერთეულების უნიფიკაცია: მაჰ→mah, მ/მეტრი→m, გბ→gb, ვტ→w, სთ→h, "6.2\"" → 6.2 in
  4. რიცხვისა და ერთეულის გაყოფა: "20000mah" → "20000 mah",  "2მ" → "2 m"
  5. ქართული სტემინგი — "ყურსასმენები" და "ყურსასმენი" ერთ ფუძეზე დაიყვანება
"""

from __future__ import annotations

import re

# --- ერთეულები --------------------------------------------------------------
UNIT_ALIASES: dict[str, str] = {
    "mah": "mah",
    "მაჰ": "mah",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "მ": "m",
    "მეტრი": "m",
    "მეტრიანი": "m",
    "sm": "sm",
    "cm": "sm",
    "სმ": "sm",
    "სანტიმეტრი": "sm",
    "mm": "mm",
    "მმ": "mm",
    "gb": "gb",
    "gigabyte": "gb",
    "გბ": "gb",
    "გიგაბაიტი": "gb",
    "tb": "tb",
    "ტბ": "tb",
    "w": "w",
    "watt": "w",
    "watts": "w",
    "ვტ": "w",
    "ვატი": "w",
    "ვატ": "w",
    "v": "v",
    "volt": "v",
    "hz": "hz",
    "ჰც": "hz",
    "mp": "mp",
    "მპ": "mp",
    "megapixel": "mp",
    "h": "h",
    "hr": "h",
    "hour": "h",
    "hours": "h",
    "სთ": "h",
    "საათი": "h",
    "in": "in",
    "inch": "in",
    "inches": "in",
    "დიუიმი": "in",
}
_UNIT_KEYS = sorted(UNIT_ALIASES, key=len, reverse=True)
_NUMBER_UNIT = re.compile(r"^([0-9]+(?:[.][0-9]+)?)(" + "|".join(_UNIT_KEYS) + r")$")

# --- ქართული დაბოლოებები (გრძელიდან მოკლისკენ) -------------------------------
KA_SUFFIXES = (
    "ებისთვის",
    "ებისგან",
    "ებიდან",
    "ებამდე",
    "ებში",
    "ებზე",
    "ებით",
    "ების",
    "ებს",
    "ები",
    "ისთვის",
    "ისგან",
    "იდან",
    "ამდე",
    "ში",
    "ზე",
    "ით",
    "ის",
    "ს",
    "ი",
)

# იგივე დაბოლოებები ლათინურად: მომხმარებელი წერს „samsungi“ ან „kabelebi“,
# ინდექსში კი „samsung“ / „kabel“ ზის. ინგლისური მრავლობითის -s-იც აქვეა.
LAT_SUFFIXES = (
    "ebistvis",
    "ebidan",
    "ebamde",
    "ebshi",
    "ebze",
    "ebit",
    "ebis",
    "ebs",
    "ebi",
    "istvis",
    "idan",
    "amde",
    "shi",
    "ze",
    "it",
    "is",
    "s",
    "i",
)

# --- არქაული ასოები ----------------------------------------------------------
ARCHAIC = str.maketrans({"ჲ": "ი", "ჳ": "ვ", "ჱ": "ე", "ჵ": "ო", "ჴ": "ხ", "ჶ": "ფ"})

_PUNCT = re.compile(r"[^\w. ]+", re.UNICODE)
_DOT_NOT_BETWEEN_DIGITS = re.compile(r"(?<![0-9])[.]|[.](?![0-9])")
_THOUSANDS_COMMA = re.compile(r"([0-9]),(?=[0-9]{3}\b)")
_THOUSANDS_SPACE = re.compile(r"([0-9])\s+([0-9]{3})(?![0-9\w])")
_INCH = re.compile(r"([0-9])\s*[\"″]")


def normalize(text: str | None) -> str:
    """ტექსტს შედარებად, სივრცით გამოყოფილ ტოკენებად აქცევს.

    ერთი ველი = ერთი გამოძახება: ათასეულების შერწყმა ველებს შორის არ უნდა
    გადავიდეს, თორემ "iPhone 15" + "128 GB" გახდებოდა "15128".
    """
    if not text:
        return ""

    value = str(text).lower().translate(ARCHAIC)
    value = _INCH.sub(r"\1 in", value)
    value = _THOUSANDS_COMMA.sub(r"\1", value)
    value = _DOT_NOT_BETWEEN_DIGITS.sub(" ", value)
    value = _PUNCT.sub(" ", value).replace("_", " ")
    value = _THOUSANDS_SPACE.sub(r"\1\2", value)

    parts: list[str] = []
    for word in value.split():
        match = _NUMBER_UNIT.match(word)
        if match:
            parts.extend([match.group(1), UNIT_ALIASES.get(match.group(2), match.group(2))])
        else:
            parts.append(UNIT_ALIASES.get(word, word))

    return " ".join(parts)


def stem(word: str) -> str:
    """უხეში სტემინგი: „ყურსასმენები“ და „ყურსასმენი“ → „ყურსასმენ“.

    სრული მორფოლოგიური ანალიზი ბიბლიოთეკას მოითხოვდა; ამ ამოცანისთვის
    დაბოლოებების ჩამოჭრა საკმარისია. ფუძეს მინიმუმ 4 სიმბოლო რჩება, რომ
    მოკლე სიტყვები არ დაინგრეს.
    """
    if len(word) < 5:
        return word
    for suffix in (*KA_SUFFIXES, *LAT_SUFFIXES):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(query: str) -> list[str]:
    return [token for token in normalize(query).split() if token]
