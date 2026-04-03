from pdf_multi_agent_analysis.chunking import chunk_markdown


def test_chunking_with_overlap() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_markdown(text, chunk_size_chars=10, overlap_chars=2)

    assert chunks == [
        "abcdefghij",
        "ijklmnopqr",
        "qrstuvwxyz",
    ]


def test_invalid_overlap_raises() -> None:
    try:
        chunk_markdown("abc", chunk_size_chars=5, overlap_chars=5)
    except ValueError as exc:
        assert "smaller" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_chunking_prefers_sentence_boundary() -> None:
    text = "Sentence one is complete. Sentence two is also complete. Sentence three finishes the thought."
    chunks = chunk_markdown(text, chunk_size_chars=45, overlap_chars=5)

    assert chunks[0].endswith(". ")
    assert chunks[0] == "Sentence one is complete. "
