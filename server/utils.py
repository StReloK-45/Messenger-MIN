# server/utils.py
import hashlib
import base64

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()[:32]

def decode_base64(encoded):
    return base64.b64decode(encoded.encode()).decode()