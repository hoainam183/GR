# Crawler, PDF→Markdown Converter & Chunking Strategies

Tài liệu kỹ thuật mô tả 3 khâu trong pipeline nạp dữ liệu của `RAG_v2`:

1. **Crawler** — tự động lấy thông báo/kế hoạch/quy định từ `ctt.hust.edu.vn`.
2. **PDF → Markdown converter** — chuyển tài liệu upload (PDF/DOCX) sang markdown.
3. **Chunking strategies** — tách markdown/JSON thành chunk để embed & index, đi sâu vào `RecursiveChunker`, `STSVChunker`, `KeHoachChunker`.

Nguồn tham chiếu chính: `scripts/auto_crawler.py`, `document_loader/pdf_to_markdown/`, `pipeline/document_pipeline.py`, `chunking/chunker/*.py`, `pipeline/chunker_factory.py`.

---

## 1. Crawler

### 1.1 Công nghệ

| Thành phần | Công nghệ |
| --- | --- |
| HTTP client | `requests.Session` (retry thủ công, backoff mũ) |
| HTML parsing | `BeautifulSoup4` (`html.parser`) |
| Lưu trạng thái crawl | File JSON local (`data/kehoach/*.json`, `data/quydinh/*.json`) |
| Staging để admin duyệt | MongoDB (`crawler_runs`, `crawler_chunks`, qua `pymongo.MongoClient`) |
| Lập lịch | APScheduler, khởi động trong `api/main.py` lifespan khi `crawler_enabled=True` (giờ mặc định 02:00) |
| Chunk khi crawl | `KeHoachChunker` (§3.4) |
| Index sau khi admin duyệt | `BGEm3Embedder` + `E5MultilingualEmbedder` → Qdrant (`QdrantStore`) + Elasticsearch (`ElasticsearchStore`) |

File hiện hành (đang được wire vào FastAPI app và admin routes): **`scripts/auto_crawler.py`**. Có 2 script cũ hơn `data/kehoach/crawl.py` + `data/kehoach/crawl_detail.py` (tách 2 phase: crawl-list riêng và crawl-detail riêng) — đây là bản tiền thân/độc lập, đã được hợp nhất logic vào class `GenericCrawler` trong `auto_crawler.py` (crawl list + detail trong 1 lần chạy) và không còn là đường chạy chính.

### 1.2 Nguồn crawl

| Pipeline | List endpoint | `id_param` | Collection đích | Retention |
| --- | --- | --- | --- | --- |
| `baiviet` | `/DisplayWeb/DisplayListBaiViet` | `baiviet` | `kehoach` | 6 tháng (`crawler_retention_months`) |
| `kehoach_list` | `/DisplayWeb/DisplayListKeHoach` | `kehoach` | `kehoach` | 6 tháng |
| `quydinh` | `/DisplayWeb/DisplayQuyChe` | `baiviet` | `quydinh` | 96 tháng (8 năm) |

Base URL: `https://ctt.hust.edu.vn`. Cả 3 pipeline dùng chung class `GenericCrawler`, chỉ khác `list_path`/`id_param`/`output_file`/`source_label`.

### 1.3 Cách crawl — incremental, newest-first

1. `GenericCrawler.crawl_new()` đọc `existing_ids` (map `baiviet_id → date_str`) từ file JSON đã lưu.
2. `_crawl_tag_incremental()` quét từng trang danh sách (`page=1,2,…`), parse mỗi `<li class="serviceContent">` lấy `baiviet_id`, `url`, `title`, `date_str`, `category`, `tag_in_title`.
3. Vì trang web sắp xếp bài mới nhất trước, crawler **dừng ngay khi gặp 1 bài đã biết và KHÔNG đổi** (`found_existing_unchanged`) hoặc khi vượt `cutoff_date` (dựa trên `max_age_months` = retention).
4. Nếu bài đã biết nhưng `date_str` đổi → coi là **bài được cập nhật** (`_is_update=True`), vẫn crawl lại detail nhưng không tính là "hit existing" (crawler tiếp tục quét trang).
5. Với mỗi bài mới/cập nhật: `_crawl_article_detail()` fetch trang detail, `_parse_detail()` lấy title/date từ `<h3>`, chọn container `div.col-md-9.col-xs-12`, resolve link `<a>` → `text (url)`, rồi gọi `_extract_readable_html_text()`:
   - Convert `<table>` → Markdown table **trước** (dùng `utils/html_table_markdown.replace_tables_with_markdown`, tránh vỡ cấu trúc bảng khi các bước sau chèn `\n`).
   - `<br>` → `\n`, `<li>` → `\n- ...`, các block-tag (`p`, `div`, `h1-h6`, `ul`, `ol`, …) được bọc `\n` trước/sau.
   - Chuẩn hoá whitespace (`_normalize_extracted_text`): gộp khoảng trắng, bỏ dòng trống thừa, strip từng dòng.
