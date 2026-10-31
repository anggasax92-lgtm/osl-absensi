import datetime as dt
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import absensi_store as ab  # noqa: E402
from fake_sheet import FakeSpreadsheet  # noqa: E402

LOK = [{"Nama Lokasi": "OSL Pusat", "Latitude": -6.2, "Longitude": 106.8, "Radius (m)": 100},
       {"Nama Lokasi": "OSL Cabang", "Latitude": -6.3, "Longitude": 106.9, "Radius (m)": 150}]
_N = [0]


def t(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ab.WIB)


def rec(nama, jenis, s, lok="OSL Pusat"):
    _N[0] += 1
    return {"ID": str(_N[0]), "Nama": nama, "Jenis": jenis, "_t": t(s), "Lokasi": lok}


def test_angka_dan_koordinat():
    assert ab.to_float("-6,25") == -6.25
    assert ab.to_float("106.8") == 106.8
    assert ab.to_float("") is None and ab.to_float("abc") is None
    assert ab.parse_koordinat("-6.208763, 106.845599") == (-6.208763, 106.845599)
    assert ab.parse_koordinat("-6.2 106.8") == (-6.2, 106.8)
    assert ab.parse_koordinat("123") is None
    assert ab.parse_koordinat("-95, 10") is None


def test_jarak_dan_radius():
    d = ab.haversine_m(-6.2, 106.8, -6.2009, 106.8)      # ~100 m ke selatan
    assert 95 < d < 105
    tempat, jarak, inside = ab.cek_lokasi(-6.2005, 106.8, LOK)
    assert tempat["Nama Lokasi"] == "OSL Pusat" and inside and jarak < 60
    tempat, jarak, inside = ab.cek_lokasi(-6.25, 106.85, LOK)
    assert not inside and jarak > 1000
    assert ab.cek_lokasi(0, 0, []) == (None, None, False)


def test_lokasi_per_karyawan():
    assert len(ab.lokasi_karyawan({"Lokasi": ""}, LOK)) == 2
    assert len(ab.lokasi_karyawan({"Lokasi": "Semua"}, LOK)) == 2
    only = ab.lokasi_karyawan({"Lokasi": "osl cabang"}, LOK)
    assert [l["Nama Lokasi"] for l in only] == ["OSL Cabang"]


def test_pin():
    assert ab.pin_cocok("0123", 123)          # Sheets membuang nol depan
    assert ab.pin_cocok(" 4567 ", "4567")
    assert not ab.pin_cocok("", "")
    assert not ab.pin_cocok("1111", "1112")


def test_aksi_berikutnya():
    now = t("2026-10-22 17:00")
    assert ab.aksi_berikutnya([], now) == ab.IN
    assert ab.aksi_berikutnya([rec("A", "IN", "2026-10-22 08:00")], now) == ab.OUT
    assert ab.aksi_berikutnya([rec("A", "IN", "2026-10-22 08:00"),
                               rec("A", "OUT", "2026-10-22 16:00")], now) == ab.IN
    # lupa clock out kemarin pagi -> hari ini mulai dari IN lagi
    assert ab.aksi_berikutnya([rec("A", "IN", "2026-10-21 07:00")], now) == ab.IN
    # shift malam: masuk 22:00 kemarin -> pagi ini OUT
    assert ab.aksi_berikutnya([rec("A", "IN", "2026-10-21 22:00")], t("2026-10-22 06:00")) == ab.OUT
    assert ab.terlalu_cepat([rec("A", "IN", "2026-10-22 16:59")], t("2026-10-22 16:59"))


