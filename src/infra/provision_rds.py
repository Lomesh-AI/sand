"""AWS RDS PostgreSQL Auto-Provisioning Script.

Provisions a Free-Tier eligible db.t4g.micro PostgreSQL instance
on AWS RDS in us-east-1 to store agent conversation history.
"""

import os
import sys
import time
import secrets
import string
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
DB_NAME = "sand_conversations"
DB_USER = "postgres_admin"
SG_NAME = "sand-postgres-sg"


def generate_secure_password(length=20):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_or_create_security_group(ec2_client, vpc_id: str) -> str:
    try:
        res = ec2_client.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [SG_NAME]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )
        if res.get("SecurityGroups"):
            sg_id = res["SecurityGroups"][0]["GroupId"]
            print(f"[AWS] Found existing Security Group: {sg_id} ({SG_NAME})", flush=True)
            return sg_id
    except Exception as e:
        print(f"[AWS] Check SG: {e}", flush=True)

    print(f"[AWS] Creating Security Group '{SG_NAME}' in VPC {vpc_id}...", flush=True)
    res = ec2_client.create_security_group(
        GroupName=SG_NAME,
        Description="Security Group for Sand Agent RDS PostgreSQL instance",
        VpcId=vpc_id,
    )
    sg_id = res["GroupId"]

    # Ingress rule for PostgreSQL port 5432
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 5432,
                    "ToPort": 5432,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "PostgreSQL access"}],
                }
            ],
        )
        print(f"[AWS] Inbound rule for Port 5432 authorized on {sg_id}.", flush=True)
    except Exception as e:
        print(f"[AWS] Ingress rule notice: {e}", flush=True)

    return sg_id


def provision_rds():
    if not ACCESS_KEY or not SECRET_KEY:
        print("[ERROR] AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found in .env!", flush=True)
        return

    ec2 = boto3.client(
        "ec2",
        region_name=REGION,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )
    rds = boto3.client(
        "rds",
        region_name=REGION,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )

    # 1. Get Default VPC
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not vpcs.get("Vpcs"):
        raise RuntimeError("No default VPC found in region " + REGION)
    default_vpc_id = vpcs["Vpcs"][0]["VpcId"]

    # 2. Setup Security Group
    sg_id = get_or_create_security_group(ec2, default_vpc_id)

    # 3. Check if DB instance exists
    try:
        dbs = rds.describe_db_instances(DBInstanceIdentifier=DB_IDENTIFIER)
        instance = dbs["DBInstances"][0]
        status = instance["DBInstanceStatus"]
        endpoint = instance.get("Endpoint", {}).get("Address", "Provisioning...")
        print(f"[AWS] RDS instance '{DB_IDENTIFIER}' already exists (status: {status}, endpoint: {endpoint})", flush=True)
        return instance
    except rds.exceptions.DBInstanceNotFoundFault:
        pass

    # 4. Create DB Instance
    db_password = os.getenv("POSTGRES_PASSWORD") or generate_secure_password()

    print(f"\n[AWS] Launching new RDS PostgreSQL instance '{DB_IDENTIFIER}' (db.t4g.micro, gp2 20GB)...", flush=True)
    create_res = rds.create_db_instance(
        DBInstanceIdentifier=DB_IDENTIFIER,
        AllocatedStorage=20,
        DBInstanceClass="db.t4g.micro",
        Engine="postgres",
        EngineVersion="15.16",
        MasterUsername=DB_USER,
        MasterUserPassword=db_password,
        DBName=DB_NAME,
        VpcSecurityGroupIds=[sg_id],
        PubliclyAccessible=True,
        BackupRetentionPeriod=0,
        StorageType="gp2",
        DeletionProtection=False,
        AutoMinorVersionUpgrade=True,
    )

    print(f"[AWS] RDS creation initiated successfully! Status: {create_res['DBInstance']['DBInstanceStatus']}", flush=True)

    # Append credentials to .env if not present
    env_file = SRC_DIR / ".env"
    with open(env_file, "a", encoding="utf-8") as f:
        f.write(f"\n# AWS RDS PostgreSQL Configuration\n")
        f.write(f"POSTGRES_DB={DB_NAME}\n")
        f.write(f"POSTGRES_USER={DB_USER}\n")
        f.write(f"POSTGRES_PASSWORD={db_password}\n")
        f.write(f"POSTGRES_PORT=5432\n")

    root_env = SRC_DIR.parent / ".env"
    if root_env.exists():
        with open(root_env, "a", encoding="utf-8") as f:
            f.write(f"\n# AWS RDS PostgreSQL Configuration\n")
            f.write(f"POSTGRES_DB={DB_NAME}\n")
            f.write(f"POSTGRES_USER={DB_USER}\n")
            f.write(f"POSTGRES_PASSWORD={db_password}\n")
            f.write(f"POSTGRES_PORT=5432\n")

    print(f"[AWS] Credentials recorded to .env. Instance will be available in ~5-8 minutes.", flush=True)
    return create_res["DBInstance"]


if __name__ == "__main__":
    provision_rds()
