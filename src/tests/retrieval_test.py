from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))

from ingestion import load_documents_from_directory
from chunking import chunk_documents
from embeddings import Embedder
from vector_search import VectorStore


docs = load_documents_from_directory("docs")
chunks = chunk_documents(docs)

texts = [chunk["text"] for chunk in chunks]

embedder = Embedder()
embeddings = embedder.embed(texts)

store = VectorStore(embeddings)


test_cases = [
    {
        "query": "How do I check Redis?",
        "expected": "docs/runbook.md"
    },
    {
        "query": "What are the security controls for containers?",
        "expected": "docs/security.md"
    },
    {
        "query": "Why was RabbitMQ selected?",
        "expected": "docs/decisions/0002-rabbitmq.md"
    },
    {
        "query": "How does the transactional outbox work?",
        "expected": "docs/decisions/0005-transactional-outbox.md"
    },
    {
        "query": "What is the monorepo structure?",
        "expected": "docs/decisions/0001-monorepo.md"
    }
]


for case in test_cases:

    query_embedding = embedder.embed_query(case["query"])

    scores, indices = store.search(query_embedding, top_k=5)

    retrieved_sources = [
        chunks[idx]["source"]
        for idx in indices
    ]

    hit = case["expected"] in retrieved_sources

    print(f"\nQuery: {case['query']}")
    print(f"Expected: {case['expected']}")
    print(f"Retrieved: {retrieved_sources}")
    print(f"Top-5 Hit: {hit}")