import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# Directories that must be ignored during scanning
IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    "out",
    "target",
    ".idea",
    ".vscode",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "eggs",
    ".eggs",
    "vendor",
    "bin",
    "obj",
    ".turbo",
    ".cache",
}

# Binary and media file extensions that should be ignored
IGNORED_EXTENSIONS: Set[str] = {
    # Binaries, libraries, and executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".msi", ".dmg", ".app",
    # Python bytecode
    ".pyc", ".pyo", ".pyd",
    # Java bytecode
    ".class", ".jar", ".war", ".ear",
    # Archives & compressed files
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".tgz",
    # Databases
    ".db", ".sqlite", ".sqlite3",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg", ".bmp", ".tiff", ".avif",
    # Audio & Video
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".mov", ".avi", ".mkv", ".webm",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Documents & Office
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # System artifacts
    ".ds_store",
    # Lock files (can be noisy, or if desired ignored; we ignore binary locks)
}

# Specific filenames that should be ignored
IGNORED_FILENAMES: Set[str] = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
}

# Sensitive / secret file prefixes or patterns that must never be scanned
SECRET_PREFIXES: Tuple[str, ...] = (
    ".env",
)
SECRET_EXTENSIONS: Set[str] = {
    ".pem",
    ".key",
    ".crt",
    ".cert",
    ".p12",
    ".pfx",
    ".pkcs12",
}
SECRET_EXACT_NAMES: Set[str] = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

# Maximum file size to scan (5 MB)
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024

# Mapping from file extensions to canonical programming/markup language names
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Python
    ".py": "Python",
    ".pyw": "Python",
    ".pyi": "Python",
    # JavaScript & TypeScript
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".tsx": "TypeScript (React)",
    # Web & Styles
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    # Data & Config
    ".json": "JSON",
    ".jsonc": "JSON",
    ".json5": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".cfg": "Config",
    # Documentation
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    # Systems languages
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C/C++ Header",
    ".hxx": "C/C++ Header",
    ".rs": "Rust",
    ".go": "Go",
    # JVM & .NET
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".cs": "C#",
    ".fs": "F#",
    # Other popular languages
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".dockerfile": "Dockerfile",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffers",
}

# Special exact filenames to language
EXACT_FILENAME_LANGUAGE_MAP: Dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "cmakelists.txt": "CMake",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "vagrantfile": "Ruby",
    "procfile": "Procfile",
}


@dataclass
class ScannedFile:
    """Metadata extracted for a scanned repository file."""

    path: str
    language: Optional[str]
    size_bytes: int
    content_hash: str


@dataclass
class ScanResult:
    """Summary and file list from repository scanning."""

    files: List[ScannedFile]
    total_scanned: int
    total_ignored: int
    primary_language: Optional[str]
    language_breakdown: Dict[str, int]


def is_binary_content(sample: bytes) -> bool:
    """Detects if a byte sample appears to be binary by checking for null bytes."""
    return b"\x00" in sample


def detect_language(path_str: str) -> Optional[str]:
    """Infers programming or markup language from file name or extension."""
    filename = os.path.basename(path_str).lower()

    if filename in EXACT_FILENAME_LANGUAGE_MAP:
        return EXACT_FILENAME_LANGUAGE_MAP[filename]

    _, ext = os.path.splitext(filename)
    if ext in EXTENSION_LANGUAGE_MAP:
        return EXTENSION_LANGUAGE_MAP[ext]

    return None


def is_ignored_path(rel_parts: Tuple[str, ...]) -> bool:
    """Checks whether any segment in the path is in the ignored directories set."""
    for part in rel_parts:
        lower_part = part.lower()
        if lower_part in IGNORED_DIRECTORIES:
            return True
        # Ignore hidden directories like .cache, .github/actions, etc. if in ignored set
        if lower_part.startswith(".") and lower_part in IGNORED_DIRECTORIES:
            return True
    return False


def is_ignored_file(filename: str) -> bool:
    """Checks whether a file should be ignored based on name, extension, or secret patterns."""
    lower_name = filename.lower()

    # Exact ignored file names
    if lower_name in IGNORED_FILENAMES:
        return True

    # Secret / credential files (.env, .env.local, .env.prod, id_rsa, etc.)
    if any(lower_name.startswith(prefix) for prefix in SECRET_PREFIXES):
        return True
    if lower_name in SECRET_EXACT_NAMES:
        return True

    # Extension check
    _, ext = os.path.splitext(lower_name)
    if ext in IGNORED_EXTENSIONS or ext in SECRET_EXTENSIONS:
        return True

    return False


def scan_repository(root_dir: str) -> ScanResult:
    """Recursively scans a repository root directory, filters out ignored

    and binary files, and returns metadata for each relevant source file.
    """
    root_path = Path(root_dir).resolve()
    scanned_files: List[ScannedFile] = []
    ignored_count = 0
    language_counts: Dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Exclude ignored directories in-place so os.walk does not traverse them
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in IGNORED_DIRECTORIES and not d.lower().startswith(".venv")
        ]

        # Calculate relative path from root
        rel_dir = os.path.relpath(dirpath, root_path)
        rel_parts = () if rel_dir == "." else tuple(Path(rel_dir).parts)

        if is_ignored_path(rel_parts):
            ignored_count += len(filenames)
            continue

        for filename in filenames:
            if is_ignored_file(filename):
                ignored_count += 1
                continue

            full_file_path = os.path.join(dirpath, filename)

            try:
                stat = os.stat(full_file_path)
                file_size = stat.st_size

                # Skip files exceeding maximum size
                if file_size > MAX_FILE_SIZE_BYTES:
                    ignored_count += 1
                    continue

                # Read first 8KB to check for binary content
                with open(full_file_path, "rb") as f:
                    chunk = f.read(8192)
                    if is_binary_content(chunk):
                        ignored_count += 1
                        continue

                    # Compute full SHA-256 content hash
                    hasher = hashlib.sha256(chunk)
                    while True:
                        more = f.read(65536)
                        if not more:
                            break
                        hasher.update(more)
                    content_hash = hasher.hexdigest()

                # Normalized relative path with forward slashes (cross-platform)
                rel_path = (
                    f"{rel_dir}/{filename}".replace("\\", "/")
                    if rel_dir != "."
                    else filename
                )

                language = detect_language(rel_path)
                if language:
                    language_counts[language] = language_counts.get(language, 0) + 1

                scanned_files.append(
                    ScannedFile(
                        path=rel_path,
                        language=language,
                        size_bytes=file_size,
                        content_hash=content_hash,
                    )
                )

            except (OSError, PermissionError):
                # Unreadable file or broken symlink
                ignored_count += 1
                continue

    # Determine primary language (most frequent recognized language)
    primary_language: Optional[str] = None
    if language_counts:
        primary_language = max(language_counts.items(), key=lambda item: item[1])[0]

    # Sort files alphabetically by path
    scanned_files.sort(key=lambda item: item.path)

    return ScanResult(
        files=scanned_files,
        total_scanned=len(scanned_files),
        total_ignored=ignored_count,
        primary_language=primary_language,
        language_breakdown=language_counts,
    )
