import csv
import os
from datetime import datetime


class DataNormalizer:

    def __init__(self, data_dir):
        self.data_dir = data_dir

    # Load a CSV file
    def load_csv(self, filename):
        path = os.path.join(self.data_dir, filename)

        with open(path, "r", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    # Normalize dates
    def normalize_date(self, value):
        if not value:
            return None

        value = value.strip()

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d"
        ]

        for fmt in formats:
            try:
                date = datetime.strptime(value, fmt)
                return date.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return value

    # Normalize laboratory values
    def normalize_lab_value(self, value):

        if value is None:
            return None

        value = value.strip()

        # Missing value
        if value == "":
            return None

        # Below detection limit
        if value.startswith("<"):
            return {
                "value": value[1:].strip(),
                "operator": "<"
            }

        # Non-detect / non-numeric
        if value.upper() == "ND":
            return {
                "value": None,
                "operator": "ND"
            }

        # Decimal comma -> decimal point
        value = value.replace(",", ".")

        try:
            return {
                "value": float(value),
                "operator": "="
            }

        except ValueError:
            return {
                "value": value,
                "operator": "="
            }

    # Normalize one row
    def normalize_row(self, row):

        normalized = {}

        for key, value in row.items():

            if value is None:
                normalized[key] = None
                continue

            value = value.strip()

            if value == "":
                normalized[key] = None

            elif "date" in key.lower():
                normalized[key] = self.normalize_date(value)

            else:
                normalized[key] = value

        return normalized

    # Normalize an entire CSV table
    def normalize_table(self, filename):

        rows = self.load_csv(filename)

        normalized_rows = []

        for row in rows:
            normalized_rows.append(
                self.normalize_row(row)
            )

        return normalized_rows