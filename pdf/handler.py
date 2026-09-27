import hashlib
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def extract_text_content(source):
    reader = PdfReader(source)
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    return "\n".join(parts)


def compute_content_digest(source):
    content = extract_text_content(source)
    return hashlib.sha256(content.encode("utf-8")).digest()


def compute_file_sha256(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def embed_qr_images(input_path, qr_images, output_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    last_index = len(reader.pages) - 1
    for i, page in enumerate(reader.pages):
        if i == last_index and qr_images:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
            qr_size = 90
            margin = 20
            spacing = 10
            x = page_width - margin - qr_size
            y = margin
            for qr_image in qr_images:
                image_reader = ImageReader(qr_image)
                c.drawImage(image_reader, x, y, width=qr_size, height=qr_size, mask="auto")
                x -= (qr_size + spacing)
            c.save()
            buffer.seek(0)
            overlay_reader = PdfReader(buffer)
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)


def extract_embedded_images(path):
    reader = PdfReader(path)
    images = []
    for page in reader.pages:
        try:
            for img in page.images:
                images.append(img.image)
        except Exception:
            continue
    return images


def get_page_count(path):
    reader = PdfReader(path)
    return len(reader.pages)
