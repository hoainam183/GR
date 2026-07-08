# RAG_v2 - Chatbot học vụ HUST

`RAG_v2` là hệ thống chatbot học vụ cho Đại học Bách khoa Hà Nội. Dự án gồm backend FastAPI, web app React/Vite, mobile app Expo/React Native và các service hạ tầng cho RAG: Qdrant, Elasticsearch, MongoDB, Redis.

README này là runbook để một người mới clone source có thể cài mới môi trường, tạo config, dựng hạ tầng, build lại index dữ liệu và chạy được backend, frontend, mobile.

## Tổng Quan

Hệ thống trả lời câu hỏi học vụ dựa trên các nhóm dữ liệu nội bộ:

| Collection | Nội dung |
| --- | --- |
| `ctdt` | Chương trình đào tạo, học phần, tín chỉ, học kỳ, điều kiện học phần |
| `quydinh` | Quy chế, quy định học vụ, học bổng, tốt nghiệp, ngoại ngữ |
| `kehoach` | Kế hoạch học kỳ, lịch đăng ký, thông báo, deadline |
| `stsv` | Sổ tay sinh viên, thủ tục, biểu mẫu, hỗ trợ sinh viên |
| `test` | Collection dùng cho upload/dev |

Luồng runtime cơ bản:

```text
Web/Mobile
  -> FastAPI backend
  -> RAG pipeline / LangGraph agent
  -> Qdrant vector search + Elasticsearch BM25
  -> reranker
  -> LLM sinh câu trả lời
  -> MongoDB/Redis lưu session, log, cache
```

## Stack Chính

| Phần | Công nghệ |
| --- | --- |
| Backend API | FastAPI, Uvicorn, Pydantic |
| RAG pipeline | Python, LangChain/LangGraph |
| Vector DB | Qdrant |
| Keyword search | Elasticsearch 8.7 + Vietnamese analyzer |
| Database | MongoDB |
| Cache/session/rate limit | Redis |
| Embedding | `BAAI/bge-m3`, `intfloat/multilingual-e5-large` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| LLM mặc định | DeepSeek cho answer generation, Gemini cho reflection/synthesis |
| Web | React, Vite, TanStack Query, shadcn/Radix |
| Mobile | Expo, React Native, `@rag/shared` |
| Monorepo JS | npm workspaces, Turbo |

## Cấu Trúc Thư Mục

```text
RAG_v2/
├── api/                     # FastAPI app, routes, middleware
├── auth/                    # JWT, OAuth, RBAC
├── backend/                 # Entry point chạy backend
├── cache/                   # Redis client, session, history, rate limit
├── config/                  # Settings đọc từ .env
├── data/                    # Dữ liệu nguồn và chunk JSON trong repo
├── document_loader/         # Convert PDF/DOCX sang markdown, cleaning
├── embedding/               # BGE-M3, E5 embedders
├── frontend/chat-companion/ # Web app
├── llm/                     # LLM providers
├── mobile/                  # Expo mobile app
├── models/                  # MongoDB models/client/logger
├── packages/shared/         # Shared TypeScript API/types/utils
├── pipeline/                # RAGPipeline, flows, document pipeline
├── query/                   # Router, reflection, decomposer
├── reranking/               # Cross-encoder reranker
├── retrieval/               # Qdrant, Elasticsearch, hybrid search
├── scripts/                 # Crawler/index/metadata scripts
├── tests/                   # Pytest suite
├── docker-compose.yml       # Local infra services
├── package.json             # npm workspace scripts
└── requirements.txt         # Python dependencies
```

## Yêu Cầu Máy

Khuyến nghị:

- Python 3.11.
- Node.js >= 18.18 và npm.
- Docker Desktop hoặc Docker Engine + Docker Compose.
- RAM tối thiểu 16 GB nếu chạy embedding/reranker local; 32 GB sẽ thoải mái hơn.
- Disk còn trống vài chục GB cho Python packages, npm packages, Docker images và HuggingFace model cache.
- Internet trong lần cài dependencies, pull Docker images và download models lần đầu.

Lệnh kiểm tra nhanh:

```bash
python3.11 --version
node --version
npm --version
docker --version
docker compose version
```

## Setup Backend Python

Chạy từ root của repo chứa thư mục `src/`, sau đó vào `src/RAG_v2`:

