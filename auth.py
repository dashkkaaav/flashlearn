import hashlib
import uuid


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password, password_hash):
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash


def generate_session_token():
    return str(uuid.uuid4())