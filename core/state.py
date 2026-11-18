"""State management and session detection per Section 12."""

import datetime
import json
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple


STATE_DIR = ".eventos"
STATE_PATH = os.path.join(STATE_DIR, "state.json")
ARCHIVE_DIR = os.path.join(STATE_DIR, "archive")


def default_state() -> Dict[str, Any]:
    return {
        "version": 3,
        "messages": [],
        "facts": [],
        "constraints": [],
        "plan": None,
        "rejections": [],
        "runs": 0,
        "session_tokens": 0,
        "trace_history": [],
    }


def load_state(path: str = STATE_PATH) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def save_state(state: Dict[str, Any], path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def archive_state(path: str = STATE_PATH) -> Optional[str]:
    if not os.path.exists(path):
        return None
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(ARCHIVE_DIR, f"{ts}.json")
    shutil.copy2(path, dest)
    return dest


def detect_session(
    state: Optional[Dict[str, Any]], blocks: List[Dict[str, Any]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Returns (mode, new_blocks) per Section 12:
    - No state file (or no prior messages): 'fresh', all blocks.
    - State exists and >= 1 input block hash is in state:
        unseen blocks only -> 'update' (or 'nothing_new' if empty).
    - State exists, no hash overlap, and len(blocks) <= 2:
        'update' (a single new message file).
    - State exists, no hash overlap, and len(blocks) >= 3:
        'new_pack' (archive old state and run fresh).
    """
    if not state or not state.get("messages"):
        return "fresh", blocks

    known_hashes = {m.get("hash") for m in state.get("messages", []) if m.get("hash")}
    overlap = [b for b in blocks if b.get("hash") in known_hashes]

    if overlap:
        unseen = [b for b in blocks if b.get("hash") not in known_hashes]
        if not unseen:
            return "nothing_new", []
        return "update", unseen

    if len(blocks) <= 2:
        return "update", blocks

    return "new_pack", blocks


def get_known_keys(state: Optional[Dict[str, Any]]) -> List[str]:
    if not state:
        return []
    keys = sorted(
        {
            f.get("key", "")
            for f in state.get("facts", [])
            if f.get("key") and f.get("superseded_by") is None
        }
    )
    return [k for k in keys if k]
