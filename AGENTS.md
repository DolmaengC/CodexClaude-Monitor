# Repository Guidelines

## Project Structure & Module Organization
This repository is currently an empty scaffold with only Git metadata. Keep the root clean as the project takes shape. Place application code in `src/`, tests in `tests/`, reusable assets in `assets/`, and helper automation in `scripts/`. Store toolchain config at the repository root, for example `package.json`, `pyproject.toml`, or `Makefile`.

## Build, Test, and Development Commands
No build, test, or local-run commands are configured yet. When you introduce tooling, expose a small set of standard entry points from the root so contributors do not need to guess. Typical examples:

- `npm test` or `pytest` for the automated test suite
- `npm run dev` or `python -m <module>` for local development
- `npm run lint` or `ruff check .` for static checks

Update this file when those commands become part of the repository contract.

## Coding Style & Naming Conventions
Match the formatter and linter of the selected stack and commit the config with the first implementation. Until then, prefer readable defaults: 4-space indentation for Python, 2 spaces for JSON/YAML/Markdown, `snake_case` for Python modules, `camelCase` for JavaScript or TypeScript variables, and `PascalCase` for classes and React components. Use descriptive file names and avoid committing generated artifacts unless the workflow requires them.

## Testing Guidelines
Add tests with the first feature instead of backfilling later. Mirror the source layout under `tests/` and use framework-standard names such as `test_monitor.py` or `monitor.test.ts`. Keep tests fast, deterministic, and isolated from external services unless a dedicated integration setup is documented.

## Commit & Pull Request Guidelines
There is no existing commit history in this repository, so establish the convention now: use short, imperative commit subjects such as `Add initial monitor scaffold`. Keep pull requests focused, explain behavior changes and risk, link related issues, and include screenshots or log excerpts when UI or CLI output changes.

## Security & Configuration Tips
Do not commit secrets, tokens, or machine-specific settings. Keep local values in ignored files such as `.env.local` and provide a sanitized `.env.example` whenever configuration becomes required.
