import re
from typing import Dict
from urllib.parse import urlparse


GITHUB_HOSTS = {"github.com", "www.github.com"}

GITHUB_OWNER_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9_]|-(?=[a-zA-Z0-9_])){0,38}$")

# Repository name validation:
# Alphanumeric, hyphen, underscore, period; max 100 characters; cannot be '.' or '..'
GITHUB_REPO_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{1,100}$")


def parse_github_url(url: str) -> Dict[str, str]:
    """Validates and parses a GitHub repository URL.

    Accepts HTTPS, HTTP, and SSH formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - http://github.com/owner/repo
    - git@github.com:owner/repo.git

    Returns a dictionary containing:
    - 'owner': GitHub repository owner/organization
    - 'name': Repository name
    - 'normalized_url': Canonical HTTPS URL (https://github.com/owner/repo)

    Raises:
        ValueError: If the URL is invalid, not hosted on GitHub, or malformed.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be a non-empty string.")

    cleaned_url = url.strip()
    owner: str = ""
    repo: str = ""

    # Check for SSH format: git@github.com:owner/repo.git
    ssh_match = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$", cleaned_url)
    if ssh_match:
        owner = ssh_match.group(1)
        repo = ssh_match.group(2)
    else:
        # Check HTTP / HTTPS format
        try:
            parsed = urlparse(cleaned_url)
        except Exception as exc:
            raise ValueError(f"Malformed URL: {exc}") from exc

        if not parsed.scheme or parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Repository URL must use HTTP, HTTPS, or SSH (git@github.com:...).")

        if not parsed.netloc or parsed.netloc.lower() not in GITHUB_HOSTS:
            raise ValueError(f"Only repositories on GitHub are supported. Host '{parsed.netloc}' is not GitHub.")

        path = parsed.path.strip("/")
        # Path must be exactly owner/repo (optional trailing .git)
        path_parts = [part for part in path.split("/") if part]
        if len(path_parts) != 2:
            raise ValueError(
                "Invalid GitHub repository path. Expected 'https://github.com/<owner>/<repo>'."
            )

        owner = path_parts[0]
        repo = path_parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

    # Clean and validate owner
    owner = owner.strip()
    if not owner or not GITHUB_OWNER_REGEX.match(owner):
        raise ValueError(
            f"Invalid GitHub owner/organization name: '{owner}'. "
            "Must be 1-39 alphanumeric characters or hyphens (not starting or ending with hyphen)."
        )

    # Clean and validate repository name
    repo = repo.strip()
    if not repo or repo in {".", ".."} or not GITHUB_REPO_REGEX.match(repo):
        raise ValueError(
            f"Invalid GitHub repository name: '{repo}'. "
            "Must be 1-100 characters containing letters, numbers, hyphens, underscores, or periods."
        )

    canonical_url = f"https://github.com/{owner}/{repo}"

    return {
        "owner": owner,
        "name": repo,
        "normalized_url": canonical_url,
    }


def is_valid_github_url(url: str) -> bool:
    """Checks whether a given URL is a valid GitHub repository URL."""
    try:
        parse_github_url(url)
        return True
    except (ValueError, TypeError):
        return False
