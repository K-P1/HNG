"""Tests for all API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import db


@pytest.fixture(autouse=True)
def clear_db():
    """Clear database before each test."""
    db.clear()
    yield
    db.clear()


client = TestClient(app)


class TestCreateStringEndpoint:
    """Tests for POST /strings endpoint - integration tests only."""
    
    def test_create_string_success(self):
        """Test creating a new string successfully."""
        response = client.post("/strings", json={"value": "Hello World"})
        assert response.status_code == 201
        data = response.json()
        assert data["value"] == "Hello World"
        assert "id" in data
        assert "properties" in data
        assert "created_at" in data

    def test_create_exact_duplicate_conflict(self):
        """Exact duplicate should return 409; case-variant should be allowed (spec allows exact match dedupe)."""
        client.post("/strings", json={"value": "Test String"})
        response_dup = client.post("/strings", json={"value": "Test String"})
        assert response_dup.status_code == 409
        # case-variant allowed
        response_case = client.post("/strings", json={"value": "test string"})
        assert response_case.status_code == 201

    def test_create_missing_value(self):
        """Missing 'value' should return 400 (Bad Request)."""
        response = client.post("/strings", json={})
        assert response.status_code == 400

    def test_create_wrong_type(self):
        """Non-string value returns 422 (Unprocessable Entity)."""
        response = client.post("/strings", json={"value": 123})
        assert response.status_code == 422

    def test_create_invalid_json_body(self):
        """Malformed JSON body should result in 400 Bad Request per spec."""
        response = client.post(
            "/strings",
            content=b'{"value": "oops"',  # truncated JSON
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestGetStringEndpoint:
    """Tests for GET /strings/{string_id} endpoint."""

    def test_get_string_success(self):
        """Retrieve by string value per spec."""
        client.post("/strings", json={"value": "test string"})
        response = client.get("/strings/test string")
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "test string"

    def test_get_string_not_found(self):
        """Non-existent raw string returns 404."""
        response = client.get("/strings/nonexistent_value")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_string_preserves_created_at(self):
        """created_at should remain the same across retrievals."""
        create_response = client.post("/strings", json={"value": "test"})
        created_at_1 = create_response.json()["created_at"]
        
        get_response = client.get("/strings/test")
        assert get_response.status_code == 200
        created_at_2 = get_response.json()["created_at"]
        assert created_at_1 == created_at_2


class TestGetAllStringsEndpoint:
    """Tests for GET /strings endpoint with filtering."""

    def setup_method(self):
        """Create test data."""
        db.clear()
        client.post("/strings", json={"value": "hello"})
        client.post("/strings", json={"value": "racecar"})
        client.post("/strings", json={"value": "hello world"})
        client.post("/strings", json={"value": "a"})

    def test_get_all_strings(self):
        """Test retrieving all strings without filters."""
        response = client.get("/strings")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 4
        assert len(data["data"]) == 4

    def test_filter_by_palindrome(self):
        """Test filtering by palindrome status."""
        response = client.get("/strings?is_palindrome=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2  # "racecar" and "a"

    def test_filter_by_min_length(self):
        """Test filtering by minimum length."""
        response = client.get("/strings?min_length=5")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_filter_by_max_length(self):
        """Test filtering by maximum length."""
        response = client.get("/strings?max_length=5")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_filter_by_word_count(self):
        """Test filtering by word count."""
        response = client.get("/strings?word_count=1")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_filter_by_contains_character(self):
        """Test filtering by character presence."""
        response = client.get("/strings?contains_character=a")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_filter_combined(self):
        """Test combining multiple filters."""
        response = client.get("/strings?is_palindrome=true&min_length=1&max_length=10")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_invalid_min_length(self):
        """Test that negative min_length returns 400."""
        response = client.get("/strings?min_length=-1")
        assert response.status_code == 400

    def test_invalid_max_length(self):
        """Test that negative max_length returns 400."""
        response = client.get("/strings?max_length=-1")
        assert response.status_code == 400

    def test_invalid_word_count(self):
        """Test that negative word_count returns 400."""
        response = client.get("/strings?word_count=-1")
        assert response.status_code == 400

    def test_min_greater_than_max(self):
        """Test that min_length > max_length returns 400."""
        response = client.get("/strings?min_length=10&max_length=5")
        assert response.status_code == 400

    def test_contains_character_multiple_chars(self):
        """Test that contains_character with multiple characters returns 400."""
        response = client.get("/strings?contains_character=abc")
        assert response.status_code == 400


class TestFilterByNaturalLanguageEndpoint:
    """Tests for GET /strings/filter-by-natural-language endpoint."""

    def setup_method(self):
        """Create test data."""
        db.clear()
        client.post("/strings", json={"value": "a"})
        client.post("/strings", json={"value": "racecar"})
        client.post("/strings", json={"value": "hello world"})
        client.post("/strings", json={"value": "level"})

    def test_single_word_palindromes(self):
        """Test NL query for single word palindromes."""
        response = client.get(
            "/strings/filter-by-natural-language?query=single%20word%20palindromes"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert "interpreted_query" in data

    def test_strings_longer_than(self):
        """Test NL query for strings longer than N characters."""
        response = client.get(
            "/strings/filter-by-natural-language?query=strings%20longer%20than%2010%20characters"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

    def test_strings_containing_character(self):
        """Test NL query for strings containing specific character."""
        response = client.get(
            "/strings/filter-by-natural-language?query=strings%20containing%20the%20letter%20a"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_palindromic_strings(self):
        """Test NL query for palindromic strings."""
        response = client.get(
            "/strings/filter-by-natural-language?query=palindromic%20strings"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_missing_query_param_results_in_400(self):
        """Missing required 'query' should be treated as 400, not 422."""
        response = client.get("/strings/filter-by-natural-language")
        assert response.status_code == 400

    def test_non_palindromic_strings(self):
        """Test NL query for non/not palindromic strings."""
        response = client.get(
            "/strings/filter-by-natural-language?query=non%20palindromic%20strings"
        )
        assert response.status_code == 200
        data = response.json()
        # From setup: a, racecar, hello world, level -> non-palindromic: 'hello world' only
        assert data["count"] == 1

    def test_at_least_three_words(self):
        """Test NL query for 'at least 3 words' returns none with current fixtures."""
        response = client.get(
            "/strings/filter-by-natural-language?query=strings%20with%20at%20least%203%20words"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_contain_the_first_vowel(self):
        """Test NL query for 'contain the first vowel' (heuristic maps to 'a')."""
        response = client.get(
            "/strings/filter-by-natural-language?query=strings%20that%20contain%20the%20first%20vowel"
        )
        assert response.status_code == 200
        data = response.json()
        # From fixtures: 'a', 'racecar', 'hello world', 'level' -> those containing 'a': 'a', 'racecar' => 2
        assert data["count"] == 2


class TestDeleteStringEndpoint:
    """Tests for DELETE /strings/{string_id} endpoint."""

    def test_delete_string_success(self):
        """Delete by raw string value."""
        client.post("/strings", json={"value": "to delete"})
        # Verify it exists
        get_response = client.get("/strings/to delete")
        assert get_response.status_code == 200
        # Delete it
        delete_response = client.delete("/strings/to delete")
        assert delete_response.status_code == 204
        assert delete_response.text == "" or delete_response.text == "null"
        # Verify it's gone
        get_response = client.get("/strings/to delete")
        assert get_response.status_code == 404

    def test_delete_nonexistent_string(self):
        """Deleting non-existent raw string returns 404."""
        response = client.delete("/strings/nonexistent_value")
        assert response.status_code == 404

    def test_delete_string_not_in_get_all(self):
        """After deletion by value, count should decrease."""
        client.post("/strings", json={"value": "string1"})
        client.post("/strings", json={"value": "string2"})
        # Verify both exist
        response = client.get("/strings")
        assert response.json()["count"] == 2
        # Delete one by value
        client.delete("/strings/string2")
        # Verify only one remains
        response = client.get("/strings")
        assert response.json()["count"] == 1


class TestPropertyComputation:
    """Tests for string property computation - integration only."""

    def test_response_structure(self):
        """Test that response has correct structure."""
        response = client.post("/strings", json={"value": "Hello World"})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "value" in data
        assert "properties" in data
        assert "created_at" in data
        assert isinstance(data["properties"], dict)
