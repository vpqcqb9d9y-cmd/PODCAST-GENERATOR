from src.dialogue.chunker import TokenChunker


def test_chunker_splits_long_transcript():
    paragraph = "זוהי פסקה ארוכה עם הרבה מילים שמתארות תרחישי ענן."
    text = "\n\n".join([paragraph] * 20)
    chunker = TokenChunker(max_tokens=50, overlap_tokens=5)
    chunks = list(chunker.chunk(text))
    assert len(chunks) >= 2
    assert sum(len(chunk.split()) for chunk in chunks) >= len(text.split()) * 0.9

