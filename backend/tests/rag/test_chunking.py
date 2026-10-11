from app.rag.chunking import chunk, count_tokens
from app.rag.extract import Page


def _pages():
    para = " ".join(f"word{i}" for i in range(60))
    return [Page(1, "\n\n".join([para] * 6)), Page(2, "Heading Here\n\n" + "\n\n".join([para] * 4))]


def test_no_chunk_exceeds_max_tokens():
    chunks = chunk(_pages(), max_tokens=100, overlap=0.15)
    assert len(chunks) > 3
    assert all(c.token_count <= 100 for c in chunks)
    assert all(count_tokens(c.content) == c.token_count for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_oversized_single_sentence_is_split():
    chunks = chunk([Page(1, "alpha " * 1000)], max_tokens=50)
    assert len(chunks) > 1 and all(c.token_count <= 50 for c in chunks)


def test_overlap_applied():
    chunks = chunk(_pages(), max_tokens=100, overlap=0.15)
    shared = 0
    for a, b in zip(chunks, chunks[1:]):
        tail = a.content.split()[-3:]
        if b.content.split()[:20] and tail[-1] in b.content.split()[:20]:
            shared += 1
    assert shared >= len(chunks) - 2
    none = chunk(_pages(), max_tokens=100, overlap=0.0)
    assert sum(c.token_count for c in none) < sum(c.token_count for c in chunks)


def test_deterministic_and_meta():
    a = chunk(_pages(), max_tokens=100)
    b = chunk(_pages(), max_tokens=100)
    assert a == b
    assert a[0].meta["page"] == 1
    assert any(c.meta["page"] == 2 for c in a)
    assert any(c.meta.get("section") == "Heading Here" for c in a)


def test_empty_input():
    assert chunk([]) == []
    assert chunk([Page(1, "   \n\n ")]) == []
