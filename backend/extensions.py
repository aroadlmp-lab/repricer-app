import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from cryptography.fernet import Fernet

db = SQLAlchemy()
migrate = Migrate()

_fernet_key = os.environ.get('FERNET_KEY', Fernet.generate_key().decode())
fernet = Fernet(_fernet_key.encode() if isinstance(_fernet_key, str) else _fernet_key)


def encrypt_value(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
