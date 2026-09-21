from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag"))
from pipeline import RAGPipeline


rag = RAGPipeline("docs")

results = rag.search("Why was RabbitMQ selected?")

for score, idx in results:
    chunk = rag.chunks[idx]
    print("\nSCORE:", score)
    print("SOURCE:", chunk["source"])
    print(chunk["text"][:500])