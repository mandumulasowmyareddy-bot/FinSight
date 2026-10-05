# FinSight API reference

Base URL: `http://localhost:8000`. Interactive request and schema reference: `/docs`.

Except for registration, login, and health, requests use `Authorization: Bearer <access_token>`. Amounts are positive INR values; type determines whether a transaction is income or expense. Every query is scoped to the signed-in account.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service check |
| POST | `/auth/register` | Create a user and return an access token |
| POST | `/auth/login` | Verify credentials and return a token |
| GET | `/auth/me` | Current account details |
| GET, POST | `/transactions` | List (optional `start`/`end`) or create transactions |
| PUT, DELETE | `/transactions/{id}` | Update or delete an owned transaction |
| GET, POST | `/budgets` | List current period budgets with actual spend, or create/update a category budget |
| DELETE | `/budgets/{id}` | Delete an owned budget |
| GET | `/analytics/summary` | Period income, expense, savings, categories, and budget use |
| GET | `/analytics/trends` | Monthly total and category expense series |
| GET | `/insights` | Data-based category, trend, unusual-spending and recurrence observations |
| GET | `/predictions/monthly` | Per-user forecast, baseline, history basis, risk, and evaluation metrics |
| GET, POST | `/goals` | List or create savings goals |
| PUT, DELETE | `/goals/{id}` | Update progress/details or delete a goal |
| GET | `/health-score` | Explainable descriptive score and factors |
| GET | `/notifications` | Account-scoped notices |
| PUT | `/notifications/{id}/read` | Mark an owned notice as read |

Errors use FastAPI status codes and short, user-safe detail messages. Validation errors return 422; missing or foreign-owned records return 404.
