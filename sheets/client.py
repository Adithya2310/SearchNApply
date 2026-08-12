import os

import gspread
from google.oauth2.service_account import Credentials

from .schema import SHEETS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    """Read/write layer over the job search Google Sheet.

    Every module (M1, M4, M5, M6, M7, ...) talks to the Sheet only through
    this class, never directly through gspread, so the schema lives in one
    place (schema.py).
    """

    def __init__(self, spreadsheet_id=None, credentials_path=None):
        self.spreadsheet_id = spreadsheet_id or os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"]
        credentials_path = credentials_path or os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self._gc = gspread.authorize(creds)
        self._spreadsheet = self._gc.open_by_key(self.spreadsheet_id)
        self._worksheet_cache = {}

    def ensure_schema(self):
        """Create any missing tabs with the correct header row.

        Never touches existing data. Raises if an existing tab's header
        row doesn't match schema.py, since silently reordering columns
        would corrupt every other module's reads/writes.
        """
        all_worksheets = {ws.title: ws for ws in self._spreadsheet.worksheets()}
        for sheet_name, columns in SHEETS.items():
            if sheet_name not in all_worksheets:
                ws = self._spreadsheet.add_worksheet(
                    title=sheet_name, rows=1000, cols=max(len(columns), 1)
                )
                ws.append_row(columns, value_input_option="RAW")
            else:
                ws = all_worksheets[sheet_name]
                header = ws.row_values(1)
                if not header:
                    ws.append_row(columns, value_input_option="RAW")
                elif header != columns:
                    raise ValueError(
                        f"Sheet '{sheet_name}' header {header} does not match "
                        f"expected schema {columns}"
                    )
            self._worksheet_cache[sheet_name] = ws

    def _worksheet(self, sheet_name):
        if sheet_name not in SHEETS:
            raise ValueError(f"Unknown sheet '{sheet_name}'")
        if sheet_name not in self._worksheet_cache:
            # Not populated by ensure_schema (e.g. called before it, or in a
            # fresh process) — self._spreadsheet.worksheet() does its own
            # metadata read, so we only want to pay that cost once per sheet.
            self._worksheet_cache[sheet_name] = self._spreadsheet.worksheet(sheet_name)
        return self._worksheet_cache[sheet_name]

    def get_rows(self, sheet_name):
        """Return every data row as a list of dicts keyed by column name."""
        ws = self._worksheet(sheet_name)
        return ws.get_all_records(expected_headers=SHEETS[sheet_name])

    def append_row(self, sheet_name, row):
        """Append one row. `row` is a dict of column -> value; columns left
        out of `row` are written blank.
        """
        self.append_rows(sheet_name, [row])

    def append_rows(self, sheet_name, rows):
        """Append many rows in a single API call. Use this over append_row
        in a loop whenever writing more than one row — Sheets' per-minute
        write/read quotas are easy to blow through one row at a time.
        """
        if not rows:
            return
        ws = self._worksheet(sheet_name)
        columns = SHEETS[sheet_name]
        values = [[row.get(col, "") for col in columns] for row in rows]
        ws.append_rows(values, value_input_option="RAW")

    def find_row_index(self, sheet_name, id_column, id_value):
        """1-indexed sheet row (header = row 1) matching id_column ==
        id_value, or None if not found.
        """
        columns = SHEETS[sheet_name]
        if id_column not in columns:
            raise ValueError(f"'{id_column}' is not a column of '{sheet_name}'")
        ws = self._worksheet(sheet_name)
        col_index = columns.index(id_column) + 1
        col_values = ws.col_values(col_index)
        for offset, value in enumerate(col_values[1:], start=2):
            if value == str(id_value):
                return offset
        return None

    def update_row(self, sheet_name, id_column, id_value, updates):
        """Merge `updates` (dict of column -> new value) into the row where
        id_column == id_value. Raises if no such row exists.
        """
        row_index = self.find_row_index(sheet_name, id_column, id_value)
        if row_index is None:
            raise ValueError(f"No row in '{sheet_name}' where {id_column} == {id_value}")

        columns = SHEETS[sheet_name]
        ws = self._worksheet(sheet_name)
        current = ws.row_values(row_index)
        current += [""] * (len(columns) - len(current))
        for col, value in updates.items():
            if col not in columns:
                raise ValueError(f"'{col}' is not a column of '{sheet_name}'")
            current[columns.index(col)] = value

        start_a1 = gspread.utils.rowcol_to_a1(row_index, 1)
        end_a1 = gspread.utils.rowcol_to_a1(row_index, len(columns))
        ws.update(f"{start_a1}:{end_a1}", [current], value_input_option="RAW")
