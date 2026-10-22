# Absensi Karyawan — One Stop Laundry

App Streamlit terbuka (tanpa login) untuk **clock in / clock out** karyawan:

1. Karyawan pilih nama + ketik **PIN** pribadi.
2. Lokasi HP diambil dari browser (GPS). Absen hanya bisa kalau berada di dalam
   **radius lokasi kerja** yang boleh untuknya.
3. **Selfie** lewat kamera (bukan dari galeri), dikecilkan lalu disimpan.
4. App otomatis menentukan *Clock In* atau *Clock Out* (clock in terakhir < 20 jam lalu → Clock Out).

Semua data masuk ke satu **Google Sheet** dan direkap di app OSL
(`osl-invoice-web`) tab **🕒 Rekap Absensi** — di sana juga daftar karyawan, PIN,
dan titik lokasi kerja diatur.

## File
| File | Isi |
|---|---|
| `app.py` | Halaman absensi (mobile-first) |
| `absensi_store.py` | Logika + akses Google Sheet. **Sama persis** dengan file di repo `osl-invoice-web`; kalau diubah, salin ke sana. |
| `tests/` | `python tests/test_absensi_store.py` (pakai Sheet tiruan, tanpa Google) |

## Isi Google Sheet (dibuat otomatis)
- `Karyawan`: Nama · PIN · Lokasi (`Semua` atau nama lokasi dipisah koma) · Aktif (`Ya`/`Tidak`)
- `Lokasi`: Nama Lokasi · Latitude · Longitude · Radius (m)
- `Absensi`: ID · Waktu · Tanggal · Jam · Nama · Jenis (IN/OUT) · Lokasi · Latitude · Longitude ·
  Akurasi (m) · Jarak (m) · Perangkat · Foto (JPEG base64 ±10-30 KB)

## Setup (sekali)
1. Buat Google Sheet kosong, mis. *Absensi OSL*. **Share** ke `client_email` service account sebagai **Editor**.
2. Streamlit Cloud → **Create app** → repo `anggasax92-lgtm/osl-absensi`, branch `main`, file `app.py`.
3. **Settings → Secrets** (isi yang sama juga ditempel di Secrets app OSL):
   ```toml
   absensi_sheet_id = "ID Sheet (di antara /d/ dan /edit pada URL)"

   [gcp_service_account]
   ... isi JSON service account ...
   ```
   Di app OSL boleh ditambah `absensi_app_url = "https://....streamlit.app"` supaya link absensi tampil di tab Rekap.
4. **Share → Make this app public** supaya karyawan bisa membuka tanpa akun.
5. Di app OSL → Rekap Absensi → *Karyawan & Lokasi*: isi lokasi laundry + karyawan + PIN.

## Catatan keamanan
- Lokasi berasal dari HP karyawan; aplikasi *fake GPS* bisa memalsukannya. Selfie + jarak +
  akurasi GPS di setiap catatan membantu memeriksa kejanggalan.
- PIN salah 5x → halaman terkunci sampai dibuka ulang. Tidak ada data rahasia selain PIN di Sheet,
  dan Sheet hanya bisa dibaca pemilik + service account.
