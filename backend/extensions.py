import os
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from cryptography.fernet import Fernet

db = SQLAlchemy()
migrate = Migrate()

_logger = logging.getLogger(__name__)
_fernet_key = os.environ.get('FERNET_KEY')
if not _fernet_key:
    _fernet_key = Fernet.generate_key().decode()
    _logger.warning('FERNET_KEY no configurada — usando clave efímera. Todos los marketplaces pasarán a mock mode si el proceso se reinicia.')
fernet = Fernet(_fernet_key.encode() if isinstance(_fernet_key, str) else _fernet_key)


def encrypt_value(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