```bash
cd src/RAG_v2
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
cd src/RAG_v2
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

`requirements.txt` là file dependency Python chính của backend. File này bao gồm FastAPI, LangChain/LangGraph, Qdrant client, Elasticsearch client, Motor/PyMongo, Redis, sentence-transformers, FlagEmbedding, docling/PDF tooling, pytest và các package phụ trợ. Lần cài đầu có thể lâu vì dependency nặng.

## Setup Node Workspace

Chạy ở root `src/RAG_v2`:

```bash
npm install
```

Lệnh này cài dependencies cho npm workspaces:

- `frontend/chat-companion`
- `mobile`
- `packages/shared`

Cần chạy `npm install` ở root để web và mobile resolve được package nội bộ `@rag/shared`.

## Cấu Hình `.env`

Sau khi copy `.env.example` thành `.env`, sửa các giá trị cần thiết:

```dotenv
LLM_PROVIDER=deepseek
EMBEDDING_PROVIDER=ensemble
RERANKER_PROVIDER=bge

GOOGLE_API_KEY=your-google-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
OPENAI_API_KEY=
TAVILY_API_KEY=

JWT_SECRET_KEY=replace-with-a-long-random-secret

QDRANT_HOST=localhost
QDRANT_PORT=6333
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=rag_chatbot
MONGODB_ENABLED=true

REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
USE_REDIS_SESSION=true
USE_REDIS_CACHE=true
USE_REDIS_HISTORY=true

API_HOST=0.0.0.0
API_PORT=8000
```

Ghi chú quan trọng:

- `GOOGLE_API_KEY` bắt buộc vì backend kiểm tra key này khi startup.
- `DEEPSEEK_API_KEY` cần có nếu giữ `LLM_PROVIDER=deepseek`.
- `JWT_SECRET_KEY` không nên để giá trị mẫu khi có người khác dùng chung môi trường.
- `TAVILY_API_KEY` chỉ cần khi bật web-search fallback.
- Nếu không muốn dùng Redis lúc dev, có thể set `REDIS_ENABLED=false`, `USE_REDIS_SESSION=false`, `USE_REDIS_CACHE=false`, `USE_REDIS_HISTORY=false`.
- Nếu không muốn dùng MongoDB lúc dev, có thể set `MONGODB_ENABLED=false`, nhưng một số tính năng session/auth/admin/log sẽ bị giới hạn.

Tạo secret nhanh:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Setup Docker Services

`docker-compose.yml` hiện chạy các service hạ tầng: Qdrant, Elasticsearch, MongoDB, Redis. Backend và frontend container đang được comment, nên mặc định app sẽ chạy local bằng Python/npm.

Từ `src/RAG_v2`:

```bash
docker compose up -d qdrant elasticsearch mongodb redis
docker compose ps
```

Sau khi clone mới thường chưa có thư mục runtime data. Không cần tạo sẵn; Docker Compose sẽ tạo dữ liệu local cho các service khi start. Đây là dữ liệu runtime, không nên coi là source code.

Ports mặc định:

| Service | URL/Port |
| --- | --- |
| Backend API | `http://localhost:8000` |
| Qdrant | `http://localhost:6333` |
| Elasticsearch | `http://localhost:9200` |
| MongoDB | `mongodb://localhost:27017` |
| Redis | `redis://localhost:6379/0` |
| Web frontend | Vite sẽ in URL khi chạy, thường là `http://localhost:5173` |

Kiểm tra Elasticsearch Vietnamese analyzer:

```bash
.venv/bin/python scripts/index_to_es.py --smoke-test-only
```

Nếu lệnh này fail vì không thấy `vi_analyzer`, hãy đảm bảo bạn đang chạy Elasticsearch image từ `docker-compose.yml`, không phải một Elasticsearch khác trên máy.

## Index Dữ Liệu Cho Clone Mới

Clone mới không có Qdrant/Elasticsearch index sẵn. Sau khi Docker services đã chạy, build lại index từ dữ liệu trong `data/`.

Từ `src/RAG_v2`:

```bash
.venv/bin/python scripts/index_stsv.py
.venv/bin/python - <<'PY'
import json
from pathlib import Path

d = Path("data/kehoach/chunks")
chunks = []
for name in ("kehoach_list_all_chunks.json", "baiviet_all_chunks.json"):
    chunks.extend(json.loads((d / name).read_text(encoding="utf-8")))
(d / "kehoach_all_chunks.json").write_text(
    json.dumps(chunks, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
PY
.venv/bin/python scripts/index_kehoach.py
.venv/bin/python scripts/index_parent_child.py --collection quydinh
.venv/bin/python scripts/index_parent_child.py --collection ctdt
.venv/bin/python scripts/index_to_es.py --recreate --collections stsv quydinh kehoach ctdt
```

Thứ tự trên làm các việc:

