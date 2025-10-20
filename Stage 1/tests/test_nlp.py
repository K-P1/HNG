from app.NLP import interpret_nl_query


def test_single_word_palindromic():
    q = "all single word palindromic strings"
    res = interpret_nl_query(q)
    assert res['original'] == q
    parsed = res['parsed_filters']
    assert parsed.get('word_count') == 1
    assert parsed.get('is_palindrome') is True


def test_strings_longer_than_10():
    q = "strings longer than 10 characters"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    # longer than 10 => min_length = 11
    assert parsed.get('min_length') == 11


def test_contains_letter_z():
    q = "strings containing the letter z"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    assert parsed.get('contains_character') == 'z'


def test_non_palindromic_strings():
    q = "non palindromic strings"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    assert parsed.get('is_palindrome') is False


def test_not_palindromic_strings():
    q = "not palindromic strings"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    assert parsed.get('is_palindrome') is False


def test_at_least_three_words():
    q = "strings with at least three words"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    assert parsed.get('min_word_count') == 3


def test_contain_the_first_vowel():
    q = "strings that contain the first vowel"
    res = interpret_nl_query(q)
    parsed = res['parsed_filters']
    # first vowel heuristic maps to 'a'
    assert parsed.get('contains_character') == 'a'
