"""
Crawler CTT - Đại học Bách Khoa Hà Nội
=======================================
Crawl danh sách bài viết theo từng category (tag),
sau đó crawl nội dung từng bài và lưu ra JSON.

Cài đặt:
    pip install requests beautifulsoup4

Chạy:
    python crawler_ctt_bkhn.py
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import time
import json
import logging
import os
import re
from datetime import datetime

# ─────────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────────

BASE_URL = "https://ctt.hust.edu.vn"

# Các category muốn crawl — key là tên hiển thị, value là tag trên URL
# Cách lấy: vào website, click từng category, copy phần tag=... trên URL
TAGS = {
    "ĐTĐH": "%C4%90T%C4%90H",  # Đào tạo đại học
    # "NCKH": "...",             # Nghiên cứu khoa học — thêm vào sau khi có URL
    # "TCCB": "...",             # Tổ chức cán bộ
    # "CTSV": "...",             # Công tác sinh viên
}

LIST_PATH = "/DisplayWeb/DisplayListBaiViet"
DETAIL_PATH = "/DisplayWeb/DisplayBaiViet"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DELAY_BETWEEN_REQUESTS = 1.0  # giây — tránh bị block
OUTPUT_FILE = "output_ctt_bkhn.json"

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
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


def normalize_extracted_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"([“\"'(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([”\"')\],.;:!?])", r"\1", text)
    text = re.sub(r" *\n+ *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_readable_html_text(container: BeautifulSoup) -> str:
    clone = BeautifulSoup(str(container), "html.parser")
    for tag in clone.find_all(["script", "style", "noscript"]):
        tag.decompose()
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
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str) -> BeautifulSoup | None:
    """GET request, trả về BeautifulSoup hoặc None nếu lỗi."""
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        res.encoding = "utf-8"
        return BeautifulSoup(res.text, "html.parser")
    except requests.RequestException as e:
        log.error(f"Lỗi khi fetch {url}: {e}")
        return None


def build_list_url(tag_encoded: str, page: int = 1) -> str:
    """Tạo URL danh sách bài viết theo tag và số trang."""
    return f"{BASE_URL}{LIST_PATH}?tag={tag_encoded}&page={page}"


def build_detail_url(href: str) -> str:
    """Ghép base URL với href tương đối từ thẻ <a>."""
    return urljoin(BASE_URL, href)


# ─────────────────────────────────────────────
# PARSE DANH SÁCH BÀI VIẾT
# ─────────────────────────────────────────────


def get_total_pages(soup: BeautifulSoup) -> int:
    """Lấy tổng số trang từ pagination."""
    # Cách 1: đọc href của nút "skip to last"
    last_li = soup.select_one("li.PagedList-skipToLast a")
    if last_li and last_li.get("href"):
        href = last_li["href"]
        try:
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            return int(params["page"][0])
        except (KeyError, ValueError, IndexError):
            pass

    # Cách 2: fallback — lấy số lớn nhất trong pagination
    page_numbers = []
    for a in soup.select("ul.pagination li a"):
        try:
            page_numbers.append(int(a.text.strip()))
        except ValueError:
            pass

    return max(page_numbers) if page_numbers else 1


def parse_article_links(soup: BeautifulSoup, category: str) -> list[dict]:
    """Trích xuất danh sách bài viết từ một trang danh sách."""
    articles = []

    for li in soup.select("li.serviceContent"):
        a_tag = li.select_one("a.contentTitle")
        date_tag = li.select_one("p.datetime.contentTex")
        title_p = li.select_one("a.contentTitle p.title")

        if not a_tag or not a_tag.get("href"):
            continue

        # Tách tag category ([ĐTĐH]) và tiêu đề thuần
        tag_text = None
        title_text = None
        if title_p:
            b_tag = title_p.select_one("b")
            if b_tag:
                tag_text = b_tag.get_text(strip=True).strip("[]")
                b_tag.decompose()
            title_text = (
                title_p.get_text(separator=" ").strip().strip('"').strip()
            )

        # Lấy baiviet ID từ href
        href = a_tag["href"]
        baiviet_id = None
        try:
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            baiviet_id = int(params["baiviet"][0])
        except (KeyError, ValueError, IndexError):
            pass

        articles.append(
            {
                "baiviet_id": baiviet_id,
                "url": build_detail_url(href),
                "title": title_text,
                "category": category,
                "tag_in_title": tag_text,
                "date_str": date_tag.get_text(strip=True) if date_tag else None,
            }
        )

    return articles


def crawl_list(tag_encoded: str, category: str) -> list[dict]:
    """Crawl toàn bộ trang danh sách của một category."""
    log.info(f"[{category}] Đang đọc trang 1...")
    first_soup = fetch(build_list_url(tag_encoded, 1))
    if not first_soup:
        return []

    total_pages = get_total_pages(first_soup)
    log.info(f"[{category}] Tổng số trang: {total_pages}")

    all_links = parse_article_links(first_soup, category)

    for page in range(2, total_pages + 1):
        log.info(f"[{category}] Trang {page}/{total_pages}")
        url = build_list_url(tag_encoded, page)
        soup = fetch(url)
        if not soup:
            continue

        new_links = parse_article_links(soup, category)
        if not new_links:
            log.warning(f"  Trang {page} không có bài — dừng sớm.")
            break

        all_links.extend(new_links)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    log.info(f"[{category}] Tổng {len(all_links)} bài viết trong danh sách")
    return all_links


# ─────────────────────────────────────────────
# PARSE NỘI DUNG BÀI VIẾT
# ─────────────────────────────────────────────


def parse_article_content(soup: BeautifulSoup, url: str) -> dict:
    """
    Trích xuất tiêu đề + nội dung từ trang chi tiết bài viết.
    Selector có thể cần điều chỉnh sau khi inspect trang chi tiết.
    """
    # Tiêu đề — thử nhiều selector phổ biến
    title = None
    for selector in [
        "h1.title",
        "h1",
        ".article-title",
        ".post-title",
        ".contentTitle",
    ]:
        tag = soup.select_one(selector)
        if tag:
            title = tag.get_text(strip=True)
            break

    # Nội dung chính
    content_html = None
    content_text = None
    for selector in [
        ".content-detail",
        ".article-content",
        ".post-content",
        "#content",
        ".content",
        "div.col-md-9 .item",  # layout phổ biến của BKHN
    ]:
        tag = soup.select_one(selector)
        if tag:
            content_html = str(tag)
            content_text = extract_readable_html_text(tag)
            break

    # Ngày đăng trên trang chi tiết (nếu có)
    date_detail = None
    for selector in ["p.datetime", ".date", ".post-date", "span.date"]:
        tag = soup.select_one(selector)
        if tag:
            date_detail = tag.get_text(strip=True)
            break

    return {
        "title_detail": title,
        "date_detail": date_detail,
        "content_text": content_text,
        "content_html": content_html,
    }


def crawl_detail(article: dict) -> dict:
    """Crawl nội dung cho một bài viết, merge vào dict gốc."""
    soup = fetch(article["url"])
    if not soup:
        article["error"] = "fetch_failed"
        return article

    detail = parse_article_content(soup, article["url"])
    article.update(detail)

    # Dùng title từ trang chi tiết nếu danh sách bị cắt ngắn
    if not article.get("title") and detail.get("title_detail"):
        article["title"] = detail["title_detail"]

    return article


# ─────────────────────────────────────────────
# PIPELINE CHÍNH
# ─────────────────────────────────────────────


def run():
    all_articles = []

    # ── Bước 1: Crawl danh sách từ tất cả categories ──
    for category, tag_encoded in TAGS.items():
        links = crawl_list(tag_encoded, category)
        all_articles.extend(links)

    # Deduplicate theo baiviet_id (phòng trường hợp bài xuất hiện ở nhiều tag)
    seen_ids = set()
    unique_articles = []
    for a in all_articles:
        key = a.get("baiviet_id") or a["url"]
        if key not in seen_ids:
            seen_ids.add(key)
            unique_articles.append(a)
    log.info(f"Tổng sau dedup: {len(unique_articles)} bài")

    # ── Bước 2: Crawl nội dung từng bài ──
    for i, article in enumerate(unique_articles):
        log.info(f"[{i+1}/{len(unique_articles)}] {article['url']}")
        crawl_detail(article)

        # Thêm timestamp crawl
        article["crawled_at"] = datetime.now().isoformat()

        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Lưu tạm mỗi 50 bài phòng crash
        if (i + 1) % 50 == 0:
            _save(unique_articles, OUTPUT_FILE + ".tmp")
            log.info(f"  → Đã lưu tạm {i+1} bài")

    # ── Bước 3: Lưu kết quả ──
    _save(unique_articles, OUTPUT_FILE)
    log.info(
        f"✅ Hoàn thành! Đã lưu {len(unique_articles)} bài vào {OUTPUT_FILE}"
    )

    # Xoá file tạm
    if os.path.exists(OUTPUT_FILE + ".tmp"):
        os.remove(OUTPUT_FILE + ".tmp")


def _save(data: list, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run()
