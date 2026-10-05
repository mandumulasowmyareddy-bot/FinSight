from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, decode_user_id, hash_password, verify_password
from app.database import get_db
from app.models.entities import Budget, FinancialGoal, Notification, Transaction, User
from app.schemas.api import BudgetInput, GoalInput, LoginInput, RegisterInput, TransactionInput
from app.services.forecasting import personal_forecast

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    user_id = decode_user_id(credentials.credentials) if credentials else None
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    return user


@router.post("/auth/register", status_code=201)
def register(data: RegisterInput, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@router.post("/auth/login")
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


@router.get("/transactions")
def list_transactions(start: date | None = None, end: date | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Transaction).where(Transaction.user_id == user.id)
    if start:
        query = query.where(Transaction.date >= start)
    if end:
        query = query.where(Transaction.date <= end)
    return db.scalars(query.order_by(Transaction.date.desc(), Transaction.id.desc())).all()


@router.post("/transactions", status_code=201)
def create_transaction(data: TransactionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = Transaction(user_id=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    record_transaction_notices(db, user.id, row)
    return row


@router.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: int, data: TransactionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if not row:
        raise HTTPException(404, "Transaction not found.")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    record_transaction_notices(db, user.id, row)
    return row


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if not row:
        raise HTTPException(404, "Transaction not found.")
    db.delete(row)
    db.commit()


def period_rows(db: Session, user_id: int, month: int | None, year: int | None):
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user_id)).all()
    if year:
        rows = [row for row in rows if row.date.year == year and (month is None or row.date.month == month)]
    return rows


def record_budget_notice(db: Session, user_id: int, budget: Budget, spent: Decimal) -> None:
    if budget.amount <= 0:
        return
    percent = float(spent / budget.amount * 100)
    state = "Exceeded" if percent > 100 else "Critical" if percent >= 90 else "Warning" if percent >= 70 else None
    if not state:
        return
    message = f"{budget.category} budget {state.lower()}: ₹{float(spent):,.0f} of ₹{float(budget.amount):,.0f} used ({percent:.0f}%) for {budget.year}-{budget.month:02d}."
    kind = f"budget_{state.lower()}"
    if not db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.kind == kind, Notification.message == message)):
        db.add(Notification(user_id=user_id, kind=kind, message=message))
        db.commit()


def record_transaction_notices(db: Session, user_id: int, row: Transaction) -> None:
    if row.type != "expense":
        return
    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.category == row.category, Budget.month == row.date.month, Budget.year == row.date.year))
    if budget:
        start = date(row.date.year, row.date.month, 1)
        end = date(row.date.year + (row.date.month == 12), 1 if row.date.month == 12 else row.date.month + 1, 1)
        rows = db.scalars(select(Transaction.amount).where(Transaction.user_id == user_id, Transaction.category == row.category, Transaction.type == "expense", Transaction.date >= start, Transaction.date < end)).all()
        record_budget_notice(db, user_id, budget, sum(rows, Decimal(0)))
    previous = db.scalars(select(Transaction.amount).where(Transaction.user_id == user_id, Transaction.category == row.category, Transaction.type == "expense", Transaction.id != row.id)).all()
    amounts = sorted(float(amount) for amount in previous)
    if len(amounts) >= 5:
        median = amounts[len(amounts) // 2]
        if float(row.amount) >= max(median * 3, median + 5000):
            message = f"Unusually high {row.category} transaction: ₹{float(row.amount):,.0f} on {row.date.isoformat()}. Review the category and details."
            if not db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.kind == "unusual", Notification.message == message)):
                db.add(Notification(user_id=user_id, kind="unusual", message=message))
                db.commit()


@router.get("/analytics/summary")
def summary(month: int | None = None, year: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = period_rows(db, user.id, month, year)
    income = sum((r.amount for r in rows if r.type == "income"), Decimal(0))
    expenses = sum((r.amount for r in rows if r.type == "expense"), Decimal(0))
    expense_rows = [r for r in rows if r.type == "expense"]
    categories: dict[str, Decimal] = defaultdict(Decimal)
    for row in expense_rows:
        categories[row.category] += row.amount
    today = date.today()
    budget_month, budget_year = month or today.month, year or today.year
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id, Budget.month == budget_month, Budget.year == budget_year)).all()
    actuals = defaultdict(Decimal)
    for row in period_rows(db, user.id, budget_month, budget_year):
        if row.type == "expense":
            actuals[row.category] += row.amount
    budget_total = sum((b.amount for b in budgets), Decimal(0))
    used_total = sum((actuals[budget.category] for budget in budgets), Decimal(0))
    return {
        "income": float(income), "expenses": float(expenses), "savings": float(income - expenses),
        "savings_rate": round(float((income - expenses) / income * 100), 1) if income else None,
        "transaction_count": len(rows), "top_category": max(categories, key=categories.get) if categories else None,
        "category_spending": [{"category": k, "amount": float(v)} for k, v in sorted(categories.items(), key=lambda item: item[1], reverse=True)],
        "budget_total": float(budget_total), "budget_used": float(used_total),
        "budget_usage_percent": round(float(used_total / budget_total * 100), 1) if budget_total else None,
        "period": {"month": month, "year": year},
    }


