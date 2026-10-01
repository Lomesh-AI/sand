from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        try:
            self.model = CrossEncoder(model_name, local_files_only=True, device="cpu")
        except Exception:
            self.model = CrossEncoder(model_name, device="cpu")

    def rerank(self, query, chunks, candidates_indices, top_k=5):
        """Rerank the candidates based on their relevance to the query."""
        pairs = [(query, chunks[idx]["text"]) for idx in candidates_indices]
        scores = self.model.predict(
            pairs,
            show_progress_bar=False,
        )
        ranked = sorted(
            [(float(score), idx) for idx, score in zip(candidates_indices, scores)],
            key=lambda x: x[0],
            reverse=True,
        )
        return ranked[:top_k]

    