from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives import hashes


def sign_digest(private_key, digest):
    signature = private_key.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        utils.Prehashed(hashes.SHA256())
    )
    return signature


def sign_multiple(private_keys_with_digest):
    signatures = []
    for private_key, digest in private_keys_with_digest:
        signatures.append(sign_digest(private_key, digest))
    return signatures
