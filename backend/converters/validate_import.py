"""
Standalone validation module for pre-import file review.
Called by /api/import/validate — does NOT write to any database.
"""

import os
import json
import re
import pandas as pd
from typing import Dict, Any, List, Optional


_TYPE_MAP = {
    "int64": "INTEGER",
    "int32": "INTEGER",
    "float64": "FLOAT",
    "float32": "FLOAT",
    "bool": "BOOLEAN",
    "datetime64[ns]": "DATETIME",
    "object": "TEXT",
}

# Fixed-format types, checked by pattern/range rather than a plain python cast.
# ENUM is handled separately since it needs a per-column allowed-value list.
_SUPPORTED_OVERRIDES = [
    "TEXT", "ALPHA", "INTEGER", "FLOAT", "BOOLEAN", "DATETIME",
    "EMAIL", "PHONE", "CURRENCY", "PERCENTAGE", "ID", "ENUM",
]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Loose international phone check: optional +, 7-15 digits, allowing spaces/dashes/parens
_PHONE_PATTERN = re.compile(r"^\+?[\d\s\-().]{7,20}$")
_PHONE_DIGITS_PATTERN = re.compile(r"\d")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# Generic ID fallback: alphanumeric (+ - _), no spaces, reasonably short
_GENERIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,40}$")
_CURRENCY_STRIP_PATTERN = re.compile(r"[,\s]")
_CURRENCY_SYMBOL_PATTERN = re.compile(r"^[^\d\-]*")
# ALPHA: letters, spaces, hyphens (for hyphenated names), apostrophes (O'Brien),
# and common accented characters via Unicode category. Nothing else.
_ALPHA_PATTERN = re.compile(r"^[\w\s\-\']+$", re.UNICODE)
_ALPHA_DIGITS_PATTERN = re.compile(r"\d")


