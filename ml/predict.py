"""Per-user monthly forecasting with a sklearn implementation and a safe pure-Python fallback."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import math


def _python_months(records: list[dict]) -> list[tuple[str, float]]:
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        if record.get("type", "expense") != "expense":
            continue
        try:
            day = date.fromisoformat(str(record["date"])[:10])
            amount = float(record["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if amount > 0 and math.isfinite(amount):
            totals[day.strftime("%Y-%m")] += amount
    return sorted(totals.items())


def _features(values: list[float]):
    return [[1.0, values[index - 1], sum(values[index - 3:index]) / 3] for index in range(3, len(values))]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small regularized normal equation using pivoted elimination."""
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-10:
            augmented[col][col] += 1e-8
        else:
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        if abs(divisor) < 1e-12:
            continue
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [augmented[row][k] - factor * augmented[col][k] for k in range(size + 1)]
    return [augmented[index][-1] for index in range(size)]


def _fit_linear(features: list[list[float]], targets: list[float]) -> list[float]:
    width = len(features[0])
    matrix = [[sum(row[a] * row[b] for row in features) for b in range(width)] for a in range(width)]
    vector = [sum(row[a] * target for row, target in zip(features, targets)) for a in range(width)]
    # A tiny ridge term keeps small/flat histories numerically stable; the intercept is exempt.
    for index in range(1, width):
        matrix[index][index] += 1e-8
    return _solve(matrix, vector)


def _predict(weights: list[float], features: list[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, features))


def _metrics(actual: list[float], predicted: list[float]) -> dict:
    errors = [got - want for want, got in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    denominator = sum((value - sum(actual) / len(actual)) ** 2 for value in actual)
    r2 = 1 - sum(error * error for error in errors) / denominator if len(actual) > 1 and denominator else None
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "r2": round(r2, 3) if r2 is not None else None, "holdout_months": len(actual)}


def _sklearn_model(records: list[dict]):
    # Keep Pandas/NumPy/scikit-learn as the preferred academic pipeline. Import lazily so
    # transaction entry and the honest baseline remain usable if native wheels are unavailable.
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    try:
        from .preprocessing import monthly_expenses, supervised_months
    except ImportError:
        from preprocessing import monthly_expenses, supervised_months

    monthly = monthly_expenses(records)
    x, y = supervised_months(monthly)
    holdout = min(2, max(1, len(y) // 5))
    validation = LinearRegression().fit(x.iloc[:-holdout], y.iloc[:-holdout])
    predictions = np.maximum(0, validation.predict(x.iloc[-holdout:]))
    metrics = {"mae": round(float(mean_absolute_error(y.iloc[-holdout:], predictions)), 2), "rmse": round(float(np.sqrt(mean_squared_error(y.iloc[-holdout:], predictions))), 2), "r2": round(float(r2_score(y.iloc[-holdout:], predictions)), 3) if holdout > 1 else None, "holdout_months": holdout}
    model = LinearRegression().fit(x, y)
    values = monthly.astype(float).tolist()
    amount = max(0.0, float(model.predict(pd.DataFrame([{"previous_month": values[-1], "previous_three_average": sum(values[-3:]) / 3}]))[0]))
    basis = [{"month": str(period), "expense": round(float(value), 2)} for period, value in monthly.iloc[-3:].items()]
    parameters = {"intercept": float(model.intercept_), "coefficients": [float(value) for value in model.coef_], "features": list(x.columns)}
    return amount, metrics, basis, "Linear regression with lag and rolling-average features", parameters


def forecast(records: list[dict], minimum_months: int = 9) -> dict:
    months = _python_months(records)
    if len(months) < minimum_months:
        return {"available": False, "amount": None, "method": None, "history_months": len(months), "basis": [], "metrics": None, "message": f"A personal model needs at least {minimum_months} months with recorded expenses. You currently have {len(months)}."}
    try:
        amount, metrics, basis, method, parameters = _sklearn_model(records)
    except (ImportError, OSError):
        # The same lagged linear-regression model runs without native scientific wheels.
        # This is useful on locked-down student/Windows environments; no canned forecast is used.
        labels, raw_values = zip(*months)
        values = list(raw_values)
        x, y = _features(values), values[3:]
        holdout = min(2, max(1, len(y) // 5))
        validation_weights = _fit_linear(x[:-holdout], y[:-holdout])
        validation = [max(0.0, _predict(validation_weights, row)) for row in x[-holdout:]]
        metrics = _metrics(y[-holdout:], validation)
        weights = _fit_linear(x, y)
        amount = max(0.0, _predict(weights, [1.0, values[-1], sum(values[-3:]) / 3]))
        basis = [{"month": label, "expense": round(value, 2)} for label, value in months[-3:]]
        method = "Linear regression with lag and rolling-average features (standard-library fallback)"
        parameters = {"intercept": weights[0], "coefficients": weights[1:], "features": ["previous_month", "previous_three_average"]}
    return {"available": True, "amount": round(amount, 2), "method": method, "history_months": len(months), "basis": basis, "metrics": metrics, "model_parameters": parameters, "message": None}
