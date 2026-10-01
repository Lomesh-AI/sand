import faiss
import numpy as np

class VectorStore:
    def __init__(self, embeddings=None, index=None):
        if index is not None:
            self.index = index
        elif embeddings is not None:
            embeddings = np.asarray(embeddings, dtype=np.float32)
            dimensions = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimensions)
            self.index.add(embeddings)
        else:
            raise ValueError("Either embeddings or index must be provided")

    def save(self, file_path):
        faiss.write_index(self.index, str(file_path))

    @classmethod
    def load(cls, file_path):
        index = faiss.read_index(str(file_path))
        return cls(index=index)
    
    def search(self, query_embedding, top_k=5):
        top_k = min(top_k, self.index.ntotal)
        if top_k == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.int64)

        query_embedding = np.asarray(
            [query_embedding],
            dtype="float32"
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        return scores[0], indices[0]