def _read_file(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        if isinstance(raw, dict):
            for key in ("data", "rows", "records", "results"):
                if key in raw and isinstance(raw[key], list):
                    return pd.DataFrame(raw[key])
            return pd.DataFrame([raw])
        raise ValueError("Unsupported JSON structure.")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


# --- Column-name hint patterns (applied when dtype gives object/TEXT) ---
# Each entry: (compiled_regex, inferred_type)
# Tried in order; first match wins. Case-insensitive.
_NAME_HINTS: List[tuple] = []  # populated below to avoid re.compile at import time

def _build_name_hints():
    global _NAME_HINTS
    _NAME_HINTS = [
        (re.compile(r"e.?mail",          re.I), "EMAIL"),
        (re.compile(r"phone|mobile|cell|tel", re.I), "PHONE"),
        (re.compile(r"(^|_)(user|cust|order|prod|item|txn|transaction|ref|row|rec|record)"
                    r"[_\s]?(id|no|num|number|code|key)($|[_\s])",  re.I), "ID"),
        (re.compile(r"(^|_)(id|uuid|guid)($|_)",               re.I), "ID"),
        (re.compile(r"date|time|timestamp|created|updated|purchased|at$", re.I), "DATETIME"),
        (re.compile(r"price|amount|cost|total|revenue|salary|fee|charge|final", re.I), "CURRENCY"),
        (re.compile(r"percent|pct|discount|rate|ratio|share|tax", re.I), "PERCENTAGE"),
        (re.compile(r"category|cat$|genre|type$|status|method|mode|payment", re.I), "TEXT"),
        (re.compile(r"name|title|description|label|tag|remark|note|comment", re.I), "TEXT"),
    ]

_build_name_hints()


def _sample_infer(series: pd.Series) -> str:
    """Infer the best type for an object-dtype column by sampling up to 50
    non-null values and running each candidate checker against them.
    Returns the type that passes for the highest proportion of samples,
    with a minimum 80 % pass rate required to commit — otherwise TEXT."""
    samples = [str(v).strip() for v in series.dropna().head(50) if str(v).strip()]
    if not samples:
        return "TEXT"

    n = len(samples)

    # Ordered from most specific to least so we don't misclassify an ID as TEXT
    candidates = [
        ("EMAIL",      lambda v: bool(_EMAIL_PATTERN.match(v))),
        ("DATETIME",   _sample_is_datetime),
        ("CURRENCY",   _check_currency),
        ("PERCENTAGE", _check_percentage),
        ("ID",         _check_id),
        ("PHONE",      _check_phone),
    ]

    best_type, best_rate = "TEXT", 0.0
    for type_name, checker in candidates:
        passes = sum(1 for v in samples if checker(v))
        rate = passes / n
        if rate >= 0.80 and rate > best_rate:
            best_type, best_rate = type_name, rate

    return best_type


def _sample_is_datetime(value: str) -> bool:
    """Lightweight date/datetime pattern check without parsing overhead."""
    # Covers DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, and ISO 8601
    _DT_PAT = re.compile(
        r"^(\d{1,4}[-/\.]\d{1,2}[-/\.]\d{2,4}"          # date part
        r"([ T]\d{2}:\d{2}(:\d{2})?)?$)"                  # optional time
    )
    return bool(_DT_PAT.match(value.strip()))


def _detect_column_types(df: pd.DataFrame) -> Dict[str, str]:
    """Two-pass type detection:
    1. Use pandas dtype for numeric/bool/datetime columns — those are reliable.
    2. For object (string) columns, sample actual values first, then fall back
       to column-name pattern hints, then default to TEXT.
    """
    types = {}
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        pandas_type = _TYPE_MAP.get(dtype_str)

        if pandas_type and pandas_type != "TEXT":
            # Pandas gave us a concrete numeric/bool/datetime type.
            # Still run name hints for FLOAT/INTEGER — a column named
            # "Price(Rs.)" or "Discount(%)" deserves CURRENCY/PERCENTAGE
            # even though pandas sees it as a plain float/int.
            if pandas_type in ("FLOAT", "INTEGER"):
                col_norm = col.strip()
                for pattern, hint_type in _NAME_HINTS:
                    if hint_type in ("CURRENCY", "PERCENTAGE", "ID") and pattern.search(col_norm):
                        types[col] = hint_type
                        break
                else:
                    types[col] = pandas_type
            else:
                types[col] = pandas_type
            continue

        # Object dtype — sample the values to infer the real type.
        inferred = _sample_infer(df[col])
        if inferred != "TEXT":
            types[col] = inferred
            continue

        # Value sampling gave TEXT (ambiguous). Try column-name hints.
        col_norm = col.strip()
        for pattern, hint_type in _NAME_HINTS:
            if pattern.search(col_norm):
                types[col] = hint_type
                break
        else:
            types[col] = "TEXT"

    return types


def _check_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.match(value.strip()))


def _check_phone(value: str) -> bool:
    v = value.strip()
    if not _PHONE_PATTERN.match(v):
        return False
    digit_count = len(_PHONE_DIGITS_PATTERN.findall(v))
    return 7 <= digit_count <= 15


def _check_currency(value: str) -> bool:
    v = value.strip()
    # Strip a single leading currency symbol/word (₹, $, Rs., USD, etc.) and
    # thousands separators, then require the remainder to parse as a number.
    v = _CURRENCY_SYMBOL_PATTERN.sub("", v, count=1)
    v = _CURRENCY_STRIP_PATTERN.sub("", v)
    try:
        amount = float(v)
    except (ValueError, TypeError):
        return False
    return amount >= 0


def _check_percentage(value: str) -> bool:
    v = value.strip().rstrip("%")
    try:
        amount = float(v)
    except (ValueError, TypeError):
        return False
    return 0 <= amount <= 100


def _check_id(value: str) -> bool:
    v = value.strip()
    if _UUID_PATTERN.match(v):
        return True
    if not _GENERIC_ID_PATTERN.match(v) or " " in v:
        return False
    # Require it to look distinctly ID-like: a mix of letters AND digits
    # (e.g. "d41e0b55-c", "12772337" alone is fine too since it's all-digit,
    # but a plain word like "InvalidCategoryName" or "Electronics" should
    # NOT pass — pure-alpha strings are far more likely to be ordinary text).
    has_digit = any(ch.isdigit() for ch in v)
    has_alpha = any(ch.isalpha() for ch in v)
    is_pure_alpha_word = has_alpha and not has_digit
    return not is_pure_alpha_word


