"""Text pipeline: chunking edge cases and normalization contract."""

import pytest

from app.services.document_processing import chunk_text, normalize_text


def test_chunk_text_never_emits_empty_chunks():
    # Text sized so the final window is whitespace-only
    text = "a" * 500 + " " * 80
    chunks = chunk_text(text, chunk_size=500, overlap=100)
    assert all(chunks), "whitespace tails must be dropped, not embedded"


def test_chunk_text_overlap_windows():
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=2)
    assert chunks == ["abcd", "cdef", "efgh", "ghij", "ij"]


def test_chunk_text_rejects_overlap_ge_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=100, overlap=100)


def test_normalize_merges_broken_lines_into_sentences():
    raw = "The quick brown\nfox jumps over\nthe lazy dog.\nSecond sentence.\n"
    assert (
        normalize_text(raw)
        == "The quick brown fox jumps over the lazy dog. Second sentence."
    )


def test_normalize_output_is_single_line():
    raw = "One.\n\n\nTwo.\n \nThree without period\ncontinues here."
    result = normalize_text(raw)
    assert "\n" not in result
    assert "  " not in result
