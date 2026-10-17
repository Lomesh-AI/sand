"""PostgreSQL Memory and Persistence Module for Multi-Agent System.

Provides:
1. Production LangGraph checkpointing via AsyncPostgresSaver (persisting graph state).
2. Human-readable conversation store (storing past turns, tool calls, and queries).
3. Graceful fallback to InMemorySaver when database is offline or not configured.
"""

import os
import sys
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parents[1]
for env_f in [SRC_DIR / ".env", SRC_DIR.parent / ".env"]:
    if env_f.exists():
        load_dotenv(env_f, override=False)

logger = logging.getLogger("agent.memory")

if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

_pool = None
_checkpointer = None


def get_postgres_conninfo() -> Optional[str]:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "sand_conversations")
    user = os.getenv("POSTGRES_USER", "postgres_admin")
    password = os.getenv("POSTGRES_PASSWORD")

    if not host or not password:
        return None

    return f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=prefer"


async def get_postgres_pool():
    """Get or create async connection pool."""
    global _pool
    conninfo = get_postgres_conninfo()
    if not conninfo:
        return None

    if _pool is None:
        try:
            from psycopg_pool import AsyncConnectionPool

            _pool = AsyncConnectionPool(
                conninfo=conninfo,
                min_size=1,
                max_size=10,
                open=False,
            )
            await _pool.open()
            logger.info("Connected to PostgreSQL Connection Pool on AWS RDS.")
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL: {e}")
            _pool = None

    return _pool


async def init_postgres_tables():
    """Initialize conversation history and audit tables in PostgreSQL."""
    pool = await get_postgres_pool()
    if not pool:
        return False

    schema_sql = """
    CREATE TABLE IF NOT EXISTS agent_conversations (
        id SERIAL PRIMARY KEY,
        thread_id VARCHAR(128) NOT NULL,
        turn_number INT NOT NULL DEFAULT 1,
        user_query TEXT NOT NULL,
        final_answer TEXT,
        visited_specialists TEXT[],
        tools_called TEXT[],
        latency_seconds FLOAT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_thread_id ON agent_conversations(thread_id);
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(schema_sql)
            await conn.commit()
        logger.info("Initialized 'agent_conversations' schema in PostgreSQL.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL schema: {e}")
        return False


async def record_conversation_turn(
    thread_id: str,
    user_query: str,
    final_answer: str,
    visited_specialists: Optional[List[str]] = None,
    tools_called: Optional[List[str]] = None,
    latency_seconds: Optional[float] = None,
) -> bool:
    """Save a completed conversation turn to PostgreSQL."""
    pool = await get_postgres_pool()
    if not pool:
        return False

    insert_sql = """
    INSERT INTO agent_conversations (
        thread_id, user_query, final_answer, visited_specialists, tools_called, latency_seconds
    ) VALUES (%s, %s, %s, %s, %s, %s);
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    insert_sql,
                    (
                        thread_id,
                        user_query,
                        final_answer,
                        visited_specialists or [],
                        tools_called or [],
                        latency_seconds or 0.0,
                    ),
                )
            await conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error recording conversation to PostgreSQL: {e}")
        return False


async def get_thread_history(thread_id: str) -> List[Dict[str, Any]]:
    """Retrieve all past conversation turns for a given thread_id."""
    pool = await get_postgres_pool()
    if not pool:
        return []

    query_sql = """
    SELECT user_query, final_answer, visited_specialists, tools_called, latency_seconds, created_at
    FROM agent_conversations
    WHERE thread_id = %s
    ORDER BY created_at ASC;
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query_sql, (thread_id,))
                rows = await cur.fetchall()
                return [
                    {
                        "user_query": r[0],
                        "final_answer": r[1],
                        "visited_specialists": r[2],
                        "tools_called": r[3],
                        "latency_seconds": r[4],
                        "created_at": r[5].isoformat() if r[5] else None,
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.error(f"Error fetching thread history: {e}")
        return []


async def list_past_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent conversation sessions."""
    pool = await get_postgres_pool()
    if not pool:
        return []

    query_sql = """
    SELECT thread_id, user_query, final_answer, created_at
    FROM agent_conversations
    ORDER BY created_at DESC
    LIMIT %s;
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query_sql, (limit,))
                rows = await cur.fetchall()
                return [
                    {
                        "thread_id": r[0],
                        "user_query": r[1],
                        "final_answer": (r[2][:120] + "...") if r[2] and len(r[2]) > 120 else r[2],
                        "created_at": r[3].isoformat() if r[3] else None,
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.error(f"Error listing past conversations: {e}")
        return []