def test_pasangkan_shift():
    rows = [rec("Budi", "IN", "2026-10-20 08:00"), rec("Budi", "OUT", "2026-10-20 16:30"),
            rec("Budi", "IN", "2026-10-21 08:00"),                      # lupa clock out
            rec("Budi", "IN", "2026-10-22 08:00"), rec("Budi", "OUT", "2026-10-22 12:00"),
            rec("Sari", "OUT", "2026-10-21 17:00"),                     # tanpa clock in
            rec("Sari", "IN", "2026-10-21 22:00"), rec("Sari", "OUT", "2026-10-22 06:00")]
    s = ab.pasangkan_shift(rows)
    budi = [x for x in s if x["Nama"] == "Budi"]
    assert [x["Durasi (jam)"] for x in budi] == [8.5, None, 4.0]
    assert budi[1]["Keterangan"] == "Tanpa clock out"
    sari = [x for x in s if x["Nama"] == "Sari"]
    assert sari[0]["Keterangan"] == "Tanpa clock in" and sari[0]["Clock In"] is None
    assert sari[1]["Durasi (jam)"] == 8.0 and sari[1]["Tanggal"] == dt.date(2026, 10, 21)


def test_selfie_muat_di_sel():
    import random
    from PIL import Image
    im = Image.new("RGB", (3000, 4000))
    px = im.load()
    random.seed(1)
    for x in range(0, 3000, 7):              # gambar berisik = sulit dikompres
        for y in range(0, 4000, 7):
            px[x, y] = (random.randrange(256), random.randrange(256), random.randrange(256))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    b64 = ab.kecilkan_selfie(buf.getvalue())
    assert len(b64) <= ab.MAX_FOTO_CHARS
    back = Image.open(io.BytesIO(ab.foto_bytes(b64)))
    assert max(back.size) <= 360


def test_store_bolak_balik():
    s = ab.Store(FakeSpreadsheet())
    assert s.karyawan() == [] and s.lokasi() == [] and s.catatan() == []
    s.simpan_karyawan([{"Nama": "Budi", "PIN": "0123", "Lokasi": "", "Aktif": "Ya"}])
    s.simpan_lokasi([{"Nama Lokasi": "OSL Pusat", "Latitude": -6.2, "Longitude": 106.8,
                      "Radius (m)": None}])
    assert s.karyawan()[0]["Lokasi"] == "Semua"
    assert s.lokasi()[0]["Radius (m)"] == ab.DEFAULT_RADIUS
    r1 = s.tambah_catatan(nama="Budi", jenis="IN", lokasi="OSL Pusat", lat=-6.2, lon=106.8,
                          akurasi=12, jarak=8, perangkat="ua", foto_b64="AAA",
                          waktu=t("2026-10-22 08:00"))
    s.tambah_catatan(nama="Budi", jenis="OUT", lokasi="OSL Pusat", lat=-6.2, lon=106.8,
                     akurasi=12, jarak=8, perangkat="ua", foto_b64="BBB",
                     waktu=t("2026-10-22 16:00"))
    c = s.catatan()
    assert [x["Jenis"] for x in c] == ["IN", "OUT"] and "Foto" not in c[0]
    assert c[0]["ID"] == r1["ID"] and c[0]["Jarak (m)"] == 8.0
    assert s.catatan(mulai=dt.date(2026, 10, 23)) == []
    assert s.foto([x["_row"] for x in c]) == {2: "AAA", 3: "BBB"}
    s.simpan_karyawan([])                     # simpan ulang master menghapus baris lama
    assert s.karyawan() == []


def test_cari_config():
    sa = {"type": "service_account", "client_email": "x@y", "private_key": "K"}
    sid = "1mLOr9EjxTuvFQrj_lMZRhSfDHvyUKZ-A3sE0kNOD_nk"
    # urutan benar
    assert ab.cari_config({"absensi_sheet_id": sid, "gcp_service_account": sa})[:2] == (sid, sa)
    # salah urutan: id tertempel di bawah [gcp_service_account]
    got = ab.cari_config({"gcp_service_account": {**sa, "absensi_sheet_id": sid}})
    assert got[0] == sid and got[1] == sa
    # di bawah tabel lain + URL lengkap
    got = ab.cari_config({"auth": {"absensi_sheet_id": f"https://docs.google.com/spreadsheets/d/{sid}/edit"},
                          "gcp_service_account": sa})
    assert got[0] == sid
    # kosong / kredensial tak lengkap
    assert ab.cari_config({}) == ("", None, [])
    sid2, creds, seen = ab.cari_config({"APP_PASSWORD": "", "gcp_service_account": {"a": 1}})
    assert creds is None and seen == ["APP_PASSWORD", "[gcp_service_account]"]


