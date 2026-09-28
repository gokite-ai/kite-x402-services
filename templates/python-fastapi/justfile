# Kite x402 Python/FastAPI Template — development commands
# Install: brew install just

set positional-arguments := true

venv := ".venv"
python := venv / "bin" / "python3"
uvicorn := venv / "bin" / "uvicorn"
pip := venv / "bin" / "pip"

_default:
    @just --list

# Create virtual environment
venv:
    python3 -m venv {{venv}}

# Install dependencies
install: venv
    {{pip}} install -r requirements.txt

# Lint with Ruff
lint:
    {{venv}}/bin/ruff check .

# Format with Ruff
format:
    {{venv}}/bin/ruff format .

# Check spelling
typos:
    typos

# Run all tests
test:
    {{venv}}/bin/pytest -v test/

# Validate service manifest against schema
validate:
    {{python}} ../../scripts/validate.py

# Start dev server (reload on changes)
run port="8080":
    {{uvicorn}} server:app --host 0.0.0.0 --port {{port}} --reload

# Clean Python cache
clean:
    rm -rf __pycache__/ .pytest_cache/ *.egg-info/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Full clean: venv + cache
distclean: clean
    rm -rf {{venv}}
