# Database migrations (manual)

Run all commands from the project root with the virtualenv active.

## Phase A — After infrastructure setup (no models yet)

```powershell
cd c:\Users\olado\Documents\fastapi-projects\smartsales_backend
.\.venv\Scripts\Activate.ps1
python -c "from app.database import Base, engine; print('OK', engine.url)"
alembic check
```

If `alembic check` is unavailable, use `alembic history` (empty history is expected).

## Phase B — Business table only (`businesses`)

Prerequisites:

- PostgreSQL is running
- `DATABASE_URL` in `.env` is correct
- `app.models.business` is imported in `alembic/env.py`

### 1. Confirm metadata

```powershell
cd c:\Users\olado\Documents\fastapi-projects\smartsales_backend
.\.venv\Scripts\Activate.ps1
python -c "from app.database import Base; from app.models import business; print(sorted(Base.metadata.tables.keys()))"
```

Expected output: `['businesses']`.

### 2. Generate migration

```powershell
alembic revision --autogenerate -m "add businesses table"
```

Review the generated file under `alembic/versions/` before applying. Confirm:

- `CREATE TYPE industry_category_enum AS ENUM (...)`
- Table `businesses` with all columns
- Unique constraints on `business_email` and `whatsapp_phone_number_id`
- `downgrade()` drops the table and enum type

### 3. Apply migration

```powershell
alembic upgrade head
```

### 4. Verify

```powershell
alembic current
alembic history
```

### 5. Rollback (if needed)

```powershell
alembic downgrade -1
```

## Phase C — Remaining models (later)

After Lead, Message, Sale, and BusinessSettings are implemented, uncomment their imports in `alembic/env.py`, then:

```powershell
alembic revision --autogenerate -m "add tenant tables"
alembic upgrade head
```

Review each generated revision before applying.

## Fresh Alembic init (only if config is broken)

```powershell
# Backup the alembic folder first, then:
alembic init alembic
# Re-apply changes from alembic.ini and alembic/env.py in the repo
```
