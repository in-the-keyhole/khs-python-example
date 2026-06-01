# khs-python-example — FastAPI for Node developers

A minimal FastAPI server, structured so each piece maps to something you
already know from Express / Fastify. Skim the **Mental model** section first,
then run it and poke at the code.

---

## 1. Setup

This project uses [**uv**](https://docs.astral.sh/uv/) — the modern,
all-in-one Python project manager (think `nvm` + `npm` + `npx`, but Rust-fast).
It manages the Python version, virtualenv, and dependencies for you.

### Install uv (once per machine)

```bash
# macOS / Linux
brew install uv                                                   # if you have Homebrew
curl -LsSf https://astral.sh/uv/install.sh | sh                   # otherwise

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Bootstrap the project

From the project root:

```bash
uv sync
```

That single command:

1. Reads `pyproject.toml` and sees this project needs **Python 3.12+**.
2. Downloads & installs Python 3.12 if you don't already have it.
3. Creates `.venv/` in the project root.
4. Installs all dependencies from `pyproject.toml` into `.venv/`.
5. Writes `uv.lock` (commit this — it's your `package-lock.json`).

No `source .venv/bin/activate` needed.

### Cross-platform support

The lockfile is resolved to work on all of these out of the box:

- macOS Intel (`x86_64`)
- macOS Apple Silicon (`arm64`)
- Linux x86_64 (including WSL2 on Windows)
- Windows native (`win32` / AMD64)

This is configured in `pyproject.toml` under `[tool.uv] required-environments`.
**Caveat for Windows:** Apache Airflow doesn't officially support Windows, so
the Airflow dev deps (`apache-airflow*`) are scoped to non-Windows platforms
with a `; sys_platform != 'win32'` marker. The FastAPI app, tests, lint,
format, and Terraform examples all work on every platform — only the
`airflow/dags/*.py` files can't be locally imported on native Windows.
Use WSL2, or the devcontainer (see below), to sidestep this entirely.

### Three ways to run the project

| Mode                    | When to use                                      | How to start                       |
| ----------------------- | ------------------------------------------------ | ---------------------------------- |
| **Native (uv)**         | Fastest iteration. Default.                      | `uv sync && uv run poe dev`        |
| **Docker (compose)**    | Test the production image locally; reproduce a prod-like environment. | `docker compose up --build`        |
| **Devcontainer**        | Identical Linux dev env across all your machines. Avoids the Windows-Airflow caveat. | VSCode → "Reopen in Container"     |

#### Docker

[Dockerfile](Dockerfile) is a two-stage build that produces a slim
production image with just the venv + app code (~150 MB) running as a
non-root user. [compose.yaml](compose.yaml) bind-mounts `./app` for
hot-reload during local development.

```bash
docker compose up --build        # build + run, foreground
docker compose up -d             # background
docker compose down              # stop + remove
docker compose logs -f api       # tail logs
```

#### Devcontainer

[.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) defines a
Microsoft-published Python 3.12 base, installs uv, runs `uv sync` on first
boot, and pre-configures VSCode with the right Python interpreter, ruff
formatter, and recommended extensions. Open the project in VSCode →
**Dev Containers: Reopen in Container** → wait ~60s on first launch.

Because the container is Linux, Airflow installs natively — your DAGs are
fully resolvable, lintable, and importable even when the host is Windows.
For a multi-machine setup this is the lowest-friction path to "same env
everywhere".

### Run the dev server

```bash
uv run uvicorn app.main:app --reload
```

`uv run <cmd>` executes a command inside the project's venv automatically —
the equivalent of `npx`. You'll prefix most commands with `uv run`.

- `uvicorn` = the ASGI server (analogous to Node's runtime + `app.listen()`).
- `app.main:app` = "import `app` from the module `app.main`" — same idea
  as `require('./app/main').app`.
- `--reload` = nodemon-style hot reload.

Then open:

- http://127.0.0.1:8000 — root route
- http://127.0.0.1:8000/docs — **interactive Swagger UI, free, auto-generated
  from your code.** This alone is worth the price of admission.
- http://127.0.0.1:8000/redoc — alternative API docs

### Try it

```bash
curl http://127.0.0.1:8000/items
curl -X POST http://127.0.0.1:8000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"widget","price":9.99}'
curl http://127.0.0.1:8000/items/1
```

Try sending an invalid body (`{"name":""}`) and watch FastAPI return a
detailed 422 — no manual validation written.

### Common uv commands

| Task                          | Command                                     |
| ----------------------------- | ------------------------------------------- |
| Install/refresh deps          | `uv sync`                                   |
| Add a new dependency          | `uv add httpx`                              |
| Add a dev-only dependency     | `uv add --dev pytest`                       |
| Remove a dependency           | `uv remove httpx`                           |
| Run any command in the venv   | `uv run <cmd>` (e.g. `uv run python`)       |
| Open a Python REPL            | `uv run python`                             |
| Upgrade a package             | `uv lock --upgrade-package fastapi`         |

### npm scripts equivalent: Poe the Poet

Tasks are defined under `[tool.poe.tasks]` in `pyproject.toml` — the
closest analogue to `package.json` "scripts". Run them with:

```bash
uv run poe              # list available tasks
uv run poe dev          # start the dev server (hot reload)
uv run poe test         # run pytest
uv run poe lint         # ruff check (ESLint equivalent)
uv run poe format       # ruff format (Prettier equivalent)
uv run poe check        # lint + format check + tests — the CI gate
uv run poe test:k validation   # `test:k` forwards extra args to pytest -k
```

| npm                          | Poe                                |
| ---------------------------- | ---------------------------------- |
| `npm run <task>`             | `uv run poe <task>`                |
| `package.json` `"scripts"`   | `pyproject.toml` `[tool.poe.tasks]`|
| ESLint / Prettier            | `ruff check` / `ruff format`       |

Other Python task runners you'll see in real codebases: **`just`** (a
`justfile`, similar to Make but cleaner), **`make`** (universal,
gnarly syntax), **`tox`** / **`nox`** (testing-matrix focused).

---

## 2. Mental model: Node → Python

| Node / Express / Fastify             | Python / FastAPI (with uv)                    |
| ------------------------------------ | --------------------------------------------- |
| `package.json`                       | `pyproject.toml`                              |
| `package-lock.json`                  | `uv.lock`                                     |
| `npm install`                        | `uv sync`                                     |
| `npm install foo`                    | `uv add foo`                                  |
| `npm uninstall foo`                  | `uv remove foo`                               |
| `npx <cmd>`                          | `uv run <cmd>`                                |
| `node_modules/`                      | `.venv/` (managed for you by uv)              |
| `nvm use 20`                         | `requires-python` in `pyproject.toml`         |
| `require('./foo')` / `import`        | `from app.foo import bar`                     |
| `module.exports = app`               | module-level `app = FastAPI()` — imported by path |
| `const app = express()`              | `app = FastAPI()`                             |
| `app.listen(8000)`                   | `uvicorn app.main:app` (server is separate)   |
| `app.get('/items', handler)`         | `@router.get('/items')` above a function      |
| Express `Router()` / Fastify plugin  | `APIRouter(prefix='/items')`                  |
| `req.params.id`                      | function arg matching the path: `item_id: int` |
| `req.query.limit`                    | function arg with a default: `limit: int = 10` |
| `req.body` (+ Zod/Joi validation)    | function arg typed as a Pydantic model        |
| `res.json(data)`                     | `return data` (dict or Pydantic model)        |
| `res.status(404).json(...)`          | `raise HTTPException(404, detail=...)`        |
| Middleware                           | `@app.middleware('http')` or `Depends(...)`   |
| `nodemon`                            | `uvicorn --reload`                            |
| Jest / Vitest                        | `pytest`                                      |
| ESLint / Prettier                    | `ruff` (linter + formatter, all in one)       |
| TypeScript types                     | type hints — but enforced *at runtime* by FastAPI |

### The one big idea that's different

In Express you reach **into** a `req` object to pull things out. In FastAPI
you declare what you want as **typed function parameters** and the framework
inspects the signature to figure out where each value comes from:

```python
def get_item(
    item_id: int,                              # path param (matches {item_id})
    include_meta: bool = False,                # query string (?include_meta=true)
    payload: ItemCreate,                       # request body (Pydantic model)
    store: ItemStore = Depends(get_store),     # dependency injection
) -> Item:
    ...
```

No `req`, no `res`. The types *are* the contract — they drive validation,
serialization, and the auto-generated OpenAPI docs.

---

## 3. Project layout

```
app/                 # FastAPI server (Python web-app side) — layered MVC-style
  main.py            # entrypoint — like server.js / app.js
  models/            # MODELS: static schemas (no behavior), split by slice
    items.py         #   ItemCreate, Item
    orders.py        #   OrderStatus, OrderCreate, Order (SQLModel table)
    common.py        #   Message (shared response envelope)
  routers/           # VIEWS: thin endpoints — validate input, call a service, shape the response
    items.py         # a router — like an Express Router
    orders.py        # orders CRUD against Postgres (see §10)
    streaming.py     # streaming responses / SSE
    demo.py          # async vs sync lab
  services/          # data-access layer the views depend on (see §3.1)
    items.py         # in-memory "DB" for items — a stateful singleton + DI provider
    orders.py        # stateless persistence functions for orders (take a Session)
  controllers/       # business-logic layer — an intentional stub today (see §3.1)
  clients/           # CLIENTS: connections to external systems (see §3.1)
    db.py            # SQLModel engine + session DI provider for orders (see §10)
    datadog.py       # DogStatsD metrics client — sends analytics to Datadog (see §3.2)
  middleware/        # cross-cutting request wrappers
    metrics.py       # per-request throughput + latency metrics (see §3.2)
tests/               # pytest suite (see §6)
airflow/             # Airflow DAGs — the Python you'll actually write at work (see §8)
  dags/
    etl_basic.py
    bigquery_pipeline.py
    postgres_to_bq_orders.py   # the end-to-end ETL DAG (see §10)
infra/               # Terraform: GCS, Pub/Sub, SA, Workload Identity (see §9)
  main.tf            # APIs, GCS, Pub/Sub, Airflow SA + Workload Identity
  cloudsql.tf        # Cloud SQL Postgres + Secret Manager (see §10)
  bigquery.tf        # BigQuery analytics dataset + tables (see §10)
Dockerfile           # multi-stage prod image (see §1)
compose.yaml         # api + postgres for local end-to-end (see §1, §10)
.devcontainer/       # VSCode "Reopen in Container" config (see §1)
pyproject.toml       # project metadata + deps (like package.json)
uv.lock              # locked dep versions (like package-lock.json) — commit it
.venv/               # managed by uv — do not commit
.gitignore
```

Read them in this order: `main.py` → `routers/items.py` → `models/items.py` → `services/items.py`.

### 3.1 How the layers fit together

The app is organized in an MVC-ish layering, mapped onto FastAPI idioms:

| Layer | Lives in | Role |
| --- | --- | --- |
| **Views** | `app/routers/` | Endpoints. Parse/validate input (via the typed signature), call a service, shape the HTTP response (status codes, 404s). No data-access logic. |
| **Controllers** | `app/controllers/` | Business logic / use cases. An intentional empty stub today — current endpoints are thin CRUD with no business logic to hold yet. |
| **Services** | `app/services/` | Data access. Two shapes: a *stateful singleton* (`items.ItemStore`, owns in-memory state) and *stateless functions* (`orders`, each take a request-scoped `Session`). |
| **Models** | `app/models/` | Static data + declarative validation, split by slice (`items`, `orders`, `common`). No methods, no behavior. |
| **Clients** | `app/clients/` | Connections to external systems (the Postgres engine + `get_session` today; a cache or queue would join it). Services depend on clients; clients hold no business logic. |

The dependency direction is one-way — `views → controllers → services → clients → external systems` — and the wiring between layers is FastAPI's `Depends(...)`, not ad-hoc imports. `orders.py` is the clearest example: the router holds no SQL, it just delegates to `app.services.orders`. (`streaming.py` and `demo.py` keep their trivial generator logic inline — they're teaching examples, not worth a service layer.)

### 3.2 Sending metrics to Datadog (the clients layer in action)

`app/clients/datadog.py` is a second client alongside `db.py` — it sends custom
application metrics ("analytics") to Datadog over **DogStatsD**. The flow is the
same one you'd run in production on GKE or Cloud Run:

```
  app  --UDP-->  Datadog Agent (DogStatsD :8125)  --HTTPS-->  Datadog
```

The app never holds a Datadog API key — it fires fire-and-forget UDP packets at
a local Agent, which batches and forwards them. Sends never block and never
raise, so instrumentation can't slow down or break a request.

**Safe by default.** Metrics are OFF unless `DD_METRICS_ENABLED` is truthy. With
it off (local dev, the test suite), every metric call is a no-op and no socket
is opened — the app runs exactly as if Datadog weren't wired in.

**The demo.** `POST /orders` emits two metrics (see `app/routers/orders.py`):

- `khs.orders.created` — a **counter**, tagged `region:` and `status:`
- `khs.orders.total_cents` — a **histogram** (Datadog derives avg/p95/max), same tags

The view gets the client via `Depends(get_metrics)` — the same DI seam as the DB
session and item store. That's also what makes it testable without a network:
`tests/test_metrics.py` overrides `get_metrics` with a recording fake and asserts
the endpoint emits the expected metrics.

**App-wide request metrics.** `app/middleware/metrics.py` emits two metrics for
*every* request (not just orders):

- `khs.http.requests` — a **counter** (throughput)
- `khs.http.request.duration_ms` — a **histogram** (latency)

both tagged `method:`, `status:`, and `path:` — where `path` is the matched
*route template* (`/orders/{order_id}`), never the raw path, so tag cardinality
stays bounded. It's a **pure ASGI middleware** on purpose: Starlette's
`BaseHTTPMiddleware` buffers the response body, which would break the
`/stream/*` endpoints and skew timing; the ASGI version only reads the status
line off `send`, leaving streaming intact (there's a test for exactly that).

**See it end-to-end locally.** Bring up the Agent (compose `observability`
profile) with your API key, then run the app with metrics on:

```bash
export DD_API_KEY=...    # app.datadoghq.com → Organization Settings → API Keys
docker compose --profile observability up -d datadog-agent   # DogStatsD on :8125
DD_METRICS_ENABLED=true uv run poe dev                       # app emits to the agent

# create a few orders, then look for `khs.orders.created` in Datadog → Metrics Explorer
curl -X POST http://localhost:8000/orders -H 'Content-Type: application/json' \
  -d '{"customer_id": 42, "total_cents": 1999, "region": "us-west"}'
```

Without an Agent (or with `DD_METRICS_ENABLED` unset) everything still works —
the metrics simply go nowhere. To add more later, inject the client into any
view and call `increment` / `gauge` / `histogram`; domain-event metrics could
also move into an `orders` controller as business logic grows.

---

## 4. Python-isms worth knowing on day one

- **Indentation is syntax.** Four spaces per level. No braces. Don't mix tabs and spaces.
- **No `const` / `let`.** Just `x = 5`. Reassignment is allowed; convention is
  `UPPER_CASE` for constants.
- **`None` is `null`/`undefined`.** Single value, no twin gotcha.
- **`snake_case` for functions and variables**, `PascalCase` for classes.
  PEP 8 is the style guide everyone follows. `ruff format` enforces it.
- **f-strings** are template literals: `f"Item {item_id} deleted"`.
- **Type hints are optional but FastAPI requires them** for parameters it
  needs to introspect. They are checked at runtime by FastAPI / Pydantic,
  unlike TypeScript which erases them at build time.
- **`from foo import bar`** is the most common form. There is no default
  export; everything is named.
- **No `async` required.** FastAPI handlers can be plain `def` *or* `async def`.
  Use `async def` only when you're calling something awaitable
  (e.g. `httpx`, `asyncpg`). Plain `def` handlers run on a threadpool —
  fine for CPU-light work and learning.

---

## 5. Async & streaming lab

Two new routers let you poke at Python's async model directly.

### Streaming responses (`app/routers/streaming.py`)

Async generators (`async def` + `yield`) wrapped in `StreamingResponse`.
The full body never sits in memory — chunks ship as they're produced.

```bash
# Plain text, one line per chunk (-N disables curl buffering)
curl -N 'http://127.0.0.1:8000/stream/count?to=5&delay=0.5'

# Server-Sent Events — the format LLM token streams use
curl -N http://127.0.0.1:8000/stream/events

# NDJSON — one JSON object per line, great for piping
curl -N http://127.0.0.1:8000/stream/json | jq -c .
```

In the browser console try:

```js
const es = new EventSource('http://127.0.0.1:8000/stream/events')
es.onmessage = (e) => console.log(JSON.parse(e.data))
```

### Sync vs. async, felt directly (`app/routers/demo.py`)

Three endpoints that all "sleep" for `?seconds=N`. Hit each one **twice in
parallel** and time the total — the difference is the whole lesson:

```bash
# BAD — time.sleep blocks the loop. Two calls serialize.
time (curl -s 'http://127.0.0.1:8000/demo/blocking?seconds=2' & \
      curl -s 'http://127.0.0.1:8000/demo/blocking?seconds=2' & wait)
#   → ~4 seconds

# GOOD — asyncio.sleep yields. Two calls overlap.
time (curl -s 'http://127.0.0.1:8000/demo/async-sleep?seconds=2' & \
      curl -s 'http://127.0.0.1:8000/demo/async-sleep?seconds=2' & wait)
#   → ~2 seconds

# ALSO GOOD — plain `def` runs on FastAPI's threadpool.
time (curl -s 'http://127.0.0.1:8000/demo/threadpool?seconds=2' & \
      curl -s 'http://127.0.0.1:8000/demo/threadpool?seconds=2' & wait)
#   → ~2 seconds
```

The takeaway: inside `async def` you must **never** call a blocking sync
function. Either switch to an async variant (`asyncio.sleep`, `httpx`,
`aiofiles`, `asyncpg`) or drop the `async` keyword so FastAPI runs your
handler on a thread instead.

---

## 6. Testing

### The Python testing stack vs. Node

| Node                                  | Python                                          |
| ------------------------------------- | ----------------------------------------------- |
| `jest` / `vitest` / `mocha`           | **`pytest`** (de facto standard)                |
| `expect(x).toBe(y)`                   | plain `assert x == y` (pytest rewrites assertions for great error messages) |
| `beforeEach` / `beforeAll`            | `@pytest.fixture` in `conftest.py`              |
| `supertest`                           | `fastapi.testclient.TestClient`                 |
| `nock` (HTTP mocking)                 | `respx` for `httpx` / `responses` for `requests`|
| `sinon` (general mocking)             | `unittest.mock` (stdlib) / `pytest-mock`        |
| Snapshot testing                      | `syrupy`                                        |
| Coverage (`c8`, `nyc`)                | `coverage` + `pytest-cov`                       |
| Playwright (browser e2e)              | **`playwright` Python binding** (same API)      |
| Cypress                               | (no direct equivalent — Playwright wins here)   |

### What we set up in this project

Dev-only deps live in `[dependency-groups]` `dev` in `pyproject.toml`:

```toml
[dependency-groups]
dev = ["httpx>=0.28", "pytest>=9", "pytest-asyncio>=1"]
```

Add more with `uv add --dev <package>`. `uv sync` installs them; `uv sync --no-dev`
gives you a prod-only install.

### Run the tests

```bash
uv run pytest                     # all unit tests (fast, no database)
uv run pytest -v                  # verbose, lists each test
uv run pytest tests/test_storage.py        # one file
uv run pytest -k validation       # filter by name substring
uv run pytest -x                  # stop at first failure
uv run pytest --lf                # rerun only last-failed tests

uv run poe test                   # same as `pytest` — unit only
uv run poe test:int               # integration tests against a real Postgres (see below)
```

`uv run pytest` (and `poe test` / `poe check`) run **unit tests only** — the
integration suite is deselected by default so the everyday loop stays fast and
needs no database. See [Integration testing against real Postgres](#integration-testing-against-real-postgres) below.

### Three layers of tests, three files

The testing pyramid maps directly:

| Layer            | File                              | Tool used         |
| ---------------- | --------------------------------- | ----------------- |
| Unit             | `tests/test_storage.py`           | plain `assert`    |
| API integration  | `tests/test_items_api.py`, `tests/test_demo_api.py` | `TestClient`      |
| API + DB (SQLite) | `tests/test_orders_api.py`        | `TestClient` + in-memory SQLite |
| Streaming        | `tests/test_streaming_api.py`     | `TestClient.stream` |
| DB integration   | `tests/test_orders_integration.py` | `TestClient` + real Postgres (opt-in) |

`TestClient` is the heart of Python web testing — it runs your ASGI app
**in-process** (no server, no socket) and exposes a requests-like API.
Same role `supertest` plays in Node, just simpler to set up.

### `conftest.py` — pytest's magic file

`tests/conftest.py` defines **fixtures**: setup functions any test can
opt into by name. Look at it — the fixtures come in two families:

*In-memory / SQLite (the fast default):*

- `store` — a fresh `ItemStore` per test.
- `client` — a `TestClient` with `app.dependency_overrides` patched to
  use that per-test store. This is the Pythonic answer to "how do I
  swap a real database for a fake one in tests?" — FastAPI's DI system
  has a built-in seam for exactly that.
- `session` / `orders_client` — the same seam one layer down: an
  in-memory SQLite database per test, with `get_session` overridden so the
  Postgres-backed `/orders` handlers run without any database server.

*Real Postgres (opt-in, for integration tests):*

- `pg_engine` / `pg_session` / `integration_client` — point `get_session`
  at the throwaway `postgres-test` container instead. Covered in
  [Integration testing against real Postgres](#integration-testing-against-real-postgres).

A test just declares the fixture as a parameter and pytest wires it up:

```python
def test_create_and_get(client):     # `client` is the fixture
    client.post("/items", json={...})
    ...
```

No imports, no boilerplate, automatic per-test isolation.

### Integration testing against real Postgres

The `/orders` unit tests run against **in-memory SQLite** — fast, zero setup,
and they exercise the handlers, queries, and validation for real. But SQLite
isn't Postgres: it silently fakes things like `TIMESTAMPTZ`, and it won't catch
Postgres-specific SQL or constraint behavior. So there's a second, opt-in suite
that runs the same slice against a **real Postgres** in a throwaway container.

```bash
uv run poe test:int
```

That one command:

1. Starts a dedicated `postgres-test` container (Compose `test` profile,
   port **5433** so it never collides with your dev DB on 5432, `tmpfs`
   storage so it's in-memory and wiped on stop) and waits for it to be healthy.
2. Runs only the tests marked `@pytest.mark.integration`.
3. Tears the container down afterward — even if a test fails.

The integration tests live in `tests/test_orders_integration.py` and are
**deselected from the default `pytest` run** (via `addopts = -m "not
integration"` in `pyproject.toml`), so `poe test` and `poe check` stay fast and
need no Docker.

**How the isolation works.** The `pg_session` fixture opens a transaction per
test and **rolls it back** at teardown, so the shared database returns to empty
between tests with no truncation or table re-creation. It uses SQLAlchemy's
`join_transaction_mode="create_savepoint"`, which lets the handlers call
`session.commit()` for real (committing into a SAVEPOINT) while the outer
transaction still unwinds everything on rollback. Fast *and* exercises real
commit/refresh paths.

**Pointing at a different database.** The fixture reads `TEST_DATABASE_URL` and
falls back to the local `postgres-test` URL. In CI, set that env var to your
service-container's URL and `uv run pytest -m integration` runs the same suite
unchanged. If the database isn't reachable, the integration tests **skip** with
a pointer to `poe test:int` rather than erroring.

The pattern generalizes: as more of the app becomes database-backed, new
integration tests reuse these same fixtures — SQLite for the fast inner loop,
real Postgres for the prod-like gate.

### Where does Playwright fit?

Playwright has an official Python binding (`pip install playwright`,
`playwright install`) with the **same API** as the JS version. Use it
when you have a real browser frontend to drive.

This project is a backend-only API, so there's no browser to test. The
`TestClient` covers everything Playwright would — but at the HTTP layer
instead of the DOM layer. If you later add a React or HTMX frontend,
`uv add --dev playwright` and you're off.

For testing FastAPI against a *real* uvicorn process (e.g. to verify
production startup, signals, multi-worker behavior), spin up the server
with `subprocess.Popen` in a fixture and hit it with `httpx`. Rarely
needed — `TestClient` is faster and catches the same bugs 95% of the time.

---

## 7. Where this project leaves off, and what's next at work

FastAPI is great for learning Python web idioms, but at Keyhole your
production Python is mostly going to live in **Airflow DAGs on GKE**.
Two extra folders bridge from the web-app world we've been in to your
actual stack:

- **[airflow/](airflow/)** — DAG examples + a Node→Airflow concept map. The
  Python you'll write at work.
- **[infra/](infra/)** — Terraform module showing GCS, Pub/Sub, a service
  account, and Workload Identity binding, plus an AWS→GCP cheat sheet.

Both folders have their own README that takes a Node/AWS engineer to a
"can read existing code with confidence" baseline. Read in this order:

1. `airflow/README.md` — what Airflow is and how it differs from FastAPI
2. `airflow/dags/etl_basic.py` — classic API
3. `airflow/dags/bigquery_pipeline.py` — TaskFlow API + GCP operators
4. `infra/README.md` — AWS→GCP service map and IaC tooling overview
5. `infra/main.tf` — a real Terraform module, fully annotated

---

## 8. Next steps if you have time

1. Add an `update_item` (`PUT /items/{id}`) — reuse `ItemCreate`. Write a
   test for it before writing the handler (TDD).
2. Add a query param: `GET /items?in_stock=true`.
3. Modify `/stream/events` to push real-time data: read from a file as it
   grows, watch a queue, or stream tokens from an HTTP call to another API.
4. Add `pytest-cov` (`uv add --dev pytest-cov`) and run
   `uv run pytest --cov=app --cov-report=term-missing` to see which lines
   are exercised.
5. Swap the in-memory `ItemStore` for SQLite via `sqlmodel` (a thin wrapper
   over SQLAlchemy + Pydantic, same author as FastAPI). Add it with
   `uv add sqlmodel`. Your tests should *barely change* — that's the point
   of the `dependency_overrides` pattern.

---

## 10. End-to-end ETL example: Postgres → BigQuery

This project now carries a small but realistic e-commerce ETL slice end to
end. The **FastAPI** `/orders` router writes order rows into a **Postgres**
`orders` table. A daily **Airflow** DAG (`postgres_to_bq_orders`, runs at
02:00 UTC) extracts the previous day's rows, lands them in BigQuery
`analytics.orders_raw` (partitioned on `DATE(ingested_at)`, clustered by
`region`, reloaded idempotently by deleting the partition first), then
aggregates them into `analytics.sales_daily` with `order_count` and
`gross_revenue` per region per day. Same data shape, same flow you'd ship
to production — just smaller.

```
  FastAPI /orders  ─►  Postgres (orders)
                              │  (Airflow DAG: postgres_to_bq_orders, daily 02:00 UTC)
                              ▼
                       BigQuery analytics.orders_raw
                              │  (aggregate task in same DAG)
                              ▼
                       BigQuery analytics.sales_daily
```

### Local end-to-end

You can run the FastAPI → Postgres half on your laptop with just Docker
Compose and uv. The BigQuery half is exercised via the Airflow DAG against
real GCP (or a Composer dev environment) — there's no good local stand-in
for BQ.

```bash
docker compose up -d postgres               # start local PG
uv run poe dev                              # FastAPI talks to it
# create an order:
curl -X POST http://localhost:8000/orders -H 'Content-Type: application/json' \
  -d '{"customer_id": 42, "total_cents": 1999, "region": "us-west"}'
```

Then `curl http://localhost:8000/orders` to list them, or filter with
`?status=pending&region=us-west`. `DATABASE_URL` defaults to
`postgresql+psycopg://app:app@localhost:5432/orders` so the native
`uv run poe dev` process connects to the Compose-managed Postgres without
any extra env setup.

### Files involved

| File                                          | Purpose                                                                 |
| --------------------------------------------- | ----------------------------------------------------------------------- |
| `app/clients/db.py`                           | SQLModel sync engine + `get_session` DI provider, reads `DATABASE_URL`. |
| `app/models.py` (extended)                    | Adds the `OrderCreate` input schema and the `Order` SQLModel table.     |
| `app/routers/orders.py`                       | `/orders` CRUD router — POST, GET (with `?status=&region=`), GET by id, DELETE. |
| `airflow/dags/postgres_to_bq_orders.py`       | The daily DAG: extract from PG → load to `orders_raw` → aggregate to `sales_daily`. |
| `infra/cloudsql.tf`                           | Cloud SQL Postgres instance + DB + user, password in Secret Manager.    |
| `infra/bigquery.tf`                           | BigQuery `analytics` dataset + `orders_raw` and `sales_daily` tables.   |
| `compose.yaml`                                | Adds the local `postgres` service and wires `api` to depend on it.      |

### GCP services + IAM

- **Cloud SQL for Postgres** — `db-f1-micro`, Postgres 16, database `orders`,
  user `app`. Password generated via `random_password` and stored in
  **Secret Manager** (no plaintext in state outputs you'd want to share).
  Public IP is on for dev convenience; prod should flip to private IP +
  VPC peering.
- **BigQuery** — dataset `analytics` containing:
  - `orders_raw` (raw landing table, partitioned by `DATE(ingested_at)`,
    clustered by `region`)
  - `sales_daily` (aggregate, partitioned by `day`, clustered by `region`)
- **Secret Manager** — holds the generated Cloud SQL `app` password.
- **IAM** on the `airflow_worker` service account:
  - `roles/cloudsql.client` at the project level (so the worker can dial
    the Cloud SQL Auth Proxy).
  - `roles/bigquery.dataEditor` on the `analytics` dataset (write rows,
    not admin the dataset).
  - `roles/bigquery.jobUser` at the project level (kick off load/query
    jobs — this role lives at the project, not the dataset).

### Production deploy notes

- On GKE, the Airflow worker pod authenticates via **Workload Identity** —
  the K8s SA is bound to the `airflow_worker` GCP SA, so no JSON key files
  ride along with the pod. (Same pattern as AWS IRSA.)
- Cloud SQL access from the worker pod typically goes through the
  **Cloud SQL Auth Proxy** as a sidecar — `PostgresHook` then connects to
  `127.0.0.1:5432` and the proxy handles auth + TLS to the instance.
- For prod, switch the Cloud SQL instance to **private IP** only and reach
  it over VPC peering. The `public_ip = true` setting in
  `infra/cloudsql.tf` is a dev-only convenience.
- The DAG file itself deploys to **Cloud Composer** simply by copying
  `airflow/dags/postgres_to_bq_orders.py` into the environment's
  GCS `dags/` bucket — Composer picks it up automatically on its next
  parse cycle.

---

## 11. Troubleshooting

- **`command not found: uv`** — `brew install uv`.
- **`command not found: uvicorn`** — you ran `uvicorn ...` instead of
  `uv run uvicorn ...`. Prefix project commands with `uv run`.
- **`ModuleNotFoundError: No module named 'app'`** — you're in the wrong
  directory. Run from the project root.
- **Port 8000 in use** — `uv run uvicorn app.main:app --reload --port 8001`.
- **Dependencies feel out of date** — `uv sync` re-reconciles `.venv` with
  the lockfile.
