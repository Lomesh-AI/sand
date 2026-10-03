import os
import sys
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class S3RAGStorage:
    """
    Manages synchronization of RAG vector index (index.faiss)
    and chunk metadata (chunks.json) with AWS S3.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: str = "rag",
        region: Optional[str] = None,
    ):
        self.bucket_name = (
            bucket_name
            or os.environ.get("RAG_S3_BUCKET")
            or os.environ.get("AWS_S3_BUCKET")
            or ""
        ).strip()
        self.prefix = (
            prefix
            or os.environ.get("RAG_S3_PREFIX")
            or "rag"
        ).strip().strip("/")
        self.region = (
            region
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self._s3_client = None

    @property
    def is_enabled(self) -> bool:
        """Returns True if boto3 is installed and an S3 bucket is specified."""
        return bool(BOTO3_AVAILABLE and self.bucket_name)

    def get_client(self):
        """Lazily initialize boto3 S3 client using IAM role or standard credentials."""
        if not self.is_enabled:
            return None
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.region)
        return self._s3_client

    def download_assets(self, target_dir: Path) -> bool:
        """
        Download index.faiss and chunks.json from S3 into target_dir.
        Returns True if both files were successfully retrieved.
        """
        if not self.is_enabled:
            return False

        client = self.get_client()
        if not client:
            return False

        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        files_to_download = ["index.faiss", "chunks.json"]
        success_count = 0

        for filename in files_to_download:
            s3_key = f"{self.prefix}/{filename}" if self.prefix else filename
            local_path = target_dir / filename

            try:
                print(f"[S3RAGStorage] Downloading s3://{self.bucket_name}/{s3_key} -> {local_path}...", file=sys.stderr, flush=True)
                client.download_file(self.bucket_name, s3_key, str(local_path))
                if local_path.exists() and local_path.stat().st_size > 0:
                    success_count += 1
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "Unknown")
                print(f"[S3RAGStorage] S3 download skipped for {s3_key} (Error {code})", file=sys.stderr, flush=True)
            except NoCredentialsError:
                print("[S3RAGStorage] AWS credentials not found. Falling back to local RAG assets.", file=sys.stderr, flush=True)
                return False
            except Exception as exc:
                print(f"[S3RAGStorage] Failed to download {s3_key}: {exc}", file=sys.stderr, flush=True)

        return success_count == len(files_to_download)

    def upload_assets(self, source_dir: Path) -> bool:
        """
        Upload local index.faiss and chunks.json from source_dir to S3.
        Returns True if both files were successfully uploaded.
        """
        if not self.is_enabled:
            print("[S3RAGStorage] S3 upload skipped: RAG_S3_BUCKET is not set.", file=sys.stderr, flush=True)
            return False

        client = self.get_client()
        if not client:
            return False

        source_dir = Path(source_dir)
        files_to_upload = ["index.faiss", "chunks.json"]
        success_count = 0

        for filename in files_to_upload:
            local_path = source_dir / filename
            if not local_path.exists():
                print(f"[S3RAGStorage] Local file not found for upload: {local_path}", file=sys.stderr, flush=True)
                continue

            s3_key = f"{self.prefix}/{filename}" if self.prefix else filename
            try:
                print(f"[S3RAGStorage] Uploading {local_path} -> s3://{self.bucket_name}/{s3_key}...", flush=True)
                client.upload_file(str(local_path), self.bucket_name, s3_key)
                print(f"[S3RAGStorage] Successfully uploaded {filename} to S3.", flush=True)
                success_count += 1
            except Exception as exc:
                print(f"[S3RAGStorage] Failed to upload {filename} to S3: {exc}", file=sys.stderr, flush=True)

        return success_count == len(files_to_upload)
