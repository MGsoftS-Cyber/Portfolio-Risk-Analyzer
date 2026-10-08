"""Validate CSV rows without mutating saved portfolio data."""

import csv
import io
from .schemas import PriceInput


def spreadsheet_safe(value):
    return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value


def preview_prices(text):
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames != ["date", "asset", "price"]:
            return {"rows": [], "errors": [{"row": 1, "message": "Required header: date,asset,price"}], "valid": False}
        rows = []
        errors = []
        seen = set()
        for index, row in enumerate(reader, 2):
            if index > 20001:
                errors.append({"row": index, "message": "Maximum 20,000 observations."})
                break
            try:
                value = PriceInput.model_validate(row)
                key = (value.date, value.asset)
                if key in seen:
                    raise ValueError("Duplicate asset/date observation.")
                seen.add(key)
                rows.append(value.model_dump(mode="json"))
            except Exception:
                errors.append(
                    {"row": index, "message": "Invalid date, asset, positive price, or duplicate observation."}
                )
        if not rows:
            errors.append({"row": 1, "message": "Supply at least one valid price row."})
        return {"rows": rows, "errors": errors, "valid": not errors}
    except csv.Error:
        return {"rows": [], "errors": [{"row": 1, "message": "Malformed CSV."}], "valid": False}
