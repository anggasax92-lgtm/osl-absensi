"""Tiruan gspread.Spreadsheet dalam memori untuk tes (tanpa Google)."""
import re


class WorksheetNotFound(Exception):
    pass


def _col(letter):
    n = 0
    for ch in letter:
        n = n * 26 + ord(ch) - 64
    return n


class FakeWS:
    def __init__(self, title):
        self.title, self.data = title, []

    def _ensure(self, r, c):
        while len(self.data) < r:
            self.data.append([])
        row = self.data[r - 1]
        while len(row) < c:
            row.append("")

    def update(self, values, range_name="A1", value_input_option=None):
        m = re.match(r"([A-Z]+)(\d+)", range_name)
        c0, r0 = _col(m.group(1)), int(m.group(2))
        for i, row in enumerate(values):
            for j, v in enumerate(row):
                self._ensure(r0 + i, c0 + j)
                self.data[r0 + i - 1][c0 + j - 1] = v

    def row_values(self, r):
        return [str(x) for x in self.data[r - 1]] if len(self.data) >= r else []

    def get_all_values(self):
        w = max((len(r) for r in self.data), default=0)
        return [[("" if x is None else str(x)) for x in r] + [""] * (w - len(r)) for r in self.data]

    def get(self, rng):
        a, b = rng.split(":")
        c0, c1 = _col(a), _col(b)
        return [[str(x) for x in r[c0 - 1:c1]] for r in self.data]

    def batch_clear(self, ranges):
        for rng in ranges:
            m = re.match(r"[A-Z]+(\d+)", rng)
            del self.data[int(m.group(1)) - 1:]

    def append_row(self, row, value_input_option=None, insert_data_option=None):
        self.data.append(list(row))

    def batch_get(self, ranges):
        out = []
        for rng in ranges:
            m = re.match(r"([A-Z]+)(\d+)", rng)
            c, r = _col(m.group(1)), int(m.group(2))
            try:
                out.append([[str(self.data[r - 1][c - 1])]])
            except IndexError:
                out.append([])
        return out


class FakeSpreadsheet:
    def __init__(self):
        self.sheets = {}

    def worksheet(self, title):
        if title not in self.sheets:
            raise WorksheetNotFound(title)
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        self.sheets[title] = FakeWS(title)
        return self.sheets[title]