K_AYU = {"Nama": "Ayu", "Tipe": "Tetap", "Area Piket": "Area Gosok, Area Kamar Lipat Taplak",
         "Day Off": "Sabtu"}
K_DANI = {"Nama": "Dani", "Tipe": "Freelance", "Area Piket": "", "Day Off": ""}


def test_default_aturan_dari_nama():
    s = ab.Store(FakeSpreadsheet())
    # Sheet lama: hanya 4 kolom, tanpa Tipe / Area Piket / Day Off
    w = s.ws(ab.SHEET_KARYAWAN, ["Nama", "PIN", "Lokasi", "Aktif"])
    w.update([["Ayu", "1111", "", "Ya"], ["Ami", "2222", "", "Ya"], ["Lukman", "3333", "", "Ya"],
              ["Dani", "4444", "", "Ya"], ["Budi", "5555", "", "Ya"]], "A2")
    s2 = ab.Store(s.sh)                                   # buka ulang: header diperluas otomatis
    ks = {k["Nama"]: k for k in s2.karyawan()}
    assert s2.ws(ab.SHEET_KARYAWAN, ab.HEAD_KARYAWAN).row_values(1) == ab.HEAD_KARYAWAN
    assert ab.area_piket(ks["Ayu"]) == ["Area Gosok", "Area Kamar Lipat Taplak"]
    assert ab.area_piket(ks["Lukman"]) == ["Area Depan/Luar"]
    assert ab.area_piket(ks["Ami"]) == ["Area Mesin Cuci & Pengering"]
    assert [ab.day_off_idx(ks[n]) for n in ("Ayu", "Ami", "Lukman")] == [5, 0, 6]
    assert ab.is_freelance(ks["Dani"]) and not ab.wajib_piket(ks["Dani"])
    assert ab.day_off_idx(ks["Dani"]) is None
    assert ab.wajib_piket(ks["Budi"]) and ab.day_off_idx(ks["Budi"]) is None   # tak dikenal = tetap
    # nilai di Sheet menggantikan bawaan; '-' = sengaja kosong
    s2.simpan_karyawan([{"Nama": "Ayu", "PIN": "1", "Lokasi": "Semua", "Aktif": "Ya",
                         "Tipe": "Tetap", "Area Piket": "Area Baru", "Day Off": "-"}])
    ayu = s2.karyawan()[0]
    assert ab.area_piket(ayu) == ["Area Baru"] and ab.day_off_idx(ayu) is None


def test_day_off_kalender_dan_tukar():
    # Oktober 2026 punya 5 Sabtu (3,10,17,24,31) dan 4 Senin; Ayu libur Sabtu
    assert ab.jatah_day_off(K_AYU, 2026, 10) == 5
    assert ab.jatah_day_off({**K_AYU, "Day Off": "Senin"}, 2026, 10) == 4
    assert ab.jatah_day_off(K_DANI, 2026, 10) == 0
    assert ab.status_jadwal(K_AYU, dt.date(2026, 10, 31)) == ab.OFF
    assert ab.status_jadwal(K_AYU, dt.date(2026, 10, 30)) == ab.KERJA
    assert ab.status_jadwal(K_DANI, dt.date(2026, 10, 31)) == ab.KERJA      # freelance tanpa day off
    # sakit Rabu 21 Okt, day off minggu itu (Sabtu 24 Okt) dipindah jadi hari kerja
    tukar = [{"Nama": "Ayu", "Tanggal Sakit": "2026-10-21", "Day Off Dipindah": "2026-10-24"}]
    assert ab.status_jadwal(K_AYU, dt.date(2026, 10, 21), tukar) == ab.SAKIT
    assert ab.status_jadwal(K_AYU, dt.date(2026, 10, 24), tukar) == ab.KERJA
    assert ab.status_jadwal(K_AYU, dt.date(2026, 10, 17), tukar) == ab.OFF   # minggu lain tak terpengaruh
    assert ab.status_jadwal({**K_AYU, "Nama": "Ami"}, dt.date(2026, 10, 24), tukar) == ab.OFF


