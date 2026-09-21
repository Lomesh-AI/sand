from rank_bm25 import BM25Okapi

class BM25Store:
    def __init__(self, chunks):
        self.chunks = chunks
        tokenized = [
            chunk["text"].lower().split() for chunk in chunks
        ]
        self.bm25 = BM25Okapi(tokenized)

    def search(self, query, top_k=5):
        query_tokens = query.lower().split()
        scores = self.bm25.get_scores(query_tokens)
        top_indices = scores.argsort()[-top_k:][::-1]

        return [(scores[idx], idx) for idx in top_indices]
