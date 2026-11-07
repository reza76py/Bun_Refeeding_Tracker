# Shelf Replenishment Workload Tracker — Release 1 (MVP)

A small, reliable web app that **estimates** how long it takes to move products
from replenishment cages onto shelves, and lets you **measure** the real time so
you can compare forecast vs actual. Built for one person, two aisles, one store.

It is a personal workload-estimation tool — **not** an official Bunnings app and
not connected to any inventory, POS or ordering system. All data is entered by
hand.

> **Core principle:** every forecast here comes from *editable planning
> assumptions*, not a verified Bunnings or industry standard. Forecasts are never
> presented as measured time — measured actuals are stored and shown separately.

---

## What Release 1 does

- **Calculator** — edit the seven baseline variables (find, grab/unpack, place,
  units/line, other, lines/cage, cages) and instantly see time per line, per
  cage and per day, plus a by-cage-count table and a 30/45/70 sec/line what-if.
- **Today** — today's forecast scenarios and, if logged, the day's estimated vs
  measured time, interruptions, variance, and a workload-gap flag.
- **Daily log** — create a date, add cages, record actual minutes and status per
  cage (planned / in progress / complete / partial / blocked), and day-level
  shift + interruption minutes.
- **History** — 7- and 30-day totals and a per-day forecast-vs-actual table. No
  invented data: averages/charts only appear once real days exist.
- **Settings** — edit the store, aisle/bay catalogue counts, and planning
  assumptions. Saving assumptions creates a new **immutable version**; past days
  keep the snapshot they were forecast with, so history never changes.
- **Login** — Django session auth; every record is scoped to its owner.

**Deferred to later releases** (per the brief): stopwatch & per-line time study,
detailed interruption logging, CSV export and charts (Release 2); location-level
speed profiles and prediction (Release 3). No AI/ML until there's enough measured
data.

---

## Architecture

```
Browser ── React + TypeScript (Vite SPA)
   │  same origin: /api proxied to Django (Vite dev proxy, or nginx in Docker)
   ▼
Django + Django REST Framework ── session auth + CSRF
   │  pure calculation module (tracker/calculations.py) — no DB, fully unit-tested
   ▼
MySQL (default)  ·  SQLite (optional, for quick local runs and tests)
```

The domain calculations are deliberately separated from the API views and the
React components, so the maths is tested in isolation and reused by the API, the
seed command and the models.

### Folder layout

```
shelf-replenishment-tracker/
├── docker-compose.yml          # MySQL + Django(gunicorn) + nginx(React)
├── .env.example                # compose env (copy to .env)
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example            # local backend env (copy to backend/.env)
│   ├── Dockerfile  entrypoint.sh
│   ├── config/                 # Django project (settings, urls, wsgi/asgi)
│   └── tracker/                # the app
│       ├── calculations.py     # pure domain logic (forecasts, formatting)
│       ├── models.py           # Store, Aisle, Bay, AssumptionSet, WorkDay, CageLog
│       ├── services.py         # assumption versioning, active set, snapshots
│       ├── serializers.py  views.py  urls.py
│       ├── management/commands/seed.py
│       └── tests/              # test_calculations.py, test_api.py
└── frontend/
    ├── Dockerfile  nginx.conf
    ├── vite.config.ts          # dev proxy: /api -> http://localhost:8000
    └── src/
        ├── api/{client.ts,types.ts}   # shared API types + CSRF-aware fetch
        ├── lib/format.ts              # seconds -> "Xh Ym"
        ├── components/ui.tsx
        └── pages/{Login,Overview,Calculator,DailyLog,History,Settings}.tsx
```

---

## Running it

You have three options. **A** is the fastest to see it working (no MySQL).

### A. Quick local run with SQLite (no database to install)

**Backend** (one terminal):

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DB_ENGINE=sqlite
set DJANGO_SECRET_KEY=dev-secret
python manage.py migrate
python manage.py seed --username reza --password demo12345
python manage.py runserver
```

**Frontend** (second terminal):

```bat
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and sign in with `reza` / `demo12345`.

> The Vite dev server proxies `/api` to Django on port 8000, so the browser sees
> a single origin and session/CSRF cookies work with no CORS setup.

### B. Docker (MySQL, production-shaped)

```bash
cp .env.example .env            # then edit DJANGO_SECRET_KEY
docker compose up --build
```

