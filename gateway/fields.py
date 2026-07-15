from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "FIELD_ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode('utf-8')
    return Fernet(key)


class EncryptedCharField(models.TextField):

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        cipher = _get_fernet()
        return cipher.encrypt(value.encode('utf-8')).decode('utf-8')

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        cipher = _get_fernet()
        try:
            return cipher.decrypt(value.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            return value
