<div align="center">

# Proof

**Synthetic API monitoring as code.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/Kishan-Thanki/proof/actions/workflows/ci.yml/badge.svg)](https://github.com/Kishan-Thanki/proof/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Kishan-Thanki/proof?color=blue&logo=github)](https://github.com/Kishan-Thanki/proof/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
</div>

---

Proof runs declarative, multi-step HTTP scenarios against APIs on a schedule.

**YAML in. HTTP checks out. No database, queue, or external service required.**

## Install

```bash
pip install git+https://github.com/Kishan-Thanki/proof.git
```

## Quickstart

Create `scenarios/health.yaml`:

```yaml
version: "1.0"

global:
  base_url: "https://api.example.com"

scenarios:
  - name: "Health Check"
    interval_seconds: 30
    steps:
      - name: "GET /health"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
```

Run once:

```bash
proof run scenarios/health.yaml
```

Run continuously:

```bash
proof run scenarios/health.yaml --daemon
```

Proof reports each step with its status, HTTP code, latency, and errors.

## Multi-step scenarios

Steps can extract values from responses and reuse them later:

```yaml
steps:
  - name: "Create User"
    request:
      method: "POST"
      path: "/users"
      json:
        name: "Proof"
    expect:
      status: 201
    extract:
      user_id: "$.id"

  - name: "Fetch User"
    request:
      method: "GET"
      path: "/users/${user_id}"
    expect:
      status: 200
```

Dynamic built-ins such as `${$uuid}` and `${$timestamp}` are also supported.

## CLI

```bash
proof run <config.yaml>
proof run <config.yaml> --daemon
proof run <config.yaml> --interval 30
proof --version
```

Use `--webhook-url` to receive notifications when a scenario changes between healthy and failing states.

## Why Proof?

- **Monitoring as code** — scenarios live in Git.
- **Multi-step workflows** — test real API journeys, not just endpoints.
- **CI-friendly** — exit code `0` for success, `1` for failure.
- **Daemon mode** — continuously monitor APIs from a small server.
- **Transition alerts** — notifications only when health changes.
- **Async execution** — built for concurrent scenario checks.
