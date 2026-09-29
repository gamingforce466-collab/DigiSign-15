"""Validasi, penyisipan tanda tangan, dan ekstraksi QR untuk DOCX."""
from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt

from formats.common import extract_media_images, image_bytes, valid_ooxml_package
from qr import generator as qr_generator


def is_valid(data):
    if not valid_ooxml_package(data, "word/document.xml"):
        return False
    try:
        Document(BytesIO(data))
        return True
    except Exception:
        return False


def add_signatures(source_path, output_path, qr_images, signers):
    document = Document(str(source_path))
    document.add_page_break()
    heading = document.add_paragraph().add_run("TANDA TANGAN DIGITAL")
    heading.bold = True
    heading.font.size = Pt(16)
    for index, (qr_image, signer) in enumerate(zip(qr_images, signers), start=1):
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).paragraphs[0].add_run().add_picture(
            BytesIO(image_bytes(qr_image)), width=Inches(1.35)
        )
        details = table.cell(0, 1).paragraphs[0]
        details.add_run(f"Penandatangan #{index}\n").bold = True
        details.add_run(f"Nama: {signer.get('name', '')}\n")
        details.add_run(f"Jabatan: {signer.get('position', '')}\n")
        details.add_run(f"Institusi: {signer.get('institution', '')}\n")
        details.add_run(f"Tanggal: {signer.get('date', '')}")
        document.add_paragraph()
    document.save(str(output_path))


def extract_metadata(path):
    return qr_generator.decode_qr_from_images(extract_media_images(path, "word/media/"))