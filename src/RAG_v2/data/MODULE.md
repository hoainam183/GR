# Module: `data`

Source-verified: 2026-06-12 from `data/document_lineage.json`; all 6 `.py` helper scripts; sampled chunk JSON from `ctdt/soict/chunks_recursive_parent_child/IT2_fix_chunks.json`, `quydinh/olmocr/chunks_recursive_parent_child_3/QCDT_2025_5445_QD-DHBK_converted_chunks.json`, `quydinh/chunks/quydinh_all_chunks.json`, `quydinh/admin_upload/6a081c2e06007b85128d5f7a_recursive_chunks.json`, `kehoach/chunks/kehoach_list_all_chunks.json`, `stsv/chunks/stsv_all_chunks.json`.

## Purpose

`data/` is the local corpus and metadata store for RAG indexing. It is **not** a Python package and is never imported at runtime. Runtime components depend only on the file layout and the metadata field contracts defined below.

Indexed production collections:

- `ctdt` — curriculum documents
- `quydinh` — academic regulations
- `kehoach` — scheduled notices / plans
- `stsv` — student-support handbook articles
- `test` — admin-upload dev/testing (no curated files under `data/`)

Boundaries: `data/` owns curated source Markdown, intermediate cleaned files, and the chunk JSON arrays that feed indexing scripts. It does **not** own Qdrant collections, Elasticsearch indices, MongoDB state, or the `uploads/` directory (admin-uploaded files go there, not here).

## File Map

```text
data/
  document_lineage.json          Supersession/validity registry for ValidityFilter.

  ctdt/                          Curriculum data; 6 institute/major subdirs.
    cokhi/
    dien-dientu/
    hoa/
    soict/
    toan/                        ← two stray docling .md at major root: MI2.md, toantin.md
    vatlieu/
    <major>/
      output_docling/            Raw Markdown from PDF/DOCX via docling (one .md per program).
      clean_data/                Cleaned Markdown (*_fix.md) ready for chunking.
      chunks_recursive_parent_child/
                                 Parent/child chunk JSON (*_fix_chunks.json); indexing input.

  quydinh/                       Academic-regulation pipeline (PDF → OCR → Markdown → chunks).
    olmocr/
      quydinh/                   16 source Markdown files (OCR'd, pre-clean).
      converted/                 16 HTML-table-converted Markdown (*_converted.md).
      cleaned/                   18 cleaned Markdown (*_converted.md); indexing source.
      chunks_recursive_parent_child_3/
                                 18 per-document parent/child chunk JSON (*_chunks.json).
      batch_convert.py           Batch HTML-table converter (hardcoded absolute Windows paths — see Notes).
      convert_html_to_markdown_tables.py
                                 HTML-table-to-Markdown conversion library.
    chunks/
      quydinh_all_chunks.json    Crawl-style merged chunks (different schema — see below).
    admin_upload/                Chunk JSON from admin-uploaded PDFs (recursive_chunks schema).
    output_full.json             Aggregated source export (crawled quydinh articles).

  kehoach/                       Crawled plan/notice/news data.
    crawl.py                     Phase-1 crawler: fetches article list from ctt.hust.edu.vn by tag.
    crawl_detail.py              Phase-2 crawler: fetches full content for each article URL.
    reprocess_content_text.py    Post-processor: re-extracts content_text from saved content_html
                                 to recover relative links (/Upload/…) missed in initial crawl.
    kehoach_list_output_full.json
    baiviet_output_full.json     Raw crawl exports.
    chunks/
      kehoach_list_all_chunks.json   Plan/schedule chunks (source_list_path = /DisplayWeb/DisplayListKeHoach).
      baiviet_all_chunks.json        Article chunks (source_list_path = /DisplayWeb/DisplayListBaiViet).

  stsv/                          Student-support handbook; ~83 individual topic JSON files.
    <topic>.json                 One source document per topic (DocumentID/Title/TypeDoc/Description/…).
    clean_data/
      data.json                  Raw aggregated source.
      clean_data.py              Splits data.json into per-topic JSON files under clean_data/output/.
    chunks/
      stsv_all_chunks.json       Merged chunk set used for indexing.
```

## Helper Scripts (not runtime modules)

All scripts are standalone one-shot tools colocated with their data. None are imported by the application.

### `kehoach/crawl.py`

Crawls article listings from `ctt.hust.edu.vn/DisplayWeb/DisplayListBaiViet` by URL-encoded tag. Paginates via `li.PagedList-skipToLast a`, deduplicates by `baiviet_id`, then crawls detail pages inline. Saves incrementally every 50 articles to `output_ctt_bkhn.json.tmp`.

