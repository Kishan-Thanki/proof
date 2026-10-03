<div align="center">

# Proof

**Synthetic API monitoring that runs in the background, stays out of your data, and tells you the truth.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/your-org/proof/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/proof/actions/workflows/ci.yml)
[![Release](https://github.com/your-org/proof/actions/workflows/release.yml/badge.svg)](https://github.com/your-org/proof/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

Proof runs declarative, multi-step HTTP scenarios against your production APIs on a schedule. It checks status codes, latency budgets, response headers, and JSON schema contracts — and stops you before the silence does.

No Redis. No Celery. No database. Just a YAML file and a process.

---

## Install

```bash
pip install git+https://github.com/your-org/proof.git
```

---

## How it works

Write a scenario in YAML. Point it at your API. Run it.

```yaml
# scenarios/health.yaml
version: "1.0"

global:
  base_url: "https://api.yourapp.com"
  timeout_seconds: 5
  headers:
    X-Synthetic-Request: "true"

scenarios:
  - name: "Auth + Profile Flow"
    interval_seconds: 60
    steps:
      - name: "Login"
        request:
          method: "POST"
          path: "/auth/login"
          json:
            email: "synth-bot@yourapp.com"
            password: "test-password"
        expect:
          status: 200
          max_latency_ms: 500
        extract:
          token: "$.data.token"
          user_id: "$.data.user.id"

      - name: "Fetch Profile"
        request:
          method: "GET"
          path: "/users/${user_id}"
          headers:
            Authorization: "Bearer ${token}"
        expect:
          status: 200
          schema:
            type: "object"
            required: [id, email, name]
```

**Run once:**

```bash
proof run scenarios/health.yaml
```

**Run as a daemon** (loops on the configured interval):

```bash
proof run scenarios/health.yaml --daemon
```

---

## Output

Proof prints a Rich table for every scenario run:

```
                     Scenario: Auth + Profile Flow
 ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
 ┃ Step Name               ┃ Status ┃ HTTP Code ┃    Latency ┃ Error Details ┃
 ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
 │ Login                   │  PASS  │       200 │  123.45 ms │ -             │
 │ Fetch Profile           │  PASS  │       200 │   87.32 ms │ -             │
 └─────────────────────────┴────────┴───────────┴────────────┴───────────────┘
╭─────── Summary ────────╮
│ Status: PASSED   Total Latency: 210.77 ms │
╰───────────────────────╯
```

Failed steps show the exact assertion that broke — wrong status code, latency exceeded, schema mismatch, or missing header.

Exit code is `0` on pass, `1` on any failure — works cleanly in CI.

---

## Dynamic variables

Use built-ins anywhere in your request — path, headers, or JSON body:

| Variable | Value |
|---|---|
| `${$uuid}` | Fresh UUID v4 on every run |
| `${$timestamp}` | Unix timestamp (seconds) |
| `${$timestamp_ms}` | Unix timestamp (milliseconds) |
| `${$iso_timestamp}` | `2024-01-01T12:00:00Z` |
| `${$random_int}` | Random integer 1000–9999 |

```yaml
json:
  trace_id: "${$uuid}"
  submitted_at: "${$iso_timestamp}"
  session: "load-test-${$random_int}"
```

---

## CLI

```
proof run <config.yaml> [--once | --daemon] [--interval <seconds>]
proof --version
```

| Flag | Default | Description |
|---|---|---|
| `--once` | ✓ | Run all scenarios once and exit |
| `--daemon` | | Loop continuously on the configured interval |
| `--interval`, `-i` | From config | Override interval in daemon mode |

---

## License

MIT
