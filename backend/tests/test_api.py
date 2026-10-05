from datetime import date


def test_registration_login_and_protected_routes(client):
    assert client.get("/auth/me").status_code == 401
    created = client.post("/auth/register", json={"name": "Aanya Rao", "email": "aanya@example.local", "password": "SecurePass123"})
    assert created.status_code == 201
    assert "access_token" in created.json()
    assert client.post("/auth/login", json={"email": "aanya@example.local", "password": "wrong-password"}).status_code == 401
    logged_in = client.post("/auth/login", json={"email": "aanya@example.local", "password": "SecurePass123"})
    client.headers["Authorization"] = f"Bearer {logged_in.json()['access_token']}"
    assert client.get("/auth/me").json()["name"] == "Aanya Rao"


def test_transaction_budget_analytics_and_ownership(signed_in, client):
    first = signed_in.post("/transactions", json={"type": "income", "amount": 50000, "category": "Salary", "date": date.today().isoformat(), "payment_method": "Bank Transfer"})
    second = signed_in.post("/transactions", json={"type": "expense", "amount": 1200, "category": "Food", "description": "Lunch", "date": date.today().isoformat(), "payment_method": "UPI"})
    assert first.status_code == 201 and second.status_code == 201
    summary = signed_in.get("/analytics/summary").json()
    assert summary["income"] == 50000 and summary["expenses"] == 1200
    changed = signed_in.put(f"/transactions/{second.json()['id']}", json={"type": "expense", "amount": 1300, "category": "Food", "description": "Lunch", "date": date.today().isoformat(), "payment_method": "UPI"})
    assert changed.status_code == 200 and changed.json()["amount"] == 1300
    budget = signed_in.post("/budgets", json={"category": "Food", "amount": 1000, "month": date.today().month, "year": date.today().year})
    assert budget.status_code == 201
    assert signed_in.get("/budgets").json()[0]["status"] == "Exceeded"
    alert = signed_in.get("/notifications").json()[0]
    assert alert["kind"] == "budget_exceeded"
    assert signed_in.put(f"/notifications/{alert['id']}/read").json()["is_read"] is True
    other = client.post("/auth/register", json={"name": "Other User", "email": "other@example.local", "password": "OtherPass123"})
    client.headers["Authorization"] = f"Bearer {other.json()['access_token']}"
    assert client.get("/transactions").json() == []
    assert client.put(f"/transactions/{second.json()['id']}", json={"type": "expense", "amount": 10, "category": "Food", "date": date.today().isoformat(), "payment_method": "Cash"}).status_code == 404


def test_goals_and_cold_start_prediction(signed_in):
    goal = signed_in.post("/goals", json={"title": "Emergency reserve", "target_amount": 10000, "current_amount": 1250})
    assert goal.status_code == 201
    assert signed_in.get("/goals").json()[0]["title"] == "Emergency reserve"
    prediction = signed_in.get("/predictions/monthly").json()
    assert prediction["available"] is False
    assert "Prediction unavailable" in prediction["message"]


def test_user_specific_linear_forecast_has_chronological_metrics(signed_in):
    today = date.today()
    for offset in range(10):
        index = today.year * 12 + today.month - 1 - offset
        year, zero_month = divmod(index, 12)
        signed_in.post("/transactions", json={"type": "expense", "amount": 22000 + offset * 450, "category": "Bills", "description": "Monthly bills", "date": date(year, zero_month + 1, 5).isoformat(), "payment_method": "UPI"})
    result = signed_in.get("/predictions/monthly").json()
    assert result["available"] is True
    assert result["method"].startswith("Linear regression")
    assert result["amount"] > 0
    assert result["metrics"]["mae"] >= 0
    assert result["metrics"]["holdout_months"] >= 1


def test_insights_only_describe_observable_unusual_and_repeated_records(signed_in):
    today = date.today()
    for offset in range(8):
        index = today.year * 12 + today.month - 1 - offset
        year, zero_month = divmod(index, 12)
        signed_in.post("/transactions", json={"type": "expense", "amount": 300, "category": "Food", "description": "Usual meal", "date": date(year, zero_month + 1, 5).isoformat(), "payment_method": "UPI"})
        signed_in.post("/transactions", json={"type": "expense", "amount": 12000, "category": "Bills", "description": "Monthly rent", "date": date(year, zero_month + 1, 2).isoformat(), "payment_method": "Bank Transfer"})
    signed_in.post("/transactions", json={"type": "expense", "amount": 5800, "category": "Food", "description": "One-off dinner", "date": today.isoformat(), "payment_method": "Debit Card"})
    insights = signed_in.get("/insights").json()
    assert any(item["kind"] == "unusual transaction" for item in insights)
    assert any(item["kind"] == "possible recurring" for item in insights)
