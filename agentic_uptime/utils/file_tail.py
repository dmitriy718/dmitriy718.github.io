from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class TailState:
    offset: int = 0


def read_new_lines(path: Path, state: TailState, max_bytes: int = 200_000) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(state.offset)
        data = handle.read(max_bytes)
        state.offset = handle.tell()
    return [line for line in data.splitlines() if line]
