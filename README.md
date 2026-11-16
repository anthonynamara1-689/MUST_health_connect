# MUST HealthConnect

A Django + PostgreSQL web app built on the **MUST HIV/AIDS Policy (Nov 2019)**.

- **Students** can find HIV services near campus, read plain answers and ask a question anonymously. They need no account, and nothing they search is saved.
- **Peer educators** can record event attendance (headcounts only, no names), issue condoms and test kits, and see the quarterly report against the policy's 9 budget lines (UGX 36M a year).

The assignment topic is **database connectivity**, so the code is built to show 10 connectivity features. They are listed under "The 10 connectivity features" below.

---

## 1. Install these first (Windows)

| What | Where | Notes |
|---|---|---|
| Python 3.12 or 3.13 | python.org | Tick **"Add python.exe to PATH"** in the installer |
| PostgreSQL 17 (or 16/18) | postgresql.org → Download → Windows (EDB installer) | **Write down the `postgres` password you choose.** Keep port 5432 |
| VS Code + Python extension | code.visualstudio.com | VS Code will suggest the extensions when you open the folder |

You do **not** need Node.js. The CSS is already built and is in `static/css/tailwind.css`.

## 2. Set up (about 5 minutes)

1. Unzip the project and open the **`healthconnect`** folder in VS Code (File → Open Folder).
2. Open a terminal (Terminal → New Terminal) and run these from the project folder:

```powershell
# 1. Create mustvenv, install packages, create .env with a secret key
powershell -ExecutionPolicy Bypass -File setup.ps1

# 2. Create the database and its two users (asks for your postgres password)
powershell -ExecutionPolicy Bypass -File setup_db.ps1

# 3. Allow venv activation in PowerShell (one time per Windows user), then activate
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\mustvenv\Scripts\Activate.ps1

# 4. Build the tables, views, trigger and procedure, then load demo data
python manage.py migrate
python manage.py seed_demo

# 5. Your own admin login, then start the site
python manage.py createsuperuser
python manage.py runserver
```

3. Open **http://127.0.0.1:8000**.

Once activated, the prompt starts with `(mustvenv)`. VS Code is already set to use `mustvenv`. If it asks, choose it with Ctrl+Shift+P → "Python: Select Interpreter" → `.\mustvenv\Scripts\python.exe`.

**Shortcut:** Terminal → Run Task… lists every step above, plus "Run tests" and "Database demo". Tasks use mustvenv's Python directly, so they work without activating.

## 3. Pages and logins

| URL | Who | What |
|---|---|---|
| `/` | Students | Search, topics, featured services, next event |
| `/topics/` | Students | 10 topics |
| `/support/` | Students | Service directory: search, need and campus filters, grid/list toggle, details dialog |
| `/events/` | Students | Upcoming and recent public events |
| `/ask/` | Students | Anonymous question (stores no name, email or IP) |
| `/staff/` | Peer educators | Quarterly report against the 9 policy budget lines, with an All / Behind / On track filter |
| `/staff/events/` | Peer educators | Record attendance (gender × year headcounts, live totals) and a "Plan an event" dialog |
| `/staff/stock/` | Peer educators | Issue stock, with the SQL of each transaction replayed line by line and a crash switch |
| `/health/db/` | Anyone | JSON health check of both database connections |
| `/admin/` | Staff | Django admin |

- **Peer educator:** `peer1` / `peer-demo-2026`. This user is staff but not a superuser, so they can plan events and view the audit log but can't read student feedback.
- **Admin:** the superuser you created in step 5.

The demo passwords (peer1 and the two database roles) are only for your own laptop.

## 4. Where things are

```
healthconnect/
├── config/             settings.py (both DB connections, pool), db_router.py, urls.py
├── portal/             student side: models (Service, Feedback), views, forms
├── tracker/            staff side
│   ├── services.py     ← raw SQL transaction with SELECT ... FOR UPDATE (read this!)
│   ├── views.py        report (reads views via the read-only connection), events, stock, health
│   ├── middleware.py   friendly 503 page when PostgreSQL is down
│   ├── migrations/0002_reporting_views.py   ← SQL views, GRANT, audit trigger, stored procedure
│   ├── management/commands/   seed_demo, demo_db, bench_pool
│   └── tests.py
├── templates/          base.html, partials/ (header, footer, icons, shared CSS components), portal/, tracker/, errors/
├── static/             css/tailwind.css (prebuilt), js/alpine.min.js, fonts/, img/
├── docs/setup.sql      creates DB + roles hc_app (owner) and hc_report (read-only)
├── docs/reset.sql      wipes everything so you can start again
├── .env.example        settings template; setup.ps1 copies it to .env
└── setup.ps1, setup_db.ps1, setup.sh
```

