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
import re
from pathlib import Path

from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

BASE_URL = "https://ctt.hust.edu.vn"
INPUT_FILE = Path("output_full.json")
OUTPUT_FILE = Path("output_full.json")  # overwrite in-place

_TEXT_BLOCK_TAGS = {
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "dt",
    "dd",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "ol",
    "p",
    "section",
    "ul",
}
# Thẻ bảng cố ý không nằm ở đây — được chuyển sang Markdown bởi
# replace_tables_with_markdown() để giữ cấu trúc bảng.


def normalize_extracted_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"([“\"'(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([”\"')\],.;:!?])", r"\1", text)
    text = re.sub(r" *\n+ *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_readable_html_text(container: BeautifulSoup) -> str:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from utils.html_table_markdown import replace_tables_with_markdown

    clone = BeautifulSoup(str(container), "html.parser")
    for tag in clone.find_all(["script", "style", "noscript"]):
        tag.decompose()
    replace_tables_with_markdown(clone)
    for br in clone.find_all("br"):
        br.replace_with("\n")
    for li in clone.find_all("li"):
        li.insert_before("\n- ")
        li.append("\n")
    for tag in clone.find_all(_TEXT_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")
    return normalize_extracted_text(clone.get_text(separator=" ", strip=False))


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
    return extract_readable_html_text(soup)


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
