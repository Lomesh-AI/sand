from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class Embedder:

    def __init__(self, model_name: str = MODEL_NAME):
        import torch
        # Cap CPU threads on small instances to prevent thread pool memory bloat
        try:
            if torch.get_num_threads() > 2:
                torch.set_num_threads(2)
        except Exception:
            pass

        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            self.model = SentenceTransformer(model_name)
        
        if hasattr(self.model, "get_embedding_dimension"):
            self.dimension = self.model.get_embedding_dimension()
        else:
            self.dimension = self.model.get_sentence_embedding_dimension()

    def embed(self, text, batch_size: int = 32, show_progress_bar: bool = False):
        import torch
        with torch.inference_mode():
            return self.model.encode(
                text, 
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True,
            )
    
    def embed_query(self, query: str):
        import torch
        with torch.inference_mode():
            return self.model.encode(
                query, 
                normalize_embeddings=True,
                convert_to_numpy=True,
            )