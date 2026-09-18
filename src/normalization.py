import csv
import os
import re
from datetime import datetime


class DataNormalizer:

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def load_csv(self, filename):
        path = os.path.join(self.data_dir, filename)

        with open(path, "r", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def normalize_date(self, value):
        if not value:
            return None

        value = value.strip()

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d/%b/%Y",
            "%d %b %Y",
            "%d-%B-%Y",
            "%d/%B/%Y"
        ]

        for fmt in formats:
            try:
                date = datetime.strptime(value, fmt)
                return date.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return value

    def normalize_lab_value(self, value):
        if value is None:
            return None

        value = value.strip()

        if value == "":
            return None

        if value.upper() == "ND":
            return {
                "value": None,
                "operator": "ND"
            }

        match = re.fullmatch(
            r"<\s*([0-9]+(?:[.,][0-9]+)?)",
            value
        )

        if match:
            limit = float(match.group(1).replace(",", "."))

            return {
                "value": limit,
                "operator": "<"
            }

        match = re.fullmatch(
            r">\s*([0-9]+(?:[.,][0-9]+)?)",
            value
        )

        if match:
            limit = float(match.group(1).replace(",", "."))

            return {
                "value": limit,
                "operator": ">"
            }

        numeric_value = value.replace(",", ".")

        try:
            return {
                "value": float(numeric_value),
                "operator": "="
            }

        except ValueError:
            return {
                "value": value,
                "operator": "="
            }

    def convert_unit(self, value, from_unit, to_unit):
        if value is None:
            return None

        if from_unit == to_unit:
            return value

        if from_unit.lower() == "ukat/l" and to_unit.upper() == "U/L":
            return round(value * 60,2)

        return value

    def is_date_column(self, key):
        key_upper = key.upper()

        return (
            "DATE" in key_upper
            or key_upper.endswith("DTC")
        )

    def normalize_row(self, row):
        normalized = {}

        for key, value in row.items():

            if value is None:
                normalized[key] = None
                continue

            value = value.strip()

            if value == "":
                normalized[key] = None

            elif key.upper() == "LBORRES":
                normalized[key] = self.normalize_lab_value(value)

            elif self.is_date_column(key):
                normalized[key] = self.normalize_date(value)

            else:
                normalized[key] = value

        return normalized

    def normalize_table(self, filename):
        rows = self.load_csv(filename)

        normalized_rows = []

        for row in rows:
            normalized_rows.append(
                self.normalize_row(row)
            )

        return normalized_rows