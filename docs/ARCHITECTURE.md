# OnionLens V0.1 architecture

## Goal

OnionLens is a Google-like search interface for onion pages. V0.1 focuses on controlled crawling, text-only storage, keyword indexing, and warning labels.

## Data flow

1. Seed URLs are inserted into `crawl_frontier`.
2. The crawler fetches HTML/text pages through Tor.
3. The sanitizer removes active content and extracts title, description, visible text, links, keywords, and warning labels.
4. PostgreSQL stores crawl state and sanitized page records.
5. The indexer syncs changed records into Meilisearch.
6. The API serves search and crawler stats.
7. The frontend renders search results with warning labels.

## Guardrails

- Only `text/html`, `text/plain`, and XHTML responses are accepted.
- Images, archives, documents, media, and executables are skipped by extension and content type.
- Response size, text length, timeout, crawl delay, and depth are configurable.
- Sensitive topics are labelled, not silently hidden in V0.1.
- Raw HTML and binary content are not stored.

## Scaling path

- Multiple crawler containers can be added because the frontier uses `FOR UPDATE SKIP LOCKED`.
- Increase Meilisearch resources for the first 100,000 pages.
- Move to OpenSearch when ranking, aggregations, and very large indexes become the limiting factor.
- Add admin authentication before any public deployment.
- Add legal review, takedown workflow, abuse contact, and stricter policy handling before broad crawling.
