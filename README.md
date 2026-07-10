# Habit Tracker — Backend

Django REST Framework API for the Habit/Goal Tracker, backed by Supabase
(Postgres + Auth). This service is a thin, typed layer between the React
frontend and Supabase — it does **not** own the data or run its own auth
system. Supabase is the single source of truth for both.

## Architecture

```
React (TypeScript) ──JWT──▶ Django REST API ──scoped client──▶ Supabase (Postgres + RLS)
                                   │
                          verifies JWT signature
                          (SupabaseJWTAuthentication)
```

- **Auth**: the frontend logs in via Supabase Auth directly and gets a JWT.
  That JWT is sent as `Authorization: Bearer <token>` on every request to
  this API.
- **Authorization**: Django verifies the JWT's signature and expiry, then
  builds a Supabase client authenticated *as that user* for the duration of
  the request. Postgres Row Level Security policies do the actual
  authorization — Django never has to remember to filter `WHERE user_id = ...`
  by hand, and there is no service-role "god mode" bypass anywhere in this
  codebase.
- **Data**: `habits.models.py` is intentionally empty. There are no Django
  migrations for `habits` or `check_ins` — those tables and their RLS
  policies live in Supabase, managed via the Supabase SQL Editor/dashboard.

## Why this is harder than it looks: streak logic

See `habits/services.py` for the full writeup, but the short version:

- Dates are compared as plain `date` objects (no datetimes) because the
  `completed_at` column is `DATE`, not `TIMESTAMP` — this avoids an entire
  class of timezone bugs. The frontend is responsible for sending "the
  user's local today" as a `YYYY-MM-DD` string.
- A streak that ended yesterday still counts as "current" until today ends
  — otherwise every streak looks broken every morning before the user has
  had a chance to check in.
- Missing a single day fully breaks the streak (grace periods are a
  deliberate v2 feature, not implemented here).

Run `habits/services.py`'s logic through the test cases in this README's
"Testing" section below before trusting it in production.

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   ``` 
   Fill in from your Supabase dashboard:
   - `SUPABASE_URL` — Project Settings → API → Project URL
   - `SUPABASE_ANON_KEY` — Project Settings → API → Project API keys → anon/public
   - `SUPABASE_JWT_SECRET` — Project Settings → API → JWT Settings → JWT Secret

3. **Run the dev server**
   ```bash
   python manage.py runserver
   ```
   API will be live at `http://localhost:8000/api/`.

## Endpoints

| Method | Path                          | Description                                  |
|--------|-------------------------------|-----------------------------------------------|
| GET    | `/api/habits`                 | List the user's habits with streak data      |
| POST   | `/api/habits`                 | Create a new habit                            |
| GET    | `/api/habits/<uuid>/history`  | Check-in history + heatmap for one habit     |
| POST   | `/api/check-ins`              | Log a completion (`{habit_id, date}`)        |
| DELETE | `/api/check-ins/<uuid>`       | Remove a completion (undo a check-in)        |

Every endpoint requires `Authorization: Bearer <supabase_jwt>`.

## Testing the streak logic

The streak calculator is a pure function with no Django/Supabase
dependencies, so it's trivial to sanity-check:

```bash
python3 -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'habit_tracker.settings')
django.setup()
from datetime import date, timedelta
from habits.services import calculate_streaks

today = date.today()
print(calculate_streaks([today, today - timedelta(days=1)], today=today))
"
```

## What's deliberately NOT in the MVP (v2 ideas)

- Custom habit frequencies (e.g. "every Monday" instead of daily)
- Grace periods / one skip per week without breaking a streak
- Backfilling/editing past check-ins
- Reminders/notifications
