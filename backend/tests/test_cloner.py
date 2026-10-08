import os
import stat
import subprocess
import tempfile
import pytest
from app.services.cloner import CloneError, cleanup_directory, clone_repository


def test_cleanup_directory_with_readonly_file():
    """Verifies that cleanup_directory safely removes directories containing read-only files."""
    with tempfile.TemporaryDirectory() as base_temp:
        target_dir = os.path.join(base_temp, "nested_dir")
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, "readonly.txt")

        with open(file_path, "w") as f:
            f.write("content")

        # Set read-only attribute (simulating Windows git pack behavior)
        os.chmod(file_path, stat.S_IREAD)

        cleanup_directory(target_dir)
        assert not os.path.exists(target_dir)


def test_clone_repository_subprocess_error(monkeypatch):
    """Verifies that non-zero git exit raises a CloneError with clean message."""
    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=128,
            stdout="",
            stderr="fatal: repository 'https://github.com/fake/not-found' not found",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)

    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(CloneError) as exc_info:
            clone_repository("https://github.com/fake/not-found", temp_dir)
        assert "not found" in str(exc_info.value).lower()


def test_clone_repository_timeout(monkeypatch):
    """Verifies that subprocess timeout raises CloneError."""
    def mock_run_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=5)

    monkeypatch.setattr(subprocess, "run", mock_run_timeout)

    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(CloneError) as exc_info:
            clone_repository("https://github.com/fake/repo", temp_dir, timeout_seconds=5)
        assert "timed out" in str(exc_info.value).lower()


def test_clone_repository_git_missing(monkeypatch):
    """Verifies error when git executable is not found."""
    import shutil
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(CloneError) as exc_info:
            clone_repository("https://github.com/fake/repo", temp_dir)
        assert "git executable not found" in str(exc_info.value).lower()
