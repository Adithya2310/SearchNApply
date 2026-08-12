import re


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.rows = []  # list of lists of str, rows[0] is the header once set

    def row_values(self, row_index):
        if row_index - 1 >= len(self.rows):
            return []
        return list(self.rows[row_index - 1])

    def append_row(self, values, value_input_option=None):
        self.rows.append([str(v) for v in values])

    def append_rows(self, values, value_input_option=None):
        for row in values:
            self.rows.append([str(v) for v in row])

    def col_values(self, col_index):
        values = []
        for row in self.rows:
            values.append(row[col_index - 1] if col_index - 1 < len(row) else "")
        return values

    def get_all_records(self, expected_headers=None):
        if not self.rows:
            return []
        header = self.rows[0]
        records = []
        for row in self.rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            records.append(dict(zip(header, padded)))
        return records

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def update(self, range_a1, values, value_input_option=None):
        match = re.match(r"^[A-Z]+(\d+):[A-Z]+(\d+)$", range_a1)
        row_index = int(match.group(1))
        while len(self.rows) < row_index:
            self.rows.append([])
        self.rows[row_index - 1] = [str(v) for v in values[0]]

    def batch_update(self, data, value_input_option=None):
        for item in data:
            self.update(item["range"], item["values"])


class FakeSpreadsheet:
    def __init__(self):
        self._worksheets = {}

    def worksheets(self):
        return list(self._worksheets.values())

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title)
        self._worksheets[title] = ws
        return ws

    def worksheet(self, title):
        return self._worksheets[title]


class FakeGspreadClient:
    def __init__(self, spreadsheet):
        self._spreadsheet = spreadsheet

    def open_by_key(self, spreadsheet_id):
        return self._spreadsheet
