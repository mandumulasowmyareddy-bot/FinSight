# FinSight — Track. Understand. Predict.

FinSight is a personal financial intelligence platform for tracking transactions, understanding spending patterns, planning budgets and goals, and making explainable forecasts from a user's own history.

## Workspace assessment

The supplied workspace was empty. This repository starts with a clean monorepo; no existing data or code was present to preserve.

## Architecture

- `frontend/`: React + Vite client; React Router for navigation, Axios for API requests, Recharts for financial visualizations, and Tailwind CSS for responsive styling.
- `backend/`: FastAPI REST API, Pydantic validation, SQLAlchemy persistence, JWT authentication, and user-scoped services.
- `ml/`: transparent monthly forecasting pipeline. The application must label insufficient history as unavailable rather than inventing a prediction.
- `dataset/`: explicitly synthetic demo data only.
- `docs/`: architecture, data model, and development notes for the project review.
- MySQL is the production/demo database. SQLite may be used for local development and automated verification without changing the data model.

## Folder structure

```text
personal-finance-tracker/
├── frontend/                 React/Vite responsive client
├── backend/                  FastAPI API, models, security, and API tests
├── ml/                       Preprocessing, linear regression, evaluation, demo data
├── dataset/                  Notes about the synthetic training dataset
├── docs/                     Architecture, schema, and API reference
├── screenshots/              Review screenshots
├── README.md
└── docker-compose.yml
```

## Data model

`users` owns `transactions`, `budgets`, `financial_goals`, `predictions`, and `notifications` through foreign keys. Transactions record income or expense, amount, category, date, description, and payment method. Budgets are unique per user/category/month/year. Goals record a target amount, current progress, deadline, and status. Predictions store period, forecast amount, method, and evaluation details. Notifications store a user-scoped message, type, creation time, and read state. Ownership is checked at every API boundary.

## Planned development phases

1. Project setup and runnable frontend/backend foundations.
2. Database models and persistence.
3. Secure registration, login, and protected routes.
4. Transaction CRUD.
5. Dashboard and date filters.
6. Budget management and risk states.
7. Analytics and traceable spending insights.
8. Synthetic ML dataset and preprocessing.
9. Forecast model training and evaluation.
10. Prediction API and honest cold-start behavior.
11. Recommendations and spending patterns.
12. Goals and explainable financial health score.
13. Unusual and recurring transaction detection.
14. Backend and ML verification.
15. Responsive UI polish.
16. Project documentation.
17. Optional container/deployment preparation.

## Local development

Prerequisites: Node.js 20+, Python 3.11+, and MySQL 8+ for the MySQL configuration. See `backend/.env.example` for environment variables. The API publishes interactive OpenAPI documentation at `/docs` when running.

```powershell
# Terminal 1
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload

# Terminal 2
cd frontend
npm install
npm run dev
```

The UI uses the API base URL from `VITE_API_URL` (default `http://localhost:8000`). Never commit `.env` files or real financial records. Seed/demo content must be clearly marked synthetic.

To create the fictional viva account, run `python seed_demo.py` from `backend/`. The script prints a generated demo password (or uses `FINSIGHT_DEMO_PASSWORD` from your local environment). This creates ten months of synthetic records in the configured local database; it is never seeded automatically.

For the optional container setup, copy the root `.env.example` to `.env`, replace the values, and run `docker compose up --build`. Open the site at `http://localhost:8080` and API docs at `http://localhost:8000/docs`.

## Verification and ML demo

```powershell
# From backend/
pip install -r requirements-dev.txt
python -m pytest -q tests

# From ml/
python data/generate_synthetic.py
python train.py data/synthetic_monthly_expenses.csv
```

## Screenshots

Add verified application screenshots here as the user-facing flows are completed.

## API and database references

See [API reference](docs/api.md) and [database model](docs/data-model.md).

## Scope and limitations

FinSight is an educational project, not financial advice. Forecasts are estimates and should only be shown when there is adequate historical data; metrics are descriptive of the records entered by the user.
