# Frontend Changes

## Dark / Light Theme Toggle

### Files Modified
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

### New File
- `frontend-changes.md` (this file)

---

### index.html
- Added a fixed-position `<button id="themeToggle">` in the top-right corner of the page.
- Button contains two inline SVG icons: a **sun** (shown in light mode) and a **moon** (shown in dark mode).
- Includes `aria-label` and `title` attributes for accessibility and keyboard navigation.

### style.css
- Added a `[data-theme="light"]` rule block with a full set of CSS custom properties for the light theme:
  - Light backgrounds (`#f8fafc`, `#ffffff`)
  - Dark text (`#0f172a`, `#64748b`)
  - Adjusted surface and border colors (`#e2e8f0`)
  - Lighter shadow (`rgba(0,0,0,0.1)`)
  - Light welcome message background (`#dbeafe`)
  - Toggle-specific variables (`--toggle-bg`, `--toggle-color`)
- Added `.theme-toggle` button styles: fixed position top-right, circular, border, shadow, hover scale effect, and focus ring.
- Sun/moon icon visibility controlled via CSS: moon shown by default (dark mode), sun shown when `[data-theme="light"]` is active.
- Added smooth `transition` on `background-color`, `color`, and `border-color` for key layout elements so theme switches animate at 0.3s ease.

### script.js
- On `DOMContentLoaded`, reads `localStorage.getItem('theme')` and applies it via `document.documentElement.setAttribute('data-theme', ...)` before first render.
- Theme toggle button click handler: reads current `data-theme` on `<html>`, toggles between `"light"` and `"dark"`, and persists the choice to `localStorage`.

---

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
