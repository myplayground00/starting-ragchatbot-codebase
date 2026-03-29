#!/bin/bash
# Auto-format all frontend files with Prettier
# Run from the project root: bash scripts/format-frontend.sh

cd "$(dirname "$0")/../frontend"

echo "Formatting frontend files with Prettier..."
npx prettier --write "**/*.{html,css,js}"
echo "Done."
