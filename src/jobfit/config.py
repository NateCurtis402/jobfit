"""Settings. Everything has a working default so `make up` needs no .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader — avoids a dependency for seven lines of parsing."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_url: str
    embed_model: str
    embed_dim: int
    agent_model: str
    snapshot_dir: Path

    @classmethod
    def load(cls) -> Settings:
        _load_dotenv(REPO_ROOT / ".env")
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://jobfit:jobfit_dev_only@127.0.0.1:5432/jobfit"
            ),
            ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
            embed_dim=int(os.environ.get("EMBED_DIM", "768")),
            agent_model=os.environ.get("AGENT_MODEL", "llama3.1:8b"),
            snapshot_dir=Path(os.environ.get("SNAPSHOT_DIR", REPO_ROOT / "data" / "snapshot")),
        )
