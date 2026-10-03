from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class Embedder:

    def __init__(self, model_name: str = MODEL_NAME):
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            self.model = SentenceTransformer(model_name)

    def embed(self, text, batch_size: int = 64, show_progress_bar: bool = True):
        return self.model.encode(
            text, 
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress_bar,
        )
    
    def embed_query(self, query: str):
        return self.model.encode(
            query, 
            normalize_embeddings=True
        )