from __future__ import annotations

from pathlib import Path
from typing import Any

from officecli_native import normalize_text

from parse_markdown import parse_markdown_blocks


COVER_SIGNAL_NAMES = {
    "government": "CHINH PHU",
    "nation": "CONG HOA XA HOI CHU NGHIA VIET NAM",
    "motto": "DOC LAP - TU DO - HANH PHUC",
    "decree": "NGHI DINH",
    "decision": "QUYET DINH",
    "circular": "THONG TU",
    "serial": "SO:",
}
MAIN_STORY_PREFIXES = ("CHUONG ", "PHAN ", "MUC ", "DIEU ")


def block_text(block: dict) -> str:
    return str(block.get("text") or "").strip()


def normalized_block_text(block: dict) -> str:
    return normalize_text(block_text(block))


def detect_cover_signals(texts: list[str]) -> set[str]:
    signals: set[str] = set()
    for text in texts:
        if not text:
            continue
        if COVER_SIGNAL_NAMES["government"] in text:
            signals.add("government")
        if COVER_SIGNAL_NAMES["nation"] in text:
            signals.add("nation")
        if all(token in text for token in ["DOC LAP", "TU DO", "HANH PHUC"]):
            signals.add("motto")
        if text == COVER_SIGNAL_NAMES["decree"] or text.startswith(f"{COVER_SIGNAL_NAMES['decree']} "):
            signals.add("decree")
        if text == COVER_SIGNAL_NAMES["decision"] or text.startswith(f"{COVER_SIGNAL_NAMES['decision']} "):
            signals.add("decision")
        if text == COVER_SIGNAL_NAMES["circular"] or text.startswith(f"{COVER_SIGNAL_NAMES['circular']} "):
            signals.add("circular")
        if COVER_SIGNAL_NAMES["serial"] in text:
            signals.add("serial")
    return signals


def main_story_anchor_index(blocks: list[dict]) -> int | None:
    fallback_index: int | None = None
    first_heading_index: int | None = None
    for index, block in enumerate(blocks):
        if block.get("type") != "heading":
            continue
        normalized = normalized_block_text(block)
        if not normalized:
            continue
        if first_heading_index is None:
            first_heading_index = index
        if normalized.startswith(("CHUONG ", "PHAN ", "MUC ")):
            return index
        if fallback_index is None and normalized.startswith("DIEU "):
            fallback_index = index
    return fallback_index if fallback_index is not None else first_heading_index


def _sample_markdown(sample_content_file: str | None) -> str | None:
    if not sample_content_file:
        return None
    path = Path(sample_content_file)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _sample_texts(sample_markdown: str | None) -> list[str]:
    if not sample_markdown:
        return []
    sample_blocks, _, _ = parse_markdown_blocks(sample_markdown)
    return [normalized_block_text(block) for block in sample_blocks if normalized_block_text(block)]


def _matches_sample_text(text: str, sample_texts: list[str]) -> bool:
    if not text or len(text) < 8:
        return False
    for sample_text in sample_texts:
        if len(sample_text) < 8:
            continue
        if text in sample_text or sample_text in text:
            return True
    return False


def derive_render_window(blocks: list[dict], *, sample_content_file: str | None = None) -> dict:
    default_window = {
        "strategy": "full-document",
        "start_block_index": 0,
        "start_line": None if not blocks else blocks[0].get("line"),
        "trimmed_prefix_block_count": 0,
        "shared_cover_signals": [],
        "matched_prefix_preview": [],
        "anchor_text": None,
    }
    if not blocks:
        return default_window

    sample_markdown = _sample_markdown(sample_content_file)
    sample_texts = _sample_texts(sample_markdown)
    sample_signals = detect_cover_signals(sample_texts)
    if not sample_signals:
        return default_window

    anchor_index = main_story_anchor_index(blocks)
    if anchor_index is None or anchor_index <= 0:
        return default_window

    prefix_blocks = blocks[:anchor_index]
    prefix_texts = [normalized_block_text(block) for block in prefix_blocks if normalized_block_text(block)]
    shared_cover_signals = sorted(detect_cover_signals(prefix_texts).intersection(sample_signals))
    matched_prefix_preview = [
        block_text(block)[:120]
        for block in prefix_blocks
        if _matches_sample_text(normalized_block_text(block), sample_texts)
    ]

    if len(shared_cover_signals) < 2 and len(matched_prefix_preview) < 2:
        return default_window

    anchor_block = blocks[anchor_index]
    return {
        "strategy": "skip-prefix-covered-by-template-scaffold",
        "start_block_index": anchor_index,
        "start_line": anchor_block.get("line"),
        "trimmed_prefix_block_count": anchor_index,
        "shared_cover_signals": shared_cover_signals,
        "matched_prefix_preview": matched_prefix_preview[:8],
        "anchor_text": block_text(anchor_block),
    }


def filter_blocks(blocks: list[dict], window: dict | None) -> list[dict]:
    if not window:
        return blocks
    start_index = int(window.get("start_block_index") or 0)
    return blocks[start_index:]


def filter_outline(outline: list[dict], window: dict | None) -> list[dict]:
    if not window:
        return outline
    start_line = window.get("start_line")
    if start_line in (None, ""):
        return outline
    return [item for item in outline if int(item.get("line") or 0) >= int(start_line)]