"""Tests for text utility functions."""

import pytest

from strot.utils.text import extract_json, normalize, parse_python_code, text_match_ratio, tokenize


class TestNormalize:
    """Test Unicode normalization function."""

    def test_basic_normalization(self):
        """Test basic text normalization."""
        result = normalize("Hello World")
        assert result == "hello world"

    def test_unicode_normalization(self):
        """Test Unicode text normalization."""
        # Test with accented characters
        result = normalize("Café")
        assert result == "café"

    def test_case_folding(self):
        """Test case folding."""
        result = normalize("HELLO World")
        assert result == "hello world"

    def test_nfkc_normalization(self):
        """Test NFKC Unicode normalization."""
        # ﬁ is a ligature that should be normalized to "fi"
        result = normalize("ﬁle")
        assert "fi" in result.lower()

    def test_empty_string(self):
        """Test normalization of empty string."""
        result = normalize("")
        assert result == ""

    def test_whitespace_handling(self):
        """Test that whitespace is preserved."""
        result = normalize("hello   world")
        assert result == "hello   world"


class TestTokenize:
    """Test text tokenization function."""

    def test_basic_tokenization(self):
        """Test basic word tokenization."""
        result = tokenize("Hello world test")
        assert result == ["Hello", "world", "test"]

    def test_punctuation_removal(self):
        """Test that punctuation is removed."""
        result = tokenize("Hello, world! How are you?")
        assert result == ["Hello", "world", "How", "are", "you"]

    def test_numbers_excluded(self):
        """Test that numbers are excluded."""
        result = tokenize("Hello 123 world")
        assert result == ["Hello", "world"]

    def test_unicode_text(self):
        """Test tokenization with Unicode text."""
        result = tokenize("Hola mundo café")
        assert result == ["Hola", "mundo", "café"]

    def test_chinese_text(self):
        """Test tokenization with Chinese characters."""
        result = tokenize("你好世界")
        # Chinese tokenization may treat the whole string as one token
        # or individual characters - just check that we get some result
        assert len(result) >= 1
        assert "你好世界" in "".join(result)

    def test_empty_string(self):
        """Test tokenization of empty string."""
        result = tokenize("")
        assert result == []

    def test_only_punctuation(self):
        """Test tokenization of only punctuation."""
        result = tokenize("!@#$%^&*()")
        assert result == []


class TestTextMatchRatio:
    """Test text matching ratio function."""

    def test_exact_matches(self):
        """Test with exact substring matches."""
        subtexts = ["hello", "world"]
        text = "hello beautiful world"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 1.0

    def test_partial_matches(self):
        """Test with partial matches."""
        subtexts = ["hello", "xyz"]
        text = "hello beautiful world"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 0.5

    def test_no_matches(self):
        """Test with no matches."""
        subtexts = ["xyz", "abc"]
        text = "hello beautiful world"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 0.0

    def test_fuzzy_matching(self):
        """Test fuzzy matching behavior."""
        subtexts = ["helo"]  # Misspelled "hello"
        text = "hello world"
        ratio = text_match_ratio(subtexts, text, cutoff=70)
        assert ratio == 1.0  # Should match due to fuzzy matching

    def test_case_insensitive_matching(self):
        """Test case-insensitive matching."""
        subtexts = ["HELLO", "world"]
        text = "hello beautiful WORLD"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 1.0

    def test_unicode_matching(self):
        """Test matching with Unicode text."""
        subtexts = ["café", "naïve"]
        text = "I love café and naïve art"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 1.0

    def test_empty_subtexts(self):
        """Test with empty subtexts list."""
        subtexts = []
        text = "hello world"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 0.0

    def test_threading_safety(self):
        """Test that threading doesn't cause issues."""
        subtexts = ["hello"] * 100  # Many identical subtexts
        text = "hello world"
        ratio = text_match_ratio(subtexts, text)
        assert ratio == 1.0


class TestExtractJson:
    """Test JSON extraction function."""

    def test_basic_json_extraction(self):
        """Test extracting basic JSON."""
        text = '{"key": "value"}'
        result = extract_json(text)
        assert '"key"' in result and '"value"' in result

    def test_json_with_markdown_fences(self):
        """Test extracting JSON from markdown code fences."""
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert '"key"' in result and '"value"' in result

    def test_json_without_language_specifier(self):
        """Test extracting JSON from code fences without language."""
        text = '```\n{"key": "value"}\n```'
        result = extract_json(text)
        assert '"key"' in result and '"value"' in result

    def test_malformed_json_repair(self):
        """Test repairing malformed JSON."""
        text = '{"key": "value",}'  # Trailing comma
        result = extract_json(text)
        # json-repair should fix this
        assert result is not None

    def test_nested_json(self):
        """Test extracting nested JSON."""
        text = '{"outer": {"inner": "value"}}'
        result = extract_json(text)
        assert '"outer"' in result and '"inner"' in result

    def test_json_with_whitespace(self):
        """Test JSON with extra whitespace."""
        text = '  {"key": "value"}  '
        result = extract_json(text)
        assert '"key"' in result and '"value"' in result

    def test_json_with_text_before_after(self):
        """Test JSON embedded in other text."""
        text = 'Here is some JSON: ```json\n{"key": "value"}\n``` and more text'
        result = extract_json(text)
        assert '"key"' in result and '"value"' in result


class TestParsePythonCode:
    """Test Python code parsing function."""

    def test_basic_python_code(self):
        """Test extracting basic Python code."""
        markdown = """```python
def hello():
    return "world"
```"""
        result = parse_python_code(markdown)
        assert "def hello():" in result
        assert 'return "world"' in result

    def test_python_code_with_py_marker(self):
        """Test extracting code with 'py' language marker."""
        markdown = """```py
x = 42
print(x)
```"""
        result = parse_python_code(markdown)
        assert "x = 42" in result
        assert "print(x)" in result

    def test_code_without_language_marker(self):
        """Test extracting code without language specification."""
        markdown = """```
def test():
    pass
```"""
        result = parse_python_code(markdown)
        assert "def test():" in result
        assert "pass" in result

    def test_multiple_code_blocks(self):
        """Test extracting from multiple code blocks."""
        markdown = """First block:
```python
x = 1
```

Second block:
```python
y = 2
```"""
        result = parse_python_code(markdown)
        # Should return the first match
        assert "x = 1" in result

    def test_code_with_indentation(self):
        """Test preserving indentation in extracted code."""
        markdown = """```python
if True:
    x = 1
    if x:
        print("nested")
```"""
        result = parse_python_code(markdown)
        assert "    x = 1" in result  # Indentation preserved
        assert "        print" in result  # Nested indentation preserved

    def test_no_code_blocks_raises_error(self):
        """Test that no code blocks raises ValueError."""
        markdown = "This is just text with no code blocks."
        with pytest.raises(ValueError, match="No code found in markdown"):
            parse_python_code(markdown)

    def test_empty_code_block(self):
        """Test empty code block."""
        markdown = """```python

```"""
        result = parse_python_code(markdown)
        assert result == ""

    def test_code_with_comments(self):
        """Test code with comments."""
        markdown = '''```python
# This is a comment
def func():
    """Docstring"""
    return 42  # Inline comment
```'''
        result = parse_python_code(markdown)
        assert "# This is a comment" in result
        assert '"""Docstring"""' in result
        assert "# Inline comment" in result
