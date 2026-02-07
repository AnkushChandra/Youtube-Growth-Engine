from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from .config import settings

MEMORY_FILE: Path = settings.memory_file
MAX_LINES = settings.max_memory_lines


def read_recent_memory() -> List[str]:
    if not MEMORY_FILE.exists():
        return []
    lines = MEMORY_FILE.read_text(encoding='utf-8').splitlines()
    return lines[-MAX_LINES:]


def append_memory_entry(channel_ref: str, findings: list[str], action: str) -> str:
    timestamp = datetime.utcnow().isoformat()
    entry = f"{timestamp} | {channel_ref} | Findings: {', '.join(findings[:3])} | Next: {action}"
    with MEMORY_FILE.open('a', encoding='utf-8') as fh:
        fh.write(entry + '\n')
    return entry


def reset_memory(confirm: bool = False) -> None:
    if not confirm:
        raise ValueError('Confirmation flag required to reset memory.')
    MEMORY_FILE.write_text('', encoding='utf-8')
