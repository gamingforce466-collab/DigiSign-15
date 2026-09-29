"""Utilitas bersama format Office Open XML dan gambar."""
import zipfile
from io import BytesIO

from PIL import Image

MAX_OOXML_EXPANDED_SIZE = 200 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000


def valid_ooxml_package(data, required_member):
    try:
        with zipfile.ZipFile(BytesIO(data)) as package:
            members = package.infolist()
            if sum(member.file_size for member in members) > MAX_OOXML_EXPANDED_SIZE:
                return False
            if required_member not in package.namelist() or package.testzip() is not None:
                return False
        return True
    except Exception:
        return False


def image_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def extract_media_images(path, prefix):
    images = []
    try:
        with zipfile.ZipFile(path) as package:
            media_files = sorted(name for name in package.namelist() if name.startswith(prefix))
            for name in media_files:
                try:
                    with Image.open(BytesIO(package.read(name))) as image:
                        images.append(image.copy())
                except Exception:
                    continue
    except (OSError, zipfile.BadZipFile):
        return []
    return images