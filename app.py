#!/usr/bin/env python3
"""
Absensi Karyawan - One Stop Laundry.

App terbuka untuk siapa saja (tanpa login Google): karyawan pilih nama, ketik PIN,
lalu clock in / clock out dengan selfie. Lokasi HP diambil dari browser dan absen
hanya diterima kalau karyawan berada di dalam radius lokasi kerja.
Rekapnya dibaca app OSL (tab Rekap Absensi) dari Google Sheet yang sama.
"""
from __future__ import annotations

import time

import streamlit as st

import absensi_store as ab

st.set_page_config(page_title="Absensi OSL", page_icon="🕒", layout="centered")

st.markdown("""
<style>
:root { --osl-1:#0E7490; --osl-2:#0891B2; --osl-3:#ECFEFF; --osl-ink:#0F2B33; }
.block-container{padding-top:2.2rem;max-width:560px;}
.osl-hero{background:linear-gradient(120deg,var(--osl-1) 0%,var(--osl-2) 100%);
  color:#fff;padding:18px 20px;border-radius:16px;margin-bottom:16px;}
.osl-hero h1{margin:0;font-size:1.35rem;line-height:1.2;color:#fff;}
.osl-hero p{margin:4px 0 0;opacity:.92;font-size:.9rem;}
.jam{font-size:2.1rem;font-weight:700;color:var(--osl-ink);line-height:1.1;}
.card{background:var(--osl-3);border-radius:12px;padding:12px 14px;margin:8px 0 12px;
  color:var(--osl-ink);font-size:.92rem;}
.card b{color:var(--osl-1);}
.ok{border-left:5px solid #16A34A;} .bad{border-left:5px solid #DC2626;}
.warn{border-left:5px solid #F59E0B;}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='osl-hero'><h1>🕒 Absensi Karyawan</h1>"
            "<p>One Stop Laundry &middot; clock in / clock out dengan selfie di lokasi kerja</p>"
            "</div>", unsafe_allow_html=True)

MAX_TRIES = 5
LOKASI_BASI = 300          # detik; lokasi lebih tua dari ini harus diambil ulang


def secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


@st.cache_resource(show_spinner=False)
def get_store(sheet_id: str):
    return ab.Store(ab.buka_spreadsheet(dict(secret("gcp_service_account")), sheet_id))


@st.cache_data(ttl=60, show_spinner=False)
def load_master(sheet_id: str):
    s = get_store(sheet_id)
    return s.karyawan(), s.lokasi()


def setup_panel():
    st.error("App absensi belum disambungkan ke Google Sheet.")
    st.caption("Pengelola: isi `gcp_service_account` dan `absensi_sheet_id` di "
               "Streamlit Cloud → Settings → Secrets (lihat README).")
    st.stop()


SHEET_ID = str(secret("absensi_sheet_id", "") or "").strip()
if not SHEET_ID or not secret("gcp_service_account"):
    setup_panel()

try:
    KARYAWAN, LOKASI = load_master(SHEET_ID)
except Exception as e:
    st.error(f"Google Sheet absensi tidak bisa dibaca ({type(e).__name__}). Coba lagi sebentar.")
    st.stop()

ss = st.session_state
ss.setdefault("who", None)
ss.setdefault("tries", 0)
ss.setdefault("geo_n", 0)
ss.setdefault("cam_n", 0)
ss.setdefault("done", None)

aktif = [k for k in KARYAWAN if ab.is_aktif(k["Aktif"])]

# ------------------------------------------------------------ hasil terakhir
if ss.done:
    d = ss.done
    st.success(f"✅ {ab.LABEL[d['Jenis']]} berhasil — **{d['Nama']}**, "
               f"{d['Jam']} WIB di {d['Lokasi']}.")
    st.caption("Layar dikembalikan ke awal supaya HP ini aman dipakai karyawan lain.")
    if st.button("Selesai", type="primary", width="stretch"):
        ss.done = None
        st.rerun()
    st.stop()

# ------------------------------------------------------------- langkah 1: masuk
if ss.who is None:
    if not aktif:
        st.warning("Belum ada karyawan terdaftar. Pengelola menambahkannya di app OSL → Rekap Absensi.")
        st.stop()
    if not LOKASI:
        st.warning("Lokasi kerja belum diisi. Pengelola mengisinya di app OSL → Rekap Absensi.")
        st.stop()
    if ss.tries >= MAX_TRIES:
        st.error("Terlalu banyak PIN salah. Tutup halaman ini lalu buka lagi, "
                 "atau hubungi pengelola.")
        st.stop()
    st.markdown(f"<div class='jam'>{ab.now_wib():%H:%M} WIB</div>", unsafe_allow_html=True)
    st.caption(ab.tanggal_panjang(ab.now_wib().date()))
    with st.form("masuk"):
        nama = st.selectbox("Nama", [k["Nama"] for k in aktif], index=None,
                            placeholder="Pilih nama Anda")
        pin = st.text_input("PIN", type="password", max_chars=8, placeholder="PIN pribadi")
        if st.form_submit_button("Lanjut", type="primary", width="stretch"):
            k = next((x for x in aktif if x["Nama"] == nama), None)
            if k is None:
                st.error("Pilih nama terlebih dahulu.")
            elif not str(k["PIN"]).strip():
                st.error("PIN Anda belum dibuat. Minta pengelola mengisinya.")
            elif ab.pin_cocok(pin, k["PIN"]):
                ss.who, ss.tries = k["Nama"], 0
                ss.geo_n += 1
                st.rerun()
            else:
                ss.tries += 1
                time.sleep(1)
                st.error(f"PIN salah ({ss.tries}/{MAX_TRIES}).")
    st.stop()

# --------------------------------------------------------- langkah 2: absen
k = next((x for x in aktif if x["Nama"] == ss.who), None)
if k is None:
    ss.who = None
    st.rerun()

store = get_store(SHEET_ID)
try:
    milik = store.catatan(nama=k["Nama"])
except Exception as e:
    st.error(f"Riwayat absen tidak bisa dibaca ({type(e).__name__}). Coba lagi.")
    st.stop()
aksi = ab.aksi_berikutnya(milik)

top = st.columns([3, 1])
top[0].markdown(f"#### Halo, {k['Nama']} 👋")
if top[1].button("Ganti", help="Bukan Anda? Kembali ke pilih nama"):
    ss.who = None
    st.rerun()

if milik:
    last = max(milik, key=lambda r: r["_t"])
    st.caption(f"Absen terakhir: {ab.LABEL[last['Jenis']]} {last['_t']:%d/%m %H:%M} "
               f"di {last['Lokasi']}")
st.markdown(f"<div class='card'>Yang akan dicatat sekarang: <b>{ab.LABEL[aksi].upper()}</b></div>",
            unsafe_allow_html=True)

# lokasi dari browser
from streamlit_js_eval import streamlit_js_eval  # noqa: E402

GEO_JS = ("new Promise(r=>{if(!navigator.geolocation){r({error:'Browser tidak mendukung lokasi'});return;}"
          "navigator.geolocation.getCurrentPosition("
          "p=>r({lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy}),"
          "e=>r({error:e.code+': '+e.message}),"
          "{enableHighAccuracy:true,timeout:20000,maximumAge:0});})")

st.markdown("**1. Lokasi**")
geo = streamlit_js_eval(js_expressions=GEO_JS, key=f"geo_{ss.geo_n}")
geo_key = f"geo_t_{ss.geo_n}"
boleh_lokasi = False
lok_info = None
if geo is None:
    st.info("📍 Mengambil lokasi… Kalau browser bertanya, pilih **Izinkan / Allow**.")
elif isinstance(geo, dict) and geo.get("error"):
    st.error(f"Lokasi tidak bisa diambil ({geo['error']}).")
    st.caption("Nyalakan GPS/Lokasi di HP dan izinkan akses lokasi untuk situs ini "
               "(ikon gembok di samping alamat), lalu tekan Ambil ulang lokasi.")
else:
    ss.setdefault(geo_key, time.time())
    lat, lon, acc = float(geo["lat"]), float(geo["lon"]), float(geo.get("acc") or 0)
    tempat, jarak, inside = ab.cek_lokasi(lat, lon, ab.lokasi_karyawan(k, LOKASI))
    if tempat is None:
        st.error("Belum ada lokasi kerja untuk Anda. Hubungi pengelola.")
    elif inside:
        boleh_lokasi = True
        lok_info = (tempat, jarak, lat, lon, acc)
        st.markdown(f"<div class='card ok'>✅ Anda di <b>{tempat['Nama Lokasi']}</b> "
                    f"(± {ab.fmt_m(jarak)} m dari titik, akurasi GPS ± {ab.fmt_m(acc)} m)</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='card bad'>⛔ Anda di luar lokasi kerja. Terdekat: "
                    f"<b>{tempat['Nama Lokasi']}</b>, jarak ± {ab.fmt_m(jarak)} m "
                    f"(batas {ab.fmt_m(tempat['Radius (m)'])} m). Akurasi GPS ± {ab.fmt_m(acc)} m.</div>",
                    unsafe_allow_html=True)
        if acc > tempat["Radius (m)"]:
            st.caption("Akurasi GPS sedang rendah. Pindah ke dekat jendela/luar ruangan, "
                       "tunggu sebentar, lalu ambil ulang lokasi.")
if st.button("🔄 Ambil ulang lokasi"):
    ss.geo_n += 1
    st.rerun()

ua = streamlit_js_eval(js_expressions="navigator.userAgent", key="ua") or ""

st.markdown("**2. Selfie**")
foto = st.camera_input("Ambil selfie (wajah terlihat jelas)", key=f"cam_{ss.cam_n}",
                       label_visibility="collapsed")

siap = boleh_lokasi and foto is not None
if st.button(f"✅ {ab.LABEL[aksi]} sekarang", type="primary", width="stretch", disabled=not siap):
    if time.time() - ss.get(geo_key, 0) > LOKASI_BASI:
        st.warning("Lokasi sudah lebih dari 5 menit. Lokasi diambil ulang, silakan tekan lagi.")
        ss.geo_n += 1
        st.rerun()
    tempat, jarak, lat, lon, acc = lok_info
    with st.spinner("Menyimpan absen…"):
        milik = store.catatan(nama=k["Nama"])           # cek ulang, jangan pakai data lama
        aksi = ab.aksi_berikutnya(milik)
        if ab.terlalu_cepat(milik):
            st.warning("Anda baru saja absen kurang dari 1 menit lalu.")
            st.stop()
        rec = store.tambah_catatan(nama=k["Nama"], jenis=aksi, lokasi=tempat["Nama Lokasi"],
                                   lat=lat, lon=lon, akurasi=acc, jarak=jarak, perangkat=ua,
                                   foto_b64=ab.kecilkan_selfie(foto.getvalue()))
    ss.done = rec
    ss.who = None
    ss.cam_n += 1
    st.rerun()
if not siap:
    st.caption("Tombol aktif setelah lokasi Anda di dalam area kerja dan selfie sudah diambil.")
