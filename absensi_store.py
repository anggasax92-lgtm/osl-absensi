"""
Penyimpanan & logika absensi One Stop Laundry (dipakai bersama).

File ini SAMA PERSIS di dua repo:
  - osl-absensi      (app absensi karyawan: clock in / clock out)
  - osl-invoice-web  (tab Rekap Absensi di app OSL)
Kalau mengubah salah satu, salin ke repo lainnya.

Semua data ada di SATU Google Sheet (milik Gmail pemilik, dibagikan sebagai
Editor ke service account). Tab-tab dibuat otomatis kalau belum ada:
  Karyawan : Nama | PIN | Lokasi | Aktif
  Lokasi   : Nama Lokasi | Latitude | Longitude | Radius (m)
  Absensi  : satu baris per clock in / clock out, selfie (JPEG kecil, base64)
             di kolom paling kanan supaya rekap bisa dibaca tanpa foto.
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import math
import re
import uuid

WIB = dt.timezone(dt.timedelta(hours=7), "WIB")

SHEET_KARYAWAN = "Karyawan"
HEAD_KARYAWAN = ["Nama", "PIN", "Lokasi", "Aktif"]
SHEET_LOKASI = "Lokasi"
HEAD_LOKASI = ["Nama Lokasi", "Latitude", "Longitude", "Radius (m)"]
SHEET_ABSEN = "Absensi"
HEAD_ABSEN = ["ID", "Waktu", "Tanggal", "Jam", "Nama", "Jenis", "Lokasi",
              "Latitude", "Longitude", "Akurasi (m)", "Jarak (m)", "Perangkat", "Foto"]
COL_FOTO = "M"               # kolom Foto = kolom ke-13
RANGE_TANPA_FOTO = "A:L"

IN, OUT = "IN", "OUT"
LABEL = {IN: "Clock In", OUT: "Clock Out"}
DEFAULT_RADIUS = 100         # meter
MAX_SHIFT_HOURS = 20         # IN tanpa OUT lebih lama dari ini = lupa clock out
MIN_GAP_SECONDS = 60         # cegah tombol tertekan dua kali
MAX_FOTO_CHARS = 45_000      # batas sel Google Sheet 50.000 karakter
SEMUA = "semua"


# ----------------------------------------------------------------- waktu
def now_wib() -> dt.datetime:
    return dt.datetime.now(WIB)


def fmt_waktu(t: dt.datetime) -> str:
    return t.astimezone(WIB).strftime("%Y-%m-%d %H:%M:%S")


HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]


def tanggal_panjang(d: dt.date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def parse_waktu(s) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(str(s).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=WIB)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- angka
def to_float(x) -> float | None:
    """Terima 106.8, '106.8', '106,8' (koma desimal) atau '-6,2'."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(float(x)) else None
    s = str(x).strip().replace(" ", "")
    if not s:
        return None
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse_koordinat(text) -> tuple[float, float] | None:
    """'-6.2088, 106.8456' (format salin dari Google Maps) -> (lat, lon)."""
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(text or ""))
    if len(nums) != 2:
        return None
    lat, lon = float(nums[0]), float(nums[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def fmt_m(x) -> str:
    """1234.5 -> '1.235' (pemisah ribuan titik, gaya Indonesia)."""
    return f"{float(x):,.0f}".replace(",", ".")


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def norm_pin(p) -> str:
    s = re.sub(r"\D", "", str(p if p is not None else ""))
    return s.lstrip("0") or ("0" if s else "")


def pin_cocok(ketik, tersimpan) -> bool:
    a, b = norm_pin(ketik), norm_pin(tersimpan)
    return bool(a) and a == b


def is_aktif(v) -> bool:
    return str(v or "").strip().lower() not in ("tidak", "no", "n", "false", "0", "nonaktif", "keluar")


# ---------------------------------------------------------------- lokasi
def lokasi_karyawan(karyawan: dict, lokasi: list[dict]) -> list[dict]:
    """Lokasi yang boleh dipakai karyawan ini (kolom Lokasi kosong/'Semua' = semua)."""
    raw = str(karyawan.get("Lokasi") or "").strip()
    if not raw or raw.lower() == SEMUA:
        return list(lokasi)
    mau = {x.strip().lower() for x in raw.split(",") if x.strip()}
    return [l for l in lokasi if str(l["Nama Lokasi"]).strip().lower() in mau]


def cek_lokasi(lat, lon, lokasi: list[dict]):
    """-> (lokasi_terdekat | None, jarak_m | None, di_dalam_radius)."""
    best, best_d = None, None
    for l in lokasi:
        d = haversine_m(lat, lon, l["Latitude"], l["Longitude"])
        if best_d is None or d < best_d:
            best, best_d = l, d
    inside = best is not None and best_d <= best["Radius (m)"]
    return best, best_d, inside


# ------------------------------------------------------------------ foto
def kecilkan_selfie(raw: bytes, sisi=360) -> str:
    """JPEG kecil -> base64 yang muat di satu sel Google Sheet."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    for side, q in ((sisi, 70), (sisi, 55), (300, 50), (240, 45), (200, 40)):
        tmp = im.copy()
        tmp.thumbnail((side, side))
        buf = io.BytesIO()
        tmp.save(buf, "JPEG", quality=q, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if len(b64) <= MAX_FOTO_CHARS:
            return b64
    return b64


def foto_bytes(b64) -> bytes | None:
    try:
        return base64.b64decode(str(b64)) if b64 else None
    except Exception:
        return None


# ------------------------------------------------------------- aturan absen
def aksi_berikutnya(catatan_orang: list[dict], now: dt.datetime | None = None) -> str:
    """IN kalau belum ada shift terbuka; OUT kalau clock in terakhir < MAX_SHIFT_HOURS lalu."""
    now = now or now_wib()
    if not catatan_orang:
        return IN
    last = max(catatan_orang, key=lambda r: r["_t"])
    if last["Jenis"] == IN and now - last["_t"] < dt.timedelta(hours=MAX_SHIFT_HOURS):
        return OUT
    return IN


def terlalu_cepat(catatan_orang: list[dict], now: dt.datetime | None = None) -> bool:
    now = now or now_wib()
    if not catatan_orang:
        return False
    last = max(r["_t"] for r in catatan_orang)
    return (now - last).total_seconds() < MIN_GAP_SECONDS


def pasangkan_shift(catatan: list[dict]) -> list[dict]:
    """Catatan mentah -> satu baris per shift (IN dipasangkan dengan OUT berikutnya)."""
    out = []
    per_orang: dict[str, list[dict]] = {}
    for r in catatan:
        per_orang.setdefault(r["Nama"], []).append(r)

    def shift(nama, i, o, ket=""):
        t0 = i["_t"] if i else None
        t1 = o["_t"] if o else None
        jam = round((t1 - t0).total_seconds() / 3600, 2) if (t0 and t1) else None
        return {"Tanggal": (t0 or t1).date(), "Nama": nama,
                "Clock In": t0, "Clock Out": t1, "Durasi (jam)": jam,
                "Lokasi In": i["Lokasi"] if i else "", "Lokasi Out": o["Lokasi"] if o else "",
                "Keterangan": ket, "_id_in": i["ID"] if i else "", "_id_out": o["ID"] if o else ""}

    for nama, rows in per_orang.items():
        buka = None
        for r in sorted(rows, key=lambda x: x["_t"]):
            if r["Jenis"] == IN:
                if buka is not None:
                    out.append(shift(nama, buka, None, "Tanpa clock out"))
                buka = r
            else:
                if buka is not None and r["_t"] - buka["_t"] <= dt.timedelta(hours=MAX_SHIFT_HOURS):
                    out.append(shift(nama, buka, r))
                else:
                    if buka is not None:
                        out.append(shift(nama, buka, None, "Tanpa clock out"))
                    out.append(shift(nama, None, r, "Tanpa clock in"))
                buka = None
        if buka is not None:
            ket = ("Belum clock out" if now_wib() - buka["_t"] < dt.timedelta(hours=MAX_SHIFT_HOURS)
                   else "Tanpa clock out")
            out.append(shift(nama, buka, None, ket))
    out.sort(key=lambda s: (s["Tanggal"], s["Nama"], s["Clock In"] or s["Clock Out"]))
    return out


# ------------------------------------------------------------- Secrets
def _as_dict(x) -> dict | None:
    try:
        return {k: x[k] for k in x.keys()}
    except Exception:
        return None


def cari_config(secrets) -> tuple[str, dict | None, list[str]]:
    """Cari absensi_sheet_id + kredensial service account di Secrets, di mana pun letaknya.

    Kunci yang tertempel di bawah judul [..] lain (salah urutan di kotak Secrets) tetap
    ditemukan. -> (sheet_id, creds | None, daftar nama kunci yang terbaca)."""
    top = _as_dict(secrets) or {}
    seen, sid, creds = [], "", None

    def is_creds(d):
        return isinstance(d, dict) and d.get("client_email") and d.get("private_key")

    for k, v in top.items():
        sub = _as_dict(v) if not isinstance(v, (str, int, float, bool)) else None
        seen.append(f"[{k}]" if sub is not None else k)
        if k == "absensi_sheet_id" and str(v).strip():
            sid = str(v).strip()
        if sub is not None:
            if not sid and str(sub.get("absensi_sheet_id") or "").strip():
                sid = str(sub["absensi_sheet_id"]).strip()
            if is_creds(sub) and (creds is None or k == "gcp_service_account"):
                creds = {kk: vv for kk, vv in sub.items() if kk != "absensi_sheet_id"}
    if creds is None and is_creds(top):
        creds = {k: v for k, v in top.items() if k != "absensi_sheet_id"}
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", sid)       # URL lengkap ikut ditempel
    if m:
        sid = m.group(1)
    return sid, creds, seen


# --------------------------------------------------------- Google Sheet
def buka_spreadsheet(creds_info: dict, sheet_id: str):
    import gspread
    gc = gspread.service_account_from_dict(dict(creds_info))
    return gc.open_by_key(sheet_id)


def _rows_to_dicts(values: list[list], head: list[str]) -> list[dict]:
    out = []
    for i, row in enumerate(values[1:], start=2):
        if not any(str(c).strip() for c in row):
            continue
        row = list(row) + [""] * (len(head) - len(row))
        d = dict(zip(head, row))
        d["_row"] = i
        out.append(d)
    return out


class Store:
    """Pembungkus tipis gspread.Spreadsheet (atau tiruan di tes)."""

    def __init__(self, spreadsheet):
        self.sh = spreadsheet
        self._ws = {}

    def ws(self, title: str, head: list[str]):
        if title in self._ws:
            return self._ws[title]
        try:
            w = self.sh.worksheet(title)
        except Exception as e:
            if type(e).__name__ != "WorksheetNotFound":
                raise
            w = self.sh.add_worksheet(title=title, rows=1000, cols=len(head))
            w.update([head], "A1", value_input_option="RAW")
        if not w.row_values(1):
            w.update([head], "A1", value_input_option="RAW")
        self._ws[title] = w
        return w

    # ---- master
    def karyawan(self) -> list[dict]:
        rows = _rows_to_dicts(self.ws(SHEET_KARYAWAN, HEAD_KARYAWAN).get_all_values(), HEAD_KARYAWAN)
        out = []
        for r in rows:
            nama = str(r["Nama"]).strip()
            if nama:
                out.append({"Nama": nama, "PIN": str(r["PIN"]).strip(),
                            "Lokasi": str(r["Lokasi"]).strip(),
                            "Aktif": str(r["Aktif"]).strip() or "Ya"})
        return out

    def lokasi(self) -> list[dict]:
        rows = _rows_to_dicts(self.ws(SHEET_LOKASI, HEAD_LOKASI).get_all_values(), HEAD_LOKASI)
        out = []
        for r in rows:
            nama = str(r["Nama Lokasi"]).strip()
            lat, lon = to_float(r["Latitude"]), to_float(r["Longitude"])
            if not nama or lat is None or lon is None:
                continue
            rad = to_float(r["Radius (m)"]) or DEFAULT_RADIUS
            out.append({"Nama Lokasi": nama, "Latitude": lat, "Longitude": lon, "Radius (m)": rad})
        return out

    def _tulis_ulang(self, title, head, rows: list[list]):
        w = self.ws(title, head)
        w.batch_clear(["A2:Z"])
        if rows:
            w.update(rows, "A2", value_input_option="RAW")

    def simpan_karyawan(self, rows: list[dict]):
        self._tulis_ulang(SHEET_KARYAWAN, HEAD_KARYAWAN,
                          [[r["Nama"], str(r.get("PIN") or ""), r.get("Lokasi") or "Semua",
                            r.get("Aktif") or "Ya"] for r in rows])

    def simpan_lokasi(self, rows: list[dict]):
        self._tulis_ulang(SHEET_LOKASI, HEAD_LOKASI,
                          [[r["Nama Lokasi"], r["Latitude"], r["Longitude"],
                            r.get("Radius (m)") or DEFAULT_RADIUS] for r in rows])

    # ---- catatan absen
    def catatan(self, nama: str | None = None, mulai: dt.date | None = None,
                sampai: dt.date | None = None) -> list[dict]:
        """Semua catatan TANPA foto (cepat). `_row` = nomor baris di Sheet."""
        vals = self.ws(SHEET_ABSEN, HEAD_ABSEN).get(RANGE_TANPA_FOTO)
        out = []
        for r in _rows_to_dicts(vals, HEAD_ABSEN[:-1]):
            t = parse_waktu(r["Waktu"])
            if t is None or r["Jenis"] not in (IN, OUT):
                continue
            if nama is not None and r["Nama"] != nama:
                continue
            if mulai and t.date() < mulai:
                continue
            if sampai and t.date() > sampai:
                continue
            r["_t"] = t
            for k in ("Latitude", "Longitude", "Akurasi (m)", "Jarak (m)"):
                r[k] = to_float(r[k])
            out.append(r)
        return out

    def tambah_catatan(self, *, nama, jenis, lokasi, lat, lon, akurasi, jarak,
                       perangkat, foto_b64, waktu: dt.datetime | None = None) -> dict:
        t = waktu or now_wib()
        row = [uuid.uuid4().hex[:10], fmt_waktu(t), t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S"),
               nama, jenis, lokasi, round(lat, 6), round(lon, 6),
               round(akurasi or 0, 1), round(jarak or 0, 1), str(perangkat or "")[:200], foto_b64]
        self.ws(SHEET_ABSEN, HEAD_ABSEN).append_row(row, value_input_option="RAW",
                                                    insert_data_option="INSERT_ROWS")
        return dict(zip(HEAD_ABSEN, row))

    def foto(self, row_numbers: list[int]) -> dict[int, str]:
        """Ambil selfie hanya untuk baris yang diminta -> {nomor_baris: base64}."""
        if not row_numbers:
            return {}
        w = self.ws(SHEET_ABSEN, HEAD_ABSEN)
        rows = sorted(set(int(r) for r in row_numbers))
        res = w.batch_get([f"{COL_FOTO}{r}" for r in rows])
        out = {}
        for r, vr in zip(rows, res):
            try:
                out[r] = vr[0][0]
            except (IndexError, TypeError):
                pass
        return out
