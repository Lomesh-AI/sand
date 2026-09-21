from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))

from ingestion import load_documents_from_directory
from chunking import chunk_documents
from embeddings import Embedder
from vector_search import VectorStore
from bm25_store import BM25Store
from hybrid_retrieval import HybridRetrieval
from reranker import Reranker
from generator import Generator


# -----------------------------
# 1. Load documents
# -----------------------------

docs = load_documents_from_directory("docs")

print(f"\nDocuments loaded: {len(docs)}")


# -----------------------------
# 2. Chunk documents
# -----------------------------

chunks = chunk_documents(docs)

print(f"Chunks created: {len(chunks)}")


# -----------------------------
# 3. Create embeddings
# -----------------------------

embedder = Embedder()

texts = [chunk["text"] for chunk in chunks]

embeddings = embedder.embed(texts)

print(f"Embedding shape: {embeddings.shape}")


# -----------------------------
# 4. Build vector store
# -----------------------------

vector_store = VectorStore(embeddings)

print("FAISS index created")


# -----------------------------
# 5. Build BM25 store
# -----------------------------

bm25_store = BM25Store(chunks)

print("BM25 index created")


# -----------------------------
# 6. Hybrid retriever
# -----------------------------

retriever = HybridRetrieval(
    vector_store,
    bm25_store,
    embedder,
    chunks
)

print("Hybrid retriever ready")


# -----------------------------
# 7. Reranker
# -----------------------------

reranker = Reranker()

print("Reranker loaded")


# -----------------------------
# 8. Generator
# -----------------------------

generator = Generator()

print("Grok generator ready")


# -----------------------------
# 9. Query
# -----------------------------

query = "Why was RabbitMQ selected?"

print(f"\nQuery: {query}")


# -----------------------------
# 10. Hybrid retrieval
# -----------------------------

hybrid_results = retriever.search(
    query,
    top_k=10,
    alpha=0.5
)

candidate_indices = [
    idx for score, idx in hybrid_results
]

print("\nHybrid candidates:")

for score, idx in hybrid_results:
    print(
        f"{score:.3f} | "
        f"{chunks[idx]['source']} | "
        f"Chunk {chunks[idx]['chunk_id']}"
    )


# -----------------------------
# 11. Reranking
# -----------------------------

reranked = reranker.rerank(
    query,
    chunks,
    candidate_indices,
    top_k=5
)

print("\nReranked results:")

for score, idx in reranked:
    print(
        f"{score:.3f} | "
        f"{chunks[idx]['source']} | "
        f"Chunk {chunks[idx]['chunk_id']}"
    )


# -----------------------------
# 12. Prepare context
# -----------------------------

retrieved_chunks = [
    chunks[idx]
    for score, idx in reranked
]


# -----------------------------
# 13. Generate answer
# -----------------------------

answer = generator.generate(
    query,
    retrieved_chunks
)


# -----------------------------
# 14. Final output
# -----------------------------

print("\n" + "=" * 60)
print("FINAL ANSWER")
print("=" * 60)

print(answer)

print("\n" + "=" * 60)
print("SOURCES")
print("=" * 60)

for chunk in retrieved_chunks:
    print(
        f"- {chunk['source']} "
        f"(chunk {chunk['chunk_id']})"
    )

# from openai import OpenAI
# import os

# client = OpenAI(
#     api_key=os.environ["XAI_API_KEY"],
#     base_url="https://api.groq.com/openai/v1"
# )

# models = client.models.list()

# for model in models.data:
#     print(model.id)