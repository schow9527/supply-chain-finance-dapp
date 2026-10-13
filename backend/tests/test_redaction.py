from backend.services.redaction import redact_secrets


def test_redacts_rpc_database_environment_and_authorization_secrets():
    api_key = "api-key-must-not-survive"
    password = "database-password-must-not-survive"
    token = "authorization-token-must-not-survive"
    message = (
        f"HTTP 400 https://rpc.example.invalid/v2/{api_key} "
        f"WEB3_PROVIDER_URI=https://other.invalid/v2/{api_key} "
        f"DATABASE_URL=postgresql+psycopg://user:{password}@db.invalid/app "
        f"Authorization: Bearer {token}"
    )

    redacted = redact_secrets(message)

    assert api_key not in redacted
    assert password not in redacted
    assert token not in redacted
    assert "https://" not in redacted
    assert "postgresql" not in redacted
    assert "WEB3_PROVIDER_URI=<redacted>" in redacted
    assert "DATABASE_URL=<redacted>" in redacted
    assert "Authorization: <redacted>" in redacted
