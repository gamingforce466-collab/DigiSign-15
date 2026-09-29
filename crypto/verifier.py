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