1. Embed và upsert `stsv` vào Qdrant.
2. Tạo `data/kehoach/chunks/kehoach_all_chunks.json` từ hai file chunk đang có.
3. Embed và upsert `kehoach` vào Qdrant.
4. Embed và upsert `quydinh` vào Qdrant.
5. Embed và upsert `ctdt` vào Qdrant.
6. Tạo lại Elasticsearch indexes từ Qdrant để hybrid search có BM25.

Ghi chú:

- Lần index đầu có thể rất lâu vì phải download/load embedding models.
- `scripts/index_kehoach.py` hiện mặc định đọc `data/kehoach/chunks/kehoach_all_chunks.json`, nên clone mới cần tạo file tổng hợp này từ `kehoach_list_all_chunks.json` và `baiviet_all_chunks.json` trước khi chạy script.
- `scripts/index_to_es.py --recreate` sẽ xóa và tạo lại Elasticsearch index cho các collection được chọn.
- Nếu chỉ muốn kiểm tra Elasticsearch analyzer, dùng `--smoke-test-only` thay vì `--recreate`.
- `scripts/index_quydinh.py` có `CONFIG` nội bộ và không phải luồng mặc định khuyến nghị cho clone mới.

## Chạy Backend

Đảm bảo Docker services đã chạy và `.env` đã có key tối thiểu. Từ `src/RAG_v2`:

```bash
source .venv/bin/activate
.venv/bin/python backend/main.py
```

Backend listen ở:

```text
http://localhost:8000
```

Kiểm tra health:

```bash
curl http://localhost:8000/health
```

Expected response có dạng:

```json
{
  "status": "healthy",
  "rag_initialized": true,
  "mongo_status": "ok",
  "redis_status": "ok"
}
```

Một số endpoint hay dùng:

| Endpoint | Mục đích |
| --- | --- |
| `GET /health` | Kiểm tra backend đã init pipeline |
| `POST /chat` | Chat non-streaming |
| `POST /chat/v3` | Chat non-streaming shape ổn định cho UI |
| `POST /chat/stream` | SSE streaming |
| `GET /chat/suggest` | Suggested questions |
| `POST /auth/login` | Đăng nhập |
| `POST /auth/register` | Đăng ký |

## Chạy Web Frontend

Tạo env cho web:

```bash
cp frontend/chat-companion/.env.example frontend/chat-companion/.env
```

Nội dung tối thiểu:

```dotenv
VITE_API_URL=http://localhost:8000
```

Chạy từ root `src/RAG_v2`:

```bash
npm run dev:web
```

Hoặc chạy trực tiếp trong web app:

```bash
cd frontend/chat-companion
npm run dev
```

Vite sẽ in URL trên terminal. Mở URL đó trên browser, thường là:

```text
http://localhost:5173
```

## Chạy Mobile App

Tạo env cho mobile:

```bash
cp mobile/.env.example mobile/.env
```

