import re
from typing import Dict, Any, Optional

_NUM_WORDS = {
    'zero': 0,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
}


def _word_to_int(s: str) -> Optional[int]:
    """Convert numeric words or digit strings to integers."""
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return _NUM_WORDS.get(s)


def _safe_int(val: str) -> Optional[int]:
    """Try to convert a value (word or digit) to an int, safely."""
    n = _word_to_int(val)
    if n is not None:
        return n
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def interpret_nl_query(query: str) -> Dict[str, Any]:
    """Interpret natural language filter queries into structured filters."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    q = query.lower()
    filters: Dict[str, Any] = {}

    # Negation: handle "non/not palindromic" before positive match
    if re.search(r'\b(?:non[-\s]*|not\s+)(?:palindr?om(?:e|ic)?s?)\b', q):
        filters['is_palindrome'] = False
    elif re.search(r'\bpalindr?om(e|ic)?s?\b', q):
        filters['is_palindrome'] = True

    if re.search(r'\b(single|one)\s+word\b', q):
        filters['word_count'] = 1
    else:
        # exactly N words
        m = re.search(r'\b(?:exactly\s+)?(\d+|[a-z]+)\s+words?\b', q)
        if m:
            n = _safe_int(m.group(1))
            if n is not None:
                filters['word_count'] = n

        # at least/min/minimum N words
        m = re.search(r'\b(?:at least|min(?:imum)?)\s+(\d+|[a-z]+)\s+words?\b', q)
        if m:
            n = _safe_int(m.group(1))
            if n is not None:
                filters['min_word_count'] = max(filters.get('min_word_count', 0), n)

        # at most/max/maximum N words
        m = re.search(r'\b(?:at most|max(?:imum)?)\s+(\d+|[a-z]+)\s+words?\b', q)
        if m:
            n = _safe_int(m.group(1))
            if n is not None:
                current = filters.get('max_word_count', float('inf'))
                filters['max_word_count'] = min(current, n)

        # N or more / N or fewer words
        m = re.search(r'\b(\d+|[a-z]+)\s+or\s+more\s+words?\b', q)
        if m:
            n = _safe_int(m.group(1))
            if n is not None:
                filters['min_word_count'] = max(filters.get('min_word_count', 0), n)

        m = re.search(r'\b(\d+|[a-z]+)\s+or\s+fewer\s+words?\b', q)
        if m:
            n = _safe_int(m.group(1))
            if n is not None:
                current = filters.get('max_word_count', float('inf'))
                filters['max_word_count'] = min(current, n)

        # between A and B words
        m = re.search(r'\bbetween\s+(\d+|[a-z]+)\s+and\s+(\d+|[a-z]+)\s+words?\b', q)
        if m:
            a = _safe_int(m.group(1))
            b = _safe_int(m.group(2))
            if a is not None and b is not None:
                lo, hi = sorted([a, b])
                filters['min_word_count'] = max(filters.get('min_word_count', 0), lo)
                current = filters.get('max_word_count', float('inf'))
                filters['max_word_count'] = min(current, hi)

    m = re.search(r'length\s*(?:between|from)\s*(\d+|[a-z]+)\s*(?:and|to|-)\s*(\d+|[a-z]+)', q)
    if m:
        a_n = _safe_int(m.group(1))
        b_n = _safe_int(m.group(2))
        if a_n is not None and b_n is not None:
            filters['min_length'] = min(a_n, b_n)
            filters['max_length'] = max(a_n, b_n)

    m = re.search(r'longer than\s*(\d+|[a-z]+)\s*(?:characters?|chars?)?', q)
    if m:
        n = _safe_int(m.group(1))
        if n is not None:
            filters['min_length'] = max(filters.get('min_length', 0), n + 1)

    m = re.search(r'shorter than\s*(\d+|[a-z]+)\s*(?:characters?|chars?)?', q)
    if m:
        n = _safe_int(m.group(1))
        if n is not None:
            current_max = filters.get('max_length', float('inf'))
            filters['max_length'] = min(current_max, n - 1)

    m = re.search(r'(?:at least|minimum|min)\s*(\d+|[a-z]+)\s*(?:characters?|chars?)?', q)
    if m:
        n = _safe_int(m.group(1))
        if n is not None:
            filters['min_length'] = max(filters.get('min_length', 0), n)

    m = re.search(r'(?:at most|maximum|max)\s*(\d+|[a-z]+)\s*(?:characters?|chars?)?', q)
    if m:
        n = _safe_int(m.group(1))
        if n is not None:
            current_max = filters.get('max_length', float('inf'))
            filters['max_length'] = min(current_max, n)

    m = re.search(r'\b(?:exactly|length(?:\s*(?:is|=))?)\s*(\d+|[a-z]+)\s*(?:characters?|chars?)?\b', q)
    if m:
        n = _safe_int(m.group(1))
        if n is not None:
            filters['min_length'] = n
            filters['max_length'] = n

    # Explicit character capture only when 'letter' or 'character' is specified
    m = re.search(r"(?:contain|contains|containing)(?: the)? (?:letter|character) ['\"]?([a-z])['\"]?", q)
    if m:
        filters['contains_character'] = m.group(1)

    if 'first vowel' in q:
        # Heuristic: map to 'a' unless an explicit letter was already captured
        filters['contains_character'] = filters.get('contains_character', 'a')

    if 'min_length' in filters and 'max_length' in filters:
        if filters['min_length'] > filters['max_length']:
            raise ValueError("parsed filters conflict: min_length > max_length")

    if 'min_word_count' in filters and 'max_word_count' in filters:
        if filters['min_word_count'] > filters['max_word_count']:
            raise ValueError("parsed filters conflict: min_word_count > max_word_count")

    return {'original': query, 'parsed_filters': filters}
