from __future__ import annotations
import hashlib
import os
import stat
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



def read_bounded_regular_file(path: str | Path, max_file_bytes: int = MAX_FILE_BYTES):
    """Open without following a final symlink, reject special files and cap bytes read.

    O_NONBLOCK prevents a FIFO/device path swapped in after inventory from hanging a scan.
    O_NOFOLLOW is used where the platform provides it.
    """
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(os.fspath(path), flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("not_regular_file")
        if info.st_size > max_file_bytes:
            return None, info.st_size
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(max_file_bytes + 1)
        if len(data) > max_file_bytes:
            return None, info.st_size
        return data, info.st_size
    finally:
        os.close(fd)


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
                data, size = read_bounded_regular_file(path, max_file_bytes)
                if data is None:
                    skipped.append({"path": rel, "reason": "max_file_size"})
                    continue
                text = data.decode("utf-8", errors="replace")
                lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
                records.append(FileRecord(rel, lang, size, lines, fingerprint(data)))
            except ValueError:
                skipped.append({"path": rel, "reason": "non_regular_file"})
            except OSError as exc:
                skipped.append({"path": rel, "reason": f"read_error:{type(exc).__name__}"})
    return records, skipped