6. HTTP fetch có retry: 3 lần, backoff `1.5^attempt` giây; thất bại toàn bộ → ghi vào `_fetch_failures` (surface trong run summary), không crash pipeline.
7. `save_to_file()` prepend bài mới vào JSON tồn tại (bài mới nhất ở đầu).

### 1.4 Auto-heal & idempotency

- `PROCESSING_VERSION` (hiện = 2) đánh dấu version của logic clean/chunk. Khi logic xử lý bảng đổi, các bài cũ có `<table>` mà chưa khớp version hiện tại sẽ được `_heal_stale_table_articles()` tự re-extract lại `content_text` từ `content_html` đã lưu — **không cần crawl lại mạng**. Bài đã đúng version bị bỏ qua → idempotent, không stage trùng ở các lần crawl sau.
- Có endpoint `reprocess()`/`reprocess_existing()` để chủ động re-extract + re-chunk hàng loạt bài đã lưu (dùng khi sửa bug clean/chunk mà không muốn crawl lại).

### 1.5 Chunk & staging (không index trực tiếp)

```text
crawl (GenericCrawler)
  -> ChunkProcessor (dùng KeHoachChunker, override metadata.source)
  -> stage vào Mongo: crawler_runs (status=pending_review) + crawler_chunks
  -> admin xem/sửa/xoá chunk qua /admin/crawler/*
  -> admin bấm "index" -> DualIndexer embed (BGE-M3 + E5) -> Qdrant + Elasticsearch
```

CLI/manual/scheduled run **luôn stage để admin duyệt**; không có đường tắt index trực tiếp từ CLI (đã bị loại bỏ có chủ đích).

### 1.6 Retention

`RetentionManager.cleanup()`: tính `cutoff = now - months*30 ngày`, xoá bài quá hạn khỏi file JSON gốc, khỏi file chunks aggregate, và (khi có indexer) khỏi Qdrant + Elasticsearch theo `baiviet_id`.

---

## 2. PDF → Markdown Converter

Vị trí: `document_loader/pdf_to_markdown/`. Chọn qua tham số `converter` khi admin upload tài liệu (`POST /admin/documents`), xử lý trong `pipeline/document_pipeline.py:DocumentPipeline`.

### 2.1 Ba converter

| Converter | Thư viện | Đặc điểm | OCR? | Đọc `.docx`? |
| --- | --- | --- | --- | --- |
| `pymupdf4llm` (**default**) | `pymupdf4llm.to_markdown()` | Trích text-layer trực tiếp từ PDF, nhanh, ra markdown có heading/bảng cơ bản | Không | Không |
| `docling` | IBM `docling.DocumentConverter` | Convert đầy đủ (`export_to_markdown()` + `export_to_dict()`), xử lý được PDF scan/ảnh (OCR), parse `.docx` gốc | Có | Có |
| `pdfplumber` | `pdfplumber` | **Chỉ trích bảng** (`page.extract_tables()`), bỏ qua text thường; tự render GFM markdown table (escape `|`, pad cột theo header) | Không | Không |

Mỗi converter kế thừa `BasePDFConverter` (`base/converter.py`): lưu `<stem>.md` + `<stem>_metadata.json` vào `output_dir`, trả về `stats` (số ký tự, số dòng, converter, path).

### 2.2 Logic chọn converter & auto-fallback

`DocumentPipeline._convert_to_markdown()` (`pipeline/document_pipeline.py`):

```text
.docx                          -> luôn dùng docling (pymupdf4llm không đọc .docx)
converter == "docling"         -> docling
converter == "pdfplumber"      -> pdfplumber (không auto-fallback)
converter mặc định (pymupdf4llm):
  -> convert bằng pymupdf4llm
  -> nếu markdown quá ngắn (< settings.pdf_min_markdown_chars)
       => PDF scan/ảnh không có text-layer => tự fallback sang docling (OCR)
```

`VALID_CONVERTERS = {"pymupdf4llm", "docling", "pdfplumber"}` (khai báo ở `pipeline/chunker_factory.py`, dùng chung để validate input admin).

### 2.3 Làm sạch sau convert

