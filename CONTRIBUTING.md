# Git workflow

```
git clone <repo-url> && cd firewatch
git checkout dev && git pull
git checkout -b feature/<your-branch>     # feature/data-platform or feature/analytics
```

1. Work only in your own folders (see README).
2. One feature, one commit. Test by hand before committing.
3. Commit format: `<module>: <what> (<id>)`, e.g. `airflow: add raw validation task (B8)`.
4. Push after every commit: `git push -u origin feature/<your-branch>`.
5. Pull `dev` regularly: `git fetch && git merge origin/dev`.
6. Never commit `.env`, API keys, MAP_KEY, service-account JSON, `keys/`, `secrets.toml`, `target/`, `logs/`.
   If a secret is pushed, tell your teammate and rotate it.
7. Never push directly to `dev` or `main`; open a pull request the other person reviews.
8. Never force push on shared branches.
9. Tag the demo-ready commit on `main` as `demo-v1`.
