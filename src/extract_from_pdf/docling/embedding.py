import json
from langchain_huggingface import HuggingFaceEmbeddings
from tqdm import tqdm

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",
    model_kwargs={"device": "cpu"},  # Hoặc 'cpu' nếu không có GPU
    encode_kwargs={
        "normalize_embeddings": True,  # Normalize for cosine similarity
        "batch_size": 32,  # Batch size for encoding
    },
)

# Load chunks
with open("./output/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)


def build_embedding_input_optimized(chunk):
    """
    Tối ưu cho E5 model:
    - Natural language structure
    - No weird tags
    - Hierarchical context
    """
    meta = chunk["metadata"]
    content = chunk["content"].strip()

    # Build context hierarchy
    context_parts = []

    # Add chapter (if exists and meaningful)
    chapter = meta.get("chapter_full", "").strip()
    if chapter:
        context_parts.append(chapter)

    # Add article (if exists)
    article = meta.get("article_full", "").strip()
    if article:
        context_parts.append(article)

    # Add clause number (if not default/first clause)
    clause = meta.get("clause", "").strip()
    if clause and clause not in ["", "1"]:
        context_parts.append(f"Khoản {clause}")

    # Construct final text
    if context_parts:
        # Natural language: "context quy định: content"
        context_str = ", ".join(context_parts)
        final_text = f"{context_str} quy định:\n\n{content}"
    else:
        final_text = content

    return final_text


def build_embedding_input_alternative(chunk):
    """
    Alternative structure: More structured but still natural
    """
    meta = chunk["metadata"]
    content = chunk["content"].strip()

    parts = []

    # Title (document level)
    if meta.get("title"):
        parts.append(f"{meta['title']}\n")

    # Chapter and Article in one line
    location = []
    if meta.get("chapter_full"):
        location.append(meta["chapter_full"])
    if meta.get("article_full"):
        location.append(meta["article_full"])

    if location:
        parts.append(" > ".join(location))
        parts.append("\n")

    # Clause (if not first)
    if meta.get("clause") and meta["clause"] not in ["", "1"]:
        parts.append(f"Khoản {meta['clause']}:\n")

    # Content
    parts.append(content)

    return "".join(parts)


# Choose which structure to use
def build_embedding_input(chunk):
    # Recommend: use optimized version
    return build_embedding_input_optimized(chunk)
    # Or try alternative
    # return build_embedding_input_alternative(chunk)


# Build all embedding inputs first
print("Building embedding inputs...")
embedding_inputs = []
for chunk in tqdm(chunks, desc="Preparing texts"):
    chunk["embedding_input"] = build_embedding_input(chunk)
    embedding_inputs.append(chunk["embedding_input"])

# Batch embed documents (CRITICAL: use embed_documents, not embed_query)
print(f"\nEmbedding {len(embedding_inputs)} chunks in batches...")
print("⚠️  Using embed_documents() for passages (not embed_query)")

# Process in batches to avoid memory issues
batch_size = 32
all_embeddings = []

for i in tqdm(range(0, len(embedding_inputs), batch_size), desc="Embedding"):
    batch = embedding_inputs[i : i + batch_size]
    batch_embeddings = embeddings.embed_documents(batch)
    all_embeddings.extend(batch_embeddings)

# Assign embeddings back to chunks
print("\nAssigning embeddings to chunks...")
for i, chunk in enumerate(chunks):
    chunk["embedding"] = all_embeddings[i]

# Save
output_path = "./output/chunks_with_embeddings_2.json"
print(f"\nSaving to {output_path}...")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print("✅ Done!")
print(f"Total chunks embedded: {len(chunks)}")
print(f"Embedding dimension: {len(chunks[0]['embedding'])}")

# Verify embedding quality
print("\n📊 Sample check:")
print(f"First chunk preview:")
print(f"  Input: {chunks[0]['embedding_input'][:200]}...")
print(f"  Embedding (first 5 dims): {chunks[0]['embedding'][:5]}")
