# Scan performance and concurrency

## Is this a Snowflake Native App?

**Snowfort Audit** today is a **client-side Python CLI** (and optional Streamlit app). It runs on your machine or in a dev container and connects to Snowflake via the Snowflake Connector for Python. It is **not** a Snowflake Native App (an app running inside Snowflake’s execution environment).

- **Native Apps (inside Snowflake):** If you later run logic inside Snowflake (e.g. stored procedures, Native App framework), Snowflake supports:
  - **Async:** `session.call_nowait()` / `collect_nowait()` for fire-and-forget jobs.
  - **Parallelism:** Prefer **joblib** (e.g. `joblib.Parallel`) over Python’s `multiprocessing`/threading for CPU-bound work; Snowpark-optimized warehouses can use the `loky` backend.
- **This client (outside Snowflake):** We use **multiple Snowflake connections + a thread pool** so many rules run in parallel from the client. Each connection runs queries independently; the connector is thread-safe when each thread uses its own connection.

## Reducing scan time (client-side)

### 1. Use parallel workers (recommended)

Account-level rules run one-by-one by default. Use multiple workers so several rules run at once (each worker uses its own Snowflake connection):

```bash
snowfort audit scan --workers 4
# or 6–8 on a powerful machine / low-latency network
```

- **Sweet spot:** Often **4–8** workers. More workers mean more connections and more concurrent queries; beyond that, gains depend on warehouse and network.
- **Cost:** Each worker holds one session; short-lived queries so credit impact is usually small.

### 2. Keep view-phase as-is

The “check N account views” phase still runs **sequentially** (one cursor) to avoid opening a connection per view. If you have a very large number of views, most of the time is still in the account-level rules when using `--workers`.

### 3. Log level

Use `--log-level INFO` (default) or `WARNING` to cut down console I/O; use `DEBUG` only when diagnosing.

```bash
snowfort audit scan --workers 4 --log-level INFO
```

### 4. Future options (not implemented)

- **Skip or sample view-level checks** to shorten runs when you have many views.
- **Rule subsets** (e.g. by pillar or tag) so you run only the checks you care about.

## Summary

| Context              | Concurrency approach                          |
|----------------------|------------------------------------------------|
| This CLI (client)    | `--workers N` → N connections, thread pool     |
| Native App / Snowflake | joblib, `call_nowait` / async APIs (no client threads) |

Use **`snowfort audit scan --workers 4`** (or 6–8) to reduce wall-clock time with no code changes.
