import bcrypt


class PasswordValidationError(ValueError):
    pass


class PasswordService:
    def __init__(self, rounds: int = 12) -> None:
        self.rounds = rounds

    def hash(self, password: str) -> str:
        encoded = self._validate(password)
        return bcrypt.hashpw(
            encoded,
            bcrypt.gensalt(rounds=self.rounds),
        ).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            encoded = self._validate(password)
            return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
        except (PasswordValidationError, ValueError):
            return False

    @staticmethod
    def _validate(password: str) -> bytes:
        if not password:
            raise PasswordValidationError("Le mot de passe est obligatoire.")

        encoded = password.encode("utf-8")
        if len(encoded) > 72:
            raise PasswordValidationError(
                "Le mot de passe ne doit pas dépasser 72 octets UTF-8."
            )
        return encoded