def _check_alpha(value: str) -> bool:
    """Accept only alphabetic text: letters, spaces, hyphens, apostrophes.
    Rejects anything with digits (dates, IDs, numbers) or special characters
    (emails, currency symbols, etc.).
    Used for name/category columns where only human-readable words belong."""
    v = value.strip()
    if not v:
        return False
    # Reject immediately if any digit is present — covers dates, IDs, codes
    if _ALPHA_DIGITS_PATTERN.search(v):
        return False
    return bool(_ALPHA_PATTERN.match(v))


def _check_enum(value: str, allowed_values: Optional[List[str]]) -> bool:
    if not allowed_values:
        # No allowed-value list configured yet — don't fail every row over
        # an unconfigured column; treat as a no-op pass until the user sets one.
        return True
    normalized_allowed = {str(v).strip().lower() for v in allowed_values}
    return str(value).strip().lower() in normalized_allowed


_FORMAT_CHECKERS = {
    "EMAIL": (_check_email, "a valid email address"),
    "PHONE": (_check_phone, "a valid phone number"),
    "CURRENCY": (_check_currency, "a valid currency amount"),
    "PERCENTAGE": (_check_percentage, "a percentage between 0 and 100"),
    "ID": (_check_id, "a valid ID (UUID or alphanumeric code)"),
    "ALPHA": (_check_alpha, "alphabetic text only (letters, spaces, hyphens, apostrophes — no digits or special characters)"),
}


def _validate_row(
    row: pd.Series,
    col_types: Dict[str, str],
    column_enum_values: Optional[Dict[str, List[str]]] = None,
) -> List[Dict]:
    issues = []
    column_enum_values = column_enum_values or {}

    for col, val in row.items():
        expected = col_types.get(col, "TEXT")
        if pd.isna(val):
            issues.append({"column": col, "value": None, "issue": "null_value", "message": f"Column '{col}' is empty"})
            continue

        str_val = str(val)

        if expected == "INTEGER":
            try:
                int(float(str_val))
            except (ValueError, TypeError):
                issues.append({"column": col, "value": str_val, "issue": "type_mismatch", "message": f"Column '{col}' expects INTEGER, got '{val}'"})

        elif expected in ("FLOAT", "FLOAT64", "FLOAT32", "DOUBLE", "REAL", "DECIMAL", "NUMERIC"):
            try:
                float(str_val)
            except (ValueError, TypeError):
                issues.append({"column": col, "value": str_val, "issue": "type_mismatch", "message": f"Column '{col}' expects FLOAT, got '{val}'"})

        elif expected == "ENUM":
            allowed = column_enum_values.get(col)
            if not _check_enum(str_val, allowed):
                allowed_preview = ", ".join(allowed[:5]) + ("..." if allowed and len(allowed) > 5 else "")
                issues.append({
                    "column": col, "value": str_val, "issue": "enum_mismatch",
                    "message": f"Column '{col}' expects one of [{allowed_preview}], got '{val}'",
                })

        elif expected in _FORMAT_CHECKERS:
            checker, description = _FORMAT_CHECKERS[expected]
            if not checker(str_val):
                issues.append({
                    "column": col, "value": str_val, "issue": "format_mismatch",
                    "message": f"Column '{col}' expects {description}, got '{val}'",
                })

        elif expected in ("TEXT", "object"):
            # TEXT is permissive — it accepts any human-readable string.
            # The only thing we reject here is a bare numeric value (int/float
            # python type, or a string that parses cleanly as a number) because
            # that is the signature of a left-shifted numeric value landing in a
            # text column. Dates, IDs, and other non-alpha strings are valid TEXT.
            # Use ALPHA instead for columns that must contain only letters/words.
            is_python_numeric = isinstance(val, (int, float)) and not isinstance(val, bool)
            is_string_numeric = False
            if not is_python_numeric and isinstance(val, str):
                try:
                    float(str_val)
                    is_string_numeric = True
                except (ValueError, TypeError):
                    pass
            if is_python_numeric or is_string_numeric:
                issues.append({"column": col, "value": str_val, "issue": "numeric_in_text", "message": f"Column '{col}' expects TEXT but got numeric value '{val}'"})

        elif expected == "ALPHA":
            # ALPHA is strict — letters, spaces, hyphens, apostrophes only.
            # Rejects anything containing digits (dates, IDs, phone numbers,
            # currency values, etc.). Use this for name/category columns.
            checker, description = _FORMAT_CHECKERS["ALPHA"]
            if not checker(str_val):
                # Give a more specific message depending on what's wrong.
                has_digit = _ALPHA_DIGITS_PATTERN.search(str_val)
                detail = "contains digits or non-alphabetic characters"
                if has_digit:
                    detail = "contains digits (dates, numbers, and codes are not allowed)"
                issues.append({
                    "column": col, "value": str_val, "issue": "format_mismatch",
                    "message": f"Column '{col}' expects alphabetic text only but '{val}' {detail}",
                })

    return issues


