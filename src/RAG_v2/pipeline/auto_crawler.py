"""
Auto-Crawler Pipeline — Daily Kehoach Sync
===========================================
Automated daily pipeline:  crawl → clean → chunk → embed → index (Qdrant + ES)

Also handles **retention**: deletes articles older than N months from all stores.

Usage standalone::

    python -m pipeline.auto_crawler          # one-shot run
    python -m pipeline.auto_crawler --dry    # dry-run (no indexing)

When the FastAPI server is running with ``crawler_enabled=true``, this pipeline
is scheduled via APScheduler at the configured hour (default 02:00).
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from datetime import datetime, timedelta
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
DATA_DIR = PROJECT_ROOT / "data" / "kehoach"
OUTPUT_FILE = DATA_DIR / "output_full.json"
CHUNKS_DIR = DATA_DIR / "chunks"
CHUNKS_FILE = CHUNKS_DIR / "kehoach_all_chunks.json"

BASE_URL = "https://ctt.hust.edu.vn"
LIST_PATH = "/DisplayWeb/DisplayListBaiViet"
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
# 1. KehoachCrawler — incremental web crawl
# ═══════════════════════════════════════════════════════════════


class KehoachCrawler:
    """Incrementally crawls new articles from ctt.hust.edu.vn.

    Only fetches articles whose ``baiviet_id`` is NOT already present
    in the local ``output_full.json``.  Stops scanning as soon as it
    hits a known ID (articles are sorted newest-first on the website).
    """

    def __init__(self, delay: float = 1.0, tags: Optional[Dict[str, str]] = None):
        self.delay = delay
        self.tags = tags or {"ĐTĐH": "%C4%90T%C4%90H"}
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
        return f"{BASE_URL}{LIST_PATH}?tag={tag_encoded}&page={page}"

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
            baiviet_id = None
            try:
                params = parse_qs(urlparse(href).query)
                baiviet_id = int(params["baiviet"][0])
            except (KeyError, ValueError, IndexError):
                pass

            articles.append({
                "baiviet_id": baiviet_id,
                "url": urljoin(BASE_URL, href),
                "title": title_text,
                "category": category,
                "tag_in_title": tag_text,
                "date_str": date_tag.get_text(strip=True) if date_tag else None,
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
        data = _load_json(OUTPUT_FILE)
        return {a["baiviet_id"] for a in data if a.get("baiviet_id")}

    def _crawl_tag_incremental(
        self, tag_encoded: str, category: str, existing_ids: Set[int]
    ) -> List[Dict]:
        """Crawl pages until we hit an already-known baiviet_id."""
        page = 1
        new_arts: List[Dict] = []
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
            for item in items:
                bid = item.get("baiviet_id")
                if bid and bid in existing_ids:
                    found_existing = True
                    break
                new_arts.append(item)

            if found_existing:
                logger.info("[%s] Hit existing article — stopping.", category)
                break

            page += 1
            time.sleep(self.delay)

        logger.info("[%s] Found %d new articles.", category, len(new_arts))
        return new_arts

    def save_to_file(self, new_articles: List[Dict]) -> None:
        """Prepend new articles to output_full.json."""
        existing = _load_json(OUTPUT_FILE)
        merged = new_articles + existing
        _save_json(merged, OUTPUT_FILE)
        logger.info("Saved %d articles (total %d) to %s",
                    len(new_articles), len(merged), OUTPUT_FILE)


# ═══════════════════════════════════════════════════════════════
# 2. ChunkProcessor
# ═══════════════════════════════════════════════════════════════


class ChunkProcessor:
    """Chunks articles using KeHoachChunker and saves/updates chunks file."""

    def __init__(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from chunking.chunker.kehoach_chunker import KeHoachChunker
        self._chunker = KeHoachChunker()

    def chunk_articles(self, articles: List[Dict]) -> List[Dict]:
        all_chunks: List[Dict] = []
        for art in articles:
            try:
                chunks = self._chunker.chunk_document(art)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning("Chunk failed for baiviet_id=%s: %s",
                               art.get("baiviet_id"), e)
        logger.info("Produced %d chunks from %d articles.", len(all_chunks), len(articles))
        return all_chunks

    def save_chunks(self, new_chunks: List[Dict]) -> None:
        existing = _load_json(CHUNKS_FILE)
        merged = existing + new_chunks
        _save_json(merged, CHUNKS_FILE)
        logger.info("Saved %d new chunks (total %d).", len(new_chunks), len(merged))


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
    """Removes articles older than ``months`` from JSON, chunks, and indexes."""

    def __init__(self, months: int = 6):
        self.months = months

    def cleanup(self, indexer: Optional[DualIndexer] = None) -> int:
        cutoff = datetime.now() - timedelta(days=self.months * 30)
        logger.info("Retention cutoff: %s (%d months)", cutoff.strftime("%Y-%m-%d"),
                     self.months)

        # 1. Find expired IDs from output_full.json
        articles = _load_json(OUTPUT_FILE)
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
        _save_json(kept, OUTPUT_FILE)

        # 3. Remove from chunks file
        chunks = _load_json(CHUNKS_FILE)
        expired_set = set(expired_ids)
        new_chunks = [c for c in chunks
                      if c.get("metadata", {}).get("baiviet_id") not in expired_set]
        removed_chunks = len(chunks) - len(new_chunks)
        _save_json(new_chunks, CHUNKS_FILE)
        logger.info("Removed %d chunks from file.", removed_chunks)

        # 4. Remove from Qdrant + ES
        if indexer:
            indexer.delete_by_baiviet_ids(expired_ids)

        return len(expired_ids)


# ═══════════════════════════════════════════════════════════════
# 5. AutoCrawlPipeline — Orchestrator
# ═══════════════════════════════════════════════════════════════


class AutoCrawlPipeline:
    """End-to-end: crawl → clean → chunk → index → retention → notify."""

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

    def run(self) -> Dict[str, Any]:
        """Execute the full pipeline. Returns a summary dict."""
        start_time = datetime.now()
        summary: Dict[str, Any] = {
            "started_at": start_time.isoformat(),
            "status": "success",
            "new_articles": 0,
            "new_chunks": 0,
            "indexed": 0,
            "expired_removed": 0,
            "errors": [],
        }

        logger.info("=" * 60)
        logger.info("AUTO-CRAWL PIPELINE STARTED at %s", start_time.isoformat())
        logger.info("=" * 60)

        try:
            delay = self._settings.crawler_delay if self._settings else 1.0
            tags = self._parse_tags()

            # Step 1: Crawl
            logger.info("─── STEP 1: Crawl ───")
            crawler = KehoachCrawler(delay=delay, tags=tags)
            new_articles = crawler.crawl_new()
            summary["new_articles"] = len(new_articles)

            if new_articles:
                # Save raw data
                crawler.save_to_file(new_articles)

                # Step 2: Chunk
                logger.info("─── STEP 2: Chunk ───")
                chunker = ChunkProcessor()
                new_chunks = chunker.chunk_articles(new_articles)
                summary["new_chunks"] = len(new_chunks)

                if new_chunks:
                    chunker.save_chunks(new_chunks)

                    # Step 3: Index
                    logger.info("─── STEP 3: Index (Qdrant + ES) ───")
                    indexer = self._make_indexer()
                    indexed = indexer.index_chunks(new_chunks)
                    summary["indexed"] = indexed

            # Step 4: Retention
            logger.info("─── STEP 4: Retention ───")
            months = self._settings.crawler_retention_months if self._settings else 6
            retention = RetentionManager(months=months)
            indexer_for_del = self._make_indexer() if not new_articles else indexer
            expired = retention.cleanup(indexer=indexer_for_del)
            summary["expired_removed"] = expired

        except Exception as e:
            summary["status"] = "error"
            summary["errors"].append(str(e))
            logger.error("Pipeline FAILED: %s", e)
            logger.error(traceback.format_exc())

        elapsed = (datetime.now() - start_time).total_seconds()
        summary["elapsed_seconds"] = round(elapsed, 1)

        # Notification log
        self._notify(summary)

        return summary

    def _make_indexer(self) -> DualIndexer:
        s = self._settings
        return DualIndexer(
            qdrant_host=s.qdrant_host if s else "localhost",
            qdrant_port=s.qdrant_port if s else 6333,
            es_host=s.elasticsearch_host if s else "localhost",
            es_port=s.elasticsearch_port if s else 9200,
            collection="kehoach",
            bge=self._bge,
            e5=self._e5,
        )

    @staticmethod
    def _notify(summary: Dict[str, Any]) -> None:
        status = summary["status"]
        icon = "✅" if status == "success" else "❌"
        msg = (
            f"\n{'=' * 60}\n"
            f"{icon} AUTO-CRAWL PIPELINE {status.upper()}\n"
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

    parser = argparse.ArgumentParser(description="Auto-Crawler Pipeline for Kehoach")
    parser.add_argument("--dry", action="store_true", help="Dry run (no saving/indexing)")
    parser.add_argument("--module", choices=["crawl", "chunk", "index", "retention", "all"], 
                        default="all", help="Run a specific module or the entire pipeline")
    args = parser.parse_args()

    settings = Settings()
    pipeline = AutoCrawlPipeline(settings=settings)

    if args.module == "all":
        if args.dry:
            logger.info("DRY RUN — skipping indexing")
            crawler = KehoachCrawler(delay=settings.crawler_delay)
            arts = crawler.crawl_new()
            logger.info("Would process %d new articles.", len(arts))
        else:
            result = pipeline.run()
            logger.info("Result: %s", json.dumps(result, ensure_ascii=False, indent=2))
            
    elif args.module == "crawl":
        logger.info("Running ONLY CRAWL module...")
        crawler = KehoachCrawler(delay=settings.crawler_delay, tags=pipeline._parse_tags())
        arts = crawler.crawl_new()
        if not args.dry and arts:
            crawler.save_to_file(arts)
        logger.info("Crawl completed. Found %d new articles.", len(arts))
        
    elif args.module == "chunk":
        logger.info("Running ONLY CHUNK module...")
        # Chunk everything in output_full.json
        arts = _load_json(OUTPUT_FILE)
        chunker = ChunkProcessor()
        chunks = chunker.chunk_articles(arts)
        if not args.dry and chunks:
            # Overwrite chunks file completely for consistency
            _save_json(chunks, CHUNKS_FILE)
        logger.info("Chunk completed. Produced %d chunks from %d articles.", len(chunks), len(arts))
        
    elif args.module == "index":
        logger.info("Running ONLY INDEX module...")
        chunks = _load_json(CHUNKS_FILE)
        if not args.dry and chunks:
            indexer = pipeline._make_indexer()
            indexed = indexer.index_chunks(chunks)
            logger.info("Index completed. Indexed %d new chunks.", indexed)
        else:
            logger.info("Index skipped (dry run or no chunks).")
            
    elif args.module == "retention":
        logger.info("Running ONLY RETENTION module...")
        months = settings.crawler_retention_months
        retention = RetentionManager(months=months)
        if not args.dry:
            indexer = pipeline._make_indexer()
            expired = retention.cleanup(indexer=indexer)
            logger.info("Retention completed. Removed %d expired articles.", expired)
        else:
            logger.info("Retention skipped (dry run).")
