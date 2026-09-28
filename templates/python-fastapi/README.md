# Python + FastAPI template

A ready-to-deploy reverse proxy that charges x402 payments on the Kite chain
for every request under `/v1/*` and forwards paid requests to `UPSTREAM_URL`.

## Quick start

```bash
# Install just (optional — brew install just)

# Create venv and install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Configure
cp .env.example .env        # fill PAY_TO, UPSTREAM_URL, PRICE_USD

# Run
.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8080

# Test unpaid request → 402 + PAYMENT-REQUIRED header
curl -i "http://localhost:8080/v1/forecast?latitude=52.52&longitude=13.41"
```

With `just`:

```bash
just install
just run
```

## Commands

| `just` recipe | Effect |
|---|---|
| `install` | Create venv + install dependencies |
| `lint` | Ruff check |
| `format` | Ruff format |
| `test` | Run pytest test/ |
| `run [port]` | Start dev server (default port 8080) |
| `clean` / `distclean` | Remove caches / venv |

## Files

- `server.py` — FastAPI application: configuration, routes, reverse proxy. Edit this.
- `kite.py` — Kite chain constants and the `$0.001`-style price parser. Leave as is.

## Project structure

```
python-fastapi/
├── .editorconfig           # Editor defaults
├── .github/workflows/      # CI: lint.yml, test.yml
├── .gitignore /
　.pre-commit-config.yaml
├── CHANGELOG.md            # git-cliff generated
├── CONTRIBUTING.md
├── README.md
├── cliff.toml              # Changelog config
├── justfile                # Dev commands (just)
├── requirements.txt
├── kite.py                 # Kite network config
├── server.py               # FastAPI app
└── test/                   # Tests
```

The payment middleware verifies the signature before your upstream is called and
settles only when the upstream responded with a status below 400, so a failed
upstream call never charges the buyer.

See the repository [README](../../README.md) for the full flow and how to test
with a Kite Passport agent.
