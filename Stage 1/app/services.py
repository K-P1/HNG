from hashlib import sha256
from typing import Dict, Any, Union, Optional
from datetime import datetime, timezone
from app.NLP import interpret_nl_query


def _compute_properties(value: str) -> Dict[str, Any]:
    original = value
    hash_val = sha256(original.encode()).hexdigest()

    freq: Dict[str, int] = {}
    for c in original:
        freq[c] = freq.get(c, 0) + 1

    unique_chars = len(set(original))

    lower = original.lower()
    return {
        "length": len(original),
        "is_palindrome": lower == lower[::-1],
        "unique_characters": unique_chars,
        "word_count": len(original.split()),
        "sha256_hash": hash_val,
        "character_frequency_map": freq,
    }


def _matches_filters(record: dict, filters: Dict[str, Any]) -> bool:
    props = record.get("properties", {})
    if not filters:
        return True

    if 'is_palindrome' in filters:
        want = filters['is_palindrome']
        if isinstance(want, str):
            want = want.lower() in ('1', 'true', 'yes')
        if bool(props.get('is_palindrome')) != bool(want):
            return False

    if 'min_length' in filters:
        if props.get('length', 0) < int(filters['min_length']):
            return False

    if 'max_length' in filters:
        if props.get('length', 0) > int(filters['max_length']):
            return False

    if 'word_count' in filters:
        if props.get('word_count') != int(filters['word_count']):
            return False

    if 'contains_character' in filters:
        ch = str(filters['contains_character']).lower()
        freq_map = props.get('character_frequency_map', {})
        # Case-insensitive match: aggregate by lower-case
        found = False
        for k, v in freq_map.items():
            if k.lower() == ch and v > 0:
                found = True
                break
        if not found:
            return False

    return True


def create_string(value: str, db: dict) -> Dict[str, Any]:
    props = _compute_properties(value)
    hash_val = props["sha256_hash"]

    if hash_val in db:
        raise ValueError("String already exists")

    record = {
        "id": hash_val,
        "value": value,
        "properties": props,
        "created_at": datetime.now(timezone.utc),
    }
    db[hash_val] = record
    return record


def filter_strings(db: dict, filters: Union[dict, str]) -> Dict[str, Any]:
    interpreted_query: Dict[str, Any] = {}
    filters_dict: Dict[str, Any] = {}

    if isinstance(filters, str):
        parsed = interpret_nl_query(filters)
        filters_dict = parsed.get('parsed_filters', {})
        interpreted_query = parsed
        # If NL query yields no filters, treat as unable to parse per spec -> 400
        if not filters_dict:
            raise ValueError("unable to parse natural language query")
    else:
        filters_dict = filters

    result: Dict[str, Any] = {"records": [r for r in db.values() if _matches_filters(r, filters_dict)]}
    if interpreted_query:
        result["interpreted_query"] = interpreted_query
    return result


def get_string_by_value(string_value: str, db: dict) -> Dict[str, Any]:
    """Lookup record by hashing the exact provided string value (spec path)."""
    string_hash = sha256(string_value.encode()).hexdigest()
    record = db.get(string_hash)
    if not record:
        raise ValueError(f"String '{string_value}' not found")
    return record


def delete_string_by_value(string_value: str, db: dict) -> None:
    string_hash = sha256(string_value.encode()).hexdigest()
    if string_hash not in db:
        raise ValueError(f"String '{string_value}' not found")
    del db[string_hash]


def validate_query_filters(
    is_palindrome: Optional[bool] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    word_count: Optional[int] = None,
    contains_character: Optional[str] = None,
) -> Dict[str, Any]:
    filters: dict = {}
    
    if is_palindrome is not None:
        filters["is_palindrome"] = is_palindrome
    
    if min_length is not None:
        if min_length < 0:
            raise ValueError("min_length must be non-negative")
        filters["min_length"] = min_length
    
    if max_length is not None:
        if max_length < 0:
            raise ValueError("max_length must be non-negative")
        filters["max_length"] = max_length
    
    if word_count is not None:
        if word_count < 0:
            raise ValueError("word_count must be non-negative")
        filters["word_count"] = word_count
    
    if contains_character is not None:
        if len(contains_character) != 1:
            raise ValueError("contains_character must be a single character")
        filters["contains_character"] = contains_character.lower()
    
    if "min_length" in filters and "max_length" in filters:
        if filters["min_length"] > filters["max_length"]:
            raise ValueError("min_length cannot be greater than max_length")
    
    return filters


def get_all_strings_with_filters(db: dict, filters: Dict[str, Any]) -> Dict[str, Any]:
    result = filter_strings(db, filters)
    return {
        "data": result["records"],
        "count": len(result["records"]),
        "filters_applied": filters if filters else {},
    }


def get_strings_by_natural_language(db: dict, query: str) -> Dict[str, Any]:
    result = filter_strings(db, query)
    return {
        "data": result["records"],
        "count": len(result["records"]),
        "interpreted_query": result.get("interpreted_query", {}),
    }
