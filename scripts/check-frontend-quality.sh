#!/bin/bash
# Frontend code quality checks
# Run from the project root: bash scripts/check-frontend-quality.sh

set -e

cd "$(dirname "$0")/../frontend"

echo "=== Frontend Quality Checks ==="

echo ""
echo "[1/2] Prettier format check..."
npx prettier --check "**/*.{html,css,js}"
echo "    Format check passed."

echo ""
echo "[2/2] ESLint lint check..."
npx eslint "**/*.js"
echo "    Lint check passed."

echo ""
echo "All quality checks passed!"
