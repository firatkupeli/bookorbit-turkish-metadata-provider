import re
import unicodedata

from bs4 import BeautifulSoup


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def fold(value: str) -> str:
    value = value.translate(str.maketrans({"I": "i", "İ": "i", "ı": "i"})).casefold()
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
        ).split()
    )


def plain_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "button"]):
        tag.decompose()
    for tag in soup.find_all(["br", "p", "div", "li"]):
        tag.insert_before("\n")
        if tag.name != "br":
            tag.insert_after("\n")
    return "\n\n".join(
        line for raw in soup.get_text().splitlines() if (line := normalize_text(raw))
    )[:50000]


def author_matches(requested: str, authors: list[str] | tuple[str, ...]) -> bool:
    """Match name tokens, tolerating initials, punctuation and duplicated aliases."""
    wanted = {word for word in re.findall(r"[^\W_]+", fold(requested)) if len(word) > 1}
    if not wanted:
        return False
    for author in authors:
        actual = {word for word in re.findall(r"[^\W_]+", fold(author)) if len(word) > 1}
        if not actual:
            continue
        # Whole names may be reordered; one shared first name is not an author match.
        if actual <= wanted or wanted <= actual:
            return True
    return False


def match_title(value: str) -> str:
    value = fold(value).replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[\W_]+", " ", value).split())


def normalize_isbn(value: str) -> str | None:
    value = re.sub(r"[\s\-]", "", value).upper()
    # An all-zero ISBN-10 passes the arithmetic checksum but is a placeholder.
    if value == "0000000000":
        return None
    if re.fullmatch(r"[0-9]{13}", value) and value.startswith(("978", "979")):
        if sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0:
            return value
    if re.fullmatch(r"[0-9]{9}[0-9X]", value):
        if sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(value)) % 11 == 0:
            return value
    return None


def isbn13(value: str) -> str:
    if len(value) == 13:
        return value
    stem = "978" + value[:9]
    checksum = (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(stem))) % 10
    return stem + str(checksum)
