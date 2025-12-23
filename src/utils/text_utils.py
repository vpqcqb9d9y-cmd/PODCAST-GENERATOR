from __future__ import annotations

import re
from typing import Optional

import arabic_reshaper
from bidi.algorithm import get_display

# BiDi isolation markers (avoid LTR fragments flipping surrounding RTL)
LRI = "\u2066"  # left-to-right isolate
PDI = "\u2069"  # pop directional isolate
RLM = "\u200f"  # right-to-left mark


def _isolate_ltr_segments(text: str) -> str:
    """
    Wrap embedded LTR spans (English/numbers/model names) with LRI/PDI to
    prevent reordering issues inside RTL sentences.
    """
    pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+\/&_.]*")
    return pattern.sub(lambda m: f"{LRI}{m.group(0)}{PDI}", text)


def _anchor_punctuation(text: str) -> str:
    """
    Keep trailing punctuation on the RTL side.
    """
    if text and text[-1] in {"!", "?", "."}:
        return f"{text}{RLM}"
    return text


def shape_rtl(text: Optional[str], add_isolates: bool = True) -> str:
    """
    Apply Arabic reshaping + BiDi display for Hebrew/RTL text.

    - Uses arabic_reshaper + bidi.get_display for reliable glyph shaping.
    - Optionally wraps embedded LTR spans with LRI/PDI to avoid flip.
    - Anchors trailing punctuation to the RTL side.
    """
    if not text:
        return ""

    processed = text
    if add_isolates:
        processed = _isolate_ltr_segments(processed)
    processed = _anchor_punctuation(processed)

    # Final shaping into visual order
    try:
        reshaped = arabic_reshaper.reshape(processed)
        return get_display(reshaped)
    except Exception:
        # Defensive: fall back to original string if shaping fails
        return processed

