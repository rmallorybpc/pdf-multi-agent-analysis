def chunk_markdown(text: str, chunk_size_chars: int, overlap_chars: int) -> list[str]:
    """Split markdown text into overlapping fixed-size chunks."""
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if overlap_chars >= chunk_size_chars:
        raise ValueError("overlap_chars must be smaller than chunk_size_chars")

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(n, start + chunk_size_chars)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - overlap_chars

    return chunks
