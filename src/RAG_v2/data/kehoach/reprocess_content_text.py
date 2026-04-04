"""
reprocess_content_text.py
=========================
Tái xử lý content_text từ content_html đã lưu để khôi phục
các đường link tương đối (/Upload/...) bị mất khi crawl.

Chạy từ thư mục kehoach/:
    python reprocess_content_text.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

BASE_URL = "https://ctt.hust.edu.vn"
INPUT_FILE = Path("output_full.json")
OUTPUT_FILE = Path("output_full.json")  # overwrite in-place


def resolve_links(container) -> None:
    """Replace <a href="url">text</a> → text (url), handling both absolute and relative URLs."""
    for a in container.find_all("a"):
        href = a.get("href", "").strip()
        text = a.get_text(strip=True)
        if href:
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = BASE_URL + href
            else:
                a.replace_with(text)
                continue
            a.replace_with(f"{text} ({full_url})")
        else:
            a.replace_with(text)


def reparse_content_text(content_html: str) -> str:
    """Re-extract content_text from saved HTML with fixed link resolution."""
    soup = BeautifulSoup(content_html, "html.parser")
    # Remove h3 (title already stored separately)
    h3 = soup.select_one("h3")
    if h3:
        h3.decompose()
    resolve_links(soup)
    lines = [
        line.strip() for line in soup.get_text(separator="\n").splitlines()
    ]
    return "\n".join(line for line in lines if line)


def main():
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    log.info("Loaded %d items from %s", len(data), INPUT_FILE)

    updated = 0
    for item in data:
        ch = item.get("content_html")
        if not ch:
            continue
        new_text = reparse_content_text(ch)
        if new_text != item.get("content_text"):
            item["content_text"] = new_text
            updated += 1

    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(
        "Updated content_text for %d / %d items → saved to %s",
        updated,
        len(data),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
