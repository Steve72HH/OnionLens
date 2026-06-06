import os
from typing import Any

import meilisearch
import psycopg2
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY")
MEILI_INDEX = os.getenv("MEILI_INDEX", "sites")
STATS_API_KEY = os.getenv("STATS_API_KEY", "")


def cors_origins() -> list[str]:
    raw_value = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000")
    if raw_value.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


app = FastAPI(title="OnionLens API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET"],
    allow_headers=["*"],
)

search_client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
search_index = search_client.index(MEILI_INDEX)


def db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "onionlens"),
        user=os.getenv("POSTGRES_USER", "onionlens"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def require_stats_access(admin_key: str | None) -> None:
    if STATS_API_KEY and admin_key != STATS_API_KEY:
        raise HTTPException(status_code=403, detail="stats endpoint requires X-OnionLens-Admin-Key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "onionlens-api"}


@app.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        result = search_index.search(
            q,
            {
                "limit": limit,
                "offset": offset,
                "attributesToHighlight": ["title", "description", "keywords"],
                "attributesToCrop": ["description"],
                "cropLength": 60,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"search backend unavailable: {exc}") from exc

    return {
        "query": q,
        "estimated_total_hits": result.get("estimatedTotalHits", 0),
        "processing_time_ms": result.get("processingTimeMs", 0),
        "hits": result.get("hits", []),
    }


@app.get("/stats")
def stats(x_onionlens_admin_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_stats_access(x_onionlens_admin_key)

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sites")
            sites = cur.fetchone()[0]
            cur.execute("SELECT status, COUNT(*) FROM crawl_frontier GROUP BY status ORDER BY status")
            frontier = {row[0]: row[1] for row in cur.fetchall()}
            cur.execute(
                """
                SELECT label, COUNT(*)
                FROM sites, UNNEST(warning_labels) AS label
                GROUP BY label
                ORDER BY COUNT(*) DESC
                LIMIT 20
                """
            )
            warning_labels = [{"label": row[0], "count": row[1]} for row in cur.fetchall()]

    return {"sites": sites, "frontier": frontier, "warning_labels": warning_labels}
