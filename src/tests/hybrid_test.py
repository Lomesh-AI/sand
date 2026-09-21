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

docs = load_documents_from_directory("docs")
chunks = chunk_documents(docs)

texts = [chunk["text"] for chunk in chunks]

embedder = Embedder()

embeddings = embedder.embed(texts)

vector_store = VectorStore(embeddings)
bm25_store = BM25Store(chunks)

retriever = HybridRetrieval(
    vector_store,
    bm25_store,
    embedder,
    chunks
)


queries = [
    "How do I check Redis?",
    "Why was RabbitMQ selected?",
    "How does the transactional outbox work?",
    "What are the security controls for containers?",
    "What is the monorepo structure?"
]
reranker = Reranker()

for query in queries:

    results = retriever.search(
        query_text = query,
        top_k=10,
        alpha=0.5
    )

    results = reranker.rerank(
        query=query,
        chunks=chunks,
        candidates_indices=[idx for _, idx in results],
        tok_k=5
    )

    print(f"\nQuery: {query}")

    for idx, score in results:
        print(
            f"Score: {score:.3f} | "
            f"{chunks[idx]['source']} | "
            f"Chunk: {chunks[idx]['chunk_id']}"
        )