def _value_matches_type(value: str, expected: str, allowed_values: Optional[List[str]] = None) -> bool:
    """Lightweight re-check: does this single value satisfy a given column
    type, independent of which column it actually came from? Used by the
    row-shift detector to test whether a misplaced value would fit better
    in a neighboring column."""
    if value is None:
        return False

    str_val = str(value).strip()
    if str_val == "":
        return False

    if expected == "INTEGER":
        try:
            int(float(str_val))
            return True
        except (ValueError, TypeError):
            return False
    if expected in ("FLOAT", "FLOAT64", "FLOAT32", "DOUBLE", "REAL", "DECIMAL", "NUMERIC"):
        try:
            float(str_val)
            return True
        except (ValueError, TypeError):
            return False
    if expected == "ENUM":
        return _check_enum(str_val, allowed_values)
    if expected in _FORMAT_CHECKERS:
        checker, _ = _FORMAT_CHECKERS[expected]
        return checker(str_val)
    if expected in ("TEXT", "object"):
        try:
            float(str_val)
            return False  # purely numeric strings don't count as a good TEXT fit
        except (ValueError, TypeError):
            return True
    return False


def _detect_row_shift(
    row_data: Dict[str, Any],
    issues: List[Dict],
    columns: List[str],
    col_types: Dict[str, str],
    column_enum_values: Optional[Dict[str, List[str]]] = None,
) -> List[Dict]:
    """Detect when a missing field caused every subsequent value to land in
    the wrong column (a left-shift cascade).

    The key insight: when a value is absent from the source file (not an
    empty field — a completely missing one), pandas fills columns from the
    left with no NaN at the origin. The row looks like:

        CATEGORY='35.25'  PRICE=15  DISCOUNT=29.96  FINAL_PRICE='UPI'  ...  PURCHASE_DATE=NaN

    The signal is:  row_data[col] does NOT fit col_types[col]
                    but DOES fit col_types[col + 1]   (the shifted-right type)

    We scan left-to-right for the first column where this flip happens — that
    is the shift origin (the column whose value is missing from the source).
    Everything from that column onward is then annotated as a shift casualty.
    """
    column_enum_values = column_enum_values or {}
    if not issues:
        return issues

    issue_by_col = {iss["column"]: iss for iss in issues}

    # Walk columns left-to-right looking for the leftmost position where
    # the value does NOT fit its own type but DOES fit the next column's type.
    # That crossing point is where the missing field was.
    shift_origin_idx: Optional[int] = None
    consecutive_fits = 0  # how many columns in a row match the shifted pattern

    for i, col in enumerate(columns[:-1]):
        val = row_data.get(col)
        if val is None:
            # A trailing NaN at the end of a shifted row — stop scanning,
            # this is where the row ran out of values.
            break

        next_col = columns[i + 1]
        own_type  = col_types.get(col, "TEXT")
        next_type = col_types.get(next_col, "TEXT")

        fits_own  = _value_matches_type(val, own_type,  column_enum_values.get(col))
        fits_next = _value_matches_type(val, next_type, column_enum_values.get(next_col))

        if not fits_own and fits_next:
            if shift_origin_idx is None:
                shift_origin_idx = i
            consecutive_fits += 1
        elif shift_origin_idx is None:
            # No origin found yet and this cell isn't a clear shift signal.
            # Keep scanning — don't reset anything (there's nothing to reset).
            pass
        # Once an origin is established we do NOT reset on subsequent cells.
        # In a left-shift cascade every value from the origin onward sits in the
        # wrong column: it fits its own type by coincidence sometimes (e.g. a
        # float currency value also passes a percentage check) and may or may
        # not fit the next column's type depending on type overlap.  Resetting
        # on any ambiguous cell would erase a correct detection.  We commit to
        # the first clear origin (fits_next but not fits_own) and trust the
        # trailing NaN as corroborating evidence.

    # Require at least 1 consecutive shifted cell to commit (avoids
    # false positives on rows with a single incidental type mismatch).
    if shift_origin_idx is None or consecutive_fits < 1:
        return issues

    origin_col = columns[shift_origin_idx]

    # Synthesise a new issue for the shift origin column (the missing field).
    # The origin column currently holds a value that belongs one column to the
    # right — it has no issue entry of its own because it wasn't null.
    origin_issue = issue_by_col.get(origin_col)
    if origin_issue:
        origin_issue["possible_column_shift"] = True
        origin_issue["shift_hint"] = (
            f"A value appears to be missing before '{origin_col}' — "
            f"everything from this column onward is shifted one position to the left."
        )
    else:
        # The origin column may have passed its own type check by coincidence
        # (e.g. a numeric value in a CURRENCY column that also happens to be a
        # valid PERCENTAGE). Inject an informational shift-origin marker.
        new_issue = {
            "column": origin_col,
            "value": row_data.get(origin_col),
            "issue": "column_shift_origin",
            "message": (
                f"A value appears to be missing before '{origin_col}' — "
                f"all subsequent columns are shifted one position to the left."
            ),
            "possible_column_shift": True,
            "shift_hint": (
                f"A value appears to be missing before '{origin_col}' — "
                f"everything from this column onward is shifted one position to the left."
            ),
        }
        issues.append(new_issue)

    # Annotate every column after the origin as a shift casualty.
    for iss in issues:
        if iss.get("column") == origin_col:
            continue
        iss_col = iss.get("column")
        if iss_col not in columns:
            continue
        if columns.index(iss_col) > shift_origin_idx:
            iss["possible_column_shift"] = True
            iss["shift_hint"] = (
                f"Value displaced from the previous column — a missing field before "
                f"'{origin_col}' shifted this and all subsequent values one column to the left."
            )

    return issues


