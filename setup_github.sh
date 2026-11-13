#!/usr/bin/env bash
# Run once by the repo owner (Bhagyashri) from inside this folder.
set -e
git init -b main
git add .
git commit -m "base: project skeleton, dbt config, contracts"
# Option A: GitHub CLI (after `gh auth login`)
gh repo create firewatch --private --source=. --remote=origin --push
# Option B: create an empty repo on github.com, then:
#   git remote add origin https://github.com/<user>/firewatch.git && git push -u origin main
git checkout -b dev && git push -u origin dev
echo "Done. Add Neha as collaborator: Settings -> Collaborators."
