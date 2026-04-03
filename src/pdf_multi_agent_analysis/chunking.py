def chunk_markdown(text: str, chunk_size_chars: int, overlap_chars: int) -> list[str]:
    """Split markdown text into overlapping chunks, preferring natural boundaries."""
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if overlap_chars >= chunk_size_chars:
        raise ValueError("overlap_chars must be smaller than chunk_size_chars")

    chunks: list[str] = []
    start = 0
    n = len(text)
    min_fraction = 0.6
    preferred_separators = ("\n\n", ". ", "? ", "! ", "; ", ": ", "\n", " ")

    while start < n:
        target_end = min(n, start + chunk_size_chars)
        split_end = target_end

        if target_end < n:
            min_end = min(n, start + max(1, int(chunk_size_chars * min_fraction)))
            fallback_min_end = min(n, start + max(1, int(chunk_size_chars * 0.4)))
            window = text[start:target_end]
            search_start = max(0, min_end - start)

            best_cut = -1
            for separator in preferred_separators[:-1]:
                idx = window.rfind(separator, search_start)
                if idx < 0:
                    continue
                best_cut = idx + len(separator)
                break

            if best_cut < 0:
                fallback_start = max(0, fallback_min_end - start)
                for separator in preferred_separators[:-1]:
                    idx = window.rfind(separator, fallback_start)
                    if idx < 0:
                        continue
                    best_cut = idx + len(separator)
                    break

            if best_cut < 0:
                idx = window.rfind(" ", search_start)
                if idx >= 0:
                    best_cut = idx + 1

            if best_cut > 0:
                split_end = start + best_cut

        chunks.append(text[start:split_end])
        if split_end == n:
            break

        next_start = split_end - overlap_chars
        if next_start <= start:
            next_start = split_end
        start = next_start

    return chunks