`document_loader/clean_markdown.py:clean_markdown()`:
- Xoá vùng "MỤC LỤC" (TOC) dạng dotted-leader (`...... 12`), nhưng có cơ chế chống xoá tràn: nếu gặp ≥3 dòng nội dung thật liên tiếp trong vùng TOC thì coi như TOC đã hết và giữ lại.
- Xoá dòng gạch ngang thuần (`-----`), không đụng dòng bảng.
- Chuẩn hoá khoảng trắng, **giữ nguyên format dòng bảng** (`|...|`).

### 2.4 Nguồn markdown thứ hai: olmOCR (offline)

Ngoài luồng admin-upload real-time, `quydinh` còn có markdown được OCR sẵn **bên ngoài codebase** bằng mô hình olmOCR, đặt tại `data/quydinh/olmocr/quydinh/*.md`. Script `data/quydinh/olmocr/batch_convert.py` **không tự OCR** — nó chỉ hậu-xử lý các file `.md` này (convert HTML `<table>` còn sót lại trong output OCR sang Markdown table qua `convert_html_to_markdown_tables.py`), lưu vào `data/quydinh/olmocr/converted/`. Các file này được `OlmOcrLegalChunker` (§3.3) tiêu thụ — đây là lý do `quydinh` có **2 schema chunk không tương thích**: chunk từ crawl (`KeHoachChunker`, §3.4) và chunk từ OCR văn bản pháp quy gốc (`hierarchical`/`olmocr` chunker).

---

## 3. Chunking Strategies

### 3.1 Bảng chọn strategy

Điều phối bởi `pipeline/chunker_factory.py:_create_chunker()`:

| `strategy` | Class | Input phù hợp |
| --- | --- | --- |
| `recursive` | `RecursiveChunker` | Markdown không có cấu trúc Điều/Chương pháp lý (CTĐT, hướng dẫn) — **cũng là fallback mặc định** cho mọi input không khớp (kể cả khi chọn nhầm `kehoach`/`stsv` cho PDF upload) |
| `hierarchical` | `ArticleLegalChunkerPyMuPDF` (nếu converter=`pymupdf4llm`) hoặc `ArticleLevelLegalChunker` (nếu converter=`docling`) | Văn bản pháp quy (quy định/quy chế) upload qua admin — chọn biến thể theo converter đã convert PDF, vì `pymupdf4llm` in đậm `**CHƯƠNG**`/`**Điều**` còn `docling` sinh heading `#` |
| `olmocr` | `OlmOcrLegalChunker` | Văn bản pháp quy đã OCR bằng olmOCR (không có markdown heading, `CHƯƠNG`/`Điều` là text thuần) |
| `kehoach` | `KeHoachChunker` | JSON bài viết crawl từ `ctt.hust.edu.vn` (thông báo/kế hoạch, và cả `quydinh` khi crawl) |
| `stsv` | `STSVChunker` | JSON Sổ tay Sinh viên / Kit nhập học |

Tất cả chunker "hierarchical/olmocr/recursive" đều có fallback nội bộ: nếu văn bản không khớp cấu trúc kỳ vọng → dùng `RecursiveCharacterTextSplitter` thuần.

---

### 3.2 `RecursiveChunker` — `chunking/chunker/recursive_chunker.py`

**Dùng cho:** tài liệu markdown không có cấu trúc Điều/Chương pháp lý (CTĐT, hướng dẫn, FAQ) — và là **chunker fallback mặc định** toàn hệ thống.

#### Nguyên lý

Dựa trên `langchain_text_splitters.RecursiveCharacterTextSplitter`, với separator ưu tiên theo cấu trúc markdown tiếng Việt:

```text
"\n# " → "\n## " → "\n### " → "\n#### " → "\n---\n" → "\n\n" → "\n" → ". " → ", " → " " → ""
```

`chunk_size=1024`, `chunk_overlap=0` **có chủ đích** — vì kiến trúc parent-child dưới đây đã cung cấp ngữ cảnh qua ranh giới heading, overlap sẽ gây trùng lặp nội dung giữa các chunk.

#### Kiến trúc Parent–Child

```text
mỗi H2 section  → 1 parent chunk (toàn bộ nội dung section)
nội dung trong section → nhiều child chunk (split, không overlap)
đảm bảo: child.chunk_size ≤ parent.chunk_size
```

