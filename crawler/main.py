import hashlib
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse

import psycopg2
import requests
from bs4 import BeautifulSoup
from charset_normalizer import from_bytes
from psycopg2.extras import execute_values


TOR_PROXY = os.getenv("TOR_PROXY", "socks5h://tor:9050")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
MAX_RESPONSE_BYTES = int(os.getenv("MAX_RESPONSE_BYTES", str(1024 * 1024)))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "20000"))
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "2"))
MAX_SITES = int(os.getenv("MAX_SITES", "0"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "2"))
FRONTIER_CLAIM_BATCH_SIZE = int(os.getenv("FRONTIER_CLAIM_BATCH_SIZE", "5"))
TARGET_CHECK_INTERVAL_SECONDS = int(os.getenv("TARGET_CHECK_INTERVAL_SECONDS", "300"))
CRAWL_DELAY_SECONDS = float(os.getenv("CRAWL_DELAY_SECONDS", "2"))
SEED_FILE = os.getenv("SEED_FILE", "/app/seeds.txt")
SEED_SOURCE_DIR = os.getenv("SEED_SOURCE_DIR", "/app/seed_sources")
USER_AGENT = os.getenv("USER_AGENT", "OnionLensBot/0.1")

MAX_PATH_SEGMENTS = int(os.getenv("MAX_PATH_SEGMENTS", "10"))
MAX_LANGUAGE_SEGMENTS = int(os.getenv("MAX_LANGUAGE_SEGMENTS", "2"))
MAX_QUERY_PARAMS = int(os.getenv("MAX_QUERY_PARAMS", "6"))
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "160"))
MAX_QUEUED_PER_HOST = int(os.getenv("MAX_QUEUED_PER_HOST", "50000"))

ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")

BLOCKED_EXTENSIONS = (
    ".7z", ".bin", ".bz2", ".doc", ".docx", ".exe",
    ".gif", ".gz", ".iso", ".mkv", ".mp3",
    ".rar", ".tar", ".tgz", ".webm", ".webp", ".xls", ".xlsx", ".zip",
    ".asc", ".csv", ".dmg", ".json", ".key", ".msi", ".rpm", ".sha256",
    ".sha256sum", ".sig", ".xpi",
)

BLOCKED_PATH_PATTERNS = re.compile(
    r"(\.tar\.(gz|xz|bz2)(\.asc|\.sig|\.sha256sum?)?$|"
    r"\.(asc|csv|dmg|json|key|msi|rpm|sha256|sha256sum|sig|xpi)(\?|$))",
    re.I,
)

DROPPED_QUERY_PARAMS = {
    "sid", "session", "phpsessid", "jsessionid",
    "next", "ptrt", "return", "redirect", "redirect_uri", "url",
    "lang", "language", "sort", "archived", "page", "c", "o",
    "ref", "source", "fbclid", "gclid",
}

LANGUAGE_SEGMENTS = {
    "ar", "de", "en", "es", "fa", "fr", "ga", "hu", "id", "it",
    "ja", "ko", "nl", "pl", "pt", "ru", "tr", "uk", "zh", "zh-cn", "zh-tw",
}

BLOCKED_PATH_PREFIXES = (
    "/message/compose",
    "/session",
    "/account",
    "/isite2-xforms",
    "/nightly-builds",
    "/centos",
    "/fedora",
    "/repodata",
    "/pool/main",
)

STOP_WORDS = {
    "about", "after", "also", "and", "are", "auf", "aus", "bei", "das",
    "der", "die", "ein", "eine", "for", "from", "has", "have", "mit",
    "not", "oder", "that", "the", "und", "von", "was", "were", "will", "with",
}


class BlockedUrl(RuntimeError):
    pass


class PermanentFetchError(RuntimeError):
    pass


