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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
