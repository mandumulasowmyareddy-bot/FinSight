# FinSight architecture and project plan

## Request and data flow

React client → FastAPI route → authenticated user context → service calculations → SQLAlchemy models → MySQL. Forecasts use monthly aggregates belonging to the authenticated user, pass through preprocessing and a trained model, then return the estimate and method. Empty or insufficient history returns a clear unavailable state.

## Planned relational schema

- `users`: identity, unique email, password hash, timestamps.
- `transactions`: user FK, type, positive amount, category, description, date, payment method; indexes on `(user_id, date)` and `(user_id, category)`.
- `budgets`: user FK, category, amount, month, year; unique `(user_id, category, month, year)`.
- `financial_goals`: user FK, title, target amount, current amount, deadline, status.
- `predictions`: user FK, target month, amount, method, evaluation metadata and generation time.
- `notifications`: user FK, type, message, read state, creation time.

All child data uses ownership checks and user-scoped queries. Monetary amounts are decimal values; user-facing formatting uses INR by default.

## Review-friendly build phases

1. Project setup and runtime foundations (current).
2. Persistence and schema.
3. Authentication.
4. Transaction CRUD.
5. Dashboard and filters.
6. Budgets.
7. Analytics and insights.
8. Synthetic dataset and feature preparation.
9. Model training/evaluation.
10. Forecast API and budget risk.
11. Recommendations.
12. Goals and health score.
13. Anomaly/recurrence detection.
14. Verification.
15. Responsive polish.
16. Viva-ready docs.
17. Optional Docker/deployment.
