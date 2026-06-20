"""
crawl_detail.py
===============
Đọc output_ctt_bkhn.json, crawl nội dung chi tiết từng URL, lưu ra output_full.json

Cài đặt:
    pip install requests beautifulsoup4

Chạy:
    python crawl_detail.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import re
from datetime import datetime

# ─────────────────────────────────────────────
INPUT_FILE = "output_ctt_bkhn.json"
OUTPUT_FILE = "output_full.json"
DELAY = 1.0  # giây giữa các request
BASE_URL = "https://ctt.hust.edu.vn"  # for resolving relative links

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
    from pathlib import Path

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
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
)


def resolve_links(container):
    """
    Thay thế <a href="url">text</a> thành text (url)
    trước khi get_text() để không mất đường link.
    Xử lý cả URL tuyệt đối (http/https) lẫn URL tương đối (/Upload/...).
    """
    for a in container.find_all("a"):
        href = a.get("href", "").strip()
        text = a.get_text(strip=True)
        if href:
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = BASE_URL + href
            else:
                # anchor-only or javascript: — preserve text only
                a.replace_with(text)
                continue
            a.replace_with(f"{text} ({full_url})")
        else:
            a.replace_with(text)


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.col-md-9.col-xs-12")

    if not container:
        return {
            "title_detail": None,
            "date_detail": None,
            "content_text": None,
            "content_html": None,
        }

    h3 = container.select_one("h3")
    title = h3.get_text(strip=True) if h3 else None

    date_detail = None
    date_tag = container.select_one("p.datetime, .date, span.date")
    if date_tag:
        date_detail = date_tag.get_text(strip=True)

    content_html = str(container)

    # Clone để xử lý text mà không ảnh hưởng content_html
    clone = BeautifulSoup(content_html, "html.parser")
    h3_clone = clone.select_one("h3")
    if h3_clone:
        h3_clone.decompose()

    resolve_links(clone)  # ← xử lý link trước khi get_text

    content_text = extract_readable_html_text(clone)

    return {
        "title_detail": title,
        "date_detail": date_detail,
        "content_text": content_text,
        "content_html": content_html,
    }


def crawl_url(url: str) -> dict:
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        res.encoding = "utf-8"
        return parse_detail(res.text)
    except requests.RequestException as e:
        log.error(f"  Lỗi: {e}")
        return {
            "error": str(e),
            "title_detail": None,
            "date_detail": None,
            "content_text": None,
            "content_html": None,
        }


def run():
    # Đọc file input
    with open(INPUT_FILE, encoding="utf-8") as f:
        articles = json.load(f)
    log.info(f"Đọc {len(articles)} bài từ {INPUT_FILE}")

    for i, article in enumerate(articles):
        url = article.get("url")
        if not url:
            continue

        log.info(
            f"[{i+1}/{len(articles)}] baiviet_id={article.get('baiviet_id')} | {url}"
        )

        detail = crawl_url(url)
        article.update(detail)
        article["crawled_at"] = datetime.now().isoformat()

        # Dùng title từ trang chi tiết nếu danh sách bị null
        if not article.get("title") and detail.get("title_detail"):
            article["title"] = detail["title_detail"]

        if detail.get("content_text"):
            preview = detail["content_text"][:80].replace("\n", " ")
            log.info(f"  ✓ {preview}...")
        else:
            log.warning(f"  ✗ Không lấy được nội dung")

        # Lưu tạm mỗi 50 bài
        if (i + 1) % 50 == 0:
            _save(articles, OUTPUT_FILE)
            log.info(f"  → Đã lưu tạm {i+1}/{len(articles)} bài")

        time.sleep(DELAY)

    _save(articles, OUTPUT_FILE)
    log.info(f"\n✅ Xong! Đã lưu {len(articles)} bài vào {OUTPUT_FILE}")


def _save(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()
