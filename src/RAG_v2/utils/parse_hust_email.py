"""Utility — parse HUST student info from a ``@sis.hust.edu.vn`` email address.

HUST email format::

    <given_name>.<family_abbrev><student_number>@sis.hust.edu.vn

    e.g.  nam.nh225653@sis.hust.edu.vn

Parsing rules:

    full_name   — the first segment before the first dot, title-cased.
                  e.g. "nam"  →  "Nam"

    student_id  — the trailing digits in the local-part prefix, with "20"
                  prepended to form a full 8-digit student ID.
                  e.g. "nh225653"  →  digits "225653"  →  "20225653"

    cohort      — derived from the first 4 digits of student_id.
                  Mapping: 2020 → K65, 2021 → K66, 2022 → K67, 2023 → K68,
                           2024 → K69.
                  Unmapped years are reported as "K?".

    major       — hardcoded default: "CNTT Việt Nhật".
"""

from __future__ import annotations

import re

# ─── Domain constant ──────────────────────────────────────────────────────────
_HUST_DOMAIN = "@sis.hust.edu.vn"

# ─── Cohort year → K-label mapping ───────────────────────────────────────────
_COHORT_MAP: dict[str, str] = {
    "2020": "K65",
    "2021": "K66",
    "2022": "K67",
    "2023": "K68",
    "2024": "K69",
}

_DEFAULT_MAJOR = "CNTT Việt Nhật"


# ═══════════════════════════════════════════════════════════════════════════════

def parse_hust_email(email: str) -> dict[str, str]:
    """Parse HUST student metadata from a ``@sis.hust.edu.vn`` email address.

    Parameters
    ----------
    email:
        A valid HUST student email, e.g. ``"nam.nh225653@sis.hust.edu.vn"``.

    Returns
    -------
    dict with keys ``full_name``, ``student_id``, ``cohort``, ``major``.

    Raises
    ------
    ValueError
        If *email* does not end with ``@sis.hust.edu.vn``, or if no trailing
        numeric suffix can be found in the local part.

    Example
    -------
    >>> parse_hust_email("nam.nh225653@sis.hust.edu.vn")
    {'full_name': 'Nam', 'student_id': '20225653', 'cohort': 'K67', 'major': 'CNTT Việt Nhật'}
    """
    # ── 1. Validate domain ────────────────────────────────────────────────────
    email = email.strip().lower()
    if not email.endswith(_HUST_DOMAIN):
        raise ValueError(
            f"Email must end with {_HUST_DOMAIN!r}. Got: {email!r}"
        )

    # ── 2. Extract local part (before @) ─────────────────────────────────────
    local = email[: -len(_HUST_DOMAIN)]  # e.g. "nam.nh225653"

    # ── 3. Parse full_name from the first segment ─────────────────────────────
    # Split on dot; the first token is the given name.
    parts = local.split(".")
    given_name_raw = parts[0] if parts else local
    full_name = given_name_raw.capitalize()

    # ── 4. Extract trailing digits from the last segment ─────────────────────
    # The last segment (e.g. "nh225653") may have a letter prefix followed
    # by the student number.  We take only the trailing digit run.
    last_segment = parts[-1] if len(parts) > 1 else local
    digit_match = re.search(r"(\d+)$", last_segment)
    if not digit_match:
        raise ValueError(
            f"No numeric suffix found in local part {local!r}. "
            "Expected a format like 'name.ab225653@sis.hust.edu.vn'."
        )
    raw_digits = digit_match.group(1)  # e.g. "225653"

    # ── 5. Build full student_id ──────────────────────────────────────────────
    # Rule: prepend "20" to get the 8-digit university ID.
    student_id = "20" + raw_digits  # e.g. "20225653"

    # ── 6. Determine cohort from first 4 digits of student_id ─────────────────
    year_prefix = student_id[:4]  # e.g. "2022"
    cohort = _COHORT_MAP.get(year_prefix, "K?")

    return {
        "full_name": full_name,
        "student_id": student_id,
        "cohort": cohort,
        "major": _DEFAULT_MAJOR,
    }
