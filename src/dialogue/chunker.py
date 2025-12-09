from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

try:
    import tiktoken
except ImportError:  # pragma: no cover - fallback for environments without tiktoken
    tiktoken = None


def _basic_tokenizer(text: str) -> List[str]:
    return re.findall(r"\w+|\S", text)


@dataclass
class TokenChunker:
    """Split long transcripts into token-aware chunks for model consumption."""

    max_tokens: int = 12000
    overlap_tokens: int = 200
    encoding_name: str = "cl100k_base"

    def __post_init__(self) -> None:
        if tiktoken is not None:
            self._encoder = tiktoken.get_encoding(self.encoding_name)
        else:  # pragma: no cover
            self._encoder = None

    def _encode(self, text: str) -> List[int]:
        if self._encoder:
            return self._encoder.encode(text)
        return list(range(len(_basic_tokenizer(text))))

    def chunk(self, text: str) -> Iterable[str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            return []

        chunks: List[str] = []
        current_tokens = 0
        current_parts: List[str] = []

        for paragraph in paragraphs:
            token_len = len(self._encode(paragraph))
            if current_tokens + token_len <= self.max_tokens:
                current_parts.append(paragraph)
                current_tokens += token_len
                continue

            if current_parts:
                chunks.append("\n\n".join(current_parts))
                # start new chunk with overlap tokens from end of paragraph
                if self.overlap_tokens > 0:
                    overlap_slice = paragraph[-self.overlap_tokens :]
                    current_parts = [overlap_slice]
                    current_tokens = len(self._encode(overlap_slice))
                else:
                    current_parts = []
                    current_tokens = 0

            if token_len >= self.max_tokens:
                chunks.append(paragraph)
                current_parts = []
                current_tokens = 0
            else:
                current_parts = [paragraph]
                current_tokens = token_len

        if current_parts:
            chunks.append("\n\n".join(current_parts))
        return chunks

