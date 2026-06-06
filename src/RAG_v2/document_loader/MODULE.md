# Module: `document_loader`

Source-verified: 2026-06-05 from `document_loader/__init__.py`, `document_loader/main.py`, `document_loader/main_v2.py`, `document_loader/clean_markdown.py`, `document_loader/pdf_to_markdown/__init__.py`, `pdf_to_markdown/base/converter.py`, `pdf_to_markdown/converters/{docling_converter,pymupdf4llm_converter,__init__}.py`, `pdf_to_markdown/core/{processor,vietnamese_processor,__init__}.py`, `pdf_to_markdown/batch_converter.py`, `pdf_to_markdown/test_components.py`, and `pipeline/document_pipeline.py` (consumer).

## Purpose

`document_loader` converts source PDF/DOCX documents into Markdown and cleans converted Markdown before chunking. It does **not** handle web URLs, crawling, or HTML cleaning — only local document-to-Markdown conversion. It is consumed by the admin pipeline and by standalone CLI scripts.

## File Map

```text
document_loader/
  __init__.py                              Empty package marker.
  clean_markdown.py                        Markdown cleanup (clean_markdown, is_toc_table_row); also a standalone batch-clean script.
  main.py                                  Legacy CLI: build converter + PDFProcessor, convert single file/dir (imports use bare paths; run from package dir).
  main_v2.py                               DocumentLoaderProcessor over common.BaseProcessor; PDF/DOCX -> .md + _metadata.json with skip logic. NOTE: calls converter.convert_single(), which the current converters do NOT implement (stale).
  pdf_to_markdown/
    __init__.py                            Package marker (__version__ = "1.0.0").
    base/converter.py                      BasePDFConverter ABC: convert() contract + _save_markdown/_save_metadata/_get_stats helpers.
    converters/
      __init__.py                          Exports DoclingConverter, PyMuPDF4LLMConverter (__all__ also lists Unified/PDFPlumber names that are not implemented).
      docling_converter.py                 DoclingConverter — uses docling DocumentConverter.
      pymupdf4llm_converter.py             PyMuPDF4LLMConverter — uses pymupdf4llm; plus convert_with_images().
    core/
      __init__.py                          Exports VietnameseTextProcessor (__all__ also lists PDFDetector, which has no source file).
      processor.py                         PDFProcessor — process_single / process_directory orchestration over a converter.
      vietnamese_processor.py              VietnameseTextProcessor — Vietnamese encoding/Unicode/tone normalization.
    batch_converter.py                     Standalone batch script. BROKEN: imports simple_converter (no such module).
    test_components.py                     Manual smoke script (skipped under pytest); imports core.pdf_detector (missing).
    output_quick_test/                     Sample generated .md + _metadata.json fixtures.
```

## Conversion Contract

All converters subclass `BasePDFConverter` (`base/converter.py`) and implement:

- `convert(pdf_path: Path) -> Dict[str, Any]` — converts one document, writes `<stem>.md` and `<stem>_metadata.json` into `output_dir`, and returns a stats dict (`conversion_time`, `num_chars`, `num_lines`, `status`, `converter`, paths, etc.). The Markdown text itself is written to disk, not returned in the dict.

Implemented converters and the names used by the admin pipeline:

- `pymupdf4llm` — `PyMuPDF4LLMConverter` (default; via `pymupdf4llm.to_markdown`). Returns `{"status": "failed", ...}` on error instead of raising. Extra `convert_with_images()` re-runs with image export options.
- `docling` — `DoclingConverter` (via docling `DocumentConverter`; metadata is the document dict, including page count).

Supported input formats: PDF and DOCX (DOCX validated in `main_v2.DocumentLoaderProcessor`; `main.py`/`PDFProcessor` glob `*.pdf`).

`PDFProcessor` (`core/processor.py`) drives a converter over a single file (`process_single`) or a directory glob (`process_directory`), aggregating per-file stats.

## Vietnamese Post-Processing

`VietnameseTextProcessor` (`core/vietnamese_processor.py`) fixes Vietnamese text issues: common mojibake mappings, NFC Unicode normalization, separated tone-mark reconstruction, and whitespace cleanup (`process`, `detect_and_fix`, `is_vietnamese_text`). It is a standalone utility — the active converters do not call it.

## Cleanup Contract

`clean_markdown.py` exposes `clean_markdown(text)` and `is_toc_table_row(line)`. It strips `MỤC LỤC` (table-of-contents) sections, dotted-leader TOC rows, alignment-only rules, and normalizes whitespace while preserving table rows (`|...`). Run as a script it batch-cleans `.md` files in `../output_docling_clean`.

## Module Flow (admin pipeline consumer)

```mermaid
flowchart TD
  Upload["api/routes/upload.py / offline CLI"] --> Pipeline["pipeline/DocumentPipeline.convert_pdf"]
  Pipeline -->|converter=="docling"| Docling["DoclingConverter.convert()"]
  Pipeline -->|else| PyMuPDF["PyMuPDF4LLMConverter.convert()"]
  Docling --> MdFile["<stem>.md + _metadata.json on disk"]
  PyMuPDF --> MdFile
  MdFile --> CleanStep["DocumentPipeline.clean_markdown -> clean_markdown()"]
  CleanStep --> Chunking["chunking strategies"]
  Chunking --> Indexing["pipeline embedding + Qdrant/ES"]
```

`pipeline/document_pipeline.py` instantiates `DoclingConverter`/`PyMuPDF4LLMConverter` and calls `.convert()` directly (it does not use `main.py`, `main_v2.py`, or `PDFProcessor`), then calls `clean_markdown()` from `clean_markdown.py`.

External module boundaries:

- `document_loader` converts and cleans only. Upload state, DB records, storage paths, chunking, and indexing are owned by `pipeline`, `models`, `utils`, and `chunking`.
- Converter names (`pymupdf4llm`, `docling`) are part of the admin API/UI contract; keep them aligned with `pipeline/document_pipeline.py` and `api/routes/upload.py`.

## Maintenance Notes

- Converter output directly affects chunking and retrieval quality; update chunking/eval docs when changing it.
- Several entry points are stale/standalone and not on the pipeline path: `main.py` and `main_v2.py` (latter calls non-existent `convert_single`), `batch_converter.py` (imports missing `simple_converter`), and `test_components.py` (imports missing `core.pdf_detector`). The `__all__` lists in `converters/__init__.py` and `core/__init__.py` reference symbols with no implementation.
- Do not make admin upload depend on the generated `output_quick_test/` fixtures.

## Useful Checks

```bash
python -m py_compile document_loader/clean_markdown.py document_loader/pdf_to_markdown/base/converter.py document_loader/pdf_to_markdown/converters/*.py document_loader/pdf_to_markdown/core/*.py
python -m pytest tests/test_document_pipeline.py -q -m "not integration"
```
