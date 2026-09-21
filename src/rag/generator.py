import os
from openai import OpenAI, OpenAIError


class Generator:
    def __init__(self, model="openai/gpt-oss-20b", api_key="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"):
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("XAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_ADMIN_KEY")
        )
        self.client = None

        if self.api_key:
            client = OpenAI(
                api_key=os.environ["XAI_API_KEY"],
                base_url="https://api.groq.com/openai/v1"
            )
            self.client = client

    def _fallback_generate(self, query, chunks):
        if not chunks:
            return "I don't have enough information in the knowledge base."

        relevant = []
        for chunk in chunks[:3]:
            text = (chunk.get("text") or "").strip()
            if text:
                relevant.append(
                    f"{chunk.get('source', 'unknown')} (chunk {chunk.get('chunk_id', 'n/a')}): {text[:300]}"
                )

        if not relevant:
            return "I don't have enough information in the knowledge base."

        context_summary = "\n".join(relevant)
        return (
            "I don't have a valid LLM API key in this environment, so I'm using the "
            "best available local context.\n\n"
            f"Question: {query}\n\n{context_summary}"
        )

    def generate(self, query, chunks):
        if self.client is None:
            return self._fallback_generate(query, chunks)

        context = "\n\n".join(
            f"[SOURCE: {chunk['source']}]\n{chunk['text']}"
            for chunk in chunks
        )

        prompt = f"""
                You are an engineering knowledge assistant.

                Answer the question using ONLY the provided context.

                If the context does not contain enough information, say:
                "I don't have enough information in the knowledge base."

                Cite the relevant source after each factual statement.

                Context:
                {context}

                Question:
                {query}
                """

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
            )
            return response.output_text
        except OpenAIError:
            self.client = None
            self.api_key = None
            return self._fallback_generate(query, chunks)
