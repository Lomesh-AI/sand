from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion import load_documents_from_directory as load_documents
from chunking import chunk_documents
from embeddings import Embedder
from vector_search import VectorStore
from bm25_store import BM25Store
from hybrid_retrieval import HybridRetrieval
from reranker import Reranker


class RAGPipeline:

    def __init__(self, docs_dir="docs"):
        documents = load_documents(docs_dir)
        self.chunks = chunk_documents(documents)

        self.embedding_model = Embedder()
        embeddings = self.embedding_model.embed(
            [chunk["text"] for chunk in self.chunks]
        )

        self.vector_store = VectorStore(embeddings)
        self.bm25_store = BM25Store(self.chunks)
        self.hybrid_retriever = HybridRetrieval(
            self.vector_store,
            self.bm25_store,
            self.embedding_model,
            self.chunks,
        )
        self.reranker = Reranker()

    def search(self, query, k=5):
        candidates = self.hybrid_retriever.search(
            query,
            top_k=10,
            alpha=0.5,
        )

        indices = [idx for _, idx in candidates]

        results = self.reranker.rerank(
            query,
            self.chunks,
            indices,
            top_k=k,
        )

        return results