"""Create a clearly synthetic monthly expense CSV using only the Python standard library."""
import csv
from datetime import date
from pathlib import Path
import random

OUT = Path(__file__).with_name("synthetic_monthly_expenses.csv")
rng = random.Random(814)
with OUT.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=["date", "amount", "type", "data_label"])
    writer.writeheader()
    for offset in range(36):
        month_index = date(2023, 1, 1).month + offset
        year = 2023 + (month_index - 1) // 12
        month = (month_index - 1) % 12 + 1
        trend = 21500 + (7900 * offset / 35)
        seasonal = 1500 if month in (10, 11, 12) else 0
        amount = max(5000, trend + seasonal + rng.gauss(0, 1200))
        writer.writerow({"date": date(year, month, 1).isoformat(), "amount": f"{amount:.2f}", "type": "expense", "data_label": "synthetic_demo"})
print(f"Synthetic demonstration dataset: {OUT}")
