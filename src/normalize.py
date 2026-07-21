"""Company-name normalisation, used as the join key across registries.

The same firm shows up as "ABC LOGISTICS, INC.", "Abc Logistics Inc" and
"ABC LOGISTICS INCORPORATED" across three different government systems, so
everything is reduced to a comparable form before matching.
"""
import re
import unicodedata

# Legal-form suffixes only. Deliberately NOT stripping words like
# "INTERNATIONAL", "LOGISTICS" or "GROUP" -- those distinguish real firms.
_LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "L L C", "LTD", "LIMITED", "CO", "COMPANY",
    "CORP", "CORPORATION", "LP", "LLP", "PLLC", "PC", "PA", "SA", "SAS",
    "GMBH", "NV", "BV", "PTE", "PVT", "AG", "AB", "OY", "SRL", "SPA", "KG",
}

_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Return a comparable form of a company name (may be '' if unusable)."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().strip()
    if s.startswith("THE "):
        s = s[4:]
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()

    # Strip trailing legal-form tokens, repeatedly: "FOO INC LLC" -> "FOO".
    tokens = s.split()
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    # Trailing country-ish qualifiers that don't distinguish a firm.
    while tokens and tokens[-1] in {"USA", "US", "U S A"}:
        tokens.pop()
    return " ".join(tokens)


def clean(value: str) -> str:
    """Trim a raw CSV cell; FMC pads a lot of its fields."""
    return (value or "").strip().strip('"').strip()


def clean_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    return clean(value)
