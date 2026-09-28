# DigitalSignature

Aplikasi web tanda tangan digital berbasis Python (Flask) untuk menandatangani dokumen PDF (surat keterangan, sertifikat kegiatan, lembar pengesahan laporan) dan memverifikasi keaslian dokumen beserta identitas penandatangan melalui QR-Code.

## Fitur Utama

- Pembangkitan pasangan kunci **RSA 2048-bit dengan skema padding PSS**.
- Kunci privat **disimpan terenkripsi** (PKCS8 + AES, dengan salt/IV dari CSPRNG `os.urandom` melalui pustaka `cryptography`), tidak pernah ditulis dalam bentuk plaintext maupun ditanam di kode sumber.
- Tanda tangan dihitung atas **nilai hash SHA-256** dari konten dokumen PDF.
- Verifikasi menolak dokumen yang **diubah (tamper)** dan tanda tangan dengan **kunci publik yang tidak cocok**.
- **QR-Code** pada dokumen memuat metadata penandatangan (nama, jabatan, tanggal, institusi) beserta hash dokumen dan tautan verifikasi.
- **Fitur pengayaan**: dukungan **beberapa penandatangan (multiple signers)** pada satu dokumen yang sama.

## Struktur Proyek

```
DigitalSignature/
├── app.py
├── requirements.txt
├── .env
├── crypto/        (pembangkitan kunci, penandatanganan, verifikasi)
├── pdf/           (hashing dan penyisipan QR ke PDF)
├── qr/            (pembuatan dan pembacaan QR-Code)
├── templates/     (antarmuka web Tailwind CSS)
├── static/        (CSS & JS pendukung)
├── storage/       (dokumen, kunci, dan data tanda tangan)
└── tests/         (pengujian unit)
```

## Instalasi

1. Pastikan Python 3.10+ terpasang.
2. Buat virtual environment :
   ```
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate         # Windows
   ```
3. Instal dependensi:
   ```
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Sesuaikan isi `.env` sesuai kebutuhan (secret key Flask dan URL verifikasi).

python -m pip install --upgrade pip
pip install -r requirements.txt

```
`requirements.txt` menggunakan batas versi minimum (bukan pin persis) agar pip dapat memilih wheel yang cocok dengan sistem operasi dan versi Python Anda secara otomatis.

## Menjalankan Aplikasi

```

python app.py

```

Aplikasi akan berjalan di `http://localhost:5000`.

Alur penggunaan:
1. Buka `/sign`, buat pasangan kunci RSA baru dengan mengisi nama pemilik dan passphrase.
2. Unggah dokumen PDF, isi data penandatangan (nama, jabatan, institusi, tanggal), lalu tandatangani. Untuk menambahkan penandatangan kedua pada dokumen yang sama, isi kolom **Doc ID** yang diberikan pada hasil penandatanganan sebelumnya.
3. Unduh PDF hasil tanda tangan yang telah memuat QR-Code.
4. Buka `/verify`, unggah PDF tersebut untuk memverifikasi integritas dokumen dan keabsahan seluruh tanda tangan.

## Menjalankan Pengujian

```

pytest tests/ -v -s

```

Cakupan pengujian:
- `test_crypto.py`: ukuran kunci publik, ukuran tanda tangan RSA-2048, serta rata-rata waktu penandatanganan dan verifikasi dari 30 kali percobaan.
- `test_tamper.py`: verifikasi terhadap dokumen yang diubah isinya (harus gagal), pengubahan satu byte pada berkas (harus gagal), dan penggunaan kunci publik yang salah (harus gagal).
- `test_qr.py`: pembuatan dan pembacaan QR-Code, serta deteksi ketidakcocokan metadata QR-Code yang dipalsukan.

## Skenario Pengujian

1. Buat pasangan kunci RSA di halaman `/sign`.
2. Tandatangani sebuah dokumen PDF (misal surat keterangan), unduh hasilnya yang memuat QR-Code.
3. Buka `/verify`, unggah dokumen tersebut → verifikasi **berhasil** (integritas UTUH, tanda tangan VALID).
4. Ubah satu karakter isi dokumen PDF asli (misalnya melalui editor teks/PDF lain), lalu unggah kembali ke `/verify` → verifikasi **gagal** (integritas DIUBAH).
5. Pada form `/verify`, unggah berkas kunci publik (`.pem`) milik pihak lain sebagai *override* → tanda tangan ditampilkan **Tidak Valid** karena kunci tidak cocok.

## Ketentuan Keamanan yang Diterapkan

- Tidak ada kunci, kata sandi, atau kunci privat yang ditulis langsung di kode sumber.
- Seluruh nilai acak kriptografis (kunci RSA, salt, IV enkripsi kunci privat) dibangkitkan melalui CSPRNG bawaan pustaka `cryptography` (berbasis `os.urandom`).
- Tidak digunakan algoritma usang (MD5, SHA-1, DES, RC4, mode ECB) untuk fitur keamanan utama; hash dokumen menggunakan SHA-256 dan tanda tangan menggunakan RSA-PSS.


