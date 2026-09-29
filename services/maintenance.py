"""Operasi administratif pada penyimpanan lokal aplikasi."""
from pathlib import Path


def clear_storage(documents_dir, signatures_dir, keys_dir):
    counts = {"documents": 0, "signatures": 0, "keys": 0}
    for name, folder in (("documents", documents_dir), ("signatures", signatures_dir), ("keys", keys_dir)):
        for path in Path(folder).glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink(missing_ok=True)
                counts[name] += 1
    return counts