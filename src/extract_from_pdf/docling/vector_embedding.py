import json
from langchain_huggingface import HuggingFaceEmbeddings

# Option 2: Multilingual model (miễn phí, tốt cho tiếng Việt)
embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",
    # hoặc "intfloat/multilingual-e5-large"
)

# Embed chunks


with open("./output/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)


def build_embedding_input(chunk):
    meta = chunk["metadata"]

    parts = []

    # Header thông tin pháp lý
    parts.append(f"[Title] {meta['title']}")
    parts.append(f"[Chapter] {meta['chapter_full']}")
    parts.append(f"[Article] {meta['article_full']}")
    parts.append(f"[Clause] Khoản {meta['clause']}")

    # Content
    parts.append("\n[Content]")
    parts.append(chunk["content"])

    # Footnotes (nếu có)
    # footnotes = meta.get("footnotes")
    # if footnotes:
    #     parts.append("\n[Footnotes]")
    #     for key, fn in footnotes.items():
    #         parts.append(f"{key}. {fn['content']}")

    # print(parts)
    return "\n".join(parts)


for chunk in chunks:
    chunk["embedding_input"] = build_embedding_input(chunk)
    chunk["embedding"] = embeddings.embed_query(chunk["embedding_input"])

with open("./output/chunks_with_embeddings.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=4)

# 0.028338106349110603,