WARNING_PATTERNS = {
    "marketplace": re.compile(r"\b(vendor|escrow|marketplace|shipping|stealth|shop)\b", re.I),
    "credentials": re.compile(r"\b(combo\s*list|credential|password dump|logs? for sale)\b", re.I),
    "malware": re.compile(r"\b(botnet|ransomware|stealer|loader|exploit kit|malware)\b", re.I),
    "leaks": re.compile(r"\b(leak|database dump|breach|dox|doxx)\b", re.I),
    "adult": re.compile(r"\b(adult|porn|xxx)\b", re.I),
    "weapons": re.compile(r"\b(weapon|firearm|gun|ammo|munition)\b", re.I),
    "drugs": re.compile(r"\b(cocaine|heroin|meth|fentanyl|mdma|lsd|cannabis)\b", re.I),
}


def db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "onionlens"),
        user=os.getenv("POSTGRES_USER", "onionlens"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def onion_host(url: str) -> str:
    return urlparse(url).hostname or ""


def normalize_url(raw_url: str, base_url: str | None = None) -> str | None:
    candidate = urljoin(base_url, raw_url.strip()) if base_url else raw_url.strip()
    candidate, _fragment = urldefrag(candidate)
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.hostname or not parsed.hostname.lower().endswith(".onion"):
        return None

    host = parsed.hostname.lower()
    netloc = host if not parsed.port else f"{host}:{parsed.port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")

    path_with_query = path
    if parsed.query:
        path_with_query = f"{path_with_query}?{parsed.query}"
    if path.lower().endswith(BLOCKED_EXTENSIONS) or BLOCKED_PATH_PATTERNS.search(path_with_query):
        return None

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in DROPPED_QUERY_PARAMS:
            continue
        query_pairs.append((key, value))

    query = urlencode(sorted(query_pairs), doseq=True)
    normalized = urlunparse((parsed.scheme, netloc, path, "", query, ""))
    allowed, _reason = should_enqueue_url(normalized)
    return normalized if allowed else None


def should_enqueue_url(url: str) -> tuple[bool, str | None]:
    parsed = urlparse(url)
    path = parsed.path or "/"
    path_lower = path.lower()
    segments = [segment for segment in path_lower.strip("/").split("/") if segment]

    if any(path_lower.startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES):
        return False, "blocked path prefix"

    if "/repodata/" in path_lower:
        return False, "blocked package repository metadata"

    if re.search(r"/(centos|fedora|debian|ubuntu|pool|dists|rpm)/", path_lower):
        return False, "blocked package repository mirror"

    if parsed.query and re.search(r"(^|[&;])c=|(^|[&;])o=", parsed.query.lower()):
        return False, "blocked directory sort query"

    if "/explore/projects/topics/" in path_lower and parsed.query:
        return False, "blocked gitlab topic filter"

    if "/-/issues" in path_lower and parsed.query:
        return False, "blocked gitlab issue filter"

    if "/-/merge_requests" in path_lower and parsed.query:
        return False, "blocked gitlab merge request filter"

    if len(segments) > MAX_PATH_SEGMENTS:
        return False, "too many path segments"

    repeated = [segment for segment, count in Counter(segments).items() if count > 1]
    if repeated:
        return False, f"repeated path segment: {repeated[0]}"

    language_count = sum(1 for segment in segments if segment in LANGUAGE_SEGMENTS)
    if language_count > MAX_LANGUAGE_SEGMENTS:
        return False, "too many language path segments"

    if len(parsed.query) > MAX_QUERY_LENGTH:
        return False, "query too long"

    if len(parse_qsl(parsed.query, keep_blank_values=True)) > MAX_QUERY_PARAMS:
        return False, "too many query params"

    return True, None


