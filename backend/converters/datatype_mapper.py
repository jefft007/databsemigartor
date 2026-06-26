from sqlalchemy import Integer, String, Text, Float, DateTime, Boolean, LargeBinary


def map_datatype(source_type: str, target_db_type: str):
    """Map a source column type string to a target database SQLAlchemy type."""
    lower_type = source_type.lower()
    if "int" in lower_type or "serial" in lower_type:
        return Integer
    if "char" in lower_type or "text" in lower_type or "clob" in lower_type:
        return Text
    if "varchar" in lower_type or "string" in lower_type or "nvarchar" in lower_type:
        return String(255)
    if "float" in lower_type or "double" in lower_type or "real" in lower_type:
        return Float
    if "bool" in lower_type or "bit" in lower_type:
        return Boolean
    if "datetime" in lower_type or "timestamp" in lower_type or "date" in lower_type:
        return DateTime
    if "binary" in lower_type or "blob" in lower_type:
        return LargeBinary
    return String(255)


def check_datatype_mismatch(source_type: str, mapped_type: type, target_db_type: str) -> dict | None:
    """Check if the mapped type is a suspicious fallback (e.g., non-string mapped to String)."""
    lower_type = source_type.lower()
    
    # Known keywords that map well
    known_keywords = [
        "int", "serial", "char", "text", "clob", "string", "varchar", "nvarchar",
        "float", "double", "real", "bool", "bit", "datetime", "timestamp", "date",
        "binary", "blob"
    ]
    is_known = any(kw in lower_type for kw in known_keywords)
    
    string_keywords = ["char", "text", "clob", "string", "varchar", "nvarchar"]
    is_string_source = any(kw in lower_type for kw in string_keywords)

    # 1. Unknown or unsupported datatype mapped to String fallback
    if not is_known:
        return {
            "source_datatype": source_type,
            "target_datatype": "VARCHAR" if str(mapped_type).startswith("String") else str(mapped_type),
            "message": "Unsupported or unknown datatype, falling back to string"
        }

    # 2. Suspicious mapping (e.g. numeric/date mapped to String)
    if str(mapped_type).startswith("String") and not is_string_source:
        return {
            "source_datatype": source_type,
            "target_datatype": "VARCHAR",
            "message": "Possible datatype mismatch"
        }
    return None
