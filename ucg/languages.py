from pathlib import Path

EXTENSIONS = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
    ".dart": "dart", ".kt": "kotlin", ".kts": "kotlin", ".java": "java",
    ".sql": "sql", ".proto": "protobuf", ".go": "go", ".rs": "rust",
}

def detect_language(path: str | Path) -> str:
    return EXTENSIONS.get(Path(path).suffix.lower(), "unknown")
