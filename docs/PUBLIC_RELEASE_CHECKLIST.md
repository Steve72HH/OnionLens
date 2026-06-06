# Public Release Checklist

Use this before publishing or merging OnionLens into a public GitHub repository.

## Repository contents

- [ ] `.env` and `.env~` are absent.
- [ ] Database dumps, backups, logs, and crawl data are absent.
- [ ] Seed files do not contain private, unreviewed, or sensitive target lists.
- [ ] No production IP addresses, hostnames, SSH paths, or credentials are committed.
- [ ] `.env.example` contains only placeholders and safe local defaults.

## Technical checks

- [ ] `docker compose --env-file .env.example config` passes.
- [ ] `python -m compileall backend crawler indexer tools` passes.
- [ ] Frontend dependencies install with `npm install`.
- [ ] Fresh database schema contains all columns used by the crawler and API.

## Operational review

- [ ] Public services are behind HTTPS.
- [ ] PostgreSQL, Meilisearch, and Tor are not publicly exposed.
- [ ] `/stats` is protected with `STATS_API_KEY` or not publicly routed.
- [ ] Abuse contact and takedown process are documented.
- [ ] Legal review is complete for the intended operating jurisdiction.