Open <http://localhost:8080> and sign in with `demo` / `demo12345` (from `.env`).
nginx serves the built React app and proxies `/api` and `/admin` to gunicorn;
MySQL data persists in the `dbdata` volume. The backend waits for MySQL's
healthcheck, migrates, and seeds on first start.

### C. Local run with MySQL

Create a database and user, then:

```bat
cd backend
copy .env.example .env
rem edit .env: DB_ENGINE=mysql and the DB_* credentials
.venv\Scripts\activate
python manage.py migrate
python manage.py seed --username reza --password demo12345
python manage.py runserver
```

The MySQL driver is **PyMySQL** (pure Python) — no C compiler or system
libraries needed on Windows 11.

---

## Tests

```bat
cd backend
set DB_ENGINE=sqlite
python manage.py test
```

22 tests. They cover every calculation case in the brief (catalogue totals
3150 / 1800 / 4950; baseline 45 sec/line; 100 lines = 75 min; 2–5 cage day
totals; zero cages; find 30→40 adds 1000 sec; units 5→8) **plus** the API
guarantees: a past day's forecast is unchanged after new assumptions are saved,
measured and forecast values stay separately labelled, duplicate days are
rejected, and one user cannot read another's records.

The pure calculation tests also run with plain unittest, no database:

```bat
python -m unittest tracker.tests.test_calculations
```

---

## The baseline (provisional — not a standard)

| Sym | Variable | Baseline | Status |
|-----|----------|----------|--------|
| D | Find shelf location | 30 sec/line | assumption |
| E | Grab / unpack | 10 sec/line | assumption |
| F | Place one unit | 1 sec/unit | assumption |
| C | Units per line | 5 | assumption |
| G | Other (cleanup, cage moves) | 0 sec/line | excluded from baseline |
| B | Lines per cage | 100 | forecast input |
| A | Cages per day | 2–5 | rough range |

`line = find + unpack + (units × sec/unit) + other = 30 + 10 + 5 + 0 = 45 sec`
→ 100-line cage = **4,500 sec (1 h 15 m)** → 2–5 cages/day = **2 h 30 m – 6 h 15 m**.

The **4,950 catalogue lines** (aisle 9: 3,150; aisle 10: 1,800) describe *area
size only* — assumed distinct stocked lines, not units on shelves and not daily
replenishment demand. The app never converts a day's line operations into a
"% of catalogue replenished" figure.

---

## API reference (all under `/api/`, session-authenticated)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/auth/csrf/` | set the CSRF cookie (call before any POST/PATCH) |
| POST | `/auth/login/` · `/auth/logout/` · GET `/auth/me/` | session auth |
| GET | `/stores/` · PATCH `/stores/{id}/` | store name & timezone |
| GET | `/aisles/` · `/aisles/{id}/bays/` · PATCH `/bays/{id}/` | catalogue edit |
| GET | `/catalogue/summary/` | per-aisle & combined catalogue lines |
| GET/POST | `/assumptions/` · GET `/assumptions/active/` | versioned assumptions |
| POST | `/calculator/preview/` | forecast without saving |
| GET/POST | `/workdays/` · GET/PATCH `/workdays/{id}/` | daily log |
| POST | `/workdays/{id}/cages/` · PATCH/DELETE `/cages/{id}/` | cages |
| GET | `/dashboard/summary/?date=` · `/reports/summary/?from=&to=` | overview & history |

Durations are integer **seconds** from the backend; the UI formats them as
hours/minutes. The CSRF flow: the SPA calls `/auth/csrf/` once, then echoes the
`csrftoken` cookie in the `X-CSRFToken` header on every unsafe request.

---

## Notes & honest limitations

- This MVP was built and verified with the **SQLite** engine (full test suite +
  a live HTTP login/CSRF/calculator/work-day run through gunicorn's dev
  equivalent). The MySQL path is config-only and uses the same Django ORM; the
  Docker stack's compose file is validated, but the images were not built in the
  authoring environment, so build them once with `docker compose up --build`.
- `100 lines × 5 units = 500 units/cage` is an untested hypothesis, not a fact —
  bulky/heavy merchandise will differ. Treat all baseline numbers as starting
  points to replace with your own measured values.
- Excluded cleanup/cage-movement time (variable G = 0 in the baseline) means the
  forecast can under-estimate; add a value to G if you want it counted.
