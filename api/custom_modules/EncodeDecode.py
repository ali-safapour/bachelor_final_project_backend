from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import base64
from urllib.parse import quote


def encrypt(message, key):
    key = key.ljust(32)[:32].encode()

    cipher = Cipher(algorithms.AES(key), modes.ECB(),
                    backend=default_backend())
    encryptor = cipher.encryptor()

    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(message.encode()) + padder.finalize()

    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    return quote(base64.b64encode(encrypted).decode())


def decrypt(encrypted_message, key):
    key = key.ljust(32)[:32].encode()

    cipher = Cipher(algorithms.AES(key), modes.ECB(),
                    backend=default_backend())
    decryptor = cipher.decryptor()

    encrypted_message_bytes = base64.b64decode(encrypted_message)
    decrypted_padded = decryptor.update(
        encrypted_message_bytes) + decryptor.finalize()

    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

    return decrypted.decode()
