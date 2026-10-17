"""Monitors AWS RDS instance creation and updates .env once ready."""

import os
import sys
import time
from pathlib import Path
import boto3
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SRC_DIR / ".env")
load_dotenv(SRC_DIR.parent / ".env")

REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
DB_IDENTIFIER = "sand-postgres-db"


def wait_and_update_env():
    rds = boto3.client(
        "rds",
        region_name=REGION,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )

    print(f"[AWS] Waiting for RDS instance '{DB_IDENTIFIER}' to become available...", flush=True)

    start_time = time.time()
    while True:
        try:
            res = rds.describe_db_instances(DBInstanceIdentifier=DB_IDENTIFIER)
            instance = res["DBInstances"][0]
            status = instance["DBInstanceStatus"]
            endpoint = instance.get("Endpoint", {}).get("Address")

            elapsed = int(time.time() - start_time)
            print(f"[AWS] Elapsed: {elapsed}s | Status: {status} | Endpoint: {endpoint or 'None'}", flush=True)

            if status == "available" and endpoint:
                print(f"\n[AWS] RDS PostgreSQL is READY at: {endpoint}:5432", flush=True)

                # Update .env
                env_paths = [SRC_DIR / ".env", SRC_DIR.parent / ".env"]
                for p in env_paths:
                    if p.exists():
                        content = p.read_text(encoding="utf-8")
                        if "POSTGRES_HOST=" in content:
                            import re
                            content = re.sub(r"POSTGRES_HOST=.*", f"POSTGRES_HOST={endpoint}", content)
                        else:
                            content += f"\nPOSTGRES_HOST={endpoint}\n"
                        p.write_text(content, encoding="utf-8")
                        print(f"[AWS] Updated {p} with POSTGRES_HOST={endpoint}", flush=True)

                return endpoint

        except Exception as e:
            print(f"[AWS] Poll warning: {e}", flush=True)

        time.sleep(15)


if __name__ == "__main__":
    wait_and_update_env()
