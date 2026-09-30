"""Loads the real golfers shipped with the game (golfers.json)."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Golfer, skill_from_rank

DATA_FILE = Path(__file__).resolve().parent / "golfers.json"


def load_golfers(path: Path = DATA_FILE) -> list[Golfer]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: r["owgr"])
    return [
        Golfer(i, r["name"], r["country"], r["owgr"], r["tour"], r.get("skill", skill_from_rank(r["owgr"])))
        for i, r in enumerate(rows)
    ]
