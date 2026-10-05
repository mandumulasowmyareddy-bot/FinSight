"""Seed one entirely fictional FinSight demo account and 10 months of activity."""
from datetime import date
from decimal import Decimal
import os
import random
import secrets
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models.entities import Budget, FinancialGoal, Transaction, User
from app.routers.api import record_budget_notice, record_transaction_notices

EMAIL = "demo@finsight.local"
PASSWORD = os.getenv("FINSIGHT_DEMO_PASSWORD")


def add_demo_patterns(db, user_id: int, today: date) -> None:
    """Add one consistent recurring payment and one clearly labeled unusual fictional expense."""
    for offset in range(10):
        index = today.year * 12 + today.month - 1 - offset
        year, zero_month = divmod(index, 12)
        month = zero_month + 1
        first = date(year, month, 1)
        if not db.scalar(select(Transaction.id).where(Transaction.user_id == user_id, Transaction.category == "Subscriptions", Transaction.description == "Cloud storage plan", Transaction.date >= first, Transaction.date < date(year + (month == 12), 1 if month == 12 else month + 1, 1))):
            db.add(Transaction(user_id=user_id, type="expense", amount=Decimal("499.00"), category="Subscriptions", description="Cloud storage plan", date=date(year, month, 3), payment_method="UPI"))
    if not db.scalar(select(Transaction.id).where(Transaction.user_id == user_id, Transaction.description == "Annual celebration dinner")):
        db.add(Transaction(user_id=user_id, type="expense", amount=Decimal("5800.00"), category="Food", description="Annual celebration dinner", date=date(today.year, today.month, 2), payment_method="Debit Card"))
    db.flush()
    anomaly = db.scalar(select(Transaction).where(Transaction.user_id == user_id, Transaction.description == "Annual celebration dinner"))
    if anomaly:
        record_transaction_notices(db, user_id, anomaly)
    budgets = db.scalars(select(Budget).where(Budget.user_id == user_id, Budget.month == today.month, Budget.year == today.year)).all()
    for budget in budgets:
        start = date(today.year, today.month, 1)
        end = date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
        amounts = db.scalars(select(Transaction.amount).where(Transaction.user_id == user_id, Transaction.type == "expense", Transaction.category == budget.category, Transaction.date >= start, Transaction.date < end)).all()
        record_budget_notice(db, user_id, budget, sum(amounts, Decimal(0)))


def seed() -> None:
    Base.metadata.create_all(engine)
    random.seed(73)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user:
            add_demo_patterns(db, user.id, date.today())
            if PASSWORD:
                user.password_hash = hash_password(PASSWORD)
            db.commit()
            print(f"Updated synthetic demo account: {EMAIL}")
            if PASSWORD:
                print(f"Demo password from FINSIGHT_DEMO_PASSWORD: {PASSWORD}")
            return
        demo_password = PASSWORD or secrets.token_urlsafe(18)
        user = User(name="Aanya Rao", email=EMAIL, password_hash=hash_password(demo_password))
        db.add(user)
        db.flush()
        today = date.today()
        monthly_scale = [0.90, 1.05, 0.94, 1.12, 1.02, 1.21, 1.08, 0.97, 1.16, 1.07]
        categories = {
            "Food": (3300, 11), "Transportation": (1750, 6), "Shopping": (2450, 4),
            "Bills": (2900, 3), "Entertainment": (1100, 3), "Subscriptions": (650, 2),
            "Healthcare": (950, 1),
        }
        for offset, scale in enumerate(monthly_scale):
            month_index = today.month - (len(monthly_scale) - 1 - offset)
            year = today.year + (month_index - 1) // 12
            month = (month_index - 1) % 12 + 1
            db.add(Transaction(user_id=user.id, type="income", amount=Decimal("62000.00"), category="Salary", description="Monthly salary", date=date(year, month, 1), payment_method="Bank Transfer"))
            for category, (base, count) in categories.items():
                factor = scale * random.uniform(0.91, 1.1)
                # A gentle food trend and a shopping dip make the fictional history useful in demonstrations.
                if category == "Food":
                    factor *= 0.92 + offset * 0.025
                if category == "Shopping" and offset in (6, 7):
                    factor *= 0.72
                total = base * factor
                per_txn = total / count
                for index in range(count):
                    day = min(26, 2 + (index * 2) % 25)
                    amount = round(per_txn * random.uniform(0.78, 1.22), 2)
                    description = "Home rent" if category == "Bills" and index == 0 else "Coffee & meals" if category == "Food" else category
                    db.add(Transaction(user_id=user.id, type="expense", amount=Decimal(str(amount)), category=category, description=description, date=date(year, month, day), payment_method=random.choice(["UPI", "Debit Card", "Cash"])))
        month = today.month
        year = today.year
        for category, amount in [("Food", 5000), ("Transportation", 2800), ("Shopping", 4000), ("Bills", 5000), ("Entertainment", 2200), ("Subscriptions", 1000)]:
            db.add(Budget(user_id=user.id, category=category, amount=Decimal(str(amount)), month=month, year=year))
        db.add(FinancialGoal(user_id=user.id, title="Emergency fund", target_amount=Decimal("150000"), current_amount=Decimal("46500"), deadline=date(today.year + 1, today.month, 1)))
        add_demo_patterns(db, user.id, today)
        db.commit()
        print(f"Created synthetic demo account: {EMAIL} / {demo_password}")
        print("All seeded transactions are fictional demonstration data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
