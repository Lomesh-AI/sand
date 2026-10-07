import turbovec
import numpy as np
from pathlib import Path
from typing import Optional


class TurboVecStore:
    """
    VectorStore adapter powered by Google Research's TurboQuant algorithm via Turbovec.
    Provides extreme RAM compression (7.4x smaller) and ultra-fast quantized SIMD search.
    """

    def __init__(
        self,
        embeddings: Optional[np.ndarray] = None,
        index: Optional[turbovec.TurboQuantIndex] = None,
        dimension: int = 384,
        bit_width: int = 4,
    ):
        self.bit_width = bit_width
        self.dimension = dimension

        if index is not None:
            self.index = index
            self.dimension = index.dim
            self.bit_width = index.bit_width
        elif embeddings is not None:
            embeddings = np.asarray(embeddings, dtype=np.float32)
            self.dimension = embeddings.shape[1]
            self.index = turbovec.TurboQuantIndex(dim=self.dimension, bit_width=self.bit_width)
            self.index.add(embeddings)
        else:
            self.index = turbovec.TurboQuantIndex(dim=self.dimension, bit_width=self.bit_width)

    def add(self, embeddings: np.ndarray):
        """Incrementally add a batch of embeddings to the TurboQuant index."""
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = np.expand_dims(embeddings, axis=0)
        self.index.add(embeddings)

    def save(self, file_path: str | Path):
        """Persist the quantized index to disk."""
        self.index.write(str(file_path))

    @classmethod
    def load(cls, file_path: str | Path) -> "TurboVecStore":
        """Load a persisted TurboQuant index from disk."""
        index = turbovec.TurboQuantIndex.load(str(file_path))
        return cls(index=index)

    def search(self, query_embedding: np.ndarray, top_k: int = 5, k: Optional[int] = None):
        """Search nearest neighbors returning (scores, indices) matching VectorStore interface."""
        if k is not None:
            top_k = k

        # Check vector count
        n_vecs = getattr(self.index, "n_vectors", len(self.index))
        if n_vecs == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.int64)

        top_k = min(top_k, n_vecs)

        query_embedding = np.asarray(query_embedding, dtype=np.float32)
        if query_embedding.ndim == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)

        scores, indices = self.index.search(query_embedding, top_k)
        return scores[0], indices[0]