Key functions:
- `normalize_extracted_text(text: str) -> str` — collapses whitespace, normalises NBSP, trims blank lines.
- `extract_readable_html_text(container: BeautifulSoup) -> str` — strips scripts/styles, converts `<br>`/`<li>` to newlines, inserts newlines around block tags, then calls `normalize_extracted_text`.
- `fetch(url: str) -> BeautifulSoup | None` — GET with 15 s timeout; returns `None` on network error.
- `get_total_pages(soup: BeautifulSoup) -> int` — reads `li.PagedList-skipToLast a` href; falls back to max integer in `ul.pagination`.
- `parse_article_links(soup: BeautifulSoup, category: str) -> list[dict]` — extracts `baiviet_id`, `url`, `title`, `category`, `tag_in_title`, `date_str` from `li.serviceContent`.
- `crawl_list(tag_encoded: str, category: str) -> list[dict]` — full list crawl with 1 s delay between pages.
- `parse_article_content(soup: BeautifulSoup, url: str) -> dict` — tries multiple CSS selectors for title/content/date.
- `crawl_detail(article: dict) -> dict` — enriches article dict with `title_detail`, `date_detail`, `content_text`, `content_html`.
- `run()` — entrypoint; only `ĐTĐH` tag is active (others commented out). Output hardcoded to `output_ctt_bkhn.json`.

**Gotcha:** `OUTPUT_FILE` is a bare filename (`output_ctt_bkhn.json`), not the production `kehoach_list_output_full.json` or `baiviet_output_full.json`. The script must be run from inside `data/kehoach/` or the path adjusted.

---

### `kehoach/crawl_detail.py`

Reads `output_ctt_bkhn.json`, re-crawls each URL for full detail, writes `output_full.json`. More precise than `crawl.py`'s inline detail fetch: uses a fixed selector `div.col-md-9.col-xs-12` and calls `resolve_links()` before text extraction.

Key functions:
- `resolve_links(container)` — replaces `<a href>` tags with `text (url)` inline; handles absolute and root-relative (`/`) paths; skips anchor-only and `javascript:` hrefs.
- `parse_detail(html: str) -> dict` — parses `div.col-md-9.col-xs-12`, extracts `title_detail` from `h3`, `date_detail` from `p.datetime / .date / span.date`, `content_html`, and `content_text`.
- `crawl_url(url: str) -> dict` — GET with 15 s timeout; returns error dict on failure.
- `run()` — reads `INPUT_FILE = "output_ctt_bkhn.json"`, writes `OUTPUT_FILE = "output_full.json"`. Both are bare filenames; run from `data/kehoach/`.

---

### `kehoach/reprocess_content_text.py`

Post-processor that re-derives `content_text` from the already-saved `content_html` field in `output_full.json`. Purpose: recover relative `/Upload/…` links that were not resolved during the original crawl. Overwrites `output_full.json` in-place.

Key functions:
- `reparse_content_text(content_html: str) -> str` — removes `h3` title node, calls `resolve_links()` then `extract_readable_html_text()`.
- `main()` — iterates all items, updates `content_text` only when the re-parsed value differs, writes back.

**Gotcha:** `INPUT_FILE` and `OUTPUT_FILE` are both `Path("output_full.json")` (relative). Run from `data/kehoach/`.

---

### `quydinh/olmocr/batch_convert.py`

Iterates `*.md` files in `olmocr/quydinh/`, calls `convert_html_tables_in_file()` for each, writes `*_converted.md` to `olmocr/converted/`.

**Hardcoded absolute Windows paths:**
```python
input_dir  = Path(r"D:\GR\src\RAG_v2\data\quydinh\olmocr\quydinh")
output_dir = Path(r"D:\GR\src\RAG_v2\data\quydinh\olmocr\converted")
```
These paths must be updated to run on any machine other than the original dev machine.

---

### `quydinh/olmocr/convert_html_to_markdown_tables.py`

Library + CLI. Converts inline HTML `<table>…</table>` blocks inside Markdown files to GFM pipe tables.

Public API:
- `class HTMLTableParser(HTMLParser)` — stateful SAX-style parser; accumulates `self.tables: list[list[list[dict]]]`.
- `convert_table_to_markdown(table_data, fill_rowspan=True, fill_empty_from_above=True, fill_empty_columns=4) -> str` — handles colspan/rowspan, multi-row headers (flattened to single header row), and heuristic fill of empty leading cells from the row above.
- `convert_html_tables_in_file(input_file: str, output_file: str = None)` — reads file, replaces each `<table>…</table>` block with Markdown equivalent, writes result.

**Gotcha:** The `fill_empty_columns=4` heuristic fills empty `td` cells in the first 4 columns from the row above. This is tuned for Vietnamese regulatory tables and may produce wrong output on other table layouts.