## 5. The 10 connectivity features

| # | Feature | Where in the code | How to show it |
|---|---|---|---|
| 1 | Config from environment, no secrets in code | `.env`, `config/settings.py` (`load_dotenv`, `os.environ[...]`) | Open `.env` and settings side by side |
| 2 | Two connections with different privileges | `DATABASES["default"]` = `hc_app`, `DATABASES["reports"]` = `hc_report`; `docs/setup.sql`; `config/db_router.py` | `python manage.py demo_db`, parts 1–2 |
| 3 | Connection pooling (psycopg_pool) | `pool_options()` in `settings.py`, `DB_POOL` in `.env` | `bench_pool`, see 6.6 |
| 4 | Parameterised SQL (no injection) | `%s` placeholders in `tracker/services.py`, `tracker/views.py` | `demo_db` part 3; type `x' OR '1'='1` in the search box |
| 5 | Transactions (all or nothing) | `transaction.atomic()` in `services.issue_stock` and the events view | Over-issue, plus the crash switch, see 6.2 |
| 6 | Row locking under concurrency | `SELECT ... FOR UPDATE` in `services.py` | Two windows, see 6.3 |
| 7 | Database objects: views, trigger, stored procedure | `tracker/migrations/0002_reporting_views.py` | Report page; admin → Audit logs; `demo_db` part 5 |
| 8 | Error handling when the DB is down | `tracker/middleware.py`, `except OperationalError` in `views.stock` | Stop PostgreSQL, see 6.5 |
| 9 | ORM vs raw SQL, and the N+1 problem | ORM in `portal/views.py` (`prefetch_related`); raw SQL in `services.py` | `demo_db` part 4 |
| 10 | Health check | `db_status()` and `health_db` in `tracker/views.py`; the green badge on the report | Open `/health/db/` |

