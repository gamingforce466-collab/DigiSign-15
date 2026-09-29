"""Facade kompatibilitas untuk dispatcher dan handler format dokumen."""
from formats import (
    MIME_TYPES,
    add_signature_marks,
    compute_file_digest,
    extension_for,
    extract_qr_metadata,
    is_valid_document,
)

__all__ = [
    "MIME_TYPES",
    "add_signature_marks",
    "compute_file_digest",
    "extension_for",
    "extract_qr_metadata",
    "is_valid_document",
]