- Parent bị cắt an toàn tại `parent_chunk_max_chars` (mặc định 10 000 ký tự) nếu quá lớn — nhưng **không truncate mất data**: nếu section H2 vượt ngưỡng, ưu tiên tách theo H3 làm parent con (`_extract_h3_sections`); nếu H3 vẫn quá lớn hoặc không có H3 → `_split_into_blocks()` tách thành nhiều parent tuần tự theo ranh giới đoạn văn (`\n\n`), **không** cắt xén nội dung.
- Document không có H2 nào → toàn bộ nội dung là "orphan children" (không gắn `parent_id`).
- Preamble (text trước H2/H3 đầu tiên) cũng được split thành orphan children riêng.

#### Bảo vệ bảng Markdown

- `_protect_tables_in_text()`: bảng có kích thước ≤ `chunk_size` được thay bằng placeholder `__TABLE_NNNN__` trước khi đưa vào `text_splitter`, tránh bị cắt giữa hàng; sau split, `_restore_tables()` khôi phục lại. Bảng lớn hơn `chunk_size` được giữ nguyên để splitter tự xử lý (sẽ bị bắt lại ở bước "oversized" dưới).
- `_fix_mid_table_chunks()`: post-process — chunk nào bắt đầu giữa bảng (thiếu header+separator) sẽ được ghép lại header từ chunk liền trước.
- `_split_table_by_rows()`: tách bảng lớn thành nhiều phần theo hàng, mỗi phần tự lặp lại header+separator; số hàng/phần được tính động theo độ dài hàng trung bình để không vượt `chunk_size`.

#### Xử lý chunk quá khổ (> `chunk_size * 1.3`)

```text
_split_oversized_chunk()
  1. Tách theo sub-heading (### / ####) nếu có
  2. Section con vẫn lớn & có bảng → tách bảng theo hàng (giữ prefix/heading ngắn)
  3. Section con thuần text vẫn lớn → re-split bằng RecursiveCharacterTextSplitter
     -> nếu vẫn không hội tụ (vd nhiều bảng nhỏ ngăn bằng nhãn **in đậm**,
        không phải heading) => _hard_resplit() fallback: bảo vệ bảng nhỏ bằng
        placeholder, re-split theo đoạn/dòng, đảm bảo KHÔNG còn mảnh vượt ngưỡng
```

#### Post-processing khác (theo thứ tự áp dụng)

1. **Inject section context** — chunk không chứa heading nào (thường là chunk chỉ có table rows) được chèn heading H2/H3/H4 gần nhất vào đầu, cải thiện chất lượng embedding.
2. **Merge chunk quá nhỏ** (< `min_chunk_size`=50, ngưỡng gộp 200) vào chunk liền kề.
3. **Merge chunk chỉ-heading** (không có thân nội dung, ví dụ `"## 1. Mục tiêu đào tạo"` đứng một mình) vào chunk kế tiếp — heading đứng một mình duy nhất (title tài liệu) được giữ lại.
4. **Dedupe heading trùng lặp** sinh ra do các bước merge ở trên (chỉ xoá dòng heading trùng thứ 2, giữ toàn bộ nội dung trước/sau).
5. **Inject "khoản cha"** — chunk con bắt đầu bằng sub-item marker (`a)`, `b)`, `c)`…) mà thiếu context của khoản số cha (ví dụ bị `RecursiveCharacterTextSplitter` cắt giữa khoản 3) sẽ được tự động chèn lại dòng khoản cha vào đầu.
6. **Fix stale section metadata** — sau mọi lần merge/split, `section_h2/h3/h4` được tính lại dựa trên heading *thực tế* còn trong content (không dùng metadata cũ có thể đã lệch).
7. Ở cấp document: loại các chunk chỉ-heading còn sót giữa các section, đồng thời giảm `child_count` của parent tương ứng (không đụng parent, không mất thông tin vì heading vẫn còn trong metadata của chunk lân cận).

#### Metadata mỗi chunk

`doc_type`, `level` (`parent`/`child`), `doc_title`, `source`, `section_h1..h4`, `hierarchy_path` (`"H1 > H2 > H3"`), `chunk_index`, `total_chunks`, `chunk_size`, `chunk_type` (`parent`/`text`/`table`/`mixed`), `has_table`, `parent_id`, `child_count` (chỉ ở parent), `effective_date`/`expiry_date`/`applicable_cohort`/`applicable_major` (placeholder, điền sau bởi `chunking/enrich_metadata.py`), `document_type`.

---

### 3.3 `STSVChunker` — `chunking/chunker/stsv_chunker.py`

