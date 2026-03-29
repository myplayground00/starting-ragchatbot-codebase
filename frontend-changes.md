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