---

### `stsv/clean_data/clean_data.py`

Reads `data.json` (a dict with key `WebTitleLst`), splits each document into a separate JSON file under `clean_data/output/` with a snake_case filename derived from the Vietnamese title.

Key functions:
- `remove_accents(text: str) -> str` — NFD normalisation + diacritic strip + `đ→d / Đ→D`.
- `title_to_filename(title: str) -> str` — lowercases, strips non-alphanumeric, collapses spaces to `_`, appends `.json`.
- `clean_html(html_text: str) -> str` — strips HTML, converts `<a>` to Markdown `[text](url)`, joins non-empty lines with `\n`.
- `main()` — reads `data.json` relative to script `__file__`; writes to `output/` subdirectory. **Does not write to the parent `stsv/` directory.** The per-topic JSON files in `stsv/*.json` were produced by a previous run of this or a similar script.

---

## Data Directory Layout and Chunk File Conventions

### `ctdt/` — Curriculum Chunks

Per-major, per-document. Each `*_fix_chunks.json` is a JSON array of chunk objects:

```json
{
  "id": "<uuid>",
  "chunk_id": "chunk_NNNN",
  "readable_id": "chunk_NNNN",
  "content": "… markdown text …",
  "metadata": {
    "doc_type": "curriculum",
    "level": "parent" | "child",
    "doc_title": "…",
    "source": "",
    "section_h1": "…", "section_h2": "…", "section_h3": null, "section_h4": null,
    "hierarchy_path": "h1 > h2 > …",
    "chunk_index": 0,
    "total_chunks": N,
    "chunk_size": N,
    "chunk_type": "parent" | "child" | "text",
    "has_table": false,
    "parent_id": null | "<uuid>",
    "child_count": N,           // present on parent chunks only
    "effective_date": null,
    "expiry_date": null,
    "applicable_cohort": null,
    "applicable_major": null,
    "document_type": "curriculum",
    "major_name": "…",
    "major_code": "IT2" | "ITE6" | …
  }
}
```

### `quydinh/olmocr/chunks_recursive_parent_child_3/` — Regulation Chunks (OCR pipeline)

Same parent/child schema as `ctdt`. Notable: `doc_type` is always `"curriculum"` (not `"regulation"`) in the current data — a known quirk of the chunker. `applicable_cohort` and `applicable_major` are present but `null` in the data; they are intended to be populated manually or by a post-processing step.

### `quydinh/chunks/quydinh_all_chunks.json` — Regulation Chunks (crawled)

**Different schema** from the OCR pipeline. These are crawled-style chunks from `ctt.hust.edu.vn/DisplayWeb/DisplayQuyChe`:

```json
{
  "chunk_id": "<uuid>",
  "content": "…",
  "metadata": {
    "baiviet_id": 44574,
    "title": "…",
    "category": "ĐTĐH",
    "tag_in_title": "ĐTĐH",
    "date_str": "29/9/2025",
    "url": "https://ctt.hust.edu.vn/…",
    "source": "quydinh",
    "section_label": null,
    "chunk_index": 0,
    "chunk_size": N,
    "total_chunks": N,
    "source_list_path": "/DisplayWeb/DisplayQuyChe",
    "applicable_cohort": ["K70"] | null,
    "applicable_major": null
  }
}
```

No `id`/`readable_id`, no hierarchy fields, no `level`/`parent_id`.

### `quydinh/admin_upload/` — Admin-uploaded Regulation Chunks

Shares the recursive parent/child schema but adds extra fields:

```json
"strategy": "recursive",
"document_id": "<mongo_object_id>",
"filename": "QD HOC PHI - 2025-2026-final.pdf",
"collection": "quydinh"
```

### `kehoach/chunks/` — Plan / Notice Chunks

Both `kehoach_list_all_chunks.json` and `baiviet_all_chunks.json` share this schema:

```json
{
  "chunk_id": "<uuid>",
  "content": "…",
  "metadata": {
    "baiviet_id": 28237,
    "title": "…",
    "category": "ĐTĐH",
    "tag_in_title": "DTDH",
    "date_str": "5/5/2026",
    "url": "https://ctt.hust.edu.vn/…",
    "source": "kehoach",
    "section_label": null | "",
    "chunk_index": 0,
    "chunk_size": N,
    "total_chunks": N,
    "source_list_path": "/DisplayWeb/DisplayListKeHoach" | "/DisplayWeb/DisplayListBaiViet"
  }
}
```

No `id`, no hierarchy, no `applicable_cohort`. `tag_in_title` can be ASCII-transliterated (`"DTDH"`) or contain the original Vietnamese (`"ĐTĐH"`).