def load_seeds(conn):
    seed_files = []
    if os.path.exists(SEED_FILE):
        seed_files.append(SEED_FILE)
    if os.path.isdir(SEED_SOURCE_DIR):
        for filename in sorted(os.listdir(SEED_SOURCE_DIR)):
            if filename.endswith(".txt"):
                seed_files.append(os.path.join(SEED_SOURCE_DIR, filename))

    urls = []
    for seed_file in seed_files:
        with open(seed_file, "r", encoding="utf-8") as handle:
            urls.extend(line.strip() for line in handle if line.strip() and not line.startswith("#"))

    rows = []
    for raw_url in urls:
        normalized = normalize_url(raw_url)
        if normalized:
            rows.append((normalized, normalized, onion_host(normalized)))

    if rows:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO crawl_frontier (url, normalized_url, onion_host, depth, status)
                VALUES %s
                ON CONFLICT (url) DO NOTHING
                """,
                rows,
                template="(%s, %s, %s, 0, 'queued')",
                page_size=1000,
            )
    conn.commit()
    if urls:
        print(f"loaded {len(urls)} seed candidates from {len(seed_files)} files", flush=True)


def site_count(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sites")
        return cur.fetchone()[0]


def next_frontier_batch(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, url, depth
            FROM crawl_frontier
            WHERE status IN ('queued', 'retry') AND next_attempt_at <= NOW()
            ORDER BY depth ASC, id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (FRONTIER_CLAIM_BATCH_SIZE,),
        )
        rows = cur.fetchall()
        if not rows:
            conn.commit()
            return []

        ids = [row[0] for row in rows]

        cur.execute(
            "UPDATE crawl_frontier SET status = 'fetching', updated_at = NOW() WHERE id = ANY(%s)",
            (ids,),
        )
        conn.commit()
        return [{"id": row[0], "url": row[1], "depth": row[2]} for row in rows]


def mark_frontier(conn, frontier_id, status, error=None, commit=True):
    delay = datetime.now(timezone.utc) + timedelta(minutes=15)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_frontier
            SET status = %s,
                attempts = attempts + 1,
                last_error = %s,
                next_attempt_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (status, error, delay, frontier_id),
        )
    if commit:
        conn.commit()


def mark_failure(conn, frontier_id, exc):
    message = str(exc)[:500]
    if isinstance(exc, BlockedUrl):
        mark_frontier(conn, frontier_id, "blocked", message)
        return "blocked"
    if isinstance(exc, PermanentFetchError):
        mark_frontier(conn, frontier_id, "failed", message)
        return "failed"

    with conn.cursor() as cur:
        cur.execute("SELECT attempts FROM crawl_frontier WHERE id = %s", (frontier_id,))
        row = cur.fetchone()
    attempts = row[0] if row else 0
    if attempts + 1 >= MAX_ATTEMPTS:
        mark_frontier(conn, frontier_id, "failed", message)
        return "failed"

    mark_frontier(conn, frontier_id, "retry", message)
    return "retry"


def fetch(session, url):
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True, allow_redirects=True)
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if response.status_code >= 400:
        if response.status_code in {400, 401, 403, 404, 405, 410, 451}:
            raise PermanentFetchError(f"http status {response.status_code}")
        raise RuntimeError(f"http status {response.status_code}")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise BlockedUrl(f"blocked content type {content_type}")

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=16384):
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise BlockedUrl("response exceeds max size")
        chunks.append(chunk)

    body = b"".join(chunks)
    return decode_response(body, response), response.status_code


def decode_response(body, response):
    header_encoding = response.encoding
    if header_encoding and header_encoding.lower() not in {"iso-8859-1", "latin-1"}:
        return body.decode(header_encoding, errors="replace")

    detected = from_bytes(body).best()
    if detected and detected.encoding:
        return str(detected)

    return body.decode("utf-8", errors="replace")


def sanitize(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "object", "embed", "svg"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = clean_space(soup.title.string)[:240]

    description = ""
    meta_description = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta_description and meta_description.get("content"):
        description = clean_space(meta_description["content"])[:500]

    text = clean_space(soup.get_text(" "))
    text = text[:MAX_TEXT_CHARS]
    if not description:
        description = text[:500]

    return soup, title or "Untitled onion page", description, text


def clean_space(value):
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_keywords(text):
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text.lower())
    terms = [word for word in words if word not in STOP_WORDS and not word.isdigit()]
    return [term for term, _count in Counter(terms).most_common(30)]


def warning_labels(text):
    labels = []
    for label, pattern in WARNING_PATTERNS.items():
        if pattern.search(text):
            labels.append(label)
    return labels


def extract_links(soup, base_url):
    links = set()
    for anchor in soup.find_all("a", href=True):
        normalized = normalize_url(anchor["href"], base_url)
        if normalized:
            links.add(normalized)
    return sorted(links)


def save_site(conn, url, status_code, title, description, text, keywords, labels):
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    host = onion_host(url)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sites (
                url, normalized_url, onion_host, title, description, content_text,
                keywords, language, warning_labels, content_hash, http_status, last_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'unknown', %s, %s, %s, NOW())
            ON CONFLICT (url) DO UPDATE SET
                normalized_url = EXCLUDED.normalized_url,
                onion_host = EXCLUDED.onion_host,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                content_text = EXCLUDED.content_text,
                keywords = EXCLUDED.keywords,
                warning_labels = EXCLUDED.warning_labels,
                content_hash = EXCLUDED.content_hash,
                http_status = EXCLUDED.http_status,
                last_seen = NOW()
            """,
            (url, url, host, title, description, text, keywords, labels, digest, status_code),
        )


