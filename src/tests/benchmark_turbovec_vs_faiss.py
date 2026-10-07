"""Turbovec (Google TurboQuant) vs. FAISS Comprehensive Benchmark

Evaluates and compares:
1. Index file size and memory compression ratio
2. Index build and write latency across 36,369 real vectors
3. Query search latency percentiles (P50, P90, P95, P99, Mean)
4. Query Throughput (Queries Per Second - QPS)
5. Recall@10 accuracy vs. exact unquantized FAISS IndexFlatIP
"""

import os
import sys
import time
import json
from pathlib import Path
import numpy as np

SAND_ROOT = Path(__file__).resolve().parents[2]
DATA_S3 = SAND_ROOT / "data_s3"
FAISS_PATH = DATA_S3 / "index.faiss"

import faiss
import turbovec


def main():
    print("=" * 70)
    print("  TURBOVEC (GOOGLE TURBOQUANT) VS. FAISS 36,369 VECTOR BENCHMARK")
    print("=" * 70)

    if not FAISS_PATH.exists():
        print(f"Error: {FAISS_PATH} not found. Please ensure data_s3/index.faiss exists.")
        return

    # 1. Load original FAISS index and reconstruct all vectors
    print("\n[Step 1] Loading base FAISS index and extracting real vectors...")
    t0 = time.perf_counter()
    faiss_idx = faiss.read_index(str(FAISS_PATH))
    num_vectors = faiss_idx.ntotal
    dim = faiss_idx.d
    faiss_load_ms = (time.perf_counter() - t0) * 1000

    print(f" - FAISS index loaded in {faiss_load_ms:.2f}ms")
    print(f" - Total Vectors: {num_vectors:,} | Dimension: {dim}")

    t0 = time.perf_counter()
    vectors = faiss_idx.reconstruct_n(0, num_vectors)
    reconstruct_ms = (time.perf_counter() - t0) * 1000
    print(f" - Reconstructed {num_vectors:,} float32 vectors in {reconstruct_ms:.2f}ms")

    # 2. Benchmark Configurations
    configs = [
        {"name": "FAISS (FlatIP - float32)", "type": "faiss", "bits": 32},
        {"name": "TurboVec (4-bit TurboQuant)", "type": "turbovec", "bits": 4},
        {"name": "TurboVec (3-bit TurboQuant)", "type": "turbovec", "bits": 3},
        {"name": "TurboVec (2-bit TurboQuant)", "type": "turbovec", "bits": 2},
    ]

    # Generate 100 realistic normalized query vectors
    np.random.seed(42)
    # Mix 50 queries from existing vectors (realistic in-corpus) + 50 random normalized queries
    sample_indices = np.random.choice(num_vectors, 50, replace=False)
    in_corpus_queries = vectors[sample_indices] + np.random.normal(0, 0.05, (50, dim)).astype(np.float32)
    faiss.normalize_L2(in_corpus_queries)

    random_queries = np.random.randn(50, dim).astype(np.float32)
    faiss.normalize_L2(random_queries)

    test_queries = np.vstack([in_corpus_queries, random_queries])
    print(f" - Generated {len(test_queries)} benchmark queries.")

    # 3. Ground truth top-10 from FAISS exact search
    print("\n[Step 2] Computing exact Ground-Truth Top-10 neighbors via FAISS...")
    ground_truth_indices = []
    faiss_latencies = []
    for i in range(len(test_queries)):
        q = test_queries[i:i+1]
        t_start = time.perf_counter()
        scores, idxs = faiss_idx.search(q, 10)
        faiss_latencies.append((time.perf_counter() - t_start) * 1000)
        ground_truth_indices.append(set(idxs[0]))

    faiss_file_size = os.path.getsize(FAISS_PATH) / (1024 * 1024)

    results = []

    # Record FAISS metrics
    results.append({
        "name": "FAISS (FlatIP - float32)",
        "bit_width": 32,
        "build_time_sec": 0.0,
        "file_size_mb": round(faiss_file_size, 2),
        "compression_ratio": "1.0x (Baseline)",
        "mean_latency_ms": round(float(np.mean(faiss_latencies)), 3),
        "p50_latency_ms": round(float(np.percentile(faiss_latencies, 50)), 3),
        "p90_latency_ms": round(float(np.percentile(faiss_latencies, 90)), 3),
        "p95_latency_ms": round(float(np.percentile(faiss_latencies, 95)), 3),
        "p99_latency_ms": round(float(np.percentile(faiss_latencies, 99)), 3),
        "qps": round(1000.0 / float(np.mean(faiss_latencies)), 1),
        "recall_at_10": 100.0,
    })

    # 4. Benchmark each TurboVec configuration
    for cfg in configs[1:]:
        bit_w = cfg["bits"]
        name = cfg["name"]
        print(f"\n[Benchmarking] {name}...")

        # Build index
        t0 = time.perf_counter()
        tq_idx = turbovec.TurboQuantIndex(dim=dim, bit_width=bit_w)
        tq_idx.add(vectors)
        build_sec = time.perf_counter() - t0
        print(f"  -> Built {bit_w}-bit index in {build_sec:.2f}s")

        # Save to disk to measure size
        tq_file = DATA_S3 / f"index_turbovec_{bit_w}bit.tq"
        tq_idx.write(str(tq_file))
        tq_size_mb = os.path.getsize(tq_file) / (1024 * 1024)
        compression = round(faiss_file_size / tq_size_mb, 2)
        print(f"  -> File size: {tq_size_mb:.2f} MB ({compression}x smaller than FAISS!)")

        # Search benchmark & Recall calculation
        latencies = []
        overlaps = []
        for i in range(len(test_queries)):
            q = test_queries[i:i+1]
            t_start = time.perf_counter()
            scores, idxs = tq_idx.search(q, 10)
            lat = (time.perf_counter() - t_start) * 1000
            latencies.append(lat)

            # Compute Recall@10 against FAISS ground truth
            retrieved_set = set(idxs[0])
            overlap = len(retrieved_set.intersection(ground_truth_indices[i])) / 10.0
            overlaps.append(overlap)

        mean_lat = float(np.mean(latencies))
        p50 = float(np.percentile(latencies, 50))
        p90 = float(np.percentile(latencies, 90))
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
        recall = float(np.mean(overlaps)) * 100.0
        qps = 1000.0 / mean_lat

        print(f"  -> Latency: P50={p50:.3f}ms | P90={p90:.3f}ms | P99={p99:.3f}ms | Mean={mean_lat:.3f}ms")
        print(f"  -> Recall@10 vs Exact Search: {recall:.1f}%")
        print(f"  -> Throughput: {qps:.1f} QPS")

        results.append({
            "name": name,
            "bit_width": bit_w,
            "build_time_sec": round(build_sec, 2),
            "file_size_mb": round(tq_size_mb, 2),
            "compression_ratio": f"{compression}x",
            "mean_latency_ms": round(mean_lat, 3),
            "p50_latency_ms": round(p50, 3),
            "p90_latency_ms": round(p90, 3),
            "p95_latency_ms": round(p95, 3),
            "p99_latency_ms": round(p99, 3),
            "qps": round(qps, 1),
            "recall_at_10": round(recall, 1),
        })

    # Save results to JSON
    out_json = SAND_ROOT / "docs" / "turbovec_benchmark_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print markdown table
    print("\n" + "=" * 80)
    print("  FINAL COMPARATIVE BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    header = "| Index Engine | Bits | Size (MB) | Compression | P50 Latency | P99 Latency | QPS | Recall@10 |"
    sep = "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    print(header)
    print(sep)
    for r in results:
        line = f"| **{r['name']}** | {r['bit_width']} | **{r['file_size_mb']} MB** | **{r['compression_ratio']}** | **{r['p50_latency_ms']} ms** | **{r['p99_latency_ms']} ms** | **{r['qps']}** | **{r['recall_at_10']}%** |"
        print(line)
    print("=" * 80)


if __name__ == "__main__":
    main()
