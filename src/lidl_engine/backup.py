"""Consistent database plus evidence backups under the collector lock."""

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

from .config import Settings
from .db import connect, lock_collection


def pg_environment(settings: Settings) -> dict[str, str]:
    params = conninfo_to_dict(settings.database_url)
    mapping = {
        "host": "PGHOST",
        "port": "PGPORT",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "dbname": "PGDATABASE",
    }
    return {
        **os.environ,
        **{mapping[k]: str(v) for k, v in params.items() if k in mapping and v is not None},
    }


def backup(settings: Settings, destination: Path) -> None:
    destination.mkdir(exist_ok=False, parents=True)
    with connect(settings) as conn:
        lock_collection(conn, wait=True)
        subprocess.run(
            ["pg_dump", "--format=custom", "--file", str(destination / "database.dump")],
            env=pg_environment(settings),
            check=True,
        )
        with tarfile.open(destination / "evidence.tar.gz", "w:gz") as archive:
            for row in conn.execute("SELECT DISTINCT image_path FROM revisions").fetchall():
                archive.add(
                    settings.evidence_dir / row["image_path"],
                    arcname="evidence/" + row["image_path"],
                )
        checksums = {
            name: file_hash(destination / name) for name in ["database.dump", "evidence.tar.gz"]
        }
        (destination / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")


def restore(settings: Settings, source: Path) -> None:
    checksums = json.loads((source / "checksums.json").read_text())
    for name in ["database.dump", "evidence.tar.gz"]:
        if file_hash(source / name) != checksums[name]:
            raise ValueError("Backup checksum mismatch")
    with connect(settings) as conn:
        lock_collection(conn, wait=True)
        # Stop web and collector processes before restoring. The advisory lock prevents refresh.
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--exit-on-error",
                "--dbname",
                str(conninfo_to_dict(settings.database_url)["dbname"]),
                str(source / "database.dump"),
            ],
            env=pg_environment(settings),
            check=True,
        )
        settings.evidence_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(source / "evidence.tar.gz") as archive:
            for member in archive.getmembers():
                if member.name == "evidence":
                    continue
                if not member.isfile() or not member.name.startswith("evidence/"):
                    raise ValueError("Unexpected evidence archive member")
                name = member.name.removeprefix("evidence/")
                if "/" in name or not name.endswith(".image"):
                    raise ValueError("Invalid evidence file")
                content = archive.extractfile(member)
                if content is None:
                    raise ValueError("Missing evidence content")
                raw = content.read()
                if hashlib.sha256(raw).hexdigest() + ".image" != name:
                    raise ValueError("Evidence content checksum mismatch")
                (settings.evidence_dir / name).write_bytes(raw)


def file_hash(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()
