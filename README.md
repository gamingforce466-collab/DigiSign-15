Aplikasi web tanda tangan digital untuk PDF, Word `.docx`, JPG/JPEG, PNG, TXT, dan Excel `.xlsx`. Berkas di-hash dengan SHA-256, ditandatangani RSA-2048-PSS, lalu diverifikasi. QR-Code dipasang pada PDF, DOCX, gambar, dan XLSX; TXT menyimpan metadata verifikasi terstruktur sebagai teks.

Proyek Topik D: Aplikasi Digital Signature.

## Daftar Isi

- [Daftar Isi](#daftar-isi)
- [Fitur](#fitur)
- [Kebutuhan Sistem](#kebutuhan-sistem)
- [Instalasi](#instalasi)
  - [Windows (PowerShell)](#windows-powershell)
  - [Linux dan macOS](#linux-dan-macos)
- [Konfigurasi](#konfigurasi)
- [Menjalankan Aplikasi](#menjalankan-aplikasi)
- [Cara Penggunaan](#cara-penggunaan)
  - [1. Membuat kunci](#1-membuat-kunci)
  - [2. Menandatangani dokumen](#2-menandatangani-dokumen)
  - [3. Menambah penandatangan](#3-menambah-penandatangan)
  - [4. Verifikasi](#4-verifikasi)
  - [5. Mengulang pengujian dari awal](#5-mengulang-pengujian-dari-awal)
- [Status Verifikasi](#status-verifikasi)
- [Pengujian](#pengujian)
  - [Unit test](#unit-test)
- [Uji Kuantitatif dan Benchmark](#uji-kuantitatif-dan-benchmark)
- [Skenario Demo](#skenario-demo)
- [Keamanan](#keamanan)
- [Struktur Proyek](#struktur-proyek)
  - [Alur Kode](#alur-kode)
  - [Perubahan Struktur](#perubahan-struktur)
- [Rute Aplikasi](#rute-aplikasi)
- [Batasan](#batasan)

## Fitur

| Fitur              | Keterangan                                                                                                             |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Pasangan kunci     | RSA 2048-bit, eksponen publik 65537                                                                                    |
| Skema tanda tangan | RSA-PSS dengan MGF1-SHA256                                                                                             |
| Format dokumen     | PDF, Word `.docx`, JPG/JPEG, PNG, TXT, dan Excel `.xlsx`                                                               |
| Hash dokumen       | SHA-256 atas seluruh byte berkas yang diunggah                                                                         |
| Kunci privat       | Disimpan terenkripsi (PKCS8 PEM dengan passphrase), tidak ada di kode sumber                                           |
| QR-Code            | Memuat nama, jabatan, institusi, tanggal, hash dokumen, ID dokumen, dan tautan verifikasi                              |
| Verifikasi         | Menolak dokumen yang diubah, kunci publik yang salah, dan QR-Code palsu                                                |
| Pengayaan          | Beberapa penandatangan pada satu dokumen (diuji sampai 3 pihak)                                                        |
| Uji kuantitatif    | Waktu 30+ percobaan (mean, min, maks, std dev), ukuran tanda tangan dan kunci publik, uji tamper 1 byte pada 10 posisi |
| Rekap Excel        | Unduhan `.xlsx` berisi 3 sheet hasil pengujian                                                                         |
| Bersihkan data     | Satu tombol untuk menghapus semua kunci, dokumen, dan tanda tangan sebelum pengujian baru                              |

Bilangan acak (kunci, salt, passphrase uji, ID dokumen) dibangkitkan dengan `secrets`, `uuid`, dan `cryptography` yang berbasis CSPRNG sistem operasi. Tidak ada MD5, SHA-1, DES, RC4, atau mode ECB pada fitur keamanan.

## Kebutuhan Sistem

- Python 3.10 sampai 3.13
- Berkas sumber maksimal 30 MiB; request verifikasi maksimal 64 MiB
- pip
- Windows, Linux, atau macOS
- Koneksi internet saat pertama kali membuka aplikasi (gaya tampilan Tailwind CSS dimuat dari CDN)

Semua pustaka Python tercantum di `requirements.txt`:

| Paket                         | Fungsi                                          |
| ----------------------------- | ----------------------------------------------- |
| Flask, Werkzeug, Jinja2       | Web server dan template                         |
| Streamlit                     | Antarmuka Streamlit dan deployment Streamlit    |
| python-dotenv                 | Membaca berkas `.env`                           |
| cryptography                  | RSA, PSS, SHA-256, enkripsi kunci privat        |
| pypdf                         | Membaca dan menulis PDF                         |
| reportlab                     | Menggambar blok tanda tangan dan PDF contoh     |
| python-docx                   | Menyisipkan blok tanda tangan pada Word `.docx` |
| qrcode, Pillow                | Membuat gambar QR-Code                          |
| opencv-python-headless, numpy | Membaca QR-Code dari PDF dan gambar             |
| openpyxl                      | Membuat berkas Excel                            |
| pytest                        | Pengujian otomatis                              |

## Instalasi

### Windows (PowerShell)

```
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Jika muncul galat `running scripts is disabled`, jalankan sekali:

```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Atau pakai Command Prompt: `venv\Scripts\activate.bat`.

### Linux dan macOS

```
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Ganti `USERNAME/NAMA-REPO` dengan alamat repositori Anda. Jika proyek diterima dalam bentuk ZIP, ekstrak lalu mulai dari perintah `cd`.

## Konfigurasi

Berkas `.env` (salinan dari `.env.example`) berisi:

| Variabel            | Nilai bawaan                   | Keterangan                                                                                                         |
| ------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `FLASK_SECRET_KEY`  | `dev_fallback_secret_key`      | Kunci sesi Flask. Ganti dengan string acak panjang                                                                 |
| `VERIFY_BASE_URL`   | `http://localhost:5000/verify` | Alamat yang ditulis di QR-Code sebagai tautan verifikasi                                                           |
| `ENABLE_TEST_TOOLS` | `1`                            | Flask: `1` menampilkan tombol Isi acak, `0` menyembunyikannya. Streamlit default-nya `0` dan diatur lewat Secrets. |
| `FLASK_DEBUG`       | `0`                            | `1` untuk mode debug saat pengembangan                                                                             |

Membuat `FLASK_SECRET_KEY` acak:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

Jika aplikasi dibuka dari perangkat lain (misalnya ponsel untuk memindai QR-Code), ganti `VERIFY_BASE_URL` dengan alamat IP komputer, contoh `http://192.168.1.10:5000/verify`. Perubahan hanya berlaku untuk dokumen yang ditandatangani sesudahnya.

Folder `storage/keys`, `storage/documents`, dan `storage/signatures` dibuat otomatis jika belum ada.

## Menjalankan Aplikasi

Jalankan antarmuka Flask yang sudah tersedia:

```
python app.py
```

Buka http://localhost:5000 di browser. Hentikan dengan `Ctrl+C`.

Untuk menjalankan antarmuka Streamlit:

```
streamlit run streamlit_app.py
```

Buat konfigurasi lokal sebelum membuka Streamlit:

```
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Di Windows PowerShell, gunakan `Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml`. Ganti password contoh dengan password acak minimal 16 karakter. File `secrets.toml` lokal diabaikan Git. File contoh mengaktifkan fitur Isi acak dan Bersihkan data untuk demo; matikan keduanya saat aplikasi dibuka ke publik.

Untuk Streamlit Community Cloud, pilih `streamlit_app.py` sebagai **Main file path**, lalu isi **Settings > Secrets**:

```toml
STREAMLIT_ACCESS_PASSWORD = "password-acak-minimal-16-karakter"
STREAMLIT_VERIFY_BASE_URL = "https://nama-aplikasi.streamlit.app"
ENABLE_TEST_TOOLS = "0"
ENABLE_DATA_RESET = "0"
```

Password diperlukan untuk membuka aplikasi. Tautan QR dokumen baru menggunakan `STREAMLIT_VERIFY_BASE_URL`. `DIGISIGN_DATA_DIR` dapat diarahkan ke volume persisten pada host yang mendukungnya; disk lokal Streamlit Community Cloud tidak persisten, jadi dokumen dan kunci di sana hanya cocok untuk demo sementara. Jangan simpan password, kunci, atau data dokumen ke Git.

Agar dapat diakses dari perangkat lain di jaringan yang sama:

```
flask --app app run --host 0.0.0.0 --port 5000
```

Server bawaan Flask hanya untuk pengembangan dan demo.

## Cara Penggunaan

Menu: **Beranda**, **Tanda Tangan**, **Verifikasi**, **Uji Kuantitatif**.

### 1. Membuat kunci

1. Buka **Tanda Tangan**.
2. Pada bagian _Buat kunci_, isi nama kunci (huruf, angka, `_`, `-`, maksimal 40 karakter) dan passphrase.
3. Klik **Buat Kunci**. File `<nama>_private.pem` (terenkripsi) dan `<nama>_public.pem` tersimpan di `storage/keys/`.

Passphrase tidak disimpan. Jika hilang, kunci tidak bisa dipakai lagi.

### 2. Menandatangani dokumen

1. Pada bagian _Tandatangani dokumen_, biarkan pilihan **Dokumen baru**, lalu pilih PDF, Word `.docx`, JPG/JPEG, PNG, TXT, atau Excel `.xlsx` (maksimal 30 MiB).
2. Pilih kunci, isi passphrase, nama, jabatan, institusi, dan tanggal.
3. Klik **Tandatangani**.
4. Klik **Unduh**. Berkas hasil tetap memakai format asal. TXT menyertakan metadata teks; format lain menyertakan QR-Code.

Tombol **Isi acak** (jika `ENABLE_TEST_TOOLS=1`) mengisi nama kunci, passphrase, dan data penandatangan dengan nilai acak. Berkas dokumen tetap dipilih manual.

### 3. Menambah penandatangan

1. Buka **Tanda Tangan**.
2. Pada kolom **Dokumen**, pilih `Tambah TTD: <Doc ID> ...`. Alternatif: klik **Tambah TTD** pada baris dokumen di Beranda.
3. Pilih kunci lain, isi passphrase dan data penandatangan, lalu klik **Tandatangani**.
4. Unduh dokumen **setelah tanda tangan terakhir**. Hanya berkas terbaru yang memuat semua blok tanda tangan.

Mengunggah ulang hasil tanda tangan dengan pilihan _Dokumen baru_ akan membuat dokumen terpisah dengan Doc ID baru.

### 4. Verifikasi

1. Buka **Verifikasi**.
2. Unggah dokumen bertanda tangan (PDF, DOCX, JPG/JPEG, PNG, TXT, atau XLSX). Doc ID dibaca dari QR-Code, atau dari metadata teks untuk TXT. Request verifikasi menerima hasil hingga 64 MiB.
3. Klik **Verifikasi**. Hasil berupa status, kondisi isi dokumen, jumlah QR-Code terbaca, dan tabel penandatangan.

Opsi tambahan:

- **Doc ID**: isi jika QR-Code tidak terbaca.
- **Kunci publik pembanding (.pem)**: unggah kunci publik milik orang lain untuk menguji hasil `KEY_MISMATCH`.

### 5. Mengulang pengujian dari awal

Di **Beranda**, klik **Bersihkan semua data** lalu konfirmasi. Semua kunci, PDF, dan data tanda tangan dihapus.

## Status Verifikasi

| Status         | Arti                                                                |
| -------------- | ------------------------------------------------------------------- |
| `VALID`        | Dokumen utuh dan semua tanda tangan cocok                           |
| `TAMPERED`     | Isi dokumen berbeda dari yang ditandatangani (satu byte pun)        |
| `KEY_MISMATCH` | Dokumen utuh, tetapi tanda tangan tidak cocok dengan kunci publik   |
| `QR_FORGED`    | QR-Code memuat Doc ID yang tidak terdaftar atau datanya tidak cocok |
| `NOT_FOUND`    | Doc ID yang diisi tidak ditemukan                                   |
| `NO_QR`        | QR-Code tidak terbaca dan Doc ID tidak diisi                        |

PDF versi lama (misalnya hanya memuat 1 dari 2 blok tanda tangan) tetap `VALID` selama isinya utuh. Tampilan menunjukkan jumlah QR-Code yang terbaca, misalnya "1 dari 2".

## Pengujian

### Unit test

```
pytest tests/ -v -s
```

Total 65 tes. Opsi `-s` menampilkan angka waktu dan ukuran di terminal.

| Berkas                           | Jumlah | Isi                                                                                                                                |
| -------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_crypto.py`           | 10     | Pembuatan kunci terenkripsi, hash SHA-256, sign, verify, tamper, tanda tangan rusak, waktu 30 percobaan, ukuran, benchmark         |
| `tests/test_tamper.py`           | 6      | Ubah 1 byte di berbagai posisi, kunci publik salah                                                                                 |
| `tests/test_qr.py`               | 4      | Pembuatan dan pembacaan QR-Code, metadata palsu                                                                                    |
| `tests/test_status.py`           | 16     | Status VALID, TAMPERED, KEY_MISMATCH, QR_FORGED, NOT_FOUND, NO_QR, tiga penandatangan, halaman Verifikasi, Excel, tombol Bersihkan |
| `tests/test_flow.py`             | 10     | Alur web PDF dan format DOCX/JPG/JPEG/PNG/TXT/XLSX, tamper, dan batas upload 30 MiB                                                |
| `tests/test_enrichment.py`       | 11     | Beberapa penandatangan, blok tanda tangan PDF, Isi acak                                                                            |
| `tests/test_document_formats.py` | 8      | Validasi serta penyisipan/ekstraksi QR PDF, DOCX, JPG/JPEG, PNG, TXT, dan XLSX                                                     |

Menjalankan satu berkas atau satu tes:

```
pytest tests/test_crypto.py -v -s
pytest tests/test_status.py::test_tampered_status -v
```

Tes memakai folder sementara untuk dokumen dan tanda tangan, dan menghapus kunci uji setelah selesai.

## Uji Kuantitatif dan Benchmark

Menu **Uji Kuantitatif** menjalankan tiga pengujian sekaligus:

1. **Waktu komputasi**: tanda tangan dan verifikasi dihitung dari minimal 30 percobaan (mean, min, maks, std dev), RSA-2048-PSS dibandingkan dengan ECDSA P-256.
2. **Ukuran kriptografi**: tanda tangan, kunci publik DER dan PEM, serta rasio RSA terhadap ECDSA.
3. **Uji tamper 1 byte**: satu byte PDF bertanda tangan diubah pada 10 posisi berbeda. Semua harus berstatus `TAMPERED`.

RSA-2048-PSS adalah algoritma yang dipakai aplikasi. ECDSA P-256 hanya pembanding.

Isi jumlah percobaan (minimal 30, maksimal 1000), klik **Jalankan pengujian**, lalu klik **Unduh Rekapitulasi Data Pengujian (.xlsx)**. File `rekap_pengujian_digisign.xlsx` berisi:

| Sheet               | Isi                                                                                |
| ------------------- | ---------------------------------------------------------------------------------- |
| `Benchmark 30x`     | Waktu tanda tangan dan verifikasi tiap percobaan                                   |
| `Ringkasan Metrik`  | Mean, min, maks, std dev, ukuran tanda tangan dan kunci publik, rasio RSA vs ECDSA |
| `Uji Tamper 1-Byte` | 10 skenario: offset byte, byte asli dan baru, hash baru, status, hasil uji         |

Alternatif lewat terminal (tanpa Excel):

```
python -m crypto.benchmark
python -m crypto.benchmark 100
```

## Skenario Demo

1. Buka **Tanda Tangan**, buat kunci, tandatangani sebuah PDF, lalu unduh.
2. Buka **Verifikasi**, unggah PDF tersebut. Hasil: `VALID`.
3. Ubah satu karakter atau satu byte PDF dengan editor heksadesimal, lalu unggah lagi. Hasil: `TAMPERED`.
4. Unggah PDF asli dengan berkas `.pem` kunci publik orang lain pada kolom pembanding. Hasil: `KEY_MISMATCH`.
5. Unggah PDF lain yang ditempeli gambar QR-Code buatan sendiri. Hasil: `QR_FORGED` atau `TAMPERED`.
6. Untuk penandatangan ganda: tambahkan penandatangan kedua dan ketiga pada Doc ID yang sama, unduh, lalu verifikasi. Hasil: `VALID` dengan "3 dari 3".

## Keamanan

- Kunci privat disimpan terenkripsi dengan passphrase pengguna (PKCS8 PEM). Tidak ada kunci atau kata sandi di kode sumber.
- Nama kunci divalidasi dengan pola `[A-Za-z0-9_-]{1,40}` untuk mencegah path traversal.
- Tanda tangan dibuat atas hash SHA-256 seluruh byte berkas. Perubahan satu byte mengubah hash sehingga verifikasi gagal.
- Metadata QR (atau blok metadata pada TXT) dicocokkan dengan catatan tanda tangan di server (Doc ID, penandatangan, nama, tanggal, hash), sehingga metadata palsu ditolak.
- Berkas berikut tidak boleh diunggah ke GitHub. Semuanya sudah ada di `.gitignore`:

```
.env
storage/keys/
storage/documents/
storage/signatures/
venv/
__pycache__/
```

- Jika kunci privat pernah terunggah ke GitHub, anggap bocor: buat kunci baru dan jangan pakai yang lama. Menghapus file dari repositori tidak menghapusnya dari riwayat commit.

Menghapus berkas yang terlanjur ter-commit:

```
git rm --cached -r storage/keys .env venv
git commit -m "Hapus file sensitif dari repositori"
git push
```

## Struktur Proyek

```
app.py                  konfigurasi Flask, route, dan penghubung service
document_formats.py     façade kompatibilitas menuju dispatcher format
randomdata.py           data contoh untuk tombol Isi acak dan tes
requirements.txt        dependensi langsung aplikasi dan tes
.env.example            template konfigurasi
services/
  document_workflow.py record, signing, integritas, dan verifikasi
  maintenance.py       operasi pembersihan storage
  scenarios.py         helper tamper dan pemalsuan QR untuk tes
formats/
  __init__.py          pemetaan ekstensi dan dispatcher format
  common.py            utilitas OOXML dan gambar bersama
  docx/handler.py      validasi, penyisipan QR, dan ekstraksi Word
  image/handler.py     validasi, penyisipan QR, dan ekstraksi JPG/PNG
  txt/handler.py       metadata verifikasi teks untuk TXT
  xlsx/handler.py      validasi, sheet DigiSign, dan ekstraksi QR Excel
crypto/
    keys.py             pembuatan, penyimpanan, dan pemuatan kunci
    signer.py           tanda tangan RSA-PSS atas hash SHA-256
    verifier.py         verifikasi tanda tangan
    benchmark.py        waktu, ukuran, dan uji tamper
    excel_exporter.py   ekspor laporan pengujian ke Excel
pdf/
    handler.py          hash, blok tanda tangan, dan ekstraksi gambar PDF
qr/
    generator.py        pembuatan dan pembacaan QR-Code
  templates/              halaman HTML Jinja2
  static/                 CSS dan JavaScript browser
storage/
    keys/               kunci (tidak di-commit)
    documents/          berkas asli dan bertanda tangan (tidak di-commit)
    signatures/         catatan tanda tangan JSON (tidak di-commit)
  tests/                  tes unit, alur web, format, dan serangan
```

### Alur Kode

Route pada `app.py` menerima form dan meneruskan pekerjaan ke `services/document_workflow.py`. Service ini menangani record, hash, signing RSA-PSS, dan verifikasi. Untuk validasi, penyisipan, dan pembacaan metadata, service memanggil `document_formats.py`; façade itu meneruskan ke handler khusus di `formats/`, sementara PDF tetap menggunakan `pdf/handler.py`.

Saat verifikasi, handler format membaca QR atau metadata TXT, service membandingkan hash seluruh berkas dengan hash yang tercatat, mencocokkan metadata penandatangan, lalu memeriksa tanda tangan dengan kunci publik. Route hanya mengubah hasil service menjadi halaman atau respons unduhan.

Perilaku format:

- PDF: blok QR ditambahkan pada halaman terakhir.
- DOCX: blok tanda tangan dan QR ditambahkan ke dokumen; isi Word asli dipertahankan.
- JPG/JPEG/PNG: gambar asli dipertahankan dan blok QR ditambahkan di bawahnya.
- XLSX: sheet asli dipertahankan dan sheet `DigiSign` berisi identitas serta QR ditambahkan.
- TXT: metadata JSON ditambahkan sebagai blok teks bertanda batas. TXT dapat diverifikasi aplikasi, tetapi tidak memiliki QR gambar untuk dipindai kamera.

### Perubahan Struktur

- Logika record, signing, dan verifikasi dipisah dari `app.py` ke `services/document_workflow.py`; fungsi façade lama tetap tersedia agar route dan tes kompatibel.
- Pembersihan storage dan helper skenario uji berada di `services/maintenance.py` dan `services/scenarios.py`.
- Setiap format non-PDF memiliki handler sendiri; PDF tetap berada di `pdf/handler.py`.
- `document_formats.py` hanya mempertahankan API lama dan meneruskan operasi ke dispatcher format.
- Ukuran berkas sumber dibatasi 30 MiB dan request verifikasi 64 MiB.

## Rute Aplikasi

| Rute                 | Metode    | Fungsi                                                  |
| -------------------- | --------- | ------------------------------------------------------- |
| `/`                  | GET       | Beranda, daftar kunci dan dokumen                       |
| `/sign`              | GET, POST | Halaman dan proses tanda tangan                         |
| `/generate_keys`     | POST      | Membuat pasangan kunci                                  |
| `/download/<doc_id>` | GET       | Mengunduh dokumen bertanda tangan dalam format asal     |
| `/preview/<doc_id>`  | GET       | Membuka PDF bertanda tangan di tab baru                 |
| `/verify`            | GET, POST | Halaman dan proses verifikasi                           |
| `/benchmark`         | GET, POST | Uji kuantitatif dan benchmark                           |
| `/benchmark/xlsx`    | GET       | Unduh rekapitulasi Excel                                |
| `/clear`             | POST      | Menghapus semua kunci, dokumen, dan tanda tangan        |
| `/api/random`        | GET       | Data acak untuk Isi acak (butuh `ENABLE_TEST_TOOLS=1`)  |
| `/api/random_key`    | POST      | Kunci acak untuk Isi acak (butuh `ENABLE_TEST_TOOLS=1`) |

## Batasan

- Skema tanda tangan yang dipakai hanya RSA-2048-PSS. ECDSA P-256 hanya pembanding di benchmark.
- Tanda tangan ganda klasik dan pasca-kuantum (ECDSA + ML-DSA) dan penyimpanan hash pada blockchain uji belum tersedia. Pengayaan yang diambil adalah beberapa penandatangan pada satu dokumen.
- Tautan verifikasi di QR-Code membuka halaman Verifikasi dengan Doc ID terisi. Pengguna tetap mengunggah dokumen bertanda tangan untuk memeriksa keutuhannya.
- Data disimpan sebagai berkas lokal di folder `storage/`, tanpa basis data dan tanpa akun pengguna.
- Server bawaan Flask tidak untuk produksi.
