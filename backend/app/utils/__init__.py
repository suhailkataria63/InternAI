import re


TEXT_ARTIFACT_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "\u2028": "\n",
        "\u2029": "\n",
        "\u25cf": "\n",
        "\u2022": "\n",
        "\u25e6": "\n",
        "\uf0b7": "\n",
    }
)

INLINE_ARTIFACT_TRANSLATION = str.maketrans(
    {
        key: (" " if value == "\n" else value)
        for key, value in TEXT_ARTIFACT_TRANSLATION.items()
    }
)

PROJECT_DATE_PREFIX_RE = re.compile(
    r"^\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r"(?:\s*[-–]\s*(?:present|(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}))?"
    r"\s*[:\-–]?\s*",
    flags=re.IGNORECASE,
)

PROJECT_DATE_RANGE_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r"\s*[-–]\s*(?:present|(?:jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\s+\d{4})\b",
    flags=re.IGNORECASE,
)


def normalize_text_artifacts(text: str, preserve_newlines: bool = True) -> str:
    translation = TEXT_ARTIFACT_TRANSLATION if preserve_newlines else INLINE_ARTIFACT_TRANSLATION
    text = str(text or "").translate(translation)
    allowed_controls = "\n\t" if preserve_newlines else ""
    return "".join(
        char
        for char in text
        if char in allowed_controls or not (ord(char) < 32 or 0x7F <= ord(char) <= 0x9F)
    )


def normalize_spaces(text: str, preserve_newlines: bool = False) -> str:
    text = normalize_text_artifacts(text, preserve_newlines=preserve_newlines)
    if preserve_newlines:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    return re.sub(r"\s+", " ", text).strip()


def normalize_unmatched_brackets(text: str) -> str:
    text = str(text or "")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        stack = []
        remove_indexes = set()
        for index, char in enumerate(text):
            if char == opening:
                stack.append(index)
            elif char == closing:
                if stack:
                    stack.pop()
                else:
                    remove_indexes.add(index)
        remove_indexes.update(stack)
        if remove_indexes:
            text = "".join(char for index, char in enumerate(text) if index not in remove_indexes)
    return normalize_spaces(text).strip(" -•\t.,")


def education_for_writing(value: str) -> str:
    """Return a concise education fact while preserving status in valid parentheses."""
    text = normalize_unmatched_brackets(normalize_spaces(value))
    if not text:
        return ""

    status_match = re.search(r"\(([^)]*(?:currently pursuing|pursuing|ongoing|present)[^)]*)\)", text, re.IGNORECASE)
    has_current_status = bool(status_match) or bool(re.search(r"\bcurrently pursuing\b", text, re.IGNORECASE))
    degree_text = re.sub(r"\([^)]*(?:currently pursuing|pursuing|ongoing|present)[^)]*\)", "", text, flags=re.IGNORECASE)
    degree_text = re.sub(r"\bcurrently pursuing\b", "", degree_text, flags=re.IGNORECASE)
    degree_text = re.split(
        r"\s+(?:at|under)\s+|,\s*(?:3rd|third|4th|fourth|2nd|second|1st|first)\s+year|,\s*\d+(?:st|nd|rd|th)?\s+semester|—",
        degree_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    stop_markers = ("Chandigarh Group of Colleges", "CGC", "Landran", "PSBTE", "CBSE")
    for marker in stop_markers:
        position = degree_text.lower().find(marker.lower())
        if position > 0:
            degree_text = degree_text[:position]
            break

    degree_text = normalize_spaces(degree_text.replace("&", " and ")).strip(" ,-—")
    degree_text = re.sub(
        r"^(?:a\s+)?(B\.?\s*Tech|BTech)\s*,\s*(.+)$",
        r"a B.Tech in \2",
        degree_text,
        flags=re.IGNORECASE,
    )
    degree_text = re.sub(
        r"^(?:a\s+)?(B\.?\s*Tech|BTech)\s+in\s+(.+)$",
        r"a B.Tech in \2",
        degree_text,
        flags=re.IGNORECASE,
    )
    degree_text = re.sub(r"\bB\.?\s*Tech\b", "B.Tech", degree_text, flags=re.IGNORECASE)

    if has_current_status and degree_text:
        return f"Currently pursuing {degree_text}"
    return degree_text[:140].rsplit(" ", 1)[0].strip(" ,-—") if len(degree_text) > 140 else degree_text


def clean_field(text: str) -> str:
    return normalize_unmatched_brackets(normalize_spaces(text).strip(" -•●\t.,"))


def strip_project_dates(text: str) -> str:
    text = PROJECT_DATE_RANGE_RE.sub("", normalize_spaces(text))
    text = PROJECT_DATE_PREFIX_RE.sub("", text)
    return normalize_spaces(text).strip(" :-,.;")


def unique_preserve_order(items: list) -> list:
    seen = set()
    unique_items = []
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    return unique_items


def join_human_list(items: list[str]) -> str:
    clean_items = []
    for item in items:
        text = normalize_spaces(item)
        if text and text.lower() not in [existing.lower() for existing in clean_items]:
            clean_items.append(text)
    if len(clean_items) <= 1:
        return "".join(clean_items)
    if len(clean_items) == 2:
        return " and ".join(clean_items)
    return ", ".join(clean_items[:-1]) + ", and " + clean_items[-1]
