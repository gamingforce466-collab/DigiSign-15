"""Validasi, penyisipan tanda tangan, dan ekstraksi QR untuk gambar."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from formats.common import MAX_IMAGE_PIXELS
from qr import generator as qr_generator


def is_valid(data, extension):
    expected_format = "JPEG" if extension in (".jpg", ".jpeg") else "PNG"
    try:
        with Image.open(BytesIO(data)) as image:
            actual_format = image.format
            dimensions_ok = image.width * image.height <= MAX_IMAGE_PIXELS
            image.verify()
        return actual_format == expected_format and dimensions_ok
    except Exception:
        return False


def add_signatures(source_path, output_path, extension, qr_images, signers):
    output_format = "JPEG" if extension in (".jpg", ".jpeg") else "PNG"
    with Image.open(source_path) as opened:
        original = opened.convert("RGB")

    qr_size = max(image.width for image in qr_images)
    canvas_width = max(original.width, qr_size + 460)
    row_height = max(190, qr_size + 28)
    signed = Image.new("RGB", (canvas_width, original.height + row_height * len(qr_images)), "white")
    signed.paste(original, ((canvas_width - original.width) // 2, 0))
    draw = ImageDraw.Draw(signed)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()

    for index, (qr_image, signer) in enumerate(zip(qr_images, signers), start=1):
        y = original.height + (index - 1) * row_height
        signed.paste(qr_image.convert("RGB"), (16, y + 14))
        lines = (
            f"TANDA TANGAN DIGITAL #{index}",
            f"Nama: {signer.get('name', '')}",
            f"Jabatan: {signer.get('position', '')}",
            f"Institusi: {signer.get('institution', '')}",
            f"Tanggal: {signer.get('date', '')}",
        )
        for line_number, line in enumerate(lines):
            draw.text((195, y + 20 + line_number * 28), line, fill="black", font=font)

    signed.save(output_path, format=output_format, quality=95)


def extract_metadata(path):
    with Image.open(path) as image:
        return qr_generator.decode_qr_image_multiple(image)