Also: CHECK constraints (stock can't go negative, rating 1–5) and UNIQUE constraints in `models.py`, plus a `DateField` index.

## 6. Demo script (about 10 minutes)

**Before you start:** `runserver` is running, `seed_demo` has been run, and you are logged in as `peer1` in the browser.

### 6.1 One command for features 2, 4, 7 and 9
```powershell
python manage.py demo_db
```
It shows:
- which PostgreSQL user each connection logs in as;
- that `hc_report` is refused on the tables;
- an f-string query leaking every row next to a parameterised query matching 0;
- 6 queries vs 2 (the N+1 problem);
- the stored procedure refusing an over-issue.

It changes no data.

### 6.2 Transactions: `/staff/stock/`
1. Issue 3 condoms. The dark panel shows `BEGIN → SELECT … FOR UPDATE → UPDATE → INSERT → COMMIT`.
2. Ask for more than the stock. The panel ends in a red `ROLLBACK`, and nothing changes.
3. Crash half-way: turn on **Simulate a crash** (top of the dark panel) and issue again. The UPDATE ran, then the "crash", then ROLLBACK, and the stock number is unchanged. The switch turns itself off after each issue. (`HC_FAIL_AFTER_UPDATE=True` in `.env` does the same for every issue.)

The quantity box warns you before an over-issue, but still lets you send it, so you can show PostgreSQL refusing it.

### 6.3 Row locking: two windows at once
1. In `.env` set `HC_LOCK_DEMO_SECONDS=8` and restart runserver.
2. Open `/staff/stock/` in two browser windows, side by side, with the same item and pick-up point.
3. Click **Issue stock** in window 1, then quickly in window 2. Window 2 waits until window 1 commits, then works from the new quantity, so no stock is lost.
4. Set it back to `0` afterwards.

### 6.4 Views and the read-only connection: `/staff/`
The report is read from `v_policy_lines` and `v_quarterly_progress` through the `reports` connection, which logs in as `hc_report`. The green badge shows the live `SELECT 1` time. **Admin → Audit logs** shows rows that the PostgreSQL trigger wrote by itself.

### 6.5 Database down
1. Stop PostgreSQL. Either open `services.msc` → `postgresql-x64-17` → Stop, or in an **admin** terminal run `net stop postgresql-x64-17`.
2. Refresh `/`. You get the friendly "can't reach our database" page (HTTP 503), not a crash.
3. Open `/health/db/`. It shows `"ok": false` for both connections.
4. Start the service again (`net start postgresql-x64-17`) and refresh. The pool may need one or two refreshes to reconnect.

### 6.6 Connection pooling
1. With runserver running, run `python manage.py bench_pool --requests 200` in a second terminal. Note the time.
2. Set `DB_POOL=False` in `.env`, restart runserver, and run it again. Without the pool, every request opens a new connection, so it is slower.
3. Set it back to `True`.

### 6.7 Tests
```powershell
python manage.py test
```
The 18 tests cover these points:
- over-issue and crash roll back;
- the trigger writes the audit log;
- the CHECK constraint holds;
- the stored procedure works;
- SQL injection is harmless;
- feedback stores no identity;
- every page loads with the demo data;
- the "Plan an event" dialog saves an event, and the crash switch leaves stock unchanged.

## 7. Before you present: read these files

You should be able to explain:

1. **`tracker/services.py`**: why `FOR UPDATE`, and why everything sits inside `transaction.atomic()`.
2. **`tracker/migrations/0002_reporting_views.py`**: what each view, the trigger and the procedure do.
3. **`config/settings.py`**: the two `DATABASES` entries and `pool_options()`.
4. **`tracker/views.py` → `report`**: why it uses `connections["reports"]`.
5. **`docs/setup.sql`**: what `hc_report` is allowed to do (USAGE on the schema, SELECT on 4 views).

## 8. Changing the look

The design follows the screen plan: navy header with a sun-yellow underline on the current page, a blue band for each page title, white cards on the pale staff background, and one sun-yellow button for the main action on each screen.

- **Colours, shadows, fonts:** `tailwind.config.js` (and the copy at the top of `templates/base.html` used in CDN mode).
- **Shared building blocks** such as `btn-primary`, `input`, `select`, `panel`, `tile`, `seg` (segmented toggle) and `switch`: `templates/partials/tailwind_components.css`.
- **Icons:** `templates/partials/icon.html`. Use `{% include "partials/icon.html" with name="search" cls="h-5 w-5" %}`.
- **Interactivity** (menus, dialogs, filters, live totals) uses Alpine.js, loaded from `static/js/`. Look for `x-data`, `x-show` and `@click` in the templates.
- **Hero picture:** `static/img/hero.jpg` is an illustration. Replace it with a photo of your own if you have one (1200 × 800 is a good size).
- **New Tailwind classes:** the prebuilt CSS only contains classes already used in the templates. While you edit, set `HC_TAILWIND_CDN=True` in `.env` and every Tailwind class will work (this needs internet). Before the demo, either:
  - set it back to `False` (works offline); or
  - if you added new classes, rebuild the CSS with Node: `npm install`, then `npm run build:css`.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then try again |
| `python` opens the Microsoft Store | Install Python from python.org (setup.ps1 uses the `py` launcher if it's there) |
| `psql is not recognized` | Use `setup_db.ps1`, which finds psql itself, or run `"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -f docs\setup.sql` |
| `password authentication failed for user "postgres"` | Use the password you chose when installing PostgreSQL |
| `password authentication failed for user "hc_app"` | The passwords in `.env` must match `docs/setup.sql`. If unsure, run `docs/reset.sql` then `setup_db.ps1` again |
| `connection refused` / `could not connect to server` | The PostgreSQL service isn't running. Start it in `services.msc` |
| `KeyError: 'DJANGO_SECRET_KEY'` or `'DB_APP_USER'` | `.env` is missing. Run `setup.ps1` again |
| `permission denied for table ...` on the report | Run `python manage.py migrate` (migration 0002 grants SELECT on the views) |
| Tests: `permission denied to create database` | In psql as postgres: `ALTER ROLE hc_app CREATEDB;` |
| Page has no styling | Keep `DJANGO_DEBUG=True` locally (Django only serves static files in debug mode) |
| PostgreSQL on another port | Change `DB_PORT` in `.env` |
| Start completely fresh | `psql -U postgres -h localhost -f docs/reset.sql`, then `setup_db.ps1`, `migrate`, `seed_demo` |

macOS/Linux: use `bash setup.sh`, `psql -U postgres -h localhost -f docs/setup.sql` and `source mustvenv/bin/activate`. Everything else is the same.
