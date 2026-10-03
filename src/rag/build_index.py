#!/usr/bin/env python3
"""
Builds the FAISS vector index and chunk database from docs/
with batching, progress reporting, performance benchmarking, and S3 upload.

Usage:
    python src/rag/build_index.py --limit 500              # Quick benchmark (500 docs)
    python src/rag/build_index.py                          # Full build (all 2,241 docs)
    python src/rag/build_index.py --limit 500 --upload     # Build and upload to S3
"""

import argparse
import json
import time
from pathlib import Path
import sys

# Setup paths
SRC_DIR = Path(__file__).resolve().parents[1]
SAND_ROOT = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load .env
from dotenv import load_dotenv
for env_file in [SRC_DIR / ".env", SAND_ROOT / ".env"]:
    if env_file.exists():
        load_dotenv(env_file, override=False)





def build_and_benchmark(docs_dir: Path, data_dir: Path, limit: int = None, upload_to_s3: bool = False, batch_size: int = 64):
    from ingestion import load_documents_from_directory
    from chunking import chunk_documents
    from embeddings import Embedder
    from vector_search import VectorStore
    from s3_storage import S3RAGStorage

    print("=" * 65)
    print("ENGINEERING KNOWLEDGE RAG: VECTOR INDEX BUILDER")
    print("=" * 65)
    print(f"Docs Directory: {docs_dir}")
    print(f"Data Output:    {data_dir}")
    print(f"Batch Size:     {batch_size}")
    if limit:
        print(f"Document Limit: {limit} documents")
    print("-" * 65)

    start_total = time.time()

    # 1. Load documents
    t0 = time.time()
    all_docs = load_documents_from_directory(str(docs_dir))
    if limit and limit < len(all_docs):
        # Sort to keep deterministic selection (decisions, runbooks, then cloud arch and k8s)
        all_docs.sort(key=lambda d: d["source"])
        docs = all_docs[:limit]
    else:
        docs = all_docs
    t_load = time.time() - t0
    print(f"[1/4] Loaded {len(docs)} documents in {t_load:.2f}s (out of {len(all_docs)} total)")

    # 2. Chunk documents
    t0 = time.time()
    chunks = chunk_documents(docs)
    t_chunk = time.time() - t0
    print(f"[2/4] Generated {len(chunks)} chunks in {t_chunk:.2f}s")

    # 3. Compute Embeddings
    print(f"[3/4] Computing embeddings for {len(chunks)} chunks using all-MiniLM-L6-v2...")
    t0 = time.time()
    embedder = Embedder()
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embedder.embed(texts, batch_size=batch_size, show_progress_bar=True)
    t_embed = time.time() - t0
    embed_rate = len(chunks) / t_embed if t_embed > 0 else 0
    print(f"      Completed embeddings in {t_embed:.2f}s ({embed_rate:.1f} chunks/sec)")

    # 4. Build and Save FAISS Index
    print("[4/4] Building FAISS Vector Index and writing to disk...")
    t0 = time.time()
    data_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_dir / "index.faiss"
    chunks_file = data_dir / "chunks.json"

    vector_store = VectorStore(embeddings)
    vector_store.save(index_file)

    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    t_save = time.time() - t0

    index_size_mb = index_file.stat().st_size / (1024 * 1024)
    chunks_size_mb = chunks_file.stat().st_size / (1024 * 1024)
    total_time = time.time() - start_total

    print("-" * 65)
    print("BUILD COMPLETE SUMMARY:")
    print(f"  Total Documents:    {len(docs):,}")
    print(f"  Total Chunks:       {len(chunks):,}")
    print(f"  FAISS Index Size:   {index_size_mb:.2f} MB")
    print(f"  Chunks JSON Size:   {chunks_size_mb:.2f} MB")
    print(f"  Total Build Time:   {total_time:.2f}s")
    print("-" * 65)

    # 5. Quick Latency Benchmark
    print("LATENCY BENCHMARK (FAISS in-memory search):")
    test_queries = [
        "microservice architecture resiliency circuit breaker",
        "kubernetes pod memory limit OOM troubleshooting",
        "architecture decision record database sharding pattern",
    ]
    for q in test_queries:
        t_bench = time.time()
        q_emb = embedder.embed_query(q)
        scores, ids = vector_store.search(q_emb, top_k=5)
        dt_ms = (time.time() - t_bench) * 1000
        print(f"  Query: '{q[:40]}...' -> Search Time: {dt_ms:.2f} ms (Top match score: {scores[0]:.4f})")
    print("-" * 65)

    # 6. Upload to S3 if requested
    if upload_to_s3:
        s3 = S3RAGStorage()
        if s3.is_enabled:
            print(f"Uploading built assets to AWS S3 (s3://{s3.bucket_name}/{s3.prefix})...")
            ok = s3.upload_assets(data_dir)
            if ok:
                print("[SUCCESS] Vector index and chunks uploaded to AWS S3!")
            else:
                print("[FAILED] Failed to upload assets to S3.")
        else:
            print("[NOTICE] S3 upload skipped: RAG_S3_BUCKET is not set in .env.")


def main():
    parser = argparse.ArgumentParser(description="Build and benchmark FAISS vector index")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to index (e.g. 500)")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size (default 64)")
    parser.add_argument("--upload", action="store_true", help="Automatically upload built index to AWS S3")
    args = parser.parse_args()

    docs_dir = SAND_ROOT / "docs"
    data_dir = SAND_ROOT / "data"

    build_and_benchmark(
        docs_dir=docs_dir,
        data_dir=data_dir,
        limit=args.limit,
        upload_to_s3=args.upload,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()
