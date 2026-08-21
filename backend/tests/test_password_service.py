import pytest

from app.services.password_service import PasswordService, PasswordValidationError


def test_hashes_and_verifies_password() -> None:
    service = PasswordService(rounds=4)

    password_hash = service.hash("mot-de-passe-solide")

    assert password_hash != "mot-de-passe-solide"
    assert password_hash.startswith("$2")
    assert service.verify("mot-de-passe-solide", password_hash)
    assert not service.verify("mot-de-passe-invalide", password_hash)


def test_rejects_empty_password() -> None:
    with pytest.raises(PasswordValidationError, match="obligatoire"):
        PasswordService(rounds=4).hash("")


def test_rejects_password_over_bcrypt_limit() -> None:
    with pytest.raises(PasswordValidationError, match="72 octets"):
        PasswordService(rounds=4).hash("a" * 73)

