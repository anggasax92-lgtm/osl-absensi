#!/usr/bin/env python3
"""
Absensi Karyawan - One Stop Laundry.

App terbuka untuk siapa saja (tanpa login Google): karyawan pilih nama, ketik PIN,
lalu clock in / clock out dengan selfie. Lokasi HP diambil dari browser dan absen
hanya diterima kalau karyawan berada di dalam radius lokasi kerja.
Staff tetap wajib piket kebersihan (3 foto ruangan) sebelum clock out; freelance tidak.
Rekapnya dibaca app OSL (tab Rekap Absensi) dari Google Sheet yang sama.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import os
import time

import streamlit as st

import absensi_store as ab
import loading_icon

st.set_page_config(page_title="Absensi OSL", page_icon="🕒", layout="centered")

st.markdown("""
<style>
:root { --osl-1:#9F2063; --osl-2:#C23B80; --osl-3:#FBF0F5; --osl-ink:#2A0F1D;
        --ok:#16A34A; --bad:#DC2626; --warn:#D97706; --line:#E2E8F0; --muted:#64748B; }
header[data-testid="stHeader"]{background:transparent !important;pointer-events:none;z-index:1000003 !important;}
header[data-testid="stHeader"] *{pointer-events:none;}
[data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"],
[data-testid="stDecoration"], footer {display:none !important;}
.block-container{padding-top:5rem;padding-bottom:3rem;max-width:520px;}
/* bar atas magenta, sama dengan app OSL */
.osl-bar{position:fixed;top:0;left:0;right:0;height:60px;z-index:1000001;background:var(--osl-1);
  box-shadow:0 2px 10px rgba(80,10,45,.25);display:flex;align-items:center;gap:.6rem;
  padding:0 1rem;color:#fff;}
.osl-bar img{height:44px;width:44px;border-radius:50%;background:#fff;padding:2px;}
.osl-bar .t{font-weight:800;font-size:1rem;letter-spacing:.08em;line-height:1.05;white-space:nowrap;}
.osl-bar .t small{display:block;font-size:.6rem;font-weight:700;letter-spacing:.18em;opacity:.85;}
/* What's new + akun di kanan bar */
.st-key-abs_kanan{position:fixed;top:13px;right:1rem;z-index:1000004;width:auto !important;
  flex-wrap:nowrap !important;}
.st-key-abs_kanan button{border-radius:999px !important;min-height:0 !important;padding:.3rem .8rem !important;}
.st-key-abs_kanan button div, .st-key-abs_kanan button span, .st-key-abs_kanan button p{
  overflow:visible !important;max-width:none !important;}
.st-key-abs_kanan button p{white-space:nowrap;font-size:.85rem;}
.st-key-whatsnew button{background:#FDE7F1 !important;border:none !important;}
.st-key-whatsnew button p, .st-key-whatsnew button svg{color:#2A0F1D !important;font-weight:600;}
.st-key-akun button{background:transparent !important;border:1px solid rgba(255,255,255,.85) !important;}
.st-key-akun button p, .st-key-akun button svg{color:#fff !important;}
@media (max-width: 480px){
  .osl-bar .t{display:none;}
  .st-key-whatsnew button p{font-size:0 !important;}
  .st-key-whatsnew button p::after{margin-left:0 !important;}
  .st-key-akun button p{max-width:6.5rem;overflow:hidden;text-overflow:ellipsis;}
}
.osl-hero{background:var(--osl-3);border:1px solid #F1D5E3;color:var(--osl-ink);padding:14px 18px;
  border-radius:14px;margin-bottom:14px;}
.osl-hero .jam{font-size:2.4rem;font-weight:800;line-height:1.05;color:var(--osl-1);}
.osl-hero .tgl{font-size:.9rem;color:var(--muted);margin-top:2px;}
.me{display:flex;align-items:center;gap:12px;}
.avatar{width:46px;height:46px;border-radius:50%;background:var(--osl-1);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.25rem;flex:none;}
.me .nm{font-size:1.15rem;font-weight:700;color:var(--osl-ink);line-height:1.2;}
.me .sub{font-size:.8rem;color:var(--muted);}
.aksi{border-radius:14px;padding:12px 16px;margin:12px 0;color:#fff;font-weight:700;
  display:flex;justify-content:space-between;align-items:center;}
.aksi.in{background:var(--ok);} .aksi.out{background:var(--warn);}
.aksi small{font-weight:500;opacity:.9;font-size:.78rem;display:block;}
.aksi .big{font-size:1.35rem;letter-spacing:.02em;}
.piket{border-radius:14px;padding:12px 16px;margin:12px 0;background:#ECFEFF;
  border:1px solid #A5F3FC;color:#0E3A45;font-size:.92rem;}
.piket b{color:#0E3A45;}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 4px;}
.chip{background:#F1F5F9;border:1px solid var(--line);border-radius:999px;padding:3px 10px;
  font-size:.8rem;color:var(--osl-ink);}
.step{display:flex;align-items:center;gap:10px;margin:18px 0 8px;font-weight:700;color:var(--osl-ink);}
.step .n{width:26px;height:26px;border-radius:50%;background:var(--osl-1);color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:.85rem;flex:none;}
.step .n.done{background:var(--ok);}
.card{background:var(--osl-3);border-radius:12px;padding:12px 14px;margin:4px 0 8px;
  color:var(--osl-ink);font-size:.92rem;border-left:5px solid var(--osl-2);}
.card.ok{border-left-color:var(--ok);background:#F0FDF4;}
.card.bad{border-left-color:var(--bad);background:#FEF2F2;}
.card b{color:var(--osl-ink);}
.done-box{text-align:center;padding:26px 18px;border-radius:18px;margin-top:6px;color:#fff;}
.done-box.in{background:var(--ok);} .done-box.out{background:var(--warn);}
.done-box .ic{font-size:3.2rem;line-height:1;}
.done-box .h{font-size:1.35rem;font-weight:800;margin-top:8px;}
.done-box .jam{font-size:2.4rem;font-weight:800;margin:6px 0;}
.done-box .s{opacity:.95;font-size:.95rem;}
div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] > button{
  min-height:3.1rem;font-size:1.05rem;font-weight:700;border-radius:12px;}
[data-testid="stCameraInput"] video, [data-testid="stCameraInput"] img{border-radius:14px;}
</style>
""", unsafe_allow_html=True)

MAX_TRIES = 5
LOKASI_BASI = 300          # detik; lokasi lebih tua dari ini harus diambil ulang


def _cfg():
    try:
        return ab.cari_config(st.secrets)
    except Exception:
        return "", None, []


@st.cache_resource(show_spinner=False)
def get_store(sheet_id: str):
    return ab.Store(ab.buka_spreadsheet(_cfg()[1], sheet_id))


@st.cache_data(ttl=60, show_spinner=False)
def load_master(sheet_id: str):
    s = get_store(sheet_id)
    return s.karyawan(), s.lokasi()


@st.cache_data(ttl=60, show_spinner=False)
def load_tukar(sheet_id: str):
    try:
        return get_store(sheet_id).tukar_day_off()
    except Exception:
        return []          # jadwal day off hanya informasi; absen tidak boleh macet karenanya


def _logo() -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "osl_logo.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return f"<img src='data:image/png;base64,{base64.b64encode(f.read()).decode()}'/>"


def hero():
    st.markdown(loading_icon.CSS, unsafe_allow_html=True)
    now = ab.now_wib()
    st.markdown(f"<div class='osl-bar'>{_logo()}<div class='t'>ONE STOP<small>LAUNDRY</small></div>"
                "</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='osl-hero'>"
                f"<div class='jam'>{now:%H:%M} <span style='font-size:1rem'>WIB</span></div>"
                f"<div class='tgl'>{ab.tanggal_panjang(now.date())}</div></div>",
                unsafe_allow_html=True)


APP_VERSION = "1.4"
APP_UPDATED = "28 Okt 2026"
CHANGELOG = [
    {"version": "1.4", "date": "28 Okt 2026", "changes": [
        "Piket kebersihan: staff tetap wajib mengirim tepat 3 foto area piketnya sebelum bisa "
        "Clock Out.",
        "Staff freelance (mis. Dani) tetap bisa Clock In / Clock Out tanpa piket.",
        "Hari day off tampil di layar absen (Ayu Sabtu, Ami Senin, Lukman Minggu)."]},
    {"version": "1.3", "date": "22 Okt 2026", "changes": [
        "Ikon loading baru: mesin cuci yang sedang mencuci."]},
    {"version": "1.2", "date": "22 Okt 2026", "changes": [
        "Tampilan ikut logo One Stop Laundry: bar atas magenta berlogo.",
        "Tombol What's new dan nama karyawan yang sedang masuk di kanan atas."]},
    {"version": "1.1", "date": "22 Okt 2026", "changes": [
        "Langkah absen bernomor (lokasi → selfie), jam absen hari ini, layar sukses besar."]},
    {"version": "1.0", "date": "22 Okt 2026", "changes": [
        "Clock in / clock out dengan nama + PIN, lokasi GPS harus di area kerja, wajib selfie."]},
]


def _keluar():
    st.session_state["who"] = None


def bar_kanan():
    st.markdown(f"<style>.st-key-whatsnew button p::after{{content:'v{APP_VERSION}';margin-left:.45rem;"
                "padding:.05rem .45rem;border-radius:999px;background:#9F2063;color:#fff;"
                "font-size:.7rem;font-weight:800;}</style>", unsafe_allow_html=True)
    who = st.session_state.get("who")
    with st.container(horizontal=True, key="abs_kanan", vertical_alignment="center", gap="small",
                      width="content"):
        with st.popover("What's new", key="whatsnew"):
            st.markdown(f"**What's new** · versi {APP_VERSION} · update {APP_UPDATED}")
            for i, rel in enumerate(CHANGELOG):
                st.markdown(f"**v{rel['version']}** · {rel['date']}"
                            + ("  :violet-badge[terbaru]" if i == 0 else ""))
                st.markdown(chr(10).join(f"- {c}" for c in rel["changes"]))
        with st.popover(f"👤 {who.split(' ')[0] if who else 'Belum masuk'}", key="akun"):
            if who:
                st.caption(f"👤 Masuk sebagai **{who}**")
                st.button("Keluar / ganti karyawan", on_click=_keluar, width="stretch",
                          key="btn_keluar")
            else:
                st.caption("Pilih nama dan ketik PIN Anda untuk absen.")


def step(n, judul, selesai=False):
    st.markdown(f"<div class='step'><div class='n{' done' if selesai else ''}'>"
                f"{'✓' if selesai else n}</div>{judul}</div>", unsafe_allow_html=True)


def setup_panel(seen):
    st.error("App absensi belum disambungkan ke Google Sheet.")
    st.caption("Pengelola: isi `gcp_service_account` dan `absensi_sheet_id` di "
               "Streamlit Cloud → Settings → Secrets (lihat README).")
    st.caption("Kunci yang terbaca di Secrets: " + (", ".join(seen) or "(kosong)"))
    st.stop()


hero()
bar_kanan()
SHEET_ID, _CREDS, _SEEN = _cfg()
if not SHEET_ID or not _CREDS:
    setup_panel(_SEEN)

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
ss.setdefault("flash", "")
ss.setdefault("pk_n", 0)

aktif = [k for k in KARYAWAN if ab.is_aktif(k["Aktif"])]

# ------------------------------------------------------------ hasil terakhir
if ss.done:
    d = ss.done
    kls = "in" if d["Jenis"] == ab.IN else "out"
    st.markdown(f"<div class='done-box {kls}'><div class='ic'>✅</div>"
                f"<div class='h'>{ab.LABEL[d['Jenis']]} berhasil</div>"
                f"<div class='jam'>{d['Jam'][:5]}</div>"
                f"<div class='s'><b>{html.escape(d['Nama'])}</b> · {html.escape(d['Lokasi'])}</div></div>",
                unsafe_allow_html=True)
    st.write("")
    if st.button("Selesai", type="primary", width="stretch"):
        ss.done = None
        st.rerun()
    st.caption("Layar dikembalikan ke awal supaya HP ini aman dipakai karyawan lain.")
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
    with st.form("masuk"):
        st.markdown("**Masuk untuk absen**")
        nama = st.selectbox("Nama", [k["Nama"] for k in aktif], index=None,
                            placeholder="Pilih nama Anda")
        pin = st.text_input("PIN", type="password", max_chars=8, placeholder="PIN pribadi")
        if st.form_submit_button("Lanjut →", type="primary", width="stretch"):
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
    st.caption("Lupa PIN? Hubungi pengelola.")
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
hari_ini = [r for r in sorted(milik, key=lambda r: r["_t"]) if r["_t"].date() == ab.now_wib().date()]

top = st.columns([4, 1.3], vertical_alignment="center")
top[0].markdown(f"<div class='me'><div class='avatar'>{html.escape(k['Nama'][:1].upper())}</div>"
                f"<div><div class='nm'>Halo, {html.escape(k['Nama'])} 👋</div>"
                f"<div class='sub'>Pastikan ini nama Anda</div></div></div>",
                unsafe_allow_html=True)
if top[1].button("Ganti", help="Bukan Anda? Kembali ke pilih nama", width="stretch"):
    ss.who = None
    st.rerun()

if hari_ini:
    chips = "".join(f"<span class='chip'>{'🟢 Masuk' if r['Jenis'] == ab.IN else '🟠 Pulang'} "
                    f"{r['_t']:%H:%M}</span>" for r in hari_ini)
    st.markdown(f"<div class='chips'>{chips}</div>", unsafe_allow_html=True)
elif milik:
    last = max(milik, key=lambda r: r["_t"])
    st.caption(f"Absen terakhir: {ab.LABEL[last['Jenis']]} {last['_t']:%d/%m %H:%M}")

sub = "Mulai kerja" if aksi == ab.IN else "Selesai kerja"
st.markdown(f"<div class='aksi {'in' if aksi == ab.IN else 'out'}'>"
            f"<div><small>Yang akan dicatat</small><span class='big'>{ab.LABEL[aksi].upper()}</span></div>"
            f"<div style='font-size:.9rem'>{sub}</div></div>", unsafe_allow_html=True)
if ss.flash:
    st.warning(ss.flash)
    ss.flash = ""

# jadwal day off (informasi saja; absen tetap bisa, rekap yang menandai)
jadwal = ab.status_jadwal(k, ab.now_wib().date(), load_tukar(SHEET_ID))
idx_off = ab.day_off_idx(k)
if jadwal == ab.OFF:
    st.info(f"🛌 Hari ini **day off** Anda (hari {ab.HARI[idx_off]}). Absen tetap bisa dilakukan, "
            "tetapi rekap akan menandainya sebagai masuk di hari day off.")
elif jadwal == ab.SAKIT:
    st.info("🤒 Hari ini tercatat **libur karena sakit** (day off minggu ini sudah dipindah).")
elif idx_off is not None:
    st.caption(f"Day off tetap Anda: hari {ab.HARI[idx_off]}.")
if ab.is_freelance(k):
    st.caption("Anda staff freelance: clock in / clock out tanpa piket kebersihan.")

# piket kebersihan: wajib sebelum clock out (staff tetap)
sn = 1
if aksi == ab.OUT and ab.wajib_piket(k):
    try:
        piket_saya = store.piket(nama=k["Nama"], mulai=ab.now_wib().date() - dt.timedelta(days=2))
    except Exception as e:
        st.error(f"Data piket tidak bisa dibaca ({type(e).__name__}). Coba lagi.")
        st.stop()
    areas = ab.area_piket(k)
    area_txt = " dan ".join(areas) if areas else "area piket Anda"
    if ab.piket_selesai(piket_saya, milik):
        pk = max((p for p in piket_saya), key=lambda p: p["_t"])
        step(sn, f"Piket kebersihan <span style='font-weight:400;color:#64748B;font-size:.85rem'>"
                 f"— tercatat {pk['_t']:%H:%M}</span>", True)
        sn += 1
    else:
        step(sn, "Piket kebersihan")
        st.markdown(f"<div class='piket'>🧹 Sebelum <b>Clock Out</b>, lakukan piket di <b>{html.escape(area_txt)}</b> "
                    f"lalu foto hasilnya. Wajib tepat <b>{ab.JUMLAH_FOTO_PIKET} foto</b> "
                    "(foto langsung dari kamera).</div>", unsafe_allow_html=True)
        fotos_pk = []
        for i in range(ab.JUMLAH_FOTO_PIKET):
            f = st.camera_input(f"Foto piket {i + 1} dari {ab.JUMLAH_FOTO_PIKET}",
                                key=f"pk_{ss.pk_n}_{i}")
            fotos_pk.append(f)
            if f is None:
                break                      # kamera berikutnya baru muncul setelah foto ini diambil
        lengkap = len(fotos_pk) == ab.JUMLAH_FOTO_PIKET and all(f is not None for f in fotos_pk)
        if not lengkap:
            st.caption(f"Foto terambil: {sum(f is not None for f in fotos_pk)} dari "
                       f"{ab.JUMLAH_FOTO_PIKET}. Clock Out terbuka setelah piket terkirim.")
        if st.button(f"{'📤' if lengkap else '🔒'} Kirim piket", type="primary", width="stretch",
                     disabled=not lengkap, key="btn_piket"):
            with st.spinner("Menyimpan foto piket…"):
                terbaru = store.piket(nama=k["Nama"], mulai=ab.now_wib().date() - dt.timedelta(days=2))
                if not ab.piket_selesai(terbaru, store.catatan(nama=k["Nama"])):
                    store.tambah_piket(nama=k["Nama"], area=", ".join(areas),
                                       fotos_b64=[ab.kecilkan_foto_piket(f.getvalue())
                                                  for f in fotos_pk])
            ss.pk_n += 1
            ss.flash = "Piket tercatat. Silakan lanjut Clock Out."
            st.rerun()
        st.stop()

# lokasi dari browser
from streamlit_js_eval import streamlit_js_eval  # noqa: E402

GEO_JS = ("new Promise(r=>{if(!navigator.geolocation){r({error:'Browser tidak mendukung lokasi'});return;}"
          "navigator.geolocation.getCurrentPosition("
          "p=>r({lat:p.coords.latitude,lon:p.coords.longitude,acc:p.coords.accuracy}),"
          "e=>r({error:e.code+': '+e.message}),"
          "{enableHighAccuracy:true,timeout:20000,maximumAge:0});})")

geo = streamlit_js_eval(js_expressions=GEO_JS, key=f"geo_{ss.geo_n}")
geo_key = f"geo_t_{ss.geo_n}"
boleh_lokasi = False
lok_info = None
pesan_lokasi = None
if geo is None:
    pesan_lokasi = ("", "📍 Mengambil lokasi… Kalau browser bertanya, pilih <b>Izinkan / Allow</b>.")
elif isinstance(geo, dict) and geo.get("error"):
    pesan_lokasi = ("bad", f"⛔ Lokasi tidak bisa diambil ({html.escape(str(geo['error']))}).<br>"
                           "Nyalakan GPS dan izinkan akses lokasi untuk situs ini (ikon gembok di "
                           "samping alamat), lalu tekan <b>Ambil ulang lokasi</b>.")
else:
    ss.setdefault(geo_key, time.time())
    lat, lon, acc = float(geo["lat"]), float(geo["lon"]), float(geo.get("acc") or 0)
    tempat, jarak, inside = ab.cek_lokasi(lat, lon, ab.lokasi_karyawan(k, LOKASI))
    if tempat is None:
        pesan_lokasi = ("bad", "⛔ Belum ada lokasi kerja untuk Anda. Hubungi pengelola.")
    elif inside:
        boleh_lokasi = True
        lok_info = (tempat, jarak, lat, lon, acc)
        pesan_lokasi = ("ok", f"✅ Anda di <b>{html.escape(tempat['Nama Lokasi'])}</b><br>"
                              f"<small>± {ab.fmt_m(jarak)} m dari titik · akurasi GPS ± {ab.fmt_m(acc)} m</small>")
    else:
        saran = ("<br><small>Akurasi GPS sedang rendah. Pindah ke dekat pintu/jendela, tunggu "
                 "sebentar, lalu ambil ulang lokasi.</small>" if acc > tempat["Radius (m)"] else "")
        pesan_lokasi = ("bad", f"⛔ Anda di luar lokasi kerja.<br><small>Terdekat: "
                               f"<b>{html.escape(tempat['Nama Lokasi'])}</b>, jarak ± {ab.fmt_m(jarak)} m "
                               f"(batas {ab.fmt_m(tempat['Radius (m)'])} m)</small>{saran}")

step(sn, "Lokasi", boleh_lokasi)
st.markdown(f"<div class='card {pesan_lokasi[0]}'>{pesan_lokasi[1]}</div>", unsafe_allow_html=True)
if not boleh_lokasi and st.button("🔄 Ambil ulang lokasi", width="stretch"):
    ss.geo_n += 1
    st.rerun()

ua = streamlit_js_eval(js_expressions="navigator.userAgent", key="ua") or ""

foto = None
if boleh_lokasi:
    step(sn + 1, "Selfie", False)
    foto = st.camera_input("Ambil selfie (wajah terlihat jelas)", key=f"cam_{ss.cam_n}",
                           label_visibility="collapsed")
    if foto is None:
        st.caption("Arahkan kamera ke wajah Anda lalu tekan **Take Photo**.")
else:
    step(sn + 1, "Selfie <span style='font-weight:400;color:#64748B;font-size:.85rem'>"
            "— muncul setelah lokasi sesuai</span>")

siap = boleh_lokasi and foto is not None
st.write("")
if st.button(f"{'✅' if siap else '🔒'} {ab.LABEL[aksi]} sekarang", type="primary",
             width="stretch", disabled=not siap):
    if time.time() - ss.get(geo_key, 0) > LOKASI_BASI:
        ss.flash = "Lokasi sudah lebih dari 5 menit, jadi diambil ulang. Silakan tekan tombol lagi."
        ss.geo_n += 1
        st.rerun()
    tempat, jarak, lat, lon, acc = lok_info
    with st.spinner("Menyimpan absen…"):
        milik = store.catatan(nama=k["Nama"])           # cek ulang, jangan pakai data lama
        aksi = ab.aksi_berikutnya(milik)
        if aksi == ab.OUT and ab.wajib_piket(k) and not ab.piket_selesai(
                store.piket(nama=k["Nama"], mulai=ab.now_wib().date() - dt.timedelta(days=2)), milik):
            ss.flash = "Piket kebersihan belum tercatat. Selesaikan piket dulu sebelum Clock Out."
            st.rerun()
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
