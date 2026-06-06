import os
import time

import meilisearch
import psycopg2


MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY")
MEILI_INDEX = os.getenv("MEILI_INDEX", "sites")
BATCH_SIZE = int(os.getenv("INDEX_BATCH_SIZE", "500"))
INDEX_INTERVAL_SECONDS = int(os.getenv("INDEX_INTERVAL_SECONDS", "30"))
INDEX_WAIT_FOR_TASK = os.getenv("INDEX_WAIT_FOR_TASK", "true").lower() in {"1", "true", "yes", "on"}
INDEX_TASK_TIMEOUT_SECONDS = int(os.getenv("INDEX_TASK_TIMEOUT_SECONDS", "300"))
INDEX_TASK_POLL_INTERVAL_SECONDS = float(os.getenv("INDEX_TASK_POLL_INTERVAL_SECONDS", "2"))


def db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "onionlens"),
        user=os.getenv("POSTGRES_USER", "onionlens"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def configure_index(index):
    index.update_searchable_attributes(["title", "keywords", "description", "url", "onion_host", "warning_labels"])
    index.update_displayed_attributes(
        ["id", "url", "onion_host", "title", "description", "keywords", "warning_labels", "last_seen"]
    )
    index.update_filterable_attributes(["onion_host", "warning_labels"])
    index.update_ranking_rules(["words", "typo", "proximity", "attribute", "sort", "exactness"])
    index.update_synonyms(
        {
            "ai": ["artificial intelligence", "kuenstliche intelligenz", "künstliche intelligenz", "machine learning", "ml"],
            "artificial intelligence": ["ai", "kuenstliche intelligenz", "künstliche intelligenz", "machine learning"],
            "programmierung": ["programming", "development", "developer", "software development", "softwareentwicklung", "coding", "entwicklung"],
            "programming": ["programmierung", "development", "developer", "software development", "softwareentwicklung", "coding"],
            "development": ["programmierung", "programming", "developer", "softwareentwicklung", "coding"],
            "darknet": ["dark web", "darkweb", "tor", "onion", "hidden service", "onion service"],
            "darkweb": ["dark web", "darknet", "tor", "onion", "hidden service"],
            "virus": ["malware", "ransomware", "trojan", "trojaner", "worm", "botnet", "security"],
            "malware": ["virus", "ransomware", "trojan", "trojaner", "worm", "botnet", "security"],
            "osint": ["open source intelligence", "reconnaissance", "research", "investigation"],
            "sicherheit": ["security", "cybersecurity", "infosec", "privacy"],
        }
    )


def task_uid(task):
    if isinstance(task, dict):
        return task.get("taskUid") or task.get("uid")
    return getattr(task, "task_uid", None) or getattr(task, "taskUid", None) or getattr(task, "uid", None)


def wait_for_task(client, uid):
    if not INDEX_WAIT_FOR_TASK or uid is None:
        return

    timeout_ms = INDEX_TASK_TIMEOUT_SECONDS * 1000
    interval_ms = int(INDEX_TASK_POLL_INTERVAL_SECONDS * 1000)
    if hasattr(client, "wait_for_task"):
        result = client.wait_for_task(uid, timeout_in_ms=timeout_ms, interval_in_ms=interval_ms)
        status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
        if status == "failed":
            raise RuntimeError(f"meilisearch task {uid} failed: {result}")
        return

    deadline = time.monotonic() + INDEX_TASK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        result = client.get_task(uid)
        status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
        if status == "succeeded":
            return
        if status == "failed":
            raise RuntimeError(f"meilisearch task {uid} failed: {result}")
        time.sleep(INDEX_TASK_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"meilisearch task {uid} did not finish within {INDEX_TASK_TIMEOUT_SECONDS}s")


def index_batch(conn, index, client):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, url, onion_host, title, description, keywords, warning_labels, last_seen
            FROM sites
            WHERE indexed_at IS NULL OR indexed_at < last_seen
            ORDER BY last_seen ASC
            LIMIT %s
            """,
            (BATCH_SIZE,),
        )
        rows = cur.fetchall()

    if not rows:
        return 0

    documents = [
        {
            "id": row[0],
            "url": row[1],
            "onion_host": row[2],
            "title": row[3],
            "description": row[4],
            "keywords": row[5],
            "warning_labels": row[6],
            "last_seen": row[7].isoformat() if row[7] else None,
        }
        for row in rows
    ]
    task = index.add_documents(documents, primary_key="id")
    wait_for_task(client, task_uid(task))

    ids = [row[0] for row in rows]
    with conn.cursor() as cur:
        cur.execute("UPDATE sites SET indexed_at = NOW() WHERE id = ANY(%s)", (ids,))
    conn.commit()
    return len(rows)


def main():
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    index = client.index(MEILI_INDEX)
    configure_index(index)

    while True:
        try:
            with db_connection() as conn:
                count = index_batch(conn, index, client)
                if count:
                    print(f"indexed {count} documents", flush=True)
        except Exception as exc:
            print(f"indexer error: {exc}", flush=True)

        time.sleep(INDEX_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
