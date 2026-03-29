# Frontend Changes

## Code Quality Tooling Added

### New Files

| File | Purpose |
|---|---|
| `frontend/package.json` | npm package manifest with `format`, `format:check`, `lint`, and `quality` scripts |
| `frontend/.prettierrc` | Prettier configuration (4-space indent, single quotes, semicolons, 100-char print width) |
| `frontend/.eslintrc.json` | ESLint configuration (browser env, ES2021, `eslint:recommended`, warns on `no-console` and `no-unused-vars`) |
| `scripts/check-frontend-quality.sh` | Shell script that runs Prettier format check then ESLint; exits non-zero on any failure |
| `scripts/format-frontend.sh` | Shell script that auto-formats all frontend HTML/CSS/JS files with Prettier |

### Formatting Fixes (`frontend/script.js`)

- Removed duplicate blank line between `sendButton` event listener and the `// Suggested questions` comment block.
- Removed extra blank line after `setupEventListeners()` closing brace before `// Chat Functions`.

---

## How to Use

**Install dev dependencies** (one-time, from `frontend/`):
```bash
cd frontend && npm install
```

**Auto-format all frontend files:**
```bash
bash scripts/format-frontend.sh
# or from inside frontend/: npm run format
```

**Check formatting without changing files:**
```bash
bash scripts/check-frontend-quality.sh
# or from inside frontend/: npm run quality
```

---

## Tool Choices

- **Prettier** is the standard formatter for HTML/CSS/JS, equivalent to `black` for Python. It enforces consistent style automatically with zero configuration debates.
- **ESLint** catches common JavaScript mistakes (undefined variables, dead code, etc.) and is configured to warn rather than error on `console.*` calls, since the project uses `console.log` for debugging.
