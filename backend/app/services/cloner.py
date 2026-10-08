import logging
import os
import shutil
import stat
import subprocess
from typing import Optional


logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Exception raised when repository cloning fails."""
    pass


def remove_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows when encountering read-only files

    (such as files inside the .git directory).
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as exc:
        logger.warning("Failed to reset permissions on %s: %s", path, exc)


def cleanup_directory(directory_path: str) -> None:
    """Safely and recursively removes a directory, handling read-only permissions."""
    if not directory_path or not os.path.exists(directory_path):
        return

    try:
        shutil.rmtree(directory_path, onerror=remove_readonly)
        logger.debug("Cleaned up directory %s", directory_path)
    except Exception as exc:
        logger.warning("Error cleaning up directory %s: %s", directory_path, exc)


def clone_repository(
    repo_url: str,
    target_dir: str,
    timeout_seconds: int = 120,
    branch: Optional[str] = None,
) -> None:
    """Clones a remote GitHub repository into the target directory using a shallow clone.

    Args:
        repo_url: Validated GitHub repository URL
        target_dir: Destination directory path on local disk
        timeout_seconds: Maximum seconds to wait for git clone before aborting
        branch: Optional branch name to clone (defaults to repository default branch)

    Raises:
        CloneError: If cloning fails, times out, or git is unavailable.
    """
    git_bin = shutil.which("git")
    if not git_bin:
        raise CloneError("Git executable not found in system PATH.")

    os.makedirs(target_dir, exist_ok=True)

    cmd = [
        git_bin,
        "clone",
        "--depth",
        "1",
        "--single-branch",
    ]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, target_dir])

    # Git command environment - prevent interactive prompts for username/password
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup_directory(target_dir)
        raise CloneError(
            f"Repository cloning timed out after {timeout_seconds} seconds."
        ) from exc
    except OSError as exc:
        cleanup_directory(target_dir)
        raise CloneError(f"Failed to execute git process: {exc}") from exc

    if result.returncode != 0:
        cleanup_directory(target_dir)
        stderr_msg = result.stderr.strip()
        lower_err = stderr_msg.lower()

        if "repository not found" in lower_err:
            raise CloneError("GitHub repository not found or does not exist.")
        elif "authentication failed" in lower_err or "terminal prompts disabled" in lower_err:
            raise CloneError(
                "Cannot access repository. It may be private or require credentials."
            )
        elif "could not resolve host" in lower_err:
            raise CloneError("Network error: Could not resolve github.com.")
        elif "remote branch" in lower_err and "not found" in lower_err:
            raise CloneError(f"Specified branch '{branch}' was not found in repository.")
        else:
            # Clean generic error message without leaking sensitive system details
            first_line = stderr_msg.splitlines()[-1] if stderr_msg else "Unknown git clone error"
            raise CloneError(f"Git clone failed: {first_line}")
