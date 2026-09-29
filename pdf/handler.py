import hashlib
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

# Ukuran blok tanda tangan digital (satuan point PDF)
BLOCK_WIDTH = 118
BLOCK_PAD = 4
BLOCK_HEADER_H = 12
BLOCK_QR_SIZE = 92
BLOCK_TEXT_LINE_H = 9
BLOCK_TEXT_LINES = 4
BLOCK_GAP = 8
PAGE_MARGIN = 20
BLOCK_HEIGHT = (
    BLOCK_PAD + BLOCK_HEADER_H + BLOCK_QR_SIZE + 3
    + BLOCK_TEXT_LINE_H * BLOCK_TEXT_LINES + BLOCK_PAD
)


def compute_file_digest(path):
    """SHA-256 (bytes) atas SELURUH byte berkas, bukan hanya teks hasil ekstraksi."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.digest()


def compute_content_digest(source):
    return compute_file_digest(source)


def _fit_text(text, font, size, max_width):
    """Sanitasi ke Latin-1 dan potong dengan '..' bila melebihi lebar blok."""
    text = (text or "").strip().encode("latin-1", "replace").decode("latin-1")
    if stringWidth(text, font, size) <= max_width:
        return text
    while text and stringWidth(text + "..", font, size) > max_width:
        text = text[:-1]
    return text + ".."


def _draw_signature_block(c, x, y, qr_image, index, info):
    """Gambar satu blok: header bernomor, QR-Code, lalu nama/jabatan/institusi/tanggal."""
    inner_w = BLOCK_WIDTH - 2 * BLOCK_PAD
    c.setStrokeColorRGB(0.55, 0.6, 0.68)
    c.setLineWidth(0.8)
    c.rect(x, y, BLOCK_WIDTH, BLOCK_HEIGHT, stroke=1, fill=0)

    header_y = y + BLOCK_HEIGHT - BLOCK_HEADER_H
    c.setFillColorRGB(0.06, 0.09, 0.16)
    c.rect(x, header_y, BLOCK_WIDTH, BLOCK_HEADER_H, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(x + BLOCK_WIDTH / 2, header_y + 3.6, f"TANDA TANGAN DIGITAL #{index}")

    text_h = BLOCK_TEXT_LINE_H * BLOCK_TEXT_LINES
    qr_y = y + BLOCK_PAD + text_h + 3
    qr_x = x + (BLOCK_WIDTH - BLOCK_QR_SIZE) / 2
    c.drawImage(ImageReader(qr_image), qr_x, qr_y, width=BLOCK_QR_SIZE, height=BLOCK_QR_SIZE, mask="auto")

    c.setFillColorRGB(0, 0, 0)
    lines = [
        ("Helvetica-Bold", 7.5, info.get("name", "")),
        ("Helvetica", 6.5, info.get("position", "")),
        ("Helvetica", 6.5, info.get("institution", "")),
        ("Helvetica-Oblique", 6.5, f"Tgl: {info.get('date', '')}"),
    ]
    text_y = y + BLOCK_PAD + text_h - BLOCK_TEXT_LINE_H + 2
    for font, size, text in lines:
        c.setFont(font, size)
        c.drawCentredString(x + BLOCK_WIDTH / 2, text_y, _fit_text(text, font, size, inner_w))
        text_y -= BLOCK_TEXT_LINE_H


def embed_qr_images(input_path, qr_images, output_path, signers=None):
    """Sisipkan QR-Code ke halaman terakhir PDF.

    Bila `signers` diberikan (daftar dict name/position/institution/date, sejajar dengan
    `qr_images`), setiap penandatangan digambar sebagai blok berlabel "TANDA TANGAN DIGITAL #n"
    dengan identitasnya, disusun dari kiri ke kanan dan turun-naik baris bila halaman penuh.
    Tanpa `signers`, perilaku lama dipertahankan (deretan QR polos).
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    last_index = len(reader.pages) - 1
    for i, page in enumerate(reader.pages):
        if i == last_index and qr_images:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
            if signers and len(signers) == len(qr_images):
                columns = max(1, int((page_width - 2 * PAGE_MARGIN + BLOCK_GAP) // (BLOCK_WIDTH + BLOCK_GAP)))
                for n, (qr_image, info) in enumerate(zip(qr_images, signers), start=1):
                    row, col = divmod(n - 1, columns)
                    x = PAGE_MARGIN + col * (BLOCK_WIDTH + BLOCK_GAP)
                    y = PAGE_MARGIN + row * (BLOCK_HEIGHT + BLOCK_GAP)
                    _draw_signature_block(c, x, y, qr_image, n, info)
            else:
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
            new_page = writer.add_page(page)
            new_page.merge_page(overlay_reader.pages[0])
            continue
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


def is_valid_pdf_bytes(data):
    """True bila `data` dapat dibaca sebagai PDF yang memiliki minimal satu halaman."""
    try:
        return len(PdfReader(BytesIO(data)).pages) > 0
    except Exception:
        return False
