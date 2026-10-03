import json
from pathlib import Path
import sys
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion import load_documents_from_directory as load_documents
from chunking import chunk_documents
from embeddings import Embedder
from vector_search import VectorStore
from bm25_store import BM25Store
from hybrid_retrieval import HybridRetrieval
from reranker import Reranker


from s3_storage import S3RAGStorage


class RAGPipeline:

    def __init__(self, docs_dir="docs", cache_dir=None, s3_storage: Optional[S3RAGStorage] = None):
        docs_path = Path(docs_dir)
        if not docs_path.is_absolute():
            sand_root = Path(__file__).resolve().parents[2]
            if (sand_root / docs_dir).exists():
                docs_path = sand_root / docs_dir

        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parents[2] / "data"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.s3_storage = s3_storage or S3RAGStorage()
        index_file = self.cache_dir / "index.faiss"
        chunks_file = self.cache_dir / "chunks.json"

        # Attempt to pull cached vector store and chunks from AWS S3 if enabled and not present locally
        if self.s3_storage.is_enabled and (not index_file.exists() or not chunks_file.exists()):
            self.s3_storage.download_assets(self.cache_dir)

        self.embedding_model = Embedder()

        if index_file.exists() and chunks_file.exists():
            with open(chunks_file, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            self.vector_store = VectorStore.load(index_file)
        else:
            documents = load_documents(str(docs_path))
            self.chunks = chunk_documents(documents)
            embeddings = self.embedding_model.embed(
                [chunk["text"] for chunk in self.chunks]
            )
            self.vector_store = VectorStore(embeddings)
            self.vector_store.save(index_file)
            with open(chunks_file, "w", encoding="utf-8") as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=2)

            # Auto-upload freshly built index to S3 if configured
            if self.s3_storage.is_enabled:
                self.s3_storage.upload_assets(self.cache_dir)

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
        return self.reranker.rerank(
            query,
            self.chunks,
            indices,
            top_k=k,
        )
