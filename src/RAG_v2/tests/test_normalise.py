import re

def _canonicalise_major_code_parts(prefix: str, suffix: str) -> str:
    p = (prefix or "").upper()
    s = (suffix or "").upper()
    return f"{p}{s}" if s in {"1", "2"} else f"{p}-{s}"

_MAJOR_CODE_FUZZY_RE = re.compile(
    r"\b(IT|MI)\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]?\s*(E10|E15|E6|E7|EP|1|2)\b",
    re.IGNORECASE,
)

def _normalise_major_text(value: str) -> str:
    text = value
    text = re.sub(r"\s*-\s*", "-", text)
    text = _MAJOR_CODE_FUZZY_RE.sub(
        lambda m: _canonicalise_major_code_parts(m.group(1), m.group(2)),
        text,
    )
    return text

print(_normalise_major_text("ITE6"))
print(_normalise_major_text("IT-E6"))
print(_normalise_major_text("IT E6"))
print(_normalise_major_text("IT1"))
print(_normalise_major_text("IT 1"))
print(_normalise_major_text("IT-1"))
