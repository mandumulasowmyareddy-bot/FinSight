# FinSight data model

```mermaid
erDiagram
  USERS ||--o{ TRANSACTIONS : owns
  USERS ||--o{ BUDGETS : plans
  USERS ||--o{ FINANCIAL_GOALS : tracks
  USERS ||--o{ PREDICTIONS : receives
  USERS ||--o{ NOTIFICATIONS : receives
  USERS { int id PK string name string email UK string password_hash }
  TRANSACTIONS { int id PK int user_id FK string type decimal amount string category string description date date string payment_method }
  BUDGETS { int id PK int user_id FK string category decimal amount int month int year }
  FINANCIAL_GOALS { int id PK int user_id FK string title decimal target_amount decimal current_amount date deadline }
  PREDICTIONS { int id PK int user_id FK string target_month decimal amount string method datetime created_at }
  NOTIFICATIONS { int id PK int user_id FK string kind string message boolean is_read datetime created_at }
```

Indexes support user/date and user/category transaction queries. A unique user/category/month/year key prevents duplicate budgets. Passwords are salted scrypt hashes; raw passwords are never stored. All financial records are owner-scoped.
