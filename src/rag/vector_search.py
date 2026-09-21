import faiss
import numpy as np

class VectorStore:
    def __init__(self, embeddings):
        embeddings = np.asarray(embeddings, dtype=np.float32)
        dimensions = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimensions)
        self.index.add(embeddings)
    
    def search(self, query_embedding, top_k=5):
        query_embedding = np.asarray(
            [query_embedding],
            dtype="float32"
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        return scores[0], indices[0]