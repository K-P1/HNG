from fastapi import APIRouter, HTTPException, Query
from .db import db
from .schemas import StringRequest, StringResponse, FilterResponse
from .services import (
    create_string,
    get_string_by_value,
    delete_string_by_value,
    validate_query_filters,
    get_all_strings_with_filters,
    get_strings_by_natural_language,
)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok"}


@router.post("/strings", response_model=StringResponse, status_code=201)
def create_string_endpoint(payload: StringRequest) -> dict:
    """Create and analyze a string."""
    try:
        return create_string(payload.value, db)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/strings/filter-by-natural-language", response_model=FilterResponse)
def filter_by_natural_language(query: str = Query(...)) -> dict:
    """Filter strings using a natural language query."""
    try:
        return get_strings_by_natural_language(db, query)
    except ValueError as e:
        if "conflict" in str(e).lower():
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/strings/{string_value}", response_model=StringResponse)
def get_string_endpoint(string_value: str) -> dict:
    """Get a specific string by its raw value (spec requirement)."""
    try:
        return get_string_by_value(string_value, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/strings", response_model=FilterResponse)
def get_all_strings(
    is_palindrome: bool = Query(None),
    min_length: int = Query(None),
    max_length: int = Query(None),
    word_count: int = Query(None),
    contains_character: str = Query(None),
) -> dict:
    """Get all strings with optional filtering."""
    try:
        filters = validate_query_filters(is_palindrome, min_length, max_length, word_count, contains_character)
        return get_all_strings_with_filters(db, filters)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/strings/{string_value}", status_code=204)
def delete_string_endpoint(string_value: str) -> None:
    """Delete a string by its raw value (spec requirement)."""
    try:
        delete_string_by_value(string_value, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
