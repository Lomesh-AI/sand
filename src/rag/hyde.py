"""Hypothetical Document Embeddings (HyDE) module.

Generates concise hypothetical technical documentation passages to bridge the semantic
gap between brief user queries and detailed technical documentation chunks.

Guards applied:
1. Skip for ADRs, specific file paths, and exact title lookups to prevent hallucinated specs.
2. Short, bounded generation (max 150 tokens) for low latency.
3. Fail-safe: Always falls back to original query embedding if API fails or times out.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from src/ or project root
SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SRC_DIR.parent
for env_file in [SRC_DIR / ".env", PROJECT_DIR / ".env"]:
    if env_file.exists():
        load_dotenv(env_file, override=False)


class HyDEGenerator:
    def __init__(self, model: str = "openai/gpt-oss-20b"):
        self.model = model
        self.client = None
        api_key = (
            os.environ.get("XAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_ADMIN_KEY")
        )
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=10.0,
            )

    def generate_hypothetical_document(self, query: str) -> Optional[str]:
        """
        Generate a concise hypothetical technical documentation passage for a query.
        Returns None if skipped or if generation fails.
        """
        if not self.client:
            return None

        clean_q = query.strip()
        lower_q = clean_q.lower()

        # Guardrail 1: Skip exact lookups, filenames, and ADR references
        if any(term in lower_q for term in ["adr-", "adr ", "decision record", ".md", ".json", "list_"]):
            return None

        # Guardrail 2: Skip very short queries
        if len(clean_q) < 5:
            return None

        system_prompt = (
            "You are a technical documentation assistant. Given a software engineering or architecture query, "
            "write a short, realistic 2-3 sentence excerpt from an official architecture guide, runbook, or engineering doc "
            "that answers the query. Use precise domain terminology, technical concepts, and standard industry practices. "
            "Output ONLY the passage text without any conversational filler or introductions."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {clean_q}"},
                ],
                max_completion_tokens=400,
                temperature=0.1,
            )
            passage = response.choices[0].message.content
            if passage and len(passage.strip()) > 20:
                return passage.strip()
        except Exception as e:
            # Graceful fallback: never block or crash RAG retrieval
            print(f"[HyDE] Skipped due to: {e}", flush=True)
            return None

        return None
