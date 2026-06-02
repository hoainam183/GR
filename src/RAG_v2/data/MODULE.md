# Module: `data`

Source-verified: 2026-06-02 from the `data/` tree, retrieval metadata filters, crawler staging/indexing source, and indexing scripts.

## Purpose

`data` is the local corpus and metadata source for RAG indexing. It is not imported as a normal Python package, but many runtime components depend on its file layout and metadata conventions.

The indexed production collections are:

- `ctdt`
- `quydinh`
- `kehoach`
- `stsv`
- `test` for upload/dev use

## Directory Layout

```text
data/
  document_lineage.json  Supersession/validity registry used by ValidityFilter.
  ctdt/                  Curriculum data grouped by institute/major.
  kehoach/               Crawled plan/news data and chunks.
  quydinh/               Regulations, OCR/Markdown/chunks, admin upload area.
  stsv/                  Student-support handbook/articles and chunks.
```

Top-level count snapshot from the previous full inventory:

- `ctdt`: 113 files
- `kehoach`: 7 files
- `quydinh`: 74 files
- `stsv`: 86 files

Crawler output for `kehoach`/`quydinh` now stages new chunks in Mongo
`crawler_runs` and `crawler_chunks` before appending reviewed chunks back to
archive files during the admin-approved indexing step.

## Collection Semantics

| Collection | Content | Runtime filter focus |
| --- | --- | --- |
| `ctdt` | Curriculum, majors, courses, credits, prerequisites, semester plans. | `major_code`, `major_name` |
| `quydinh` | Academic regulations, scholarships, graduation, foreign-language rules. | `applicable_cohort`, `applicable_major` |
| `kehoach` | Schedules, registration windows, notices, deadlines. | `date_str`, freshness sorting |
| `stsv` | Forms, student-support procedures, insurance, housing, contact info. | usually no metadata prefilter |

## Metadata Contracts

All indexed chunks should have:

- stable id or `chunk_id`
- text/content field before indexing
- `metadata` dict
- collection-specific source/title fields

Common metadata:

- `title` or `doc_title`
- `source` or `url`
- `chunk_index`
- `total_chunks`
- `chunk_size`
- `document_id` for admin-uploaded documents

`ctdt` should include:

- `major_code`
- `major_name`
- `document_type` or `doc_type`
- hierarchy fields for recursive chunks when available

`quydinh` should include:

- `applicable_cohort`
- `applicable_major`
- `effective_date`
- `expiry_date`
- `document_type`
- hierarchy fields for legal chunks

`kehoach` should include:

- `baiviet_id`
- `title`
- `url`
- `category`
- `date_str`
- `source_list_path`

`stsv` should include:

- `doc_id`
- `title`
- `type_doc`
- `section_context`
- `item_label`
- `time_create`

## Lineage And Validity

`document_lineage.json` is consumed by `retrieval/validity_filter.py`.

Use it to mark old documents as superseded when a newer regulation replaces them. Retrieval should prefer active documents and drop superseded sources where possible. If too few results remain after filtering, `ValidityFilter` intentionally keeps original results rather than returning an empty answer context.

## Relationship To Other Modules

- `scripts/index_*.py` read chunk files and write Qdrant/Elasticsearch.
- `chunking/` creates or enriches chunks and metadata.
- `document_loader/` converts PDFs to Markdown for chunking.
- `pipeline/document_pipeline.py` writes admin-uploaded document artifacts under `uploads/`, not directly into curated `data/`.
- `retrieval/metadata_filters.py` assumes the metadata fields listed above.

## Module Flow

```mermaid
flowchart TD
  Raw["curated PDFs/JSON/Markdown"] --> Loader["document_loader/chunking/scripts"]
  Loader --> Chunks["data/<collection> chunk files"]
  Chunks --> IndexScripts["scripts/index_*.py"]
  Chunks --> CrawlerArchive["auto_crawler reviewed archive append"]
  Lineage["document_lineage.json"] --> Validity["retrieval/ValidityFilter"]
  IndexScripts --> Embedding["embedding BGE/E5"]
  Embedding --> Qdrant["Qdrant collections"]
  IndexScripts --> ES["Elasticsearch indexes"]
  Qdrant --> Retrieval["retrieval runtime"]
  ES --> Retrieval
  Retrieval --> Eval["evaluation current policy"]
```

External module boundaries:

- `data` is a file/metadata contract, not runtime logic.
- Runtime stores are Qdrant/Elasticsearch/Mongo; data files feed indexing and validity/freshness checks.
- Changing metadata names requires updates in chunking, scripts, retrieval filters, API traces, and evaluation labels.

## Maintenance Notes

- Do not change metadata field names casually; routing, filtering, and UI traces depend on them.
- For new CTDT major codes, update `retrieval/metadata_filters.py`, `query/reflection.py`, eval labels, and docs.
- For `kehoach`, academic term tokens such as `2025.2`, `20252`, and `2025-2` are semester scope, not posting dates.
- Generated artifacts and large raw data should not be treated as architecture source unless they define metadata contracts.
