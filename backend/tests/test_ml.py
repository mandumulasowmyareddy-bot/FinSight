from datetime import date

from ml.predict import forecast


def test_linear_regression_trains_and_reports_error_on_history():
    records = []
    for offset in range(14):
        index = 2025 * 12 + 1 - offset
        year, zero_month = divmod(index, 12)
        records.append({"date": date(year, zero_month + 1, 4).isoformat(), "amount": 18000 + offset * 600, "type": "expense"})
    result = forecast(records)
    assert result["available"]
    assert result["method"].startswith("Linear regression")
    assert result["metrics"]["mae"] >= 0
    assert len(result["model_parameters"]["coefficients"]) == 2


def test_forecast_does_not_fabricate_a_new_users_prediction():
    result = forecast([{"date": "2026-01-10", "amount": 300, "type": "expense"}], minimum_months=9)
    assert result["available"] is False
    assert result["amount"] is None
    assert result["history_months"] == 1
