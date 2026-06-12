from typing import List


CHUNK_SIZE = 500 
OVERLAP = 100 
MIN_CHUNK_LEN = 50 



def chunk_text(text: str) -> List[str]:
    text = _normalise(text)
    if not text:
        return []

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end   = start + CHUNK_SIZE
        chunk = text[start:end].strip()

        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        start += CHUNK_SIZE - OVERLAP

    return chunks


def _normalise(text: str) -> str:
    """Collapse excessive whitespace / blank lines."""
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
