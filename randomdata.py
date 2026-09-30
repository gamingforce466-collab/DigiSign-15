"""Generator contoh data untuk tombol Isi Data Acak dan pengujian.

Dipakai oleh halaman web dan tes supaya data tidak perlu diketik berulang kali.
Seluruh nilai rahasia (passphrase) dibangkitkan dengan modul `secrets` (CSPRNG).
"""
import random
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

FIRST_NAMES = [
    "Budi", "Siti", "Agus", "Dewi", "Rizky", "Putri", "Andi", "Ratna", "Fajar", "Nadia",
    "Hendra", "Maya", "Dimas", "Lestari", "Bagas", "Anisa", "Hava", "Wulan", "Yusuf", "Intan",
]
LAST_NAMES = [
    "Santoso", "Aminah", "Wijaya", "Pratama", "Kusuma", "Rahmawati", "Hidayat", "Nugroho",
    "Saputra", "Purnama", "Maulana", "Setiawan", "Nagila", "Permana", "Handayani",
]
POSITIONS = [
    "Ketua Panitia", "Sekretaris", "Dekan Fakultas", "Kepala Program Studi", "Dosen Pembimbing",
    "Wakil Dekan Bidang Akademik", "Ketua Jurusan", "Koordinator Kegiatan", "Bendahara", "Direktur",
]
INSTITUTIONS = [
    "Universitas Contoh Nusantara", "Institut Teknologi Contoh", "Politeknik Contoh Mandiri",
    "Universitas Contoh Pasundan", "Sekolah Tinggi Contoh Informatika",
]
PRODI = [
    "Teknik Informatika", "Sistem Informasi", "Manajemen", "Akuntansi", "Teknik Elektro",
    "Ilmu Komunikasi", "Statistika",
]
EVENTS = [
    "Seminar Nasional Teknologi Informasi", "Workshop Keamanan Siber", "Pelatihan Analisis Data",
    "Kuliah Umum Kecerdasan Buatan", "Lomba Karya Tulis Ilmiah",
]
REPORT_TITLES = [
    "Rancang Bangun Sistem Informasi Akademik", "Analisis Sentimen Ulasan Aplikasi Seluler",
    "Implementasi Tanda Tangan Digital pada Dokumen Akademik", "Prediksi Harga Komoditas dengan Regresi",
]


def _utc_now():
    return datetime.now(timezone.utc)


def random_person_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_owner_id(prefix="uji"):
    """Nama pemilik kunci acak yang aman dipakai sebagai nama berkas."""
    return f"{prefix}_{secrets.token_hex(3)}"


def random_passphrase():
    return secrets.token_urlsafe(9)


def random_date(days_back=30):
    day = _utc_now() - timedelta(days=random.randint(0, days_back))
    return day.strftime("%Y-%m-%d")


def random_signer():
    """Data penandatangan acak (sesuai kolom form /sign)."""
    return {
        "signer_name": random_person_name(),
        "position": random.choice(POSITIONS),
        "institution": random.choice(INSTITUTIONS),
        "signed_date": random_date(),
    }


def random_document():
    """Isi dokumen contoh acak: judul, nomor, dan paragraf isi."""
    kind = random.choice(["keterangan", "sertifikat", "pengesahan"])
    student = random_person_name()
    nim = "".join(random.choice("0123456789") for _ in range(10))
    number = f"{random.randint(1, 999):03d}/DS/{random.randint(1, 12):02d}/{_utc_now().year}"
    if kind == "keterangan":
        title = "SURAT KETERANGAN AKTIF KULIAH"
        body = (
            f"Yang bertanda tangan di bawah ini menerangkan bahwa {student} dengan NIM {nim} "
            f"adalah benar mahasiswa aktif Program Studi {random.choice(PRODI)} pada semester "
            f"{random.randint(1, 8)}. Surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya."
        )
        slug = "surat_keterangan"
    elif kind == "sertifikat":
        title = "SERTIFIKAT KEGIATAN"
        body = (
            f"Diberikan kepada {student} sebagai peserta pada kegiatan {random.choice(EVENTS)} "
            f"yang diselenggarakan pada {random_date(90)}. Sertifikat ini diterbitkan sebagai bukti partisipasi."
        )
        slug = "sertifikat_kegiatan"
    else:
        title = "LEMBAR PENGESAHAN LAPORAN"
        body = (
            f"Laporan berjudul \"{random.choice(REPORT_TITLES)}\" yang disusun oleh {student} "
            f"(NIM {nim}) telah diperiksa dan disetujui untuk dilanjutkan ke tahap berikutnya."
        )
        slug = "lembar_pengesahan"
    return {
        "title": title,
        "number": number,
        "body": body,
        "filename": f"{slug}_{secrets.token_hex(2)}.pdf",
    }


def make_random_pdf_bytes(document=None):
    """Buat PDF A4 dari `random_document()`. Kembalikan (bytes, dokumen).

    Isi ditempatkan di bagian atas halaman agar area bawah (tempat blok tanda tangan
    digital disisipkan) tetap kosong.
    """
    document = document or random_document()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 90, document["title"])
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 108, f"Nomor: {document['number']}")
    c.setFont("Helvetica", 11)
    y = height - 150
    for line in simpleSplit(document["body"], "Helvetica", 11, width - 140):
        c.drawString(70, y, line)
        y -= 16
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(70, y - 20, "Dokumen contoh acak untuk pengujian DigiSign.")
    c.save()
    return buffer.getvalue(), document
