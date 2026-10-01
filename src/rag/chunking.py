def _split_text_recursive(text: str, chunk_size: int = 1000, chunk_overlap: int = 200, separators: list[str] = None) -> list[str]:
    """Recursively split text using hierarchy of separators without external dependencies."""
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(t: str, seps: list[str]) -> list[str]:
        if not seps or len(t) <= chunk_size:
            return [t] if t else []

        sep = seps[0]
        parts = t.split(sep) if sep else list(t)
        result = []
        for part in parts:
            if len(part) <= chunk_size:
                if part:
                    result.append(part)
            else:
                result.extend(_split(part, seps[1:]))

        merged = []
        cur = []
        cur_len = 0

        for p in result:
            p_len = len(p) + (len(sep) if cur and sep else 0)
            if cur_len + p_len <= chunk_size:
                cur.append(p)
                cur_len += p_len
            else:
                if cur:
                    merged.append(sep.join(cur) if sep else "".join(cur))
                    while cur and sum(len(x) for x in cur) > chunk_overlap:
                        cur.pop(0)
                    cur_len = sum(len(x) for x in cur)
                cur.append(p)
                cur_len += len(p)

        if cur:
            merged.append(sep.join(cur) if sep else "".join(cur))
        return merged

    return _split(text, separators)


def chunk_documents(documents, chunk_size=1000, chunk_overlap=200):
    """
    Chunk documents into smaller pieces using recursive character splitting.

    Args:
        documents (list): A list of documents to be chunked.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.

    Returns:
        list: A list of chunked documents.
    """
    chunks = []

    for doc in documents:
        texts = _split_text_recursive(
            doc["text"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        for i, text in enumerate(texts):
            chunks.append({
                "text": text,
                "source": doc["source"],
                "chunk_id": i,
            })

    return chunks