from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query, chunks, candidates_indices, top_k=5):
        """Rerank the candidates based on their relevance to the query."""
        pairs = [(query, chunks[idx]["text"]) for idx in candidates_indices]
        scores = self.model.predict(pairs)
        ranked = sorted(
            [(float(score), idx) for idx, score in zip(candidates_indices, scores)],
            key=lambda x: x[0],
            reverse=True,
        )
        return ranked[:top_k]

    