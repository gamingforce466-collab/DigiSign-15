"""Dispatcher handler format dokumen DigiSign."""
import hashlib
from pathlib import Path

from .docx import handler as docx_handler
from .image import handler as image_handler
from .txt import handler as txt_handler
from .xlsx import handler as xlsx_handler
from pdf import handler as pdf_handler

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".txt": "text/plain",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def extension_for(filename, default=None):
    extension = Path(filename or "").suffix.lower() or default
    return extension if extension in MIME_TYPES else None


def is_valid_document(data, filename):
    extension = extension_for(filename)
    if not data or extension is None:
        return False
    if extension == ".pdf":
        return pdf_handler.is_valid_pdf_bytes(data)
    if extension == ".docx":
        return docx_handler.is_valid(data)
    if extension in (".jpg", ".jpeg", ".png"):
        return image_handler.is_valid(data, extension)
    if extension == ".txt":
        return txt_handler.is_valid(data)
    if extension == ".xlsx":
        return xlsx_handler.is_valid(data)
    return False


def compute_file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            digest.update(chunk)
    return digest.digest()


def add_signature_marks(source_path, output_path, extension, qr_images, signers):
    if extension == ".pdf":
        return pdf_handler.embed_qr_images(str(source_path), qr_images, str(output_path), signers=signers)
    if extension == ".docx":
        return docx_handler.add_signatures(source_path, output_path, qr_images, signers)
    if extension in (".jpg", ".jpeg", ".png"):
        return image_handler.add_signatures(source_path, output_path, extension, qr_images, signers)
    if extension == ".txt":
        return txt_handler.add_signatures(source_path, output_path, qr_images)
    if extension == ".xlsx":
        return xlsx_handler.add_signatures(source_path, output_path, qr_images, signers)
    raise ValueError("Format dokumen tidak didukung")


def extract_qr_metadata(path, extension):
    if extension == ".pdf":
        images = pdf_handler.extract_embedded_images(str(path))
        from qr import generator as qr_generator

        return qr_generator.decode_qr_from_images(images)
    if extension == ".docx":
        return docx_handler.extract_metadata(path)
    if extension in (".jpg", ".jpeg", ".png"):
        return image_handler.extract_metadata(path)
    if extension == ".txt":
        return txt_handler.extract_metadata(path)
    if extension == ".xlsx":
        return xlsx_handler.extract_metadata(path)
    return []