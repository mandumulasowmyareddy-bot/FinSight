"""Train and evaluate a demonstration model from a provided CSV of monthly data."""
import argparse
import csv
import json
from pathlib import Path

import joblib
try:
    from .predict import forecast
except ImportError:
    from predict import forecast


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path, help="CSV with date, amount, and optional type columns")
    parser.add_argument("--output", type=Path, default=Path("models/finsight_linear_regression.joblib"))
    args = parser.parse_args()
    with args.csv.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    result = forecast(records)
    if not result["available"]:
        raise SystemExit(result["message"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"method": result["method"], "model_parameters": result["model_parameters"], "evaluation": result["metrics"], "source_data": str(args.csv)}, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
