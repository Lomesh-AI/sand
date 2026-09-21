from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class Embedder:

    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str):
        return self.model.encode(
            text, 
            normalize_embeddings=True
        )
    
    def embed_query(self, query: str):
        return self.model.encode(
            query, 
            normalize_embeddings=True
        )