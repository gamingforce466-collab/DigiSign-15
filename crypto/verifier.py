from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature


def verify_digest(public_key, digest, signature):
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            utils.Prehashed(hashes.SHA256())
        )
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def verify_multiple(entries):
    results = []
    for public_key, digest, signature in entries:
        results.append(verify_digest(public_key, digest, signature))
    return results
