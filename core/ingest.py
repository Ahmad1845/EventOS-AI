"""Ingest module: split message file into numbered raw message blocks without guessing meaning."""

import hashlib
import os
import re
from typing import Dict, List, Any


def _normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _make_block(idx: int, raw_text: str) -> Dict[str, Any]:
    cleaned = raw_text.strip()
    norm = _normalize_for_hash(cleaned)
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()
    return {
        "id": idx,
        "text": cleaned,
        "hash": digest,
    }


def _try_indexed_split(content: str) -> List[str]:
    lines = content.splitlines()
    # Match lines starting with 1., 1), #1, Message 1:, or markdown table row | 1 |
    index_pattern = re.compile(
        r"^\s*(?:"
        r"(?:message\s+\d+\s*[:\-])"
        r"|(?:#\s*\d+\b)"
        r"|(?:\d+\s*[\.\)\-:])"
        r"|(?:\|\s*\d+\s*\|)"
        r")",
        re.IGNORECASE,
    )
    blocks: List[str] = []
    current: List[str] = []
    started = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if started and current:
                current.append(line)
            continue
        # Skip markdown table header or separator rows like | # | From | or |---|---|
        if re.match(r"^\|\s*(?:#|id|no\.?|---+)\s*\|", stripped, re.IGNORECASE):
            continue
        if re.match(r"^#\s+from\s+date\s+message", stripped, re.IGNORECASE):
            continue

        if index_pattern.match(line):
            if current:
                blocks.append("\n".join(current).strip())
            current = [line]
            started = True
        else:
            if started:
                current.append(line)

    if current:
        blocks.append("\n".join(current).strip())

    return [b for b in blocks if b]


def _try_blank_line_split(content: str) -> List[str]:
    parts = re.split(r"\n\s*\n+", content.strip())
    return [p.strip() for p in parts if p.strip()]


def _try_non_empty_lines(content: str) -> List[str]:
    return [line.strip() for line in content.splitlines() if line.strip()]


def ingest_file(filepath: str) -> List[Dict[str, Any]]:
    """Read filepath and split into numbered message blocks per Section 11."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if not content or not content.strip():
        return []

    # Algorithm in order, first that yields 2 or more blocks wins:
    # 1. Lines that start with an index (1., 1), #1, Message 1:, or | 1 |)
    indexed_blocks = _try_indexed_split(content)
    if len(indexed_blocks) >= 2:
        return [_make_block(i + 1, b) for i, b in enumerate(indexed_blocks)]

    # 2. Blocks separated by one or more blank lines
    blank_blocks = _try_blank_line_split(content)
    if len(blank_blocks) >= 2:
        return [_make_block(i + 1, b) for i, b in enumerate(blank_blocks)]

    # 3. Each non-empty line is a message
    line_blocks = _try_non_empty_lines(content)
    if len(line_blocks) >= 2:
        return [_make_block(i + 1, b) for i, b in enumerate(line_blocks)]

    # Single message file yields one block
    return [_make_block(1, content.strip())]
