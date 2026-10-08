import hashlib
import os
import tempfile
import pytest
from app.services.scanner import (
    detect_language,
    is_binary_content,
    is_ignored_file,
    scan_repository,
)


@pytest.fixture
def sample_repo_tree():
    """Creates a temporary directory with a mix of valid source files,

    ignored directories, secrets, binaries, and generated files.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Ignored directories & files inside them
        ignored_dirs = [
            ".git",
            "node_modules/lodash",
            "__pycache__",
            ".pytest_cache",
            ".venv/lib",
            "dist",
            "build",
            "coverage",
        ]
        for d in ignored_dirs:
            full_dir = os.path.join(temp_dir, d)
            os.makedirs(full_dir, exist_ok=True)
            with open(os.path.join(full_dir, "ignored_nested.py"), "w") as f:
                f.write("# should be ignored\n")

        # 2. Ignored files at root or in source folders
        ignored_files = [
            ".env",
            ".env.local",
            ".env.production",
            "id_rsa",
            "server.key",
            ".DS_Store",
            "Thumbs.db",
            "bundle.zip",
            "app.exe",
            "picture.png",
            "logo.svg",
            "font.woff2",
            "document.pdf",
        ]
        for f_name in ignored_files:
            file_path = os.path.join(temp_dir, f_name)
            with open(file_path, "wb") as f:
                f.write(b"dummy binary or secret content")

        # 3. Binary file masquerading as .txt (has null byte)
        binary_txt_path = os.path.join(temp_dir, "fake_text.txt")
        with open(binary_txt_path, "wb") as f:
            f.write(b"Hello\x00World\x00Binary")

        # 4. Valid source files
        valid_files = {
            "main.py": "def main():\n    print('hello world')\n",
            "src/utils.py": "def add(a, b):\n    return a + b\n",
            "src/components/Button.tsx": "export const Button = () => <button>Click</button>;\n",
            "src/styles/app.css": "body { margin: 0; background: #000; }\n",
            "Dockerfile": "FROM python:3.12-alpine\nWORKDIR /app\n",
            "README.md": "# Sample Project\nDocumentation.\n",
            "package.json": '{\n  "name": "sample"\n}\n',
        }
        for rel_path, content in valid_files.items():
            full_path = os.path.join(temp_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)

        yield temp_dir, valid_files


def test_scan_repository(sample_repo_tree):
    """Verifies that scanning correctly discovers valid source files, computes metadata,

    and excludes ignored folders, secrets, and binaries.
    """
    temp_dir, expected_valid_files = sample_repo_tree

    scan_result = scan_repository(temp_dir)

    # 1. Verify discovered file paths
    discovered_paths = {f.path for f in scan_result.files}
    expected_paths = set(expected_valid_files.keys())
    assert discovered_paths == expected_paths

    # 2. Check total counts
    assert scan_result.total_scanned == len(expected_valid_files)
    assert scan_result.total_ignored > 0

    # 3. Verify cross-platform forward-slash paths
    for f in scan_result.files:
        assert "\\" not in f.path
        assert not f.path.startswith("/")

    # 4. Verify languages detected
    file_map = {f.path: f for f in scan_result.files}
    assert file_map["main.py"].language == "Python"
    assert file_map["src/utils.py"].language == "Python"
    assert file_map["src/components/Button.tsx"].language == "TypeScript (React)"
    assert file_map["src/styles/app.css"].language == "CSS"
    assert file_map["Dockerfile"].language == "Dockerfile"
    assert file_map["README.md"].language == "Markdown"
    assert file_map["package.json"].language == "JSON"

    # 5. Verify primary language is Python (2 python files vs 1 of each other)
    assert scan_result.primary_language == "Python"

    # 6. Verify SHA-256 hash and size
    main_py = file_map["main.py"]
    expected_content = expected_valid_files["main.py"].encode("utf-8")
    expected_hash = hashlib.sha256(expected_content).hexdigest()
    assert main_py.content_hash == expected_hash
    assert main_py.size_bytes == len(expected_content)


def test_language_detection():
    """Verifies language inference by file extension and exact name."""
    assert detect_language("app/main.py") == "Python"
    assert detect_language("src/index.ts") == "TypeScript"
    assert detect_language("src/App.tsx") == "TypeScript (React)"
    assert detect_language("src/index.js") == "JavaScript"
    assert detect_language("src/App.jsx") == "JavaScript (React)"
    assert detect_language("styles.css") == "CSS"
    assert detect_language("style.scss") == "SCSS"
    assert detect_language("Dockerfile") == "Dockerfile"
    assert detect_language("Makefile") == "Makefile"
    assert detect_language("CMakeLists.txt") == "CMake"
    assert detect_language("main.rs") == "Rust"
    assert detect_language("main.go") == "Go"
    assert detect_language("index.html") == "HTML"
    assert detect_language("query.sql") == "SQL"
    assert detect_language("data.json") == "JSON"
    assert detect_language("config.yaml") == "YAML"
    assert detect_language("unknown.xyz123") is None


def test_is_ignored_file():
    """Verifies ignored file logic."""
    assert is_ignored_file(".env") is True
    assert is_ignored_file(".env.local") is True
    assert is_ignored_file(".env.production") is True
    assert is_ignored_file("id_rsa") is True
    assert is_ignored_file("cert.key") is True
    assert is_ignored_file("cert.pem") is True
    assert is_ignored_file("bundle.zip") is True
    assert is_ignored_file("app.exe") is True
    assert is_ignored_file("lib.dll") is True
    assert is_ignored_file(".DS_Store") is True
    assert is_ignored_file("Thumbs.db") is True
    assert is_ignored_file("image.png") is True
    assert is_ignored_file("main.py") is False
    assert is_ignored_file("App.tsx") is False


def test_is_binary_content():
    """Verifies binary content detection with null bytes."""
    assert is_binary_content(b"normal text string") is False
    assert is_binary_content(b"text with \x00 null byte") is True
