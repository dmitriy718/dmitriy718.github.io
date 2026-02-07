from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class CodeContext:
    files: List[Path]
    snippets: Dict[str, str]


class CodeIntrospector:
    def __init__(self, max_file_size: int = 200_000) -> None:
        self.max_file_size = max_file_size
        self.allowed_ext = {".py", ".js", ".ts", ".go", ".java", ".rs", ".yaml", ".yml"}

    def search(self, repo_path: Path, keywords: List[str], limit: int = 5) -> CodeContext:
        matches: List[Path] = []
        snippets: Dict[str, str] = {}
        for root, _, files in os.walk(repo_path):
            for filename in files:
                path = Path(root) / filename
                if path.suffix not in self.allowed_ext:
                    continue
                if path.stat().st_size > self.max_file_size:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                lowered = text.lower()
                if any(keyword.lower() in lowered for keyword in keywords):
                    matches.append(path)
                    snippet = self._snippet(text, keywords)
                    snippets[str(path)] = snippet
                    if len(matches) >= limit:
                        return CodeContext(files=matches, snippets=snippets)
        return CodeContext(files=matches, snippets=snippets)

    def _snippet(self, text: str, keywords: List[str], window: int = 3) -> str:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if any(keyword.lower() in line.lower() for keyword in keywords):
                start = max(index - window, 0)
                end = min(index + window + 1, len(lines))
                return "\n".join(lines[start:end])
        return "\n".join(lines[:10])
