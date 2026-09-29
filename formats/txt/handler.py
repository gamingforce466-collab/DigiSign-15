"""Validasi, penyimpanan metadata tanda tangan, dan ekstraksi untuk TXT."""
import json
from pathlib import Path

from qr import generator as qr_generator

TEXT_METADATA_START = "----- BEGIN DIGISIGN METADATA -----"
TEXT_METADATA_END = "----- END DIGISIGN METADATA -----"


def is_valid(data):
    try:
        text = data.decode("utf-8-sig")
        return bool(text.strip()) and "\x00" not in text
    except UnicodeDecodeError:
        return False


def add_signatures(source_path, output_path, qr_images):
    text = Path(source_path).read_bytes().decode("utf-8-sig").rstrip()
    metadata_rows = []
    for qr_image in qr_images:
        metadata = qr_generator.decode_qr_image(qr_image)
        if metadata is None:
            raise ValueError("Metadata QR tidak dapat dibaca untuk berkas TXT")
        metadata_rows.append(json.dumps(metadata, ensure_ascii=False, separators=(",", ":")))
    block = "\n\n" + TEXT_METADATA_START + "\n" + "\n".join(metadata_rows) + "\n" + TEXT_METADATA_END + "\n"
    Path(output_path).write_text(text + block, encoding="utf-8")


def extract_metadata(path):
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    try:
        start = lines.index(TEXT_METADATA_START) + 1
        end = lines.index(TEXT_METADATA_END, start)
    except ValueError:
        return []
    results = []
    for line in lines[start:end]:
        try:
            metadata = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(metadata, dict):
            results.append(metadata)
    return results