@router.get("/analytics/trends")
def trends(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user.id, Transaction.type == "expense")).all()
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    categories: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for row in rows:
        key = row.date.strftime("%Y-%m")
        monthly[key] += row.amount
        categories[row.category][key] += row.amount
    return {"monthly": [{"month": key, "expenses": float(monthly[key])} for key in sorted(monthly)], "categories": {category: {key: float(value) for key, value in sorted(values.items())} for category, values in categories.items()}}


@router.get("/budgets")
def list_budgets(month: int | None = None, year: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = date.today()
    selected_month, selected_year = month or today.month, year or today.year
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id, Budget.month == selected_month, Budget.year == selected_year)).all()
    rows = period_rows(db, user.id, selected_month, selected_year)
    spent: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        if row.type == "expense":
            spent[row.category] += row.amount
    result = []
    for budget in budgets:
        amount_used = spent[budget.category]
        percent = float(amount_used / budget.amount * 100)
        result.append({"id": budget.id, "category": budget.category, "amount": float(budget.amount), "spent": float(amount_used), "usage_percent": round(percent, 1), "status": "Exceeded" if percent > 100 else "Critical" if percent >= 90 else "Warning" if percent >= 70 else "Safe", "month": budget.month, "year": budget.year})
    return result


@router.post("/budgets", status_code=201)
def save_budget(data: BudgetInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == data.category, Budget.month == data.month, Budget.year == data.year))
    if row:
        row.amount = data.amount
    else:
        row = Budget(user_id=user.id, **data.model_dump())
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A budget already exists for this category and month.")
    db.refresh(row)
    rows = period_rows(db, user.id, row.month, row.year)
    spent = sum((item.amount for item in rows if item.type == "expense" and item.category == row.category), Decimal(0))
    record_budget_notice(db, user.id, row, spent)
    return row


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(budget_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if not row:
        raise HTTPException(404, "Budget not found.")
    db.delete(row)
    db.commit()


@router.get("/goals")
def list_goals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(FinancialGoal).where(FinancialGoal.user_id == user.id).order_by(FinancialGoal.id.desc())).all()


@router.post("/goals", status_code=201)
def create_goal(data: GoalInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = FinancialGoal(user_id=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, data: GoalInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(FinancialGoal).where(FinancialGoal.id == goal_id, FinancialGoal.user_id == user.id))
    if not row:
        raise HTTPException(404, "Goal not found.")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(FinancialGoal).where(FinancialGoal.id == goal_id, FinancialGoal.user_id == user.id))
    if not row:
        raise HTTPException(404, "Goal not found.")
    db.delete(row)
    db.commit()


