import pytest
from app.services import create_string, filter_strings, _compute_properties, _matches_filters
from app.NLP import interpret_nl_query
from datetime import datetime, timezone


class TestComputeProperties:
    """Tests for property computation."""
    
    def test_basic_analysis(self):
        props = _compute_properties("hello world")
        assert props["length"] == 11
        assert props["word_count"] == 2
        assert props["is_palindrome"] is False
        assert props["unique_characters"] == 8  # Includes space as a character

    def test_palindrome(self):
        props = _compute_properties("racecar")
        assert props["is_palindrome"] is True
        assert props["length"] == 7

    def test_character_frequency_includes_spaces(self):
        props = _compute_properties("hello world")
        freq_map = props["character_frequency_map"]
        assert " " in freq_map  # Space is included per spec
        assert freq_map["h"] == 1
        assert freq_map["l"] == 3
        assert freq_map["o"] == 2

    def test_character_frequency_basic(self):
        props = _compute_properties("aabbcc")
        assert props["character_frequency_map"]["a"] == 2
        assert props["character_frequency_map"]["b"] == 2
        assert props["character_frequency_map"]["c"] == 2

    def test_normalization(self):
        """Test that normalization is consistent."""
        props1 = _compute_properties("Hello World")
        props2 = _compute_properties("hello world")
        # Length and properties should match (normalized)
        assert props1["length"] == props2["length"]
        assert props1["is_palindrome"] == props2["is_palindrome"]

    def test_sha256_hash_of_original(self):
        """Test that hash is computed from normalized string."""
        import hashlib
        props = _compute_properties("hello")
        # Hash should be of the normalized (lowercase) string
        expected_hash = hashlib.sha256("hello".encode()).hexdigest()
        assert props["sha256_hash"] == expected_hash

    def test_unique_characters_includes_spaces(self):
        props = _compute_properties("hello world")
        # h, e, l, o, w, r, d, space => 8 distinct
        assert props["unique_characters"] == 8


class TestMatchesFilters:
    @pytest.fixture
    def sample_record(self):
        return {
            "id": "abc123",
            "value": "hello world",
            "properties": _compute_properties("hello world"),
        }

    def test_empty_filters_match(self, sample_record):
        assert _matches_filters(sample_record, {}) is True

    def test_palindrome_filter(self, sample_record):
        record = {"properties": _compute_properties("racecar")}
        assert _matches_filters(record, {"is_palindrome": True}) is True

    def test_length_filters(self, sample_record):
        assert _matches_filters(sample_record, {"min_length": 5}) is True
        assert _matches_filters(sample_record, {"max_length": 20}) is True

    def test_word_count_filter(self, sample_record):
        assert _matches_filters(sample_record, {"word_count": 2}) is True

    def test_contains_character_filter(self, sample_record):
        assert _matches_filters(sample_record, {"contains_character": "h"}) is True

    def test_combined_filters(self, sample_record):
        filters = {"min_length": 5, "word_count": 2, "is_palindrome": False}
        assert _matches_filters(sample_record, filters) is True


class TestCreateString:
    def test_create_new_string(self):
        db = {}
        record = create_string("test string", db)
        assert record["value"] == "test string"
        assert "id" in record
        assert "properties" in record
        assert "created_at" in record
        assert isinstance(record["created_at"], datetime)
        assert len(db) == 1

    def test_duplicate_raises_error(self):
        db = {}
        create_string("test string", db)
        with pytest.raises(ValueError, match="String already exists"):
            create_string("test string", db)

    def test_exact_duplicates_conflict_only(self):
        db = {}
        create_string("Test String", db)
        # Case-variant is allowed since spec dedupe is exact
        create_string("test string", db)

    def test_created_at_preserved(self):
        """Test that created_at is set and preserved."""
        db = {}
        record = create_string("test", db)
        assert "created_at" in record
        assert record["created_at"].tzinfo == timezone.utc


class TestFilterStrings:
    def test_filter_with_dict(self):
        db = {}
        create_string("hello", db)
        create_string("racecar", db)
        
        result = filter_strings(db, {"is_palindrome": True})
        assert len(result["records"]) == 1
        assert "interpreted_query" not in result

    def test_filter_with_nl_query(self):
        db = {}
        create_string("a", db)
        create_string("racecar", db)
        
        result = filter_strings(db, "single word palindromes")
        assert len(result["records"]) == 2
        assert "interpreted_query" in result

    def test_empty_db_returns_empty_records(self):
        db = {}
        result = filter_strings(db, {})
        assert result["records"] == []

    def test_filter_with_empty_filters(self):
        db = {}
        create_string("test1", db)
        create_string("test2", db)
        result = filter_strings(db, {})
        assert len(result["records"]) == len(db)
