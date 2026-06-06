# Security Policy

OnionLens is a crawler and search prototype for onion services. Treat deployments as sensitive infrastructure.

## Reporting

Please report security issues privately to the repository maintainer. Do not include live exploit details in public issues.

## Deployment guidance

- Change all values from `.env.example` before production use.
- Keep PostgreSQL, Meilisearch, and Tor private.
- Put public traffic behind HTTPS and a reverse proxy.
- Set `STATS_API_KEY` before exposing `/stats`.
- Use a clear `USER_AGENT` with an abuse/contact mailbox.
- Review seed sources before crawling.
- Do not store or publish raw HTML, binary content, database dumps, or private crawl target lists.

## Known limitations

OnionLens v0.1 does not provide a full abuse workflow, takedown process, user authentication, or legal-review automation. Add those controls before broad public operation.
