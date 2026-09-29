from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

KEYS_DIR = Path(__file__).resolve().parent.parent / "storage" / "keys"
KEYS_DIR.mkdir(parents=True, exist_ok=True)


def generate_keypair(owner_id, passphrase):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    encrypted_private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    private_path = KEYS_DIR / f"{owner_id}_private.pem"
    public_path = KEYS_DIR / f"{owner_id}_public.pem"
    with open(private_path, "wb") as f:
        f.write(encrypted_private_bytes)
    with open(public_path, "wb") as f:
        f.write(public_bytes)
    return str(private_path), str(public_path)


def load_private_key(owner_id, passphrase):
    private_path = KEYS_DIR / f"{owner_id}_private.pem"
    with open(private_path, "rb") as f:
        data = f.read()
    return serialization.load_pem_private_key(data, password=passphrase.encode("utf-8"))


def load_public_key(owner_id):
    public_path = KEYS_DIR / f"{owner_id}_public.pem"
    with open(public_path, "rb") as f:
        data = f.read()
    return serialization.load_pem_public_key(data)


def load_public_key_from_pem(pem_bytes):
    return serialization.load_pem_public_key(pem_bytes)


def public_key_to_pem(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


def key_exists(owner_id):
    private_path = KEYS_DIR / f"{owner_id}_private.pem"
    public_path = KEYS_DIR / f"{owner_id}_public.pem"
    return private_path.exists() and public_path.exists()


def list_keys():
    owners = set()
    for path in KEYS_DIR.glob("*_public.pem"):
        owners.add(path.name.replace("_public.pem", ""))
    return sorted(owners)


def delete_keypair(owner_id):
    """Hapus pasangan kunci milik owner_id (dipakai untuk membersihkan kunci uji otomatis)."""
    for suffix in ("_private.pem", "_public.pem"):
        (KEYS_DIR / f"{owner_id}{suffix}").unlink(missing_ok=True)


def generate_ephemeral_public_key():
    """Kunci publik RSA-2048 sementara (tidak disimpan) untuk skenario uji 'kunci salah'."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
