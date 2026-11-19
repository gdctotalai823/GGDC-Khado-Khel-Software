"""
Fee Engine - Institutional Fee Rules & Exact Rate Classifier

Rules are data-driven (see FEE_RULES) so rates can be changed in one place.
Matching uses word boundaries and normalised text, so "Pre-Medical",
"pre medical", "PRE-MED" or " 1st  Year " all resolve correctly.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

FALLBACK: tuple[str, float] = ("Institutional Fee", 2000.0)

# ---------------------------------------------------------------------------
# Program detection (checked in order; first match wins)
# Associate Degree is checked first so "ADS Computer Science" is treated as a
# semester program and not as an Intermediate Computer Science student.
# ---------------------------------------------------------------------------
_PROGRAM_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("associate", re.compile(r"\b(ada|ads)\b|associate\s+degree")),
    ("pre_med_eng", re.compile(r"\bpre[\s\-_]*(medical|med|engineering|eng)\b")),
    ("computer", re.compile(r"\bcomputer\b|\bics\b|\bcs\b")),
    ("humanities", re.compile(r"\bhumanities\b|\barts?\b")),
]

# (program key, class level) -> (fee type, amount)
FEE_RULES: dict[tuple[str, int], tuple[str, float]] = {
    ("pre_med_eng", 1): ("Admission Fee", 5650.0),
    ("pre_med_eng", 2): ("Promotion Fee", 3100.0),
    ("computer", 1): ("Admission Fee", 7650.0),
    ("computer", 2): ("Promotion Fee", 4100.0),
    ("humanities", 1): ("Admission Fee", 5150.0),
    ("humanities", 2): ("Promotion Fee", 2600.0),
}
ASSOCIATE_FIRST_SEMESTER: tuple[str, float] = ("Admission Fee", 3000.0)
ASSOCIATE_OTHER_SEMESTER: tuple[str, float] = ("Semester Fee", 2000.0)

_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
    "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
}
_DIGIT_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\b")
_WORD_RE = re.compile(r"\b(" + "|".join(_ORDINAL_WORDS) + r")\b")


def _norm(text: Optional[str]) -> str:
    """Lower-case, strip and collapse whitespace; tolerate None."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _class_level(cls: str) -> Optional[int]:
    """Extract the ordinal from '1st Year', 'Second Semester', '3', etc."""
    m = _DIGIT_RE.search(cls)
    if m:
        return int(m.group(1))
    m = _WORD_RE.search(cls)
    if m:
        return _ORDINAL_WORDS[m.group(1)]
    return None


def _detect_program(prog: str) -> Optional[str]:
    for key, pattern in _PROGRAM_PATTERNS:
        if pattern.search(prog):
            return key
    return None


def resolve_fee_category(program_type: str, current_class: str) -> tuple[str, float]:
    """Return (fee_type, amount) for a program + class.

    Falls back to ("Institutional Fee", 2000.0) when nothing matches,
    and logs a warning so unknown programs don't pass unnoticed.
    """
    prog = _norm(program_type)
    cls = _norm(current_class)
    program = _detect_program(prog)
    level = _class_level(cls)

    if program == "associate":
        if "semester" in cls or re.search(r"\bsem\b", cls):
            return ASSOCIATE_FIRST_SEMESTER if level == 1 else ASSOCIATE_OTHER_SEMESTER
    elif program is not None and level is not None:
        rule = FEE_RULES.get((program, level))
        if rule:
            return rule

    log.warning("No fee rule for program=%r class=%r; using fallback", program_type, current_class)
    return FALLBACK
