import os
import re

import psycopg2


MOJIBAKE_MARKERS = ("Ã", "Â", "Î", "Ï", "Ø", "Ù", "Ú", "Û", "â", "â€™", "â€œ", "â€")


def db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "onionlens"),
        user=os.getenv("POSTGRES_USER", "onionlens"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def looks_broken(value):
    return bool(value) and any(marker in value for marker in MOJIBAKE_MARKERS)


def mojibake_score(value):
    if not value:
        return 0
    return sum(value.count(marker) for marker in MOJIBAKE_MARKERS) + value.count("\ufffd") * 3


def repair_text(value):
    if not looks_broken(value):
        return value

    candidates = [value]
    for source_encoding in ("latin-1", "cp1252"):
        try:
            candidates.append(value.encode(source_encoding).decode("utf-8"))
        except UnicodeError:
            pass

    return min(candidates, key=mojibake_score)


def repair_keywords(keywords):
    return [repair_text(keyword) for keyword in keywords]


def main():
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, description, content_text, keywords
                FROM sites
                WHERE title ~ %s OR description ~ %s OR content_text ~ %s
                """,
                ("[ÃÂÎÏØÙÚÛ]", "[ÃÂÎÏØÙÚÛ]", "[ÃÂÎÏØÙÚÛ]"),
            )
            rows = cur.fetchall()

        repaired = 0
        with conn.cursor() as cur:
            for row in rows:
                site_id, title, description, content_text, keywords = row
                new_title = repair_text(title)
                new_description = repair_text(description)
                new_content_text = repair_text(content_text)
                new_keywords = repair_keywords(keywords or [])

                if (new_title, new_description, new_content_text, new_keywords) == (
                    title,
                    description,
                    content_text,
                    keywords,
                ):
                    continue

                cur.execute(
                    """
                    UPDATE sites
                    SET title = %s,
                        description = %s,
                        content_text = %s,
                        keywords = %s,
                        indexed_at = NULL
                    WHERE id = %s
                    """,
                    (new_title, new_description, new_content_text, new_keywords, site_id),
                )
                repaired += 1

        conn.commit()

    print(f"repaired {repaired} rows")


if __name__ == "__main__":
    main()
