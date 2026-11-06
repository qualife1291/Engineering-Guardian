from __future__ import annotations
import hashlib
import os
from pathlib import Path
from .languages import detect_language
from .models import FileRecord

MAX_FILE_BYTES = 5_000_000

DEFAULT_EXCLUDES = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", "target",
    ".dart_tool", ".gradle", "Pods", "vendor", "__pycache__", ".cache",
    "coverage", ".idea", ".pytest_cache", ".guardian", ".engineering-guardian"
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
SECRET_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", "credentials.json"}


def fingerprint(data: bytes) -> str:
    # stdlib-only prototype; replace with BLAKE3 in the Rust production core.
    return hashlib.blake2b(data, digest_size=20).hexdigest()


def scan_files(root: str | Path, extra_excludes: set[str] | None = None, max_file_bytes: int = MAX_FILE_BYTES):
    root = Path(root).expanduser().resolve(strict=True)
    excludes = DEFAULT_EXCLUDES | (extra_excludes or set())
    records: list[FileRecord] = []
    skipped: list[dict] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in excludes and not (Path(current) / d).is_symlink())
        for name in sorted(files):
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                skipped.append({"path": rel, "reason": "symlink"}); continue
            # Secrets must never be parsed, even if a secret filename ends in .py/.js.
            lower = name.lower()
            secret_name = (lower in SECRET_NAMES or lower.startswith('.env.')
                           or lower.endswith(('.pem', '.p12', '.pfx', '.key'))
                           or lower in {'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa'})
            if secret_name or path.suffix.lower() in SECRET_SUFFIXES:
                skipped.append({"path": rel, "reason": "sensitive_file"}); continue
            lang = detect_language(path)
            if lang == "unknown":
                skipped.append({"path": rel, "reason": "unsupported_extension"}); continue
            try:
                size = path.stat().st_size
                if size > max_file_bytes:
                    skipped.append({"path": rel, "reason": "max_file_size"}); continue
                with path.open("rb") as source_file:
                    data = source_file.read(max_file_bytes + 1)
                if len(data) > max_file_bytes:
                    skipped.append({"path": rel, "reason": "max_file_size"})
                    continue
                text = data.decode("utf-8", errors="replace")
                lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
                records.append(FileRecord(rel, lang, size, lines, fingerprint(data)))
            except (OSError, PermissionError) as exc:
                skipped.append({"path": rel, "reason": f"read_error:{type(exc).__name__}"})
    return records, skipped
