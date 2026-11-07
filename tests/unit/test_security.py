"""Password hashing and redirect safety (no database needed)."""

import pytest

from app.core.security import hash_password, verify_password
from app.modules.auth.pages import safe_next_path


def test_hash_is_salted_and_verifiable():
    first, second = hash_password("s3cret-pass"), hash_password("s3cret-pass")
    assert first != second  # random salt per hash
    assert verify_password("s3cret-pass", first)
    assert not verify_password("wrong", first)


def test_verify_against_missing_hash_is_false():
    assert verify_password("anything", None) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/orders", "/orders"),
        ("/orders/5?tab=items", "/orders/5?tab=items"),
        (None, "/"),
        ("", "/"),
        ("https://evil.example.com", "/"),
        ("//evil.example.com", "/"),
        ("orders", "/"),
    ],
)
def test_safe_next_path_only_allows_local_paths(raw, expected):
    assert safe_next_path(raw) == expected
