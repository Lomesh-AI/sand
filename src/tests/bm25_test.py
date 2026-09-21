from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))

from ingestion import load_documents_from_directory
from chunking import chunk_documents
from bm25_store import BM25Store

docs = load_documents_from_directory("docs")
chunks = chunk_documents(docs)

store = BM25Store(chunks)

queries = [
    "Redis",
    "RabbitMQ",
    "transactional outbox",
    "container security",
    "monorepo"
]

for query in queries:

    results = store.search(query, top_k=5)

    print(f"\nQuery: {query}")

    for score, idx in results:
        print(
            f"Score: {score:.3f} | "
            f"{chunks[idx]['source']} | "
            f"Chunk: {chunks[idx]['chunk_id']}"
        )