def filter_rows_by_host_queue_cap(conn, rows):
    if MAX_QUEUED_PER_HOST <= 0:
        return rows

    grouped = defaultdict(list)
    for row in rows:
        host = row[2]
        if host:
            grouped[host].append(row)

    filtered = []
    with conn.cursor() as cur:
        for host, host_rows in grouped.items():
            cur.execute(
                """
                SELECT COUNT(*)
                FROM crawl_frontier
                WHERE status = 'queued'
                  AND onion_host = %s
                """,
                (host,),
            )
            queued_count = cur.fetchone()[0]
            remaining = MAX_QUEUED_PER_HOST - queued_count
            if remaining > 0:
                filtered.extend(host_rows[:remaining])

    return filtered


def enqueue_links(conn, links, source_url, next_depth):
    if next_depth > MAX_DEPTH:
        return

    rows = []
    for link in links:
        allowed, _reason = should_enqueue_url(link)
        if allowed:
            rows.append((link, link, onion_host(link), source_url, next_depth))

    if not rows:
        return

    rows = filter_rows_by_host_queue_cap(conn, rows)
    if not rows:
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO crawl_frontier (url, normalized_url, onion_host, discovered_from, depth, status)
            VALUES %s
            ON CONFLICT (url) DO NOTHING
            """,
            rows,
            template="(%s, %s, %s, %s, %s, 'queued')",
            page_size=500,
        )


def main():
    session = requests.Session()
    session.proxies = {"http": TOR_PROXY, "https": TOR_PROXY}
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"})
    next_target_check_at = 0.0
    target_reached = False

    with db_connection() as conn:
        load_seeds(conn)

    while True:
        if MAX_SITES and time.monotonic() >= next_target_check_at:
            with db_connection() as conn:
                target_reached = site_count(conn) >= MAX_SITES
            next_target_check_at = time.monotonic() + TARGET_CHECK_INTERVAL_SECONDS
            if target_reached:
                print(f"target reached: {MAX_SITES} stored sites", flush=True)

        if target_reached:
            time.sleep(max(CRAWL_DELAY_SECONDS, 30))
            continue

        with db_connection() as conn:
            items = next_frontier_batch(conn)

        if not items:
            time.sleep(max(CRAWL_DELAY_SECONDS, 5))
            continue

        for item in items:
            try:
                body, status_code = fetch(session, item["url"])
                soup, title, description, text = sanitize(body)
                keywords = extract_keywords(f"{title} {description} {text}")
                labels = warning_labels(f"{title} {description} {text}")
                links = extract_links(soup, item["url"])
                with db_connection() as conn:
                    save_site(conn, item["url"], status_code, title, description, text, keywords, labels)
                    enqueue_links(conn, links, item["url"], item["depth"] + 1)
                    mark_frontier(conn, item["id"], "done", commit=False)
                    conn.commit()
                print(f"crawled {item['url']} links={len(links)} labels={','.join(labels)}", flush=True)
            except Exception as exc:
                with db_connection() as conn:
                    status = mark_failure(conn, item["id"], exc)
                print(f"{status} {item['url']}: {exc}", flush=True)

            time.sleep(CRAWL_DELAY_SECONDS)


if __name__ == "__main__":
    main()
