# Contributing

Thanks for taking a look at OnionLens.

## Before opening a pull request

- Keep crawler changes conservative and bounded by default.
- Do not add active onion seed lists unless they are official, public-interest, reviewed, and necessary for a test fixture.
- Do not commit `.env`, database dumps, crawl data, logs, private keys, or production hostnames.
- Run:

```bash
cp .env.example .env
docker compose --env-file .env.example config
python -m compileall backend crawler indexer tools
```

For frontend dependency checks:

```bash
cd frontend
npm ci
```

## Pull request checklist

- [ ] No secrets, dumps, logs, or private target lists are included.
- [ ] Docker Compose renders with `.env.example`.
- [ ] Python files compile.
- [ ] Documentation reflects any behavior or deployment changes.
- [ ] Safety guardrails remain enabled by default.