**Dùng cho:** dữ liệu Sổ tay Sinh viên / Kit nhập học ở dạng JSON riêng lẻ (không phải HTML crawl):

```json
{"DocumentID": int, "Title": str, "TypeDoc": str, "Description": str,
 "CreaterID": str, "TimeCreate": str, "Status": int}
```

Chunk trên field `Description` (nội dung dạng markdown-like).

#### Phân loại nội dung (4 loại, kiểm tra theo thứ tự)

| Loại | Điều kiện | Xử lý |
| --- | --- | --- |
| 1. Ngắn | `len(Description) ≤ SINGLE_CHUNK_THRESHOLD` (1 500 ký tự) | 1 chunk duy nhất, giữ nguyên |
| 2. Có phần La Mã | Regex `_RE_ROMAN` khớp (`I.`, `II.`, `III.`…) | Tách tại ranh giới phần La Mã (`_split_by_roman_then_items`); trong mỗi phần, nếu có mục số thì tiếp tục tách theo mục số |
| 3. Có mục số | Regex `_RE_NUMBERED` khớp (`1.`, `2.`, …), không có La Mã | Tách theo mục số (`_split_by_numbered_items`) |
| 4. Văn xuôi thuần | Không khớp gì | Giữ nguyên 1 segment → xử lý bởi `RecursiveCharacterTextSplitter` ở bước build chunk |

#### Tách theo mục số — sequential tracking

Điểm quan trọng: `_split_by_numbered_items()` chỉ nhận một dòng là "mục cấp cao mới" khi số thứ tự **đúng bằng số kỳ vọng tiếp theo** (1→2→3→…). Điều này tránh nhận lầm sub-item lồng bên trong (ví dụ dòng `"1. Miễn học phần…"` xuất hiện *trong* mục 8) thành một mục cấp cao mới — nếu chỉ dùng regex số đơn giản sẽ bị cắt sai vị trí.

- Mục **dài** (`> LONG_ITEM_THRESHOLD` = 300 ký tự): coi là 1 "section", tách thành 1 segment riêng.
- Mục **ngắn** (≤ 300 ký tự): gộp nhiều mục liên tiếp vào 1 segment cho đến khi tổng độ dài đạt `chunk_size` (1024).
- Phần header/preamble trước mục số đầu tiên → segment riêng, gắn `section_context` (nếu ở trong 1 phần La Mã).

#### Build chunk cuối

- Mỗi segment nếu vẫn dài hơn `chunk_size` → tiếp tục split bằng `RecursiveCharacterTextSplitter` (`chunk_overlap=150`, separators `["\n\n", "\n", ". ", ", ", " ", ""]`).
- Mảnh nhỏ hơn `MIN_CHUNK_SIZE` (60 ký tự) bị loại bỏ.
- **Context prefix**: mỗi chunk được prepend `"[Title | TypeDoc | SectionContext]"` (nếu `add_context_prefix=True`, mặc định bật) để chunk tự đứng độc lập được khi retrieval, không phụ thuộc ngữ cảnh xung quanh.

#### Metadata mỗi chunk

`doc_id`, `title`, `type_doc`, `time_create`, `section_context` (tiêu đề phần La Mã, hoặc `None`), `item_label` (số mục, có thể là khoảng `"3–5"` khi gộp nhiều mục ngắn), `chunk_index`, `total_chunks`, `chunk_size`, `has_links` (regex phát hiện markdown link `[text](url)`).

---

### 3.4 `KeHoachChunker` — `chunking/chunker/kehoach_chunker.py`

**Dùng cho:** bài viết/thông báo/kế hoạch crawl từ `ctt.hust.edu.vn` (§1), cho cả collection `kehoach` và `quydinh` (chunker giống nhau, chỉ khác `source_label` được override sau khi chunk bởi `ChunkProcessor` trong `auto_crawler.py`).

Input JSON (1 phần tử = 1 bài viết):

```json
{"baiviet_id": int, "url": str, "title": str, "category": str,
 "tag_in_title": str, "date_str": str, "title_detail": str,
 "content_text": str, "content_html": str, "crawled_at": str}
```

Chunk trên `content_text` (plain text đã convert bảng→Markdown ở bước crawl); `content_html` bị bỏ qua.

#### Phân loại nội dung (3 loại — không có "phần La Mã" như STSV)

