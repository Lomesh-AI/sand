import numpy as np

class HybridRetrieval:

    def __init__(self, vector_store, bm25_store, embedder, chunks):
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.embedder = embedder
        self.chunks = chunks

    def search(self, query_text, top_k=5, alpha=0.5, hypothetical_doc=None):
        top_k = min(top_k, len(self.chunks))
        if top_k == 0:
            return []
        
        # Dense semantic search: use hypothetical passage (HyDE) if provided, otherwise raw query
        dense_query = hypothetical_doc if hypothetical_doc else query_text
        query_embedding = self.embedder.embed_query(dense_query)
        semantic_scores, semantic_indices = self.vector_store.search(query_embedding, top_k=top_k)
        
        # Sparse keyword search: always use original user query to preserve exact keyword matching
        bm25_results = self.bm25_store.search(query_text, top_k=top_k)

        semantic = np.zeros(len(self.chunks))
        bm25 = np.zeros(len(self.chunks))

        for score, idx in zip(semantic_scores, semantic_indices):
            semantic[idx] = score
        
        for score, idx in bm25_results:
            bm25[idx] = score
        
        semantic = self._normalize_scores(semantic)
        bm25 = self._normalize_scores(bm25)

        hybrid = (
            alpha * semantic
            + (1 - alpha) * bm25
        )

        top_indices = hybrid.argsort()[-top_k:][::-1][:top_k]

        return [
            (hybrid[idx], idx)
            for idx in top_indices
        ]
    
    def _normalize_scores(self, scores):
        min_score = np.min(scores)
        max_score = np.max(scores)

        if max_score - min_score == 0:
            return np.zeros_like(scores)

        return (scores - min_score) / (max_score - min_score)
    

