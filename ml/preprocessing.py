"""Monthly aggregation and lagged features for FinSight expense forecasts."""
from __future__ import annotations

import pandas as pd


def monthly_expenses(records: list[dict]) -> pd.Series:
    frame = pd.DataFrame(records)
    if frame.empty or not {"date", "amount"}.issubset(frame.columns):
        return pd.Series(dtype="float64", name="expenses")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame = frame.dropna(subset=["date", "amount"])
    frame = frame[frame["amount"] > 0]
    if "type" in frame:
        frame = frame[frame["type"] == "expense"]
    if frame.empty:
        return pd.Series(dtype="float64", name="expenses")
    return frame.groupby(frame["date"].dt.to_period("M"))["amount"].sum().sort_index().rename("expenses")


def supervised_months(monthly: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Use only past values for each row: prior month and rolling previous-three average."""
    rows, targets = [], []
    values = monthly.astype(float).tolist()
    for index in range(3, len(values)):
        rows.append({"previous_month": values[index - 1], "previous_three_average": sum(values[index - 3:index]) / 3})
        targets.append(values[index])
    return pd.DataFrame(rows), pd.Series(targets, dtype="float64", name="next_month_expense")
