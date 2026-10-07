#!/usr/bin/env python3
"""
CLI utility to manage and synchronize RAG vector indexes (index.faiss)
and chunk metadata (chunks.json) with AWS S3.

Usage:
    python src/rag/sync_s3.py --status
    python src/rag/sync_s3.py --upload
    python src/rag/sync_s3.py --download
    python src/rag/sync_s3.py --build-and-upload
"""

import argparse
import os
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

from s3_storage import S3RAGStorage


def check_status(s3: S3RAGStorage, cache_dir: Path):
    print("=" * 60)
    print("AWS S3 RAG STORAGE STATUS")
    print("=" * 60)
    print(f"Bucket Name:  {s3.bucket_name or '(Not configured - set RAG_S3_BUCKET in .env)'}")
    print(f"Prefix:       {s3.prefix}")
    print(f"AWS Region:   {s3.region}")
    print(f"S3 Enabled:   {'YES' if s3.is_enabled else 'NO'}")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_KEY")
    print("AWS Credentials:")
    print(f"  AWS_ACCESS_KEY_ID:     {'SET (' + access_key[:4] + '...)' if access_key else 'NOT SET (will attempt IAM instance role)'}")
    print(f"  AWS_SECRET_ACCESS_KEY: {'SET' if secret_key else 'NOT SET'}")
    print("-" * 60)

    # Local Files
    index_file = cache_dir / "index.faiss"
    chunks_file = cache_dir / "chunks.json"
    print("Local Assets in", cache_dir)
    print(f"  index.faiss: {'EXISTS (' + str(index_file.stat().st_size) + ' bytes)' if index_file.exists() else 'MISSING'}")
    print(f"  chunks.json: {'EXISTS (' + str(chunks_file.stat().st_size) + ' bytes)' if chunks_file.exists() else 'MISSING'}")
    for tq_file in cache_dir.glob("index_turbovec_*.tq"):
        print(f"  {tq_file.name}: EXISTS ({tq_file.stat().st_size} bytes)")
    manifest_file = cache_dir / "turbovec_manifest.json"
    if manifest_file.exists():
        print(f"  turbovec_manifest.json: EXISTS ({manifest_file.stat().st_size} bytes)")
    print("-" * 60)

    # Remote S3 Files
    if not s3.is_enabled:
        print("[!] S3 is not enabled. Set RAG_S3_BUCKET in your .env to connect to AWS S3.")
        return

    client = s3.get_client()
    if not client:
        print("[!] Could not initialize boto3 S3 client.")
        return

    print(f"Checking objects in s3://{s3.bucket_name}/{s3.prefix}/...")
    try:
        response = client.list_objects_v2(Bucket=s3.bucket_name, Prefix=s3.prefix)
        contents = response.get("Contents", [])
        if not contents:
            print("  (Bucket is accessible, but no files found under prefix)")
        else:
            for item in contents:
                print(f"  - {item['Key']} ({item['Size']} bytes, modified {item['LastModified']})")
    except Exception as exc:
        print(f"[!] S3 connection error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Synchronize RAG vector store with AWS S3")
    parser.add_argument("--status", action="store_true", help="Check local and S3 storage status")
    parser.add_argument("--upload", action="store_true", help="Upload local index.faiss and chunks.json to S3")
    parser.add_argument("--download", action="store_true", help="Download index.faiss and chunks.json from S3")
    parser.add_argument("--upload-turbovec", action="store_true", help="Upload local TurboVec (.tq) indices to S3")
    parser.add_argument("--download-turbovec", action="store_true", help="Download TurboVec (.tq) index from S3")
    parser.add_argument("--bit-width", type=int, default=4, choices=[2, 3, 4], help="TurboVec bit width (default: 4)")
    parser.add_argument("--dir", type=str, default=None, help="Local directory to sync (default: data or data_s3)")
    parser.add_argument("--build-and-upload", action="store_true", help="Build vector store from docs and upload to S3")
    parser.add_argument("--bucket", type=str, default=None, help="Override target S3 bucket name")
    parser.add_argument("--prefix", type=str, default="rag", help="S3 prefix (folder)")

    args = parser.parse_args()

    default_dir = (SAND_ROOT / args.dir) if args.dir else (SAND_ROOT / "data_s3" if (SAND_ROOT / "data_s3").exists() else SAND_ROOT / "data")
    cache_dir = default_dir
    s3 = S3RAGStorage(bucket_name=args.bucket, prefix=args.prefix)

    if args.upload:
        if not s3.is_enabled:
            print("[ERROR] Please provide --bucket or set RAG_S3_BUCKET in .env before uploading.")
            sys.exit(1)
        print(f"Uploading assets from {cache_dir} to s3://{s3.bucket_name}/{s3.prefix}...")
        ok = s3.upload_assets(cache_dir)
        if ok:
            print("[SUCCESS] All RAG assets uploaded to AWS S3 successfully!")
        else:
            print("[FAILED] Failed to upload some or all assets to AWS S3.")

    elif args.upload_turbovec:
        if not s3.is_enabled:
            print("[ERROR] Please provide --bucket or set RAG_S3_BUCKET in .env before uploading.")
            sys.exit(1)
        print(f"Uploading TurboVec assets from {cache_dir} to s3://{s3.bucket_name}/{s3.prefix}...")
        ok = s3.upload_turbovec_assets(cache_dir)
        if ok:
            print("[SUCCESS] TurboVec assets uploaded to AWS S3 successfully!")
        else:
            print("[FAILED] Failed to upload TurboVec assets to AWS S3.")

    elif args.download:
        if not s3.is_enabled:
            print("[ERROR] Please provide --bucket or set RAG_S3_BUCKET in .env before downloading.")
            sys.exit(1)
        print(f"Downloading assets from s3://{s3.bucket_name}/{s3.prefix} to {cache_dir}...")
        ok = s3.download_assets(cache_dir)
        if ok:
            print("[SUCCESS] All RAG assets downloaded from AWS S3 successfully!")
        else:
            print("[FAILED] Failed to download assets from AWS S3.")

    elif args.download_turbovec:
        if not s3.is_enabled:
            print("[ERROR] Please provide --bucket or set RAG_S3_BUCKET in .env before downloading.")
            sys.exit(1)
        print(f"Downloading TurboVec {args.bit_width}-bit assets from s3://{s3.bucket_name}/{s3.prefix} to {cache_dir}...")
        ok = s3.download_turbovec_assets(cache_dir, bit_width=args.bit_width)
        if ok:
            print("[SUCCESS] TurboVec assets downloaded from AWS S3 successfully!")
        else:
            print("[FAILED] Failed to download TurboVec assets from AWS S3.")

    elif args.build_and_upload:
        print("Rebuilding RAG pipeline from docs/...")
        from pipeline import RAGPipeline
        pipeline = RAGPipeline(cache_dir=cache_dir, s3_storage=s3)
        if s3.is_enabled:
            print(f"Uploading freshly built index to s3://{s3.bucket_name}/{s3.prefix}...")
            s3.upload_assets(cache_dir)
            print("[SUCCESS] Build and S3 upload complete!")
        else:
            print("[DONE] Local build complete (S3 upload skipped, RAG_S3_BUCKET not set).")

    else:
        # Default action: status
        check_status(s3, cache_dir)


if __name__ == "__main__":
    main()

