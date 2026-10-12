import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    evidence_dir: Path
    schema: str = "public"
    openrouter_key: str = ""
    description_model: str = ""
    extraction_model: str = ""
    poll_seconds: float = 30
    provider: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            evidence_dir=Path(os.environ.get("EVIDENCE_DIR", "/data/evidence")),
            openrouter_key=os.environ.get("OPENROUTER_API_KEY", ""),
            description_model=os.environ.get("DESCRIPTION_MODEL", ""),
            extraction_model=os.environ.get("EXTRACTION_MODEL", ""),
            poll_seconds=float(os.environ.get("POLL_SECONDS", "30")),
            provider=os.environ.get("BATCH_PROVIDER", ""),
        )