| Loại | Điều kiện | Xử lý |
| --- | --- | --- |
| 1. Ngắn | `≤ 1500` ký tự | 1 chunk |
| 2. Có mục số | `_RE_NUMBERED` khớp | Tách bằng cùng cơ chế *sequential-tracking* như STSV (`_split_at_numbered`) — mục dài (>300) tách riêng, mục ngắn gộp nhóm tới khi đạt `chunk_size` |
| 3. Văn xuôi thuần | Không khớp | Giữ nguyên, để bước build chunk xử lý table-aware |

#### Khác biệt cốt lõi so với `STSVChunker`: table-aware splitting

Vì nội dung crawl thường chứa bảng lịch/kế hoạch (đã được convert HTML→Markdown table ngay ở bước crawl, §1.3), `KeHoachChunker` **không dùng `RecursiveCharacterTextSplitter` trực tiếp** trên toàn bộ segment mà đi qua `_split_text_table_aware()`:

```text
với mỗi khối bảng tìm được (_RE_TABLE_BLOCK) trong segment:
  - bảng ≤ chunk_size  → giữ nguyên atomic (không đụng, đi kèm prose xung quanh nếu vừa)
  - bảng > chunk_size  → tách theo HÀNG (split_table_by_rows), mỗi mảnh tự
                          lặp lại header + separator + heading prefix
phần văn xuôi xung quanh bảng → _protect_split() (bảo vệ bảng nhỏ bằng
                          placeholder, rồi mới chạy RecursiveCharacterTextSplitter)
```

- `_section_heading()`: lấy dòng đầu tiên không phải table-row của segment làm "heading prefix" — được lặp lại vào mỗi mảnh bảng đã tách, để mảnh bảng tự đứng độc lập (self-contained) khi retrieval.
- Sau khi build xong toàn bộ chunk, `fix_mid_table_chunks()` (module chung `chunking/chunker/markdown_table.py`, cũng dùng bởi `RecursiveChunker`) ghép lại header cho chunk nào vô tình bắt đầu giữa bảng.
- **Không loại bỏ mảnh chứa bảng dù ngắn hơn `MIN_CHUNK_SIZE`** — tránh mất dữ liệu bảng, đặc biệt là hàng cuối cùng của một bảng lớn bị tách.

Module `markdown_table.py` cung cấp các helper thuần (không phụ thuộc chunker cụ thể): `has_markdown_table`, `starts_mid_table`, `find_table_header`, `protect_tables`, `restore_tables`, `split_table_by_rows`, `fix_mid_table_chunks` — được port từ logic gốc trong `RecursiveChunker` rồi tách ra dùng chung với `KeHoachChunker`, tránh trùng lặp code.

#### Build chunk & context prefix

- Context prefix: `"[title]"` (chỉ `title`, khác STSV có thêm `TypeDoc`) prepend vào mỗi chunk nếu `add_context_prefix=True`.
- Nếu 1 bài viết không sinh được chunk nào (content rỗng) → fallback tạo 1 chunk chứa `title` để không mất bài viết khỏi hệ thống.

#### Metadata mỗi chunk

`baiviet_id`, `title`, `category`, `tag_in_title`, `date_str`, `url`, `section_label` (số mục, hoặc `None`), `chunk_index`, `total_chunks`, `chunk_size`, `source` (`"kehoach"` hoặc `"quydinh"` — override sau khi chunk), `has_table`.

---

### 3.5 So sánh nhanh 3 chunker chính

| | `RecursiveChunker` | `STSVChunker` | `KeHoachChunker` |
| --- | --- | --- | --- |
| Input | Markdown tự do (PDF upload) | JSON STSV | JSON bài viết crawl |
| Cấu trúc nhận diện | Heading `#`–`####`, bảng | La Mã (I./II.) → mục số (1./2.) | Mục số (1./2.) |
| Kiến trúc | Parent–child (H2 = parent) | Segment phẳng, không parent-child | Segment phẳng, không parent-child |
| Bảo vệ bảng | Placeholder + tách theo hàng khi bảng lớn | Không (input thường không có bảng markdown) | Placeholder + tách theo hàng, giữ mảnh bảng dù nhỏ |
| Overlap | 0 (dựa vào heading để giữ context) | 150 (dựa vào `RecursiveCharacterTextSplitter` khi văn xuôi) | 0 (context giữ qua mục số/prefix) |
| Context injection | Heading + "khoản cha" tự động | Title/TypeDoc/SectionContext prefix | Title prefix + heading bảng lặp lại |
| Fallback cuối | — (chính nó là fallback toàn hệ thống) | `RecursiveCharacterTextSplitter` | `RecursiveCharacterTextSplitter` (qua `_protect_split`) |
