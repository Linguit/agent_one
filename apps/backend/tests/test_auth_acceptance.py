from super_ai.auth import normalize_email, token_digest


def test_auth_security_primitives() -> None:
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert len(token_digest("opaque-token")) == 64
    assert token_digest("opaque-token") != "opaque-token"