@router.get("/insights")
def insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    expenses = [r for r in rows if r.type == "expense"]
    items = []
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in expenses:
        totals[row.category] += row.amount
    if totals:
        category = max(totals, key=totals.get)
        items.append({"kind": "category", "title": f"{category} is your largest spending category", "detail": f"₹{float(totals[category]):,.0f} across {sum(r.category == category for r in expenses)} recorded transactions in your history."})
    by_category: dict[str, list[Transaction]] = defaultdict(list)
    for row in expenses:
        by_category[row.category].append(row)
    for category, category_rows in by_category.items():
        amounts = sorted(float(row.amount) for row in category_rows)
        if len(amounts) >= 6:
            median = amounts[len(amounts) // 2]
            unusual = [row for row in category_rows if float(row.amount) >= max(median * 3, median + 5000)]
            if unusual:
                row = max(unusual, key=lambda item: item.amount)
                items.append({"kind": "unusual transaction", "title": "A larger-than-usual transaction stands out", "detail": f"{row.category} recorded ₹{float(row.amount):,.0f} on {row.date.isoformat()}, compared with a typical {category} transaction of about ₹{median:,.0f}. Check that this is categorized as intended."})
        repeated: dict[str, list[Transaction]] = defaultdict(list)
        for row in category_rows:
            label = row.description.strip().lower()
            if label and label != category.lower():
                repeated[label].append(row)
        for label, matches in repeated.items():
            months_seen = {row.date.strftime("%Y-%m") for row in matches}
            month_counts: dict[str, int] = defaultdict(int)
            for match in matches:
                month_counts[match.date.strftime("%Y-%m")] += 1
            amounts = sorted(float(match.amount) for match in matches)
            typical = amounts[len(amounts) // 2]
            spread = (amounts[-1] - amounts[0]) / typical if typical else 1
            if len(months_seen) >= 3 and max(month_counts.values()) <= 2 and spread <= 0.35:
                items.append({"kind": "possible recurring", "title": "A possible recurring payment", "detail": f"“{matches[0].description}” appears in {len(months_seen)} different months under {category}. Review the entries to confirm whether it is recurring."})
                break
    month_totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in expenses:
        month_totals[row.date.strftime("%Y-%m")] += row.amount
    months = sorted(month_totals)
    if len(months) >= 2:
        prior, current = month_totals[months[-2]], month_totals[months[-1]]
        delta = float((current - prior) / prior * 100) if prior else None
        if delta is not None:
            direction = "increased" if delta > 0 else "decreased"
            items.append({"kind": "trend", "title": f"Monthly spending {direction}", "detail": f"Total expenses changed {abs(delta):.1f}% from {months[-2]} to {months[-1]} based on recorded transactions."})
    today = date.today()
    used_budgets = list_budgets(today.month, today.year, user, db)
    for budget in used_budgets:
        if budget["status"] in ("Critical", "Exceeded"):
            items.append({"kind": "budget", "title": f"{budget['category']} budget {budget['status'].lower()}", "detail": f"₹{budget['spent']:,.0f} of ₹{budget['amount']:,.0f} used ({budget['usage_percent']:.0f}%)."})
    return items


@router.get("/predictions/monthly")
def monthly_prediction(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user.id, Transaction.type == "expense")).all()
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        monthly[row.date.strftime("%Y-%m")] += row.amount
    keys = sorted(monthly)
    if len(keys) >= 9:
        model_result = personal_forecast([{"date": row.date.isoformat(), "amount": float(row.amount), "type": row.type} for row in rows])
        if model_result and model_result.get("available"):
            today = date.today()
            month = 1 if today.month == 12 else today.month + 1
            year = today.year + (today.month == 12)
            budgets = db.scalars(select(Budget).where(Budget.user_id == user.id, Budget.month == month, Budget.year == year)).all()
            budget_total = sum((b.amount for b in budgets), Decimal(0))
            return {**model_result, "target_month": f"{year}-{month:02d}", "budget_total": float(budget_total) if budget_total else None, "risk": "high" if budget_total and model_result["amount"] > float(budget_total) else "within_budget" if budget_total else "unknown"}
    if len(keys) < 3:
        return {"available": False, "message": "Prediction unavailable yet. Record expenses in at least three different months to unlock a personal baseline.", "method": None, "history_months": len(keys)}
    last = keys[-3:]
    estimate = sum((monthly[key] for key in last), Decimal(0)) / Decimal(3)
    today = date.today()
    month = 1 if today.month == 12 else today.month + 1
    year = today.year + (today.month == 12)
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id, Budget.month == month, Budget.year == year)).all()
    budget_total = sum((b.amount for b in budgets), Decimal(0))
    return {"available": True, "amount": float(estimate), "target_month": f"{year}-{month:02d}", "method": "Three-month historical average baseline", "history_months": len(keys), "budget_total": float(budget_total) if budget_total else None, "risk": "high" if budget_total and estimate > budget_total else "within_budget" if budget_total else "unknown", "basis": [{"month": key, "expense": float(monthly[key])} for key in last]}


@router.get("/health-score")
def health_score(user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = summary(None, date.today().year, user, db)
    if data["transaction_count"] == 0:
        return {"score": None, "label": "Not enough data", "explanation": "Add transactions to build a personal financial health summary."}
    savings = data["savings_rate"]
    score = 50 if savings is None else min(100, max(0, round(savings * 1.4 + 40)))
    budget_use = data["budget_usage_percent"]
    if budget_use is not None and budget_use > 100:
        score = max(0, score - 15)
    elif budget_use is not None and budget_use < 70:
        score = min(100, score + 5)
    return {"score": score, "label": "Strong" if score >= 75 else "Building" if score >= 50 else "Needs attention", "explanation": "An indicative score based on this year's savings rate and current-month budget usage. It is descriptive, not financial advice.", "factors": {"savings_rate": savings, "budget_usage_percent": budget_use}}


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not row:
        raise HTTPException(404, "Notification not found.")
    row.is_read = True
    db.commit()
    return {"id": row.id, "is_read": True}
