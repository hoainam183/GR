# Module: `tools`

Lớp công cụ tìm kiếm web cho pipeline RAG. Bọc API Tavily thành một class dùng lại được (cache, rate-limit, retry, lọc domain, xếp hạng kết quả) để tra cứu web và trích xuất nội dung URL.

## Files

### `tavily_search.py`
Toàn bộ hiện thực: class `TavilySearchTool`, cache TTL nội bộ, các hằng danh sách domain HUST/EDU và helper kiểm tra API key.
- `is_valid_tavily_api_key()` — báo key hợp lệ (không rỗng, không phải placeholder).
- `TavilySearchTool.search()` — tìm web rồi lọc, xếp hạng, cắt ngắn, trả kèm `context` đã format cho LLM.
- `TavilySearchTool.extract()` — trích nội dung trực tiếp từ danh sách URL (trang động chưa được index), không cache.
- `TavilySearchTool.filter_results()` — loại kết quả quá ngắn, điểm thấp, homepage hoặc quá cũ theo `query_year`.
- `TavilySearchTool._rank_result_for_query()` — chấm điểm re-rank theo mã học kỳ/năm học và từ khóa "mới nhất" (so khớp accent-fold).
- `TavilySearchTool._wait_for_rate_limit()` — giữ khoảng cách tối thiểu giữa các lần gọi API.

### `__init__.py`
Re-export `TavilySearchTool`, `is_valid_tavily_api_key` và các hằng danh sách domain (`HUST_OFFICIAL_DOMAINS`, `HUST_EXTENDED_DOMAINS`, `HUST_DOMAINS`, `EDU_AUTHORITATIVE_DOMAINS`, `EDU_DOMAINS`).
