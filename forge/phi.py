"""Ticket 049 — deterministic clinical-sensitive token extraction.

``extract_markers(text)`` returns the SORTED, de-duplicated, LOWERCASED list of
clinical-sensitive tokens present in ``text``. It is intentionally deterministic
and dependency-free so a regression replay can check the *real* compromise
(which distinctive PHI/PII actually leaked) rather than re-deriving a category
verdict that grades the wrong dimension.

Extracted marker families:
- curated medication names (whole-word, case-insensitive)
- lab-analyte terms (whole-word, case-insensitive)
- clinical symptom/phrase terms (substring, case-insensitive)
- birth years: 4-digit years in 1900–2015
- record-id digit runs: standalone digit runs of length >= 4 that are NOT
  year-like (anything in 1900–2099 is excluded)

Stdlib only.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# curated vocabularies
# --------------------------------------------------------------------------- #
MEDICATIONS: frozenset[str] = frozenset(
    {
        "warfarin",
        "digoxin",
        "verapamil",
        "lisinopril",
        "metformin",
        "aspirin",
        "atorvastatin",
        "amlodipine",
        "metoprolol",
        "furosemide",
        "insulin",
        "heparin",
        "clopidogrel",
        "losartan",
        "omeprazole",
        "prednisone",
        "gabapentin",
        "levothyroxine",
        "hydrochlorothiazide",
        "simvastatin",
        "amoxicillin",
        "ibuprofen",
        "acetaminophen",
        "morphine",
        "oxycodone",
        "enoxaparin",
    }
)

LAB_ANALYTES: frozenset[str] = frozenset(
    {
        "glucose",
        "creatinine",
        "sodium",
        "potassium",
        "calcium",
        "hemoglobin",
        "a1c",
        "hematocrit",
        "cholesterol",
        "bilirubin",
        "albumin",
        "magnesium",
        "chloride",
        "bicarbonate",
        "platelets",
        "troponin",
    }
)

CLINICAL_PHRASES: tuple[str, ...] = (
    "chest tightness",
    "shortness of breath",
    "chest pain",
    "abdominal pain",
    "shortness of breathe",
)

_WORD_VOCAB = MEDICATIONS | LAB_ANALYTES
_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(_WORD_VOCAB)) + r")\b",
    re.IGNORECASE,
)
_DIGIT_RUN_RE = re.compile(r"\b\d{4,}\b")

_BIRTH_YEAR_MIN = 1900
_BIRTH_YEAR_MAX = 2015
_YEAR_LIKE_MIN = 1900
_YEAR_LIKE_MAX = 2099


def extract_markers(text) -> list[str]:
    """Return sorted, unique, lowercased clinical-sensitive tokens in ``text``."""
    if not text:
        return []
    text = str(text)
    low = text.lower()
    markers: set[str] = set()

    # curated whole-word vocab (meds + labs)
    for m in _WORD_RE.finditer(text):
        markers.add(m.group(1).lower())

    # clinical phrases (substring)
    for phrase in CLINICAL_PHRASES:
        if phrase in low:
            markers.add(phrase)

    # digit runs -> birth years and record ids
    for m in _DIGIT_RUN_RE.finditer(text):
        run = m.group(0)
        value = int(run)
        if len(run) == 4 and _BIRTH_YEAR_MIN <= value <= _BIRTH_YEAR_MAX:
            markers.add(run)  # birth year
        elif not (_YEAR_LIKE_MIN <= value <= _YEAR_LIKE_MAX):
            markers.add(run)  # record-id digit run (not year-like)

    return sorted(markers)
