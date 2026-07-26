#! /bin/bash
set -e
cd "$(dirname "$0")/.."
python3 scripts/update-readme.py 2>&1
git add README.md .project-cache.json .star-cache.json
git commit -m "auto: update README with latest projects" || true
git push || echo "Push skipped / no remote configured"
