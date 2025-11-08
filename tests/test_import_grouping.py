import pandas as pd
from app.importers.excel_importer import group_payout_rows_by_month

def test_group_payout_rows_by_month_multiple_rows_same_month():
    df = pd.DataFrame([
        {"Code": "A", "Pay Date": "2025/10/31", "Amount": 100, "Status": "Paid"},
        {"Code": "B", "Pay Date": "2025/10/15", "Amount": 200, "Status": "Paid"},
        {"Code": "C", "Pay Date": "2025/10/01", "Amount": 300, "Status": "Paid"},
    ])
    grouped, errors = group_payout_rows_by_month(df)
    assert not errors
    # Only one group for October 2025
    assert list(grouped.keys()) == [(2025, 10)]
    # Grouped DataFrame should contain all 3 rows
    assert len(grouped[(2025, 10)]) == 3
