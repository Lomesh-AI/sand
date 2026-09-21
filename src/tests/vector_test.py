from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))

from ingestion import load_documents_from_directory
from chunking import chunk_documents
from embeddings import Embedder
from vector_search import VectorStore

docs = load_documents_from_directory("docs")
chunks = chunk_documents(docs, chunk_size=1000, chunk_overlap=200)

texts = [chunk['text'] for chunk in chunks]
embedder = Embedder()
embeddings = [embedder.embed(text) for text in texts]
vector_store = VectorStore(embeddings=embeddings)

query = "How do you handle a failed worker?"

query_embedding = embedder.embed_query(query)

scores, indices = vector_store.search(query_embedding, top_k=5)

for score, idx in zip(scores, indices):
    print(f"Score: {score}, Source: {chunks[idx]['source']}, Chunk ID: {chunks[idx]['chunk_id']}")
