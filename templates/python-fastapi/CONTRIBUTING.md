# Contributing

Thank you for considering contributing to the Python/FastAPI x402 wrapper template!

## How to contribute

1. **Fork** this repository
2. **Create a branch**: `feature/your-feature` or `fix/your-fix`
3. **Follow conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, etc.
4. **Run pre-commit**: `pre-commit run --all-files` (install with `pip install pre-commit && pre-commit install`)
5. **Run tests**: `just test`
6. **Create a PR** targeting `main`

## Code style

- Python: [Ruff](https://docs.astral.sh/ruff/) (see `.pre-commit-config.yaml`)
- Spell check: [typos](https://github.com/crate-ci/typos) (install `cargo install typos-cli`)
- Pre-commit hooks check all of the above automatically

## Template conventions

- `kite.py` — Kite chain parameters only (network config, money parser)
- `server.py` — FastAPI application logic (routes, middleware, proxy)
- `test/` — pytest tests mirroring server.py structure
- Keep dependencies minimal in `requirements.txt`

## License

This template is part of `gokite-ai/kite-x402-services`. By contributing you agree to license your contributions under the same terms.