def test_validasi_tukar():
    d = dt.date
    assert ab.validasi_tukar(K_AYU, d(2026, 10, 21), d(2026, 10, 24), []) is None
    assert "day off biasa" in ab.validasi_tukar(K_AYU, d(2026, 10, 24), d(2026, 10, 24), [])
    assert "minggu yang sama" in ab.validasi_tukar(K_AYU, d(2026, 10, 21), d(2026, 10, 23), [])
    assert "minggu yang sama" in ab.validasi_tukar(K_AYU, d(2026, 10, 21), d(2026, 10, 31), [])
    assert "freelance" in ab.validasi_tukar(K_DANI, d(2026, 10, 21), d(2026, 10, 24), [])
    ada = [{"Nama": "Ayu", "Tanggal Sakit": "2026-10-21", "Day Off Dipindah": "2026-10-24"}]
    assert "sudah" in ab.validasi_tukar(K_AYU, d(2026, 10, 21), d(2026, 10, 24), ada)
    # sakit kedua di minggu yang sama: tetap sah, tanpa day off yang dipindah
    assert ab.rencana_tukar(K_AYU, d(2026, 10, 22), ada) == (None, None)
    assert ab.validasi_tukar(K_AYU, d(2026, 10, 22), None, ada) is None
    assert "sudah" in ab.validasi_tukar(K_AYU, d(2026, 10, 21), None, ada)       # tanggal sakit ganda
    assert ab.rencana_tukar(K_AYU, d(2026, 10, 21), []) == (d(2026, 10, 24), None)
    # sakit tepat di day off yang sudah dipindah (kini hari kerja) boleh dicatat
    assert ab.rencana_tukar(K_AYU, d(2026, 10, 24), ada) == (None, None)
    # minggu lain tidak terpengaruh
    assert ab.rencana_tukar(K_AYU, d(2026, 10, 28), ada) == (d(2026, 10, 31), None)
    tukar2 = ada + [{"Nama": "Ayu", "Tanggal Sakit": "2026-10-22", "Day Off Dipindah": ""}]
    assert ab.status_jadwal(K_AYU, d(2026, 10, 22), tukar2) == ab.SAKIT
    assert ab.status_jadwal(K_AYU, d(2026, 10, 24), tukar2) == ab.KERJA


def test_piket_wajib_sebelum_clock_out():
    masuk = rec("Ayu", "IN", "2026-10-22 08:00")
    pk_lama = {"Nama": "Ayu", "_t": t("2026-10-21 16:00")}
    pk_baru = {"Nama": "Ayu", "_t": t("2026-10-22 15:30")}
    assert not ab.piket_selesai([], [masuk])
    assert not ab.piket_selesai([pk_lama], [masuk])         # piket kemarin tak dihitung
    assert ab.piket_selesai([pk_lama, pk_baru], [masuk])
    assert not ab.piket_selesai([pk_baru], [])               # belum clock in


def test_store_piket_dan_tukar():
    s = ab.Store(FakeSpreadsheet())
    assert s.piket() == [] and s.tukar_day_off() == []
    try:
        s.tambah_piket(nama="Ayu", area="Area Gosok", fotos_b64=["a", "b"])
        assert False, "harus menolak selain 3 foto"
    except ValueError:
        pass
    s.tambah_piket(nama="Ayu", area="Area Gosok", fotos_b64=["a", "b", "c"],
                   waktu=t("2026-10-22 15:30"))
    s.tambah_piket(nama="Ami", area="Mesin", fotos_b64=["d", "e", "f"], waktu=t("2026-10-23 15:00"))
    pk = s.piket()
    assert [p["Nama"] for p in pk] == ["Ayu", "Ami"] and "Foto 1" not in pk[0]
    assert [p["Nama"] for p in s.piket(nama="Ami")] == ["Ami"]
    assert s.piket(mulai=dt.date(2026, 10, 23), sampai=dt.date(2026, 10, 23))[0]["Nama"] == "Ami"
    assert s.foto_piket([p["_row"] for p in pk]) == {2: ["a", "b", "c"], 3: ["d", "e", "f"]}
    s.tambah_tukar(nama="Ayu", tgl_sakit=dt.date(2026, 10, 21), tgl_off=dt.date(2026, 10, 24),
                   catatan="demam", oleh="x@y")
    tk = s.tukar_day_off()
    assert tk[0]["Nama"] == "Ayu" and tk[0]["Tanggal Sakit"] == "2026-10-21"
    s.hapus_tukar(tk[0]["_row"])
    assert s.tukar_day_off() == []