Sửa `mobile/.env`:

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://<LAN_IP>:8000
```

Trong đó `<LAN_IP>` là IP LAN của máy đang chạy backend. Ví dụ trên macOS:

```bash
ipconfig getifaddr en0
```

Nếu chạy trên điện thoại thật, không dùng `localhost` vì `localhost` lúc đó là chính điện thoại. Dùng IP LAN của laptop/PC, và đảm bảo điện thoại cùng Wi-Fi với máy chạy backend.

Chạy Expo trong mobile app:

```bash
cd mobile
npm start
```

Hoặc chạy thẳng một platform cụ thể:

```bash
npm run android
npm run ios
npm run web
```

Với Expo, có thể cần cài Expo Go trên thiết bị hoặc setup Android Studio/Xcode nếu chạy simulator.

Ghi chú: root `package.json` có script `npm run dev:mobile`, nhưng `mobile/package.json` hiện tại chưa có script `dev`. Các lệnh trực tiếp trong thư mục `mobile` ở trên là cách chạy chắc chắn nhất.

## Lệnh Kiểm Tra Nhanh

Sau khi setup, chạy các lệnh sau để khoanh vùng lỗi:

```bash
curl http://localhost:8000/health
curl http://localhost:6333/collections
curl http://localhost:9200
docker compose ps
```

Kiểm tra Python settings có load được:

```bash
.venv/bin/python -c "from config.settings import Settings; s=Settings(); print(s.llm_provider, s.qdrant_host, s.elasticsearch_host, s.mongodb_uri)"
```

Kiểm tra Node workspace:

```bash
npm run typecheck
npm run lint
```

Kiểm tra backend tests:

```bash
.venv/bin/python -m pytest
```

Một số tests có thể cần Qdrant, Elasticsearch, MongoDB, Redis hoặc model local đang sẵn sàng.

## Setup Source Code Trong IDE

Khuyến nghị mở IDE tại thư mục:

```text
src/RAG_v2
```

Thiết lập Python:

- Chọn interpreter: `.venv/bin/python`.
- Nếu IDE cần path riêng, thêm project root `src/RAG_v2` vào Python analysis/import path.
- Đặt terminal working directory mặc định là `src/RAG_v2`.
- File `.env` nằm trực tiếp ở `src/RAG_v2/.env`; backend tự load file này.

Thiết lập TypeScript/Node:

- Chạy `npm install` ở root `src/RAG_v2`.
- Web app nằm ở `frontend/chat-companion`.
- Mobile app nằm ở `mobile`.
- Shared package nằm ở `packages/shared`.
- Nếu IDE không nhận `@rag/shared`, restart TypeScript server sau khi `npm install`.

Extensions nên có:

- Python/Pylance hoặc plugin Python tương đương.
- Docker.
- ESLint.
- Prettier hoặc formatter TypeScript đang dùng trong IDE của bạn.
- React Native/Expo tools nếu phát triển mobile.

## Troubleshooting

### Backend báo lỗi `GOOGLE_API_KEY not found`

Mở `src/RAG_v2/.env` và điền:

```dotenv
GOOGLE_API_KEY=your-google-api-key
```

Backend kiểm tra key này khi startup.

### Backend không connect được Qdrant/Elasticsearch/MongoDB/Redis

Kiểm tra Docker:

```bash
docker compose ps
```

Kiểm tra ports:

```bash
curl http://localhost:6333/collections
curl http://localhost:9200
```

Nếu port đã bị service khác chiếm, dừng service đó hoặc đổi port trong Docker Compose và `.env` cho khớp.

### Elasticsearch smoke test fail vì `vi_analyzer`

Cần chạy Elasticsearch từ `docker-compose.yml` của dự án vì image này build Vietnamese analyzer plugin. Nếu đang có Elasticsearch khác ở port `9200`, dừng lại service đó trước khi start compose.

### Query không có kết quả retrieval

Thường do chưa index dữ liệu. Chạy lại:

```bash
.venv/bin/python scripts/index_stsv.py
.venv/bin/python - <<'PY'
import json
from pathlib import Path

d = Path("data/kehoach/chunks")
chunks = []
for name in ("kehoach_list_all_chunks.json", "baiviet_all_chunks.json"):
    chunks.extend(json.loads((d / name).read_text(encoding="utf-8")))
(d / "kehoach_all_chunks.json").write_text(
    json.dumps(chunks, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
PY
.venv/bin/python scripts/index_kehoach.py
.venv/bin/python scripts/index_parent_child.py --collection quydinh
.venv/bin/python scripts/index_parent_child.py --collection ctdt
.venv/bin/python scripts/index_to_es.py --recreate --collections stsv quydinh kehoach ctdt
```

### Mobile không gọi được backend

Dùng IP LAN thay vì `localhost` trong `mobile/.env`:

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000
```

Đảm bảo backend listen `0.0.0.0:8000`, điện thoại và máy tính cùng mạng, firewall không chặn port `8000`.

### Lần đầu backend/index rất chậm

Đây là bình thường vì Python packages và HuggingFace models cần download/load lần đầu. Các lần sau sẽ nhanh hơn nếu cache còn nguyên.

## Checklist Clone Mới

Dùng checklist này nếu setup từ đầu:

```bash
cd src/RAG_v2

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

npm install

cp .env.example .env
cp frontend/chat-companion/.env.example frontend/chat-companion/.env
cp mobile/.env.example mobile/.env

docker compose up -d qdrant elasticsearch mongodb redis
.venv/bin/python scripts/index_to_es.py --smoke-test-only

.venv/bin/python scripts/index_stsv.py
.venv/bin/python - <<'PY'
import json
from pathlib import Path

d = Path("data/kehoach/chunks")
chunks = []
for name in ("kehoach_list_all_chunks.json", "baiviet_all_chunks.json"):
    chunks.extend(json.loads((d / name).read_text(encoding="utf-8")))
(d / "kehoach_all_chunks.json").write_text(
    json.dumps(chunks, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
PY
.venv/bin/python scripts/index_kehoach.py
.venv/bin/python scripts/index_parent_child.py --collection quydinh
.venv/bin/python scripts/index_parent_child.py --collection ctdt
.venv/bin/python scripts/index_to_es.py --recreate --collections stsv quydinh kehoach ctdt

.venv/bin/python backend/main.py
```

Sau đó mở terminal khác:

```bash
cd src/RAG_v2
npm run dev:web
```

Mobile:

```bash
cd src/RAG_v2
cd mobile
npm start
```