def validate_file_for_import(
    file_path: str,
    column_type_overrides: Dict[str, str] = None,
    column_enum_values: Dict[str, List[str]] = None,
    page: int = 1,
    page_size: int = 100,
) -> Dict[str, Any]:
    """
    Read and validate a file without writing to any database.
    Returns all rows with validation status, column type map, and issue summary.
    """
    df = _read_file(file_path)
    df.columns = [col.strip() for col in df.columns]
    columns = list(df.columns)

    col_types = _detect_column_types(df)
    if column_type_overrides:
        for col, override in column_type_overrides.items():
            if col in col_types and override in _SUPPORTED_OVERRIDES:
                col_types[col] = override

    column_enum_values = column_enum_values or {}

    all_rows = []
    total_issues = 0
    total_shifts = 0

    for idx, (_, row) in enumerate(df.iterrows()):
        issues = _validate_row(row, col_types, column_enum_values)
        row_data = {}
        for col, val in row.items():
            if pd.isna(val):
                row_data[col] = None
            else:
                row_data[col] = val if not isinstance(val, float) else (int(val) if val == int(val) else val)

        if issues:
            issues = _detect_row_shift(row_data, issues, columns, col_types, column_enum_values)
            if any(i.get("possible_column_shift") for i in issues):
                total_shifts += 1

        all_rows.append({
            "row_index": idx,
            "data": row_data,
            "status": "error" if issues else "ok",
            "issues": issues,
        })
        if issues:
            total_issues += 1

    # Paginate
    total_rows = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = all_rows[start:end]

    issue_rows = [r for r in all_rows if r["status"] == "error"]

    return {
        "file_name": os.path.basename(file_path),
        "total_rows": total_rows,
        "total_issues": total_issues,
        "total_possible_shifts": total_shifts,
        "columns": columns,
        "column_types": col_types,
        "column_enum_values": column_enum_values,
        "supported_type_overrides": _SUPPORTED_OVERRIDES,
        "rows": page_rows,
        "issue_rows": issue_rows[:500],  # cap at 500 for safety
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, -(-total_rows // page_size)),
        },
    }