def test_foto_piket_muat_di_sel():
    import random
    from PIL import Image
    im = Image.new("RGB", (3000, 4000))
    px = im.load()
    random.seed(2)
    for x in range(0, 3000, 5):
        for y in range(0, 4000, 5):
            px[x, y] = (random.randrange(256), random.randrange(256), random.randrange(256))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    assert len(ab.kecilkan_foto_piket(buf.getvalue())) <= ab.MAX_FOTO_CHARS
    bersih = Image.new("RGB", (4000, 3000), (200, 220, 240))      # foto biasa tetap besar
    buf = io.BytesIO()
    bersih.save(buf, "JPEG")
    back = Image.open(io.BytesIO(ab.foto_bytes(ab.kecilkan_foto_piket(buf.getvalue()))))
    assert max(back.size) == 720


def test_arsip_foto_lama():
    s = ab.Store(FakeSpreadsheet())
    for hari, jenis in (("2026-06-01 08:00", "IN"), ("2026-06-02 08:00", "IN"), ("2026-10-20 08:00", "IN")):
        s.tambah_catatan(nama="Ayu", jenis=jenis, lokasi="L", lat=1, lon=1, akurasi=1, jarak=1,
                         perangkat="x", foto_b64="FOTO" + hari[5:10], waktu=t(hari))
    s.tambah_piket(nama="Ayu", area="A", fotos_b64=["a", "b", "c"], waktu=t("2026-06-01 16:00"))
    s.tambah_piket(nama="Ayu", area="A", fotos_b64=["d", "e", "f"], waktu=t("2026-10-21 16:00"))
    batas = dt.date(2026, 7, 28)                       # 3 bulan sebelum 28 Okt
    lama = s.cari_foto_lama(batas)
    assert lama == {"absensi": [2, 3], "piket": [2]}
    assert s.hapus_foto(lama) == 3
    # foto lama kosong, baris datanya tetap; foto baru utuh
    assert [c["Waktu"][:10] for c in s.catatan()] == ["2026-06-01", "2026-06-02", "2026-10-20"]
    assert s.foto([2, 3, 4]) == {4: "FOTO10-20"}
    assert s.foto_piket([2, 3]) == {3: ["d", "e", "f"]}
    assert [p["Nama"] for p in s.piket()] == ["Ayu", "Ayu"]
    assert s.cari_foto_lama(batas) == {"absensi": [], "piket": []}     # tidak ada yang tersisa
    assert s.hapus_foto({"absensi": [], "piket": []}) == 0


def test_riwayat_day_off_berlaku_ke_depan():
    s = ab.Store(FakeSpreadsheet())
    s.simpan_karyawan([{"Nama": "Ayu", "PIN": "1", "Lokasi": "Semua", "Aktif": "Ya",
                        "Tipe": "Tetap", "Area Piket": "A", "Day Off": "Sabtu"}])
    k = s.karyawan()[0]
    assert k["_riwayat"] == [] and ab.day_off_idx(k) == 5
    # Sabtu diganti Jumat mulai 1 Nov 2026
    s.tambah_riwayat(nama="Ayu", mulai=dt.date(2026, 11, 1), day_off="Jumat", dasar="Sabtu")
    s.simpan_karyawan([{"Nama": "Ayu", "PIN": "1", "Lokasi": "Semua", "Aktif": "Ya",
                        "Tipe": "Tetap", "Area Piket": "A", "Day Off": "Jumat"}])
    k = s.karyawan()[0]
    assert ab.day_off_idx(k) == 4                                     # sekarang: Jumat
    assert ab.day_off_idx(k, dt.date(2026, 10, 31)) == 5              # sebelum 1 Nov: tetap Sabtu
    assert ab.day_off_idx(k, dt.date(2026, 11, 1)) == 4
    assert ab.status_jadwal(k, dt.date(2026, 10, 31)) == ab.OFF       # Sabtu lama tetap day off
    assert ab.status_jadwal(k, dt.date(2026, 10, 30)) == ab.KERJA     # Jumat lama tetap hari kerja
    assert ab.status_jadwal(k, dt.date(2026, 11, 6)) == ab.OFF        # Jumat baru day off
    assert ab.status_jadwal(k, dt.date(2026, 11, 7)) == ab.KERJA
    # Oktober masih 5 Sabtu; November: Jumat 6,13,20,27 = 4
    assert ab.jatah_day_off(k, 2026, 10) == 5 and ab.jatah_day_off(k, 2026, 11) == 4
    # perubahan kedua tidak menambah baris dasar lagi
    s.tambah_riwayat(nama="Ayu", mulai=dt.date(2026, 12, 1), day_off="Senin", dasar="Jumat")
    assert len(s.riwayat_day_off()["Ayu"]) == 3
    # tukar sakit memakai hari day off yang berlaku pada minggu itu
    assert ab.rencana_tukar(s.karyawan()[0], dt.date(2026, 11, 4), [])[0] == dt.date(2026, 11, 6)
    assert ab.rencana_tukar(s.karyawan()[0], dt.date(2026, 10, 28), [])[0] == dt.date(2026, 10, 31)


def test_masuk_tanpa_absen():
    now = t("2026-10-28 10:00")
    masuk = [{"Nama": "Ayu", "_t": t("2026-10-28 08:00")},     # lalu Clock In 08:05 -> selesai
             {"Nama": "Ami", "_t": t("2026-10-28 08:10")},     # tidak absen -> tidak selesai
             {"Nama": "Ami", "_t": t("2026-10-28 09:00")},     # absen jam 09:20 -> selesai
             {"Nama": "Lukman", "_t": t("2026-10-28 09:50")},  # baru 10 menit -> berjalan
             {"Nama": "Dani", "_t": t("2026-10-28 08:20")}]    # absen orang lain tidak dihitung
    cat = [rec("Ayu", "IN", "2026-10-28 08:05"), rec("Ami", "IN", "2026-10-28 09:20"),
           rec("Ayu", "OUT", "2026-10-28 08:55")]              # Clock Out Ayu bukan milik sesi Dani
    r = ab.masuk_tanpa_absen(masuk, cat, now)
    assert [(x["Nama"], x["Waktu"].strftime("%H:%M"), x["Status"]) for x in r] == [
        ("Lukman", "09:50", "berjalan"), ("Ami", "09:00", "selesai"), ("Dani", "08:20", "tidak selesai"),
        ("Ami", "08:10", "tidak selesai"), ("Ayu", "08:00", "selesai")]
    # absen sebelum masuk atau setelah jendela tidak dihitung
    lewat = [rec("Ami", "IN", "2026-10-28 07:00"), rec("Ami", "IN", "2026-10-28 08:50")]
    assert ab.masuk_tanpa_absen([masuk[1]], lewat, now)[0]["Status"] == "tidak selesai"


def test_store_log_masuk():
    s = ab.Store(FakeSpreadsheet())
    assert s.masuk() == []
    s.tambah_masuk(nama="Ayu", waktu=t("2026-10-27 08:00"))
    s.tambah_masuk(nama="Ami", waktu=t("2026-10-28 08:00"))
    assert [m["Nama"] for m in s.masuk()] == ["Ayu", "Ami"]
    assert [m["Nama"] for m in s.masuk(mulai=dt.date(2026, 10, 28))] == ["Ami"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
