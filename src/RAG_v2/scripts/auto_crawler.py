"""
Auto-Crawler Pipeline — Multi-Source Sync (KeHoach + QuyDinh)
==============================================================
Automated daily pipeline:  crawl → clean → chunk → embed → index (Qdrant + ES)

Supports two pipelines:
  - **kehoach**: DisplayListBaiViet + DisplayListKeHoach → collection ``kehoach``
  - **quydinh**: DisplayQuyChe → collection ``quydinh`` (retention 8 years)

Also handles **retention**: deletes articles older than N months from all stores.

Usage standalone::

    python3 -m scripts.auto_crawler                        # run all pipelines
    python3 -m auto_crawler --pipeline kehoach     # kehoach only
    python3 -m scripts.auto_crawler --pipeline quydinh     # quydinh only
    python3 -m scripts.auto_crawler --dry                  # dry-run (no indexing)

When the FastAPI server is running with ``crawler_enabled=true``, this pipeline
is scheduled via APScheduler at the configured hour (default 02:00).
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("auto_crawler")

# ───────────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2

# ── KeHoach paths (separated) ─────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data" / "kehoach"
CHUNKS_DIR = DATA_DIR / "chunks"

BAIVIET_OUTPUT_FILE = DATA_DIR / "baiviet_output_full.json"
BAIVIET_CHUNKS_FILE = CHUNKS_DIR / "baiviet_all_chunks.json"

KEHOACH_LIST_OUTPUT_FILE = DATA_DIR / "kehoach_list_output_full.json"
KEHOACH_LIST_CHUNKS_FILE = CHUNKS_DIR / "kehoach_list_all_chunks.json"

# ── QuyDinh paths ─────────────────────────────────────────────
QUYDINH_DATA_DIR = PROJECT_ROOT / "data" / "quydinh"
QUYDINH_OUTPUT_FILE = QUYDINH_DATA_DIR / "output_full.json"
QUYDINH_CHUNKS_DIR = QUYDINH_DATA_DIR / "chunks"
QUYDINH_CHUNKS_FILE = QUYDINH_CHUNKS_DIR / "quydinh_all_chunks.json"

# ── Web constants ─────────────────────────────────────────────
BASE_URL = "https://ctt.hust.edu.vn"
LIST_PATH_BAIVIET = "/DisplayWeb/DisplayListBaiViet"
LIST_PATH_KEHOACH = "/DisplayWeb/DisplayListKeHoach"
LIST_PATH_QUYCHE = "/DisplayWeb/DisplayQuyChe"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ES metadata regexes (from retrieval/index_to_es.py)
SEM_RE = re.compile(
    r"(học kỳ\s*(?:[IVX]+|\d+)|\bhk\s*\d+|kỳ\s*\d+)", re.IGNORECASE
)
YEAR_RE = re.compile(
    r"(năm học\s*\d{4}\s*-\s*\d{4}|năm\s*\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*\d{4})",
    re.IGNORECASE,
)

# Vietnamese date regex  dd/mm/yyyy or d/m/yyyy
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────


def _parse_vn_date(date_str: str) -> Optional[datetime]:
    """Parse Vietnamese date string like '11/3/2026' → datetime."""
    m = _DATE_RE.search(date_str or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except (ValueError, TypeError):
        return None


def _load_json(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_json(data: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# 1. GenericCrawler — incremental web crawl
# ═══════════════════════════════════════════════════════════════


class GenericCrawler:
    """Incrementally crawls new articles from ctt.hust.edu.vn.

    Parameterized to support multiple source pages:
      - ``list_path``:  e.g. "/DisplayWeb/DisplayListKeHoach"
      - ``id_param``:   URL query param for the article ID ("baiviet" or "kehoach")
      - ``output_file``: path to the persistent JSON file for this source
      - ``source_label``: label stored in metadata ("kehoach" or "quydinh")

    Only fetches articles whose ID is NOT already present in the local
    output file.  Stops scanning as soon as it hits a known ID (articles
    are sorted newest-first on the website).
    """

    def __init__(
        self,
        list_path: str = LIST_PATH_BAIVIET,
        id_param: str = "baiviet",
        output_file: Path = BAIVIET_OUTPUT_FILE,
        source_label: str = "kehoach",
        delay: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
        max_age_months: Optional[int] = None,
    ):
        self.list_path = list_path
        self.id_param = id_param
        self.output_file = output_file
        self.source_label = source_label
        self.delay = delay
        self.tags = tags or {"ĐTĐH": "%C4%90T%C4%90H"}
        self.max_age_months = max_age_months
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ── HTTP ──────────────────────────────────────────────────

    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            res = self._session.get(url, timeout=15)
            res.raise_for_status()
            res.encoding = "utf-8"
            return BeautifulSoup(res.text, "html.parser")
        except requests.RequestException as e:
            logger.error("Fetch failed %s: %s", url, e)
            return None

    # ── List parsing ──────────────────────────────────────────

    def _build_list_url(self, tag_encoded: str, page: int = 1) -> str:
        return f"{BASE_URL}{self.list_path}?tag={tag_encoded}&page={page}"

    def _parse_list_page(self, soup: BeautifulSoup, category: str) -> List[Dict]:
        articles: List[Dict] = []
        for li in soup.select("li.serviceContent"):
            a_tag = li.select_one("a.contentTitle")
            date_tag = li.select_one("p.datetime.contentTex")
            title_p = li.select_one("a.contentTitle p.title")
            if not a_tag or not a_tag.get("href"):
                continue

            tag_text, title_text = None, None
            if title_p:
                b_tag = title_p.select_one("b")
                if b_tag:
                    tag_text = b_tag.get_text(strip=True).strip("[]")
                    b_tag.decompose()
                title_text = title_p.get_text(separator=" ").strip().strip('"').strip()

            href = a_tag["href"]
            href_str = href[0] if isinstance(href, list) else href
            article_id = None
            try:
                params = parse_qs(urlparse(href_str).query)
                # Support both "baiviet" and "kehoach" URL params
                article_id = int(params[self.id_param][0])
            except (KeyError, ValueError, IndexError):
                pass

            articles.append({
                "baiviet_id": article_id,
                "url": urljoin(BASE_URL, href_str),
                "title": title_text,
                "category": category,
                "tag_in_title": tag_text,
                "date_str": date_tag.get_text(strip=True) if date_tag else None,
                "source_list_path": self.list_path,
            })
        return articles

    # ── Detail parsing (reused from crawl_detail.py) ──────────

    @staticmethod
    def _resolve_links(container) -> None:
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

    def _parse_detail(self, html: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("div.col-md-9.col-xs-12")
        if not container:
            return {"title_detail": None, "date_detail": None,
                    "content_text": None, "content_html": None}

        h3 = container.select_one("h3")
        title = h3.get_text(strip=True) if h3 else None

        date_detail = None
        dt = container.select_one("p.datetime, .date, span.date")
        if dt:
            date_detail = dt.get_text(strip=True)

        content_html = str(container)

        clone = BeautifulSoup(content_html, "html.parser")
        h3_clone = clone.select_one("h3")
        if h3_clone:
            h3_clone.decompose()
        self._resolve_links(clone)
        lines = [l.strip() for l in clone.get_text(separator="\n").splitlines()]
        content_text = "\n".join(l for l in lines if l)

        return {
            "title_detail": title,
            "date_detail": date_detail,
            "content_text": content_text,
            "content_html": content_html,
        }

    def _crawl_article_detail(self, article: Dict) -> Dict:
        soup = self._fetch(article["url"])
        if not soup:
            article["error"] = "fetch_failed"
            return article
        detail = self._parse_detail(str(soup))
        article.update(detail)
        if not article.get("title") and detail.get("title_detail"):
            article["title"] = detail["title_detail"]
        article["crawled_at"] = datetime.now().isoformat()
        return article

    # ── Incremental crawl ─────────────────────────────────────

    def crawl_new(self) -> List[Dict]:
        """Return list of newly-crawled articles (with detail content)."""
        existing_ids = self._get_existing_ids()
        logger.info("Existing articles: %d", len(existing_ids))

        new_articles: List[Dict] = []
        for category, tag_encoded in self.tags.items():
            found = self._crawl_tag_incremental(tag_encoded, category, existing_ids)
            new_articles.extend(found)

        if not new_articles:
            logger.info("No new articles found.")
            return []

        # Crawl details
        logger.info("Crawling details for %d new articles …", len(new_articles))
        for i, art in enumerate(new_articles):
            logger.info("  [%d/%d] baiviet_id=%s", i + 1, len(new_articles),
                        art.get("baiviet_id"))
            self._crawl_article_detail(art)
            time.sleep(self.delay)

        return new_articles

    def _get_existing_ids(self) -> Set[int]:
        data = _load_json(self.output_file)
        return {a["baiviet_id"] for a in data if a.get("baiviet_id")}

    def _crawl_tag_incremental(
        self, tag_encoded: str, category: str, existing_ids: Set[int]
    ) -> List[Dict]:
        """Crawl pages until we hit an already-known baiviet_id or exceed max_age_months."""
        page = 1
        new_arts: List[Dict] = []
        
        cutoff_date = None
        if self.max_age_months:
            cutoff_date = datetime.now() - timedelta(days=self.max_age_months * 30)
            
        while True:
            url = self._build_list_url(tag_encoded, page)
            logger.info("[%s] Fetching page %d …", category, page)
            soup = self._fetch(url)
            if not soup:
                break

            items = self._parse_list_page(soup, category)
            if not items:
                break

            found_existing = False
            hit_cutoff = False
            for item in items:
                bid = item.get("baiviet_id")
                if bid and bid in existing_ids:
                    found_existing = True
                    break
                    
                # Check cutoff date
                if cutoff_date:
                    dt = _parse_vn_date(item.get("date_str", ""))
                    if dt and dt < cutoff_date:
                        hit_cutoff = True
                        break

                new_arts.append(item)

            if found_existing:
                logger.info("[%s] Hit existing article — stopping.", category)
                break
                
            if hit_cutoff:
                logger.info("[%s] Hit article older than %d months — stopping.", category, self.max_age_months)
                break

            page += 1
            time.sleep(self.delay)

        logger.info("[%s] Found %d new articles.", category, len(new_arts))
        return new_arts

    def save_to_file(self, new_articles: List[Dict]) -> None:
        """Prepend new articles to the output file."""
        existing = _load_json(self.output_file)
        merged = new_articles + existing
        _save_json(merged, self.output_file)
        logger.info("Saved %d articles (total %d) to %s",
                    len(new_articles), len(merged), self.output_file)


# ═══════════════════════════════════════════════════════════════
# 2. ChunkProcessor
# ═══════════════════════════════════════════════════════════════


class ChunkProcessor:
    """Chunks articles using KeHoachChunker and saves/updates chunks file.

    Parameters
    ----------
    source_label : str
        Value for ``metadata.source`` in each chunk ("kehoach" or "quydinh").
    chunks_file : Path
        Path to the aggregate chunks JSON file for this source.
    """

    def __init__(self, source_label: str = "kehoach", chunks_file: Path = BAIVIET_CHUNKS_FILE):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from chunking.chunker.kehoach_chunker import KeHoachChunker
        self._chunker = KeHoachChunker()
        self._source_label = source_label
        self._chunks_file = chunks_file

    def chunk_articles(self, articles: List[Dict]) -> List[Dict]:
        all_chunks: List[Dict] = []
        for art in articles:
            try:
                chunks = self._chunker.chunk_document(art)
                # Override source label and preserve source_list_path
                for c in chunks:
                    c["metadata"]["source"] = self._source_label
                    if "source_list_path" not in c["metadata"] and "source_list_path" in art:
                        c["metadata"]["source_list_path"] = art["source_list_path"]
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning("Chunk failed for baiviet_id=%s: %s",
                               art.get("baiviet_id"), e)
        logger.info("Produced %d chunks from %d articles.", len(all_chunks), len(articles))
        return all_chunks

    def save_chunks(self, new_chunks: List[Dict]) -> None:
        existing = _load_json(self._chunks_file)
        merged = existing + new_chunks
        _save_json(merged, self._chunks_file)
        logger.info("Saved %d new chunks (total %d) to %s.",
                    len(new_chunks), len(merged), self._chunks_file)


# ═══════════════════════════════════════════════════════════════
# 3. DualIndexer — Qdrant + Elasticsearch
# ═══════════════════════════════════════════════════════════════


class DualIndexer:
    """Embeds chunks and upserts into Qdrant + Elasticsearch."""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        es_host: str = "localhost",
        es_port: int = 9200,
        collection: str = "kehoach",
        batch_size: int = 32,
        bge=None,
        e5=None,
    ):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))

        from retrieval.qdrant_store import QdrantStore
        from retrieval.elasticsearch_store import ElasticsearchStore

        self.batch_size = batch_size
        self.collection = collection

        # Reuse embedders if provided, else create new
        if bge is None:
            from embedding.bge_m3 import BGEm3Embedder
            logger.info("Loading BGE-M3 embedder …")
            bge = BGEm3Embedder()
        if e5 is None:
            from embedding.e5_multilingual import E5MultilingualEmbedder
            logger.info("Loading E5-multilingual embedder …")
            e5 = E5MultilingualEmbedder()

        self._bge = bge
        self._e5 = e5
        self._qdrant = QdrantStore(host=qdrant_host, port=qdrant_port,
                                   collection_name=collection)
        self._es = ElasticsearchStore(host=es_host, port=es_port,
                                      index_name=collection)

    def index_chunks(self, chunks: List[Dict]) -> int:
        """Embed and upsert chunks. Returns count of newly indexed chunks."""
        # Filter already-indexed (Qdrant)
        new_chunks = self._filter_new(chunks)
        if not new_chunks:
            logger.info("All chunks already indexed — nothing to do.")
            return 0

        total = len(new_chunks)
        logger.info("Indexing %d new chunks into Qdrant + ES …", total)

        indexed = 0
        for start in range(0, total, self.batch_size):
            batch = new_chunks[start: start + self.batch_size]
            texts = [c["content"] for c in batch]
            ids = [c["chunk_id"] for c in batch]
            metas = [c.get("metadata", {}) for c in batch]

            bge_vecs = self._bge.embed_documents(texts)
            e5_vecs = self._e5.embed_documents(texts)

            # Qdrant
            self._qdrant.index_documents(
                texts=texts, bge_m3_vectors=bge_vecs,
                e5_vectors=e5_vecs, metadatas=metas, ids=ids,
            )

            # Elasticsearch — enrich metadata
            es_metas = []
            for meta, text in zip(metas, texts):
                m = dict(meta)
                sem_match = SEM_RE.search(text)
                year_match = YEAR_RE.search(text)
                parts = []
                if sem_match:
                    parts.append(sem_match.group(0).strip())
                if year_match:
                    parts.append(year_match.group(0).strip())
                if parts:
                    m["semester"] = " ".join(parts)
                es_metas.append(m)

            self._es.index_documents(texts, es_metas, ids)

            indexed += len(batch)
            logger.info("  [%d/%d] batch indexed.", indexed, total)

        return indexed

    def _filter_new(self, chunks: List[Dict]) -> List[Dict]:
        ids = [c["chunk_id"] for c in chunks]
        existing: set = set()
        for start in range(0, len(ids), 100):
            batch_ids = ids[start: start + 100]
            results = self._qdrant.client.retrieve(
                collection_name=self._qdrant.collection_name,
                ids=batch_ids, with_payload=False, with_vectors=False,
            )
            existing.update(str(r.id) for r in results)
        new = [c for c in chunks if c["chunk_id"] not in existing]
        logger.info("Filter: %d existing, %d new.", len(existing), len(new))
        return new

    def delete_by_baiviet_ids(self, baiviet_ids: List[int]) -> int:
        """Delete all points/docs matching the given baiviet_ids."""
        if not baiviet_ids:
            return 0

        from qdrant_client.models import Filter, FieldCondition, MatchAny

        deleted = 0
        # Qdrant
        try:
            self._qdrant.client.delete(
                collection_name=self._qdrant.collection_name,
                points_selector=Filter(must=[
                    FieldCondition(key="baiviet_id", match=MatchAny(any=baiviet_ids))
                ]),
            )
            logger.info("Qdrant: deleted points for %d baiviet_ids.", len(baiviet_ids))
            deleted += 1
        except Exception as e:
            logger.error("Qdrant delete failed: %s", e)

        # Elasticsearch
        try:
            for bid in baiviet_ids:
                self._es.client.delete_by_query(
                    index=self._es.index_name,
                    body={"query": {"term": {"baiviet_id": bid}}},
                    refresh=True,
                )
            logger.info("ES: deleted docs for %d baiviet_ids.", len(baiviet_ids))
            deleted += 1
        except Exception as e:
            logger.error("ES delete failed: %s", e)

        return deleted


# ═══════════════════════════════════════════════════════════════
# 4. RetentionManager
# ═══════════════════════════════════════════════════════════════


class RetentionManager:
    """Removes articles older than ``months`` from JSON, chunks, and indexes.

    Parameters
    ----------
    months : int
        Retention period. Articles older than this are deleted.
    output_file : Path
        Path to the output_full.json for this source.
    chunks_file : Path
        Path to the chunks aggregate file for this source.
    """

    def __init__(
        self,
        months: int = 6,
        output_file: Path = BAIVIET_OUTPUT_FILE,
        chunks_file: Path = BAIVIET_CHUNKS_FILE,
    ):
        self.months = months
        self.output_file = output_file
        self.chunks_file = chunks_file

    def cleanup(self, indexer: Optional[DualIndexer] = None) -> int:
        cutoff = datetime.now() - timedelta(days=self.months * 30)
        logger.info("Retention cutoff: %s (%d months)", cutoff.strftime("%Y-%m-%d"),
                     self.months)

        # 1. Find expired IDs from output_full.json
        articles = _load_json(self.output_file)
        expired_ids: List[int] = []
        kept: List[Dict] = []
        for art in articles:
            dt = _parse_vn_date(art.get("date_str", ""))
            if dt and dt < cutoff:
                bid = art.get("baiviet_id")
                if bid:
                    expired_ids.append(bid)
            else:
                kept.append(art)

        if not expired_ids:
            logger.info("No expired articles to remove.")
            return 0

        logger.info("Removing %d expired articles (older than %s).",
                     len(expired_ids), cutoff.strftime("%Y-%m-%d"))

        # 2. Remove from JSON
        _save_json(kept, self.output_file)

        # 3. Remove from chunks file
        chunks = _load_json(self.chunks_file)
        expired_set = set(expired_ids)
        new_chunks = [c for c in chunks
                      if c.get("metadata", {}).get("baiviet_id") not in expired_set]
        removed_chunks = len(chunks) - len(new_chunks)
        _save_json(new_chunks, self.chunks_file)
        logger.info("Removed %d chunks from file.", removed_chunks)

        # 4. Remove from Qdrant + ES
        if indexer:
            indexer.delete_by_baiviet_ids(expired_ids)

        return len(expired_ids)


# ═══════════════════════════════════════════════════════════════
# 5. AutoCrawlPipeline — Orchestrator
# ═══════════════════════════════════════════════════════════════


class AutoCrawlPipeline:
    """End-to-end: crawl → clean → chunk → index → retention → notify.

    Supports two independent pipelines:
      - ``run_kehoach()``: BaiViet + ListKeHoach → collection ``kehoach``
      - ``run_quydinh()``: QuyChe → collection ``quydinh`` (8-year retention)
      - ``run()``: orchestrates both pipelines
    """

    QUYDINH_RETENTION_MONTHS = 96  # 8 years

    def __init__(self, settings=None, bge=None, e5=None):
        self._settings = settings
        self._bge = bge
        self._e5 = e5

    def _parse_tags(self) -> Dict[str, str]:
        if not self._settings or not self._settings.crawler_tags:
            return {"ĐTĐH": "%C4%90T%C4%90H"}
        tags = {}
        for pair in self._settings.crawler_tags.split(","):
            pair = pair.strip()
            if ":" in pair:
                name, encoded = pair.split(":", 1)
                tags[name.strip()] = encoded.strip()
        return tags or {"ĐTĐH": "%C4%90T%C4%90H"}

    # ── Pipeline: KeHoach (BaiViet) ───────────────────────────

    def run_baiviet(self) -> Dict[str, Any]:
        """Crawl BaiViet → collection kehoach."""
        return self._run_single_pipeline(
            pipeline_name="baiviet",
            crawlers_config=[
                {
                    "list_path": LIST_PATH_BAIVIET,
                    "id_param": "baiviet",
                    "label": "BaiViet",
                }
            ],
            output_file=BAIVIET_OUTPUT_FILE,
            chunks_file=BAIVIET_CHUNKS_FILE,
            collection="kehoach",
            source_label="kehoach",
            retention_months=(
                self._settings.crawler_retention_months
                if self._settings else 6
            ),
        )

    # ── Pipeline: KeHoach (ListKeHoach) ────────────────────────

    def run_kehoach_list(self) -> Dict[str, Any]:
        """Crawl ListKeHoach → collection kehoach."""
        return self._run_single_pipeline(
            pipeline_name="kehoach_list",
            crawlers_config=[
                {
                    "list_path": LIST_PATH_KEHOACH,
                    "id_param": "kehoach",
                    "label": "ListKeHoach",
                }
            ],
            output_file=KEHOACH_LIST_OUTPUT_FILE,
            chunks_file=KEHOACH_LIST_CHUNKS_FILE,
            collection="kehoach",
            source_label="kehoach",
            retention_months=(
                self._settings.crawler_retention_months
                if self._settings else 6
            ),
        )

    def run_kehoach(self) -> Dict[str, Any]:
        """Backward compatibility: run both BaiViet and ListKeHoach."""
        return {
            "baiviet": self.run_baiviet(),
            "kehoach_list": self.run_kehoach_list()
        }

    # ── Pipeline: QuyDinh ─────────────────────────────────────

    def run_quydinh(self) -> Dict[str, Any]:
        """Crawl QuyChe → collection quydinh (8-year retention)."""
        return self._run_single_pipeline(
            pipeline_name="quydinh",
            crawlers_config=[
                {
                    "list_path": LIST_PATH_QUYCHE,
                    "id_param": "baiviet",
                    "label": "QuyChe",
                },
            ],
            output_file=QUYDINH_OUTPUT_FILE,
            chunks_file=QUYDINH_CHUNKS_FILE,
            collection="quydinh",
            source_label="quydinh",
            retention_months=self.QUYDINH_RETENTION_MONTHS,
        )

    # ── Run all ───────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Execute both pipelines. Returns combined summary."""
        kehoach = self.run_kehoach()
        quydinh = self.run_quydinh()
        return {"kehoach": kehoach, "quydinh": quydinh}

    # ── Internal: generic single-pipeline runner ──────────────

    def _run_single_pipeline(
        self,
        pipeline_name: str,
        crawlers_config: List[Dict],
        output_file: Path,
        chunks_file: Path,
        collection: str,
        source_label: str,
        retention_months: int,
    ) -> Dict[str, Any]:
        start_time = datetime.now()
        summary: Dict[str, Any] = {
            "pipeline": pipeline_name,
            "collection": collection,
            "started_at": start_time.isoformat(),
            "status": "success",
            "new_articles": 0,
            "new_chunks": 0,
            "indexed": 0,
            "expired_removed": 0,
            "saved_chunks": [],
            "errors": [],
        }

        logger.info("=" * 60)
        logger.info("PIPELINE [%s] STARTED at %s", pipeline_name, start_time.isoformat())
        logger.info("=" * 60)

        indexer = None
        try:
            delay = self._settings.crawler_delay if self._settings else 1.0
            tags = self._parse_tags()

            # Step 1: Crawl from all configured sources
            logger.info("─── STEP 1: Crawl [%s] ───", pipeline_name)
            all_new_articles: List[Dict] = []
            for cfg in crawlers_config:
                crawler = GenericCrawler(
                    list_path=cfg["list_path"],
                    id_param=cfg["id_param"],
                    output_file=output_file,
                    source_label=source_label,
                    delay=delay,
                    tags=tags,
                    max_age_months=retention_months,
                )
                logger.info("  Crawling from %s …", cfg["label"])
                new_arts = crawler.crawl_new()
                all_new_articles.extend(new_arts)

            summary["new_articles"] = len(all_new_articles)

            if all_new_articles:
                # Save raw data (single output file per pipeline)
                # Use a temporary GenericCrawler just for saving
                saver = GenericCrawler(
                    output_file=output_file,
                    source_label=source_label,
                )
                saver.save_to_file(all_new_articles)

                # Step 2: Chunk
                logger.info("─── STEP 2: Chunk [%s] ───", pipeline_name)
                chunker = ChunkProcessor(
                    source_label=source_label,
                    chunks_file=chunks_file,
                )
                new_chunks = chunker.chunk_articles(all_new_articles)
                summary["new_chunks"] = len(new_chunks)

                if new_chunks:
                    chunker.save_chunks(new_chunks)

                    # Step 3: Index
                    logger.info("─── STEP 3: Index [%s] (Qdrant + ES) ───", pipeline_name)
                    indexer = self._make_indexer(collection=collection)
                    indexed = indexer.index_chunks(new_chunks)
                    summary["indexed"] = indexed
                    if indexed > 0:
                        summary["saved_chunks"] = self._build_saved_chunk_preview(new_chunks)

                    # Invalidate LLM Cache (Phase 2) — tag-based
                    if indexed > 0:
                        try:
                            from config.settings import Settings
                            settings = Settings()
                            if settings.redis_enabled and settings.use_redis_cache:
                                from cache.redis_client import RedisManager
                                from cache.llm_cache import LLMResponseCache
                                rm = RedisManager.from_settings(settings)
                                cache = LLMResponseCache(redis_client=rm.get_client())
                                chunk_ids = [c["chunk_id"] for c in new_chunks if c.get("chunk_id")]
                                invalidated = cache.invalidate_by_docs(chunk_ids)
                                logger.info("Auto crawler: invalidated %d LLM cache entries for %d new chunks.",
                                            invalidated, len(chunk_ids))
                        except Exception:
                            logger.warning("Failed to invalidate LLM cache during auto crawl", exc_info=True)
                        try:
                            from evaluation.post_index import trigger_post_index_eval
                            from config.settings import Settings as _EvalSettings

                            trigger_post_index_eval(
                                self._settings or _EvalSettings(),
                                reason=f"auto_crawler_{pipeline_name}",
                                collection=collection,
                            )
                        except Exception:
                            logger.warning("Failed to trigger post-index eval during auto crawl", exc_info=True)

            # Step 4: Retention
            logger.info("─── STEP 4: Retention [%s] (%d months) ───",
                        pipeline_name, retention_months)
            retention = RetentionManager(
                months=retention_months,
                output_file=output_file,
                chunks_file=chunks_file,
            )
            indexer_for_del = indexer or self._make_indexer(collection=collection)
            expired = retention.cleanup(indexer=indexer_for_del)
            summary["expired_removed"] = expired

        except Exception as e:
            summary["status"] = "error"
            summary["errors"].append(str(e))
            logger.error("Pipeline [%s] FAILED: %s", pipeline_name, e)
            logger.error(traceback.format_exc())

        elapsed = (datetime.now() - start_time).total_seconds()
        summary["elapsed_seconds"] = round(elapsed, 1)

        self._notify(summary)
        return summary

    @staticmethod
    def _build_saved_chunk_preview(chunks: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        previews: List[Dict[str, Any]] = []
        for chunk in chunks[:limit]:
            metadata = chunk.get("metadata") or {}
            content = " ".join(str(chunk.get("content") or "").split())
            section_label = metadata.get("section_label")
            previews.append({
                "chunk_id": str(chunk.get("chunk_id") or ""),
                "title": str(metadata.get("title") or ""),
                "source": str(metadata.get("source") or ""),
                "url": str(metadata.get("url") or ""),
                "section_label": str(section_label) if section_label is not None else "",
                "content_preview": content[:280],
            })
        return previews

    def _make_indexer(self, collection: str = "kehoach") -> DualIndexer:
        s = self._settings
        return DualIndexer(
            qdrant_host=s.qdrant_host if s else "localhost",
            qdrant_port=s.qdrant_port if s else 6333,
            es_host=s.elasticsearch_host if s else "localhost",
            es_port=s.elasticsearch_port if s else 9200,
            collection=collection,
            bge=self._bge,
            e5=self._e5,
        )

    @staticmethod
    def _notify(summary: Dict[str, Any]) -> None:
        pipeline = summary.get("pipeline", "unknown")
        status = summary["status"]
        icon = "✅" if status == "success" else "❌"
        msg = (
            f"\n{'=' * 60}\n"
            f"{icon} PIPELINE [{pipeline}] {status.upper()}\n"
            f"  Started:  {summary.get('started_at', '?')}\n"
            f"  Elapsed:  {summary.get('elapsed_seconds', '?')}s\n"
            f"  New articles: {summary.get('new_articles', 0)}\n"
            f"  New chunks:   {summary.get('new_chunks', 0)}\n"
            f"  Indexed:      {summary.get('indexed', 0)}\n"
            f"  Expired removed: {summary.get('expired_removed', 0)}\n"
        )
        if summary.get("errors"):
            msg += f"  Errors: {summary['errors']}\n"
        msg += "=" * 60
        logger.info(msg)

        # Broadcast notification cho tất cả users khi có data mới
        if summary.get("indexed", 0) > 0:
            try:
                import asyncio

                loop = asyncio.new_event_loop()
                count = loop.run_until_complete(
                    AutoCrawler._create_user_notifications(summary)
                )
                loop.close()
                logger.info("Created %d user notifications.", count)
            except Exception:
                logger.warning("Failed to create user notifications", exc_info=True)

    @staticmethod
    async def _create_user_notifications(summary: Dict[str, Any]) -> int:
        """Broadcast notification cho tất cả users khi có dữ liệu mới."""
        from models.database import (
            NOTIFICATIONS_COLLECTION,
            USERS_COLLECTION,
            _get_settings,
            get_motor_client,
        )

        _, db_name = _get_settings()
        db = get_motor_client()[db_name]

        pipeline_name = summary.get("pipeline", "unknown")
        new_articles = summary.get("new_articles", 0)
        saved_chunks = summary.get("saved_chunks", [])

        body_parts = [
            f"Hệ thống vừa cập nhật {new_articles} bài viết mới từ nguồn {pipeline_name}."
        ]
        if saved_chunks:
            body_parts.append("\nBài viết mới:")
            for chunk in saved_chunks[:5]:
                title = chunk.get("title", "")
                url = chunk.get("url", "")
                if title and url:
                    body_parts.append(f"• {title}\n  {url}")
                elif title:
                    body_parts.append(f"• {title}")

        users_cursor = db[USERS_COLLECTION].find({}, {"_id": 1})
        user_ids = [str(u["_id"]) async for u in users_cursor]
        if not user_ids:
            return 0

        now = datetime.now(timezone.utc)
        docs = [
            {
                "user_id": uid,
                "title": "📚 Dữ liệu mới đã cập nhật",
                "body": "\n".join(body_parts),
                "type": "crawler_update",
                "read": False,
                "created_at": now,
                "related_doc_id": None,
                "metadata": {
                    "pipeline": pipeline_name,
                    "new_articles": new_articles,
                    "indexed": summary.get("indexed", 0),
                    "article_links": [
                        {"title": c.get("title", ""), "url": c.get("url", "")}
                        for c in saved_chunks[:5]
                        if c.get("url")
                    ],
                },
            }
            for uid in user_ids
        ]
        result = await db[NOTIFICATIONS_COLLECTION].insert_many(docs)
        return len(result.inserted_ids)


# ───────────────────────────────────────────────────────────────
# CLI entry point
# ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    import argparse
    _sys.path.insert(0, str(PROJECT_ROOT))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    from config.settings import Settings

    parser = argparse.ArgumentParser(
        description="Auto-Crawler Pipeline (KeHoach + QuyDinh)"
    )
    parser.add_argument("--dry", action="store_true", help="Dry run (no saving/indexing)")
    parser.add_argument(
        "--pipeline", choices=["kehoach", "quydinh", "all"],
        default="all", help="Which pipeline to run (default: all)",
    )
    parser.add_argument(
        "--module", choices=["crawl", "chunk", "index", "retention", "all"],
        default="all", help="Run a specific module or the entire pipeline",
    )
    args = parser.parse_args()

    settings = Settings()
    pipeline = AutoCrawlPipeline(settings=settings)

    # ── Resolve pipeline-specific paths ──
    def _get_pipeline_config(name: str):
        if name == "quydinh":
            return {
                "output_file": QUYDINH_OUTPUT_FILE,
                "chunks_file": QUYDINH_CHUNKS_FILE,
                "collection": "quydinh",
                "source_label": "quydinh",
                "retention_months": AutoCrawlPipeline.QUYDINH_RETENTION_MONTHS,
                "crawlers": [
                    {"list_path": LIST_PATH_QUYCHE, "id_param": "baiviet", "label": "QuyChe"},
                ],
            }
        elif name == "baiviet":
            return {
                "output_file": BAIVIET_OUTPUT_FILE,
                "chunks_file": BAIVIET_CHUNKS_FILE,
                "collection": "kehoach",
                "source_label": "kehoach",
                "retention_months": settings.crawler_retention_months,
                "crawlers": [
                    {"list_path": LIST_PATH_BAIVIET, "id_param": "baiviet", "label": "BaiViet"},
                ],
            }
        else:  # kehoach_list
            return {
                "output_file": KEHOACH_LIST_OUTPUT_FILE,
                "chunks_file": KEHOACH_LIST_CHUNKS_FILE,
                "collection": "kehoach",
                "source_label": "kehoach",
                "retention_months": settings.crawler_retention_months,
                "crawlers": [
                    {"list_path": LIST_PATH_KEHOACH, "id_param": "kehoach", "label": "ListKeHoach"},
                ],
            }

    base_pipelines = (
        ["kehoach", "quydinh"] if args.pipeline == "all"
        else [args.pipeline]
    )
    
    pipelines_to_run = []
    for p in base_pipelines:
        if p == "kehoach":
            pipelines_to_run.extend(["baiviet", "kehoach_list"])
        else:
            pipelines_to_run.append(p)

    if args.module == "all":
        if args.dry:
            for pname in pipelines_to_run:
                cfg = _get_pipeline_config(pname)
                logger.info("DRY RUN [%s] — crawl only, no indexing", pname)
                for cr in cfg["crawlers"]:
                    crawler = GenericCrawler(
                        list_path=cr["list_path"],
                        id_param=cr["id_param"],
                        output_file=cfg["output_file"],
                        source_label=cfg["source_label"],
                        delay=settings.crawler_delay,
                    )
                    arts = crawler.crawl_new()
                    logger.info("[%s/%s] Would process %d new articles.",
                                pname, cr["label"], len(arts))
        else:
            for pname in pipelines_to_run:
                runner = getattr(pipeline, f"run_{pname}")
                result = runner()
                logger.info("Result [%s]: %s", pname,
                            json.dumps(result, ensure_ascii=False, indent=2))

    elif args.module == "crawl":
        for pname in pipelines_to_run:
            cfg = _get_pipeline_config(pname)
            logger.info("Running ONLY CRAWL module [%s]...", pname)
            for cr in cfg["crawlers"]:
                crawler = GenericCrawler(
                    list_path=cr["list_path"],
                    id_param=cr["id_param"],
                    output_file=cfg["output_file"],
                    source_label=cfg["source_label"],
                    delay=settings.crawler_delay,
                    tags=pipeline._parse_tags(),
                    max_age_months=cfg["retention_months"],
                )
                arts = crawler.crawl_new()
                if not args.dry and arts:
                    crawler.save_to_file(arts)
                logger.info("[%s/%s] Crawl completed. Found %d new articles.",
                            pname, cr["label"], len(arts))

    elif args.module == "chunk":
        for pname in pipelines_to_run:
            cfg = _get_pipeline_config(pname)
            logger.info("Running ONLY CHUNK module [%s]...", pname)
            arts = _load_json(cfg["output_file"])
            chunker = ChunkProcessor(
                source_label=cfg["source_label"],
                chunks_file=cfg["chunks_file"],
            )
            chunks = chunker.chunk_articles(arts)
            if not args.dry and chunks:
                _save_json(chunks, cfg["chunks_file"])
            logger.info("[%s] Chunk completed. Produced %d chunks from %d articles.",
                        pname, len(chunks), len(arts))

    elif args.module == "index":
        for pname in pipelines_to_run:
            cfg = _get_pipeline_config(pname)
            logger.info("Running ONLY INDEX module [%s]...", pname)
            chunks = _load_json(cfg["chunks_file"])
            if not args.dry and chunks:
                indexer = pipeline._make_indexer(collection=cfg["collection"])
                indexed = indexer.index_chunks(chunks)
                logger.info("[%s] Index completed. Indexed %d new chunks.", pname, indexed)
            else:
                logger.info("[%s] Index skipped (dry run or no chunks).", pname)

    elif args.module == "retention":
        for pname in pipelines_to_run:
            cfg = _get_pipeline_config(pname)
            logger.info("Running ONLY RETENTION module [%s] (%d months)...",
                        pname, cfg["retention_months"])
            retention = RetentionManager(
                months=cfg["retention_months"],
                output_file=cfg["output_file"],
                chunks_file=cfg["chunks_file"],
            )
            if not args.dry:
                indexer = pipeline._make_indexer(collection=cfg["collection"])
                expired = retention.cleanup(indexer=indexer)
                logger.info("[%s] Retention completed. Removed %d expired articles.",
                            pname, expired)
            else:
                logger.info("[%s] Retention skipped (dry run).", pname)
