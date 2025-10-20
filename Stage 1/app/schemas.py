from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional, List


class StringRequest(BaseModel):
    """Request schema for creating/analyzing a string."""
    value: str


class StringProperties(BaseModel):
    """Computed properties of an analyzed string."""
    length: int
    is_palindrome: bool
    unique_characters: int
    word_count: int
    sha256_hash: str
    character_frequency_map: Dict[str, int]


class StringResponse(BaseModel):
    """Response schema for string records."""
    id: str
    value: str
    properties: StringProperties
    created_at: datetime


class FilterResponse(BaseModel):
    """Response schema for filtered results."""
    data: List[StringResponse]
    count: int
    interpreted_query: Optional[Dict[str, Any]] = None
    filters_applied: Optional[Dict[str, Any]] = None

