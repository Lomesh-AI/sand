import os
import sys
from pathlib import Path
import boto3
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SRC_DIR / ".env")
load_dotenv(SRC_DIR.parent / ".env")

region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

print(f"Checking AWS credentials for region: {region}...", flush=True)

try:
    ec2 = boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    default_vpc_id = vpcs["Vpcs"][0]["VpcId"] if vpcs["Vpcs"] else "None"
    print(f"Default VPC ID: {default_vpc_id}", flush=True)
except Exception as e:
    print(f"EC2 describe_vpcs notice: {e}", flush=True)

try:
    rds = boto3.client(
        "rds",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    res = rds.describe_db_engine_versions(Engine="postgres", DefaultOnly=True)
    versions = [v["EngineVersion"] for v in res.get("DBEngineVersions", [])]
    print(f"Default PostgreSQL Engine Version: {versions}", flush=True)
except Exception as e:
    print(f"RDS describe error: {e}", flush=True)
