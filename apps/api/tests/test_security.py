import bcrypt

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_verification() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_password_hash_supports_long_valid_passwords() -> None:
    password = "a" * 128
    password_hash = hash_password(password)
    assert verify_password(password, password_hash)
    assert not verify_password(password[:-1] + "b", password_hash)


def test_password_verification_supports_legacy_bcrypt_hashes() -> None:
    password = "legacy password"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_token_hash_is_deterministic_and_non_plaintext() -> None:
    token = "refresh-token"
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


def test_access_token_round_trip() -> None:
    settings = Settings(jwt_secret="test-secret", jwt_audience="tests", jwt_issuer="tests")
    token = create_access_token(subject="11111111-1111-1111-1111-111111111111", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["typ"] == "access"