### `stsv/chunks/stsv_all_chunks.json` — Student-Support Chunks

```json
{
  "chunk_id": "<uuid>",
  "content": "…",
  "metadata": {
    "doc_id": 69,
    "title": "…",
    "type_doc": "Sổ tay SV",
    "time_create": "2026-01-09 09:05:27",
    "section_context": "I. Giới thiệu chung",
    "item_label": null | "1",
    "chunk_index": 0,
    "total_chunks": N,
    "chunk_size": N,
    "has_links": false
  }
}
```

Note: source JSON files (`stsv/*.json`) use PascalCase keys (`DocumentID`, `Title`, `TypeDoc`, `Description`, `CreaterID`, `TimeCreate`, `Status`). The chunk schema uses **lowercase/snake_case** equivalents (`doc_id`, `title`, `type_doc`, `time_create`). No `id` top-level field; no hierarchy fields; no `applicable_cohort`.

### `document_lineage.json`

```json
{
  "_description": "…",
  "_usage": "…",
  "documents": [
    {
      "doc_id": "QD_5445_2025",
      "title": "…",
      "source_file": "QD_5445_2025.pdf",
      "effective_from": "2025-01-01",
      "scope": ["quydinh"],
      "replaces": ["QD_4600_2023"],
      "status": "active" | "superseded",
      "superseded_by": "QD_5445_2025"   // present only when status = "superseded"
    }
  ]
}
```

Currently has only 2 entries. Consumed by `retrieval/validity_filter.py`.

## Relationship to Other Modules

- `scripts/index_*.py` — read chunk JSON files, write to Qdrant/Elasticsearch.
- `chunking/` — creates or enriches chunk JSON from cleaned Markdown.
- `document_loader/` — converts PDFs/DOCX to Markdown for subsequent chunking.
- `pipeline/document_pipeline.py` — writes admin-uploaded artifacts under `uploads/`, not into `data/`; admin_upload chunks are placed here manually after review.
- `retrieval/metadata_filters.py` — consumes `major_code`, `applicable_cohort`, `applicable_major`.
- `retrieval/validity_filter.py` — consumes `document_lineage.json`.

## Maintenance Notes

- **Do not rename metadata fields without updating** `retrieval/metadata_filters.py`, `chunking/`, `scripts/index_*.py`, API traces, and evaluation labels simultaneously.
- `batch_convert.py` has hardcoded absolute Windows paths (`D:\GR\…`). Update before running on any other machine.
- `crawl.py` only crawls the `ĐTĐH` tag; other categories (`NCKH`, `TCCB`, `CTSV`) are commented out with TODOs.
- `kehoach/crawl.py` and `crawl_detail.py` write to bare filenames (`output_ctt_bkhn.json`, `output_full.json`) — they must be run from `data/kehoach/` or paths adjusted.
- `reprocess_content_text.py` is a one-shot fix for link resolution; re-running it is idempotent (only updates records where the re-parsed text differs).
- The `toan/` major has two stray `MI2.md` and `toantin.md` at the major root (outside `output_docling/`). These are not used by indexing scripts and may be cleaned up.
- `quydinh` has two distinct chunk schemas that are **not interchangeable**: OCR-pipeline chunks (recursive hierarchy) and crawled chunks (baiviet/source_list_path). Retrieval filters must account for both.
- `document_lineage.json` has only 2 entries and does not represent the full document inventory. Expand it as regulations are superseded.
- `stsv/clean_data/clean_data.py` writes to `clean_data/output/`, not to the parent `stsv/` directory. The per-topic JSON files currently in `stsv/*.json` likely came from a previous run or equivalent script.

## Useful Checks

```bash
# Verify all ctdt chunk files are present (one per clean_data/*.md)
python -c "
import json, pathlib
for chunks in pathlib.Path('data/ctdt').rglob('*_fix_chunks.json'):
    data = json.loads(chunks.read_text(encoding='utf-8'))
    print(chunks.relative_to('data'), len(data), 'chunks')
"

# Check document_lineage.json for syntax
python -m json.tool data/document_lineage.json > /dev/null

# Count active vs superseded documents
python -c "
import json; d=json.load(open('data/document_lineage.json', encoding='utf-8'))
from collections import Counter
print(Counter(x['status'] for x in d['documents']))
"

# Verify quydinh crawled chunks have applicable_cohort populated where expected
python -c "
import json
data = json.load(open('data/quydinh/chunks/quydinh_all_chunks.json', encoding='utf-8'))
missing = [c['metadata']['title'] for c in data if c['metadata'].get('applicable_cohort') is None]
print(f'{len(missing)}/{len(data)} chunks missing applicable_cohort')
"
```
