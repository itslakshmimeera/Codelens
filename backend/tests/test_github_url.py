import pytest
from app.services.github_url import is_valid_github_url, parse_github_url


def test_valid_github_urls():
    """Verifies that valid GitHub repository URLs parse correctly."""
    valid_cases = [
        ("https://github.com/tiangolo/fastapi", "tiangolo", "fastapi", "https://github.com/tiangolo/fastapi"),
        ("https://github.com/tiangolo/fastapi.git", "tiangolo", "fastapi", "https://github.com/tiangolo/fastapi"),
        ("https://github.com/tiangolo/fastapi/", "tiangolo", "fastapi", "https://github.com/tiangolo/fastapi"),
        ("http://github.com/facebook/react", "facebook", "react", "https://github.com/facebook/react"),
        ("git@github.com:torvalds/linux.git", "torvalds", "linux", "https://github.com/torvalds/linux"),
        ("git@github.com:psf/requests", "psf", "requests", "https://github.com/psf/requests"),
        ("https://www.github.com/user-name/repo-name", "user-name", "repo-name", "https://github.com/user-name/repo-name"),
        ("https://github.com/user_123/repo.js", "user_123", "repo.js", "https://github.com/user_123/repo.js"),
    ]

    for url, expected_owner, expected_name, expected_normalized in valid_cases:
        assert is_valid_github_url(url) is True
        result = parse_github_url(url)
        assert result["owner"] == expected_owner
        assert result["name"] == expected_name
        assert result["normalized_url"] == expected_normalized


def test_invalid_github_urls():
    """Verifies that invalid or unsupported URLs raise ValueError."""
    invalid_cases = [
        "",
        "   ",
        None,
        12345,
        "not-a-url",
        "https://gitlab.com/owner/repo",
        "https://bitbucket.org/owner/repo",
        "https://github.com/",
        "https://github.com/owner",
        "https://github.com/owner/",
        "https://github.com/owner/repo/pull/123",
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo/blob/main/README.md",
        "https://github.com/-invalid-owner/repo",
        "https://github.com/owner/..",
        "https://github.com/owner/.",
    ]

    for url in invalid_cases:
        assert is_valid_github_url(url) is False  # type: ignore
        with pytest.raises(ValueError):
            parse_github_url(url)  # type: ignore
