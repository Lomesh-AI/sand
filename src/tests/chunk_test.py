from ingestion import load_documents_from_directory
from chunking import chunk_documents

docs = load_documents_from_directory("docs")
chunks = chunk_documents(docs, chunk_size=1000, chunk_overlap=200)

print(f"Loaded {len(docs)} documents from the 'docs' directory.")
print(f"Chunked into {len(chunks)} chunks.")

for chunk in chunks:
    print(f"Source: {chunk['source']}, Chunk ID: {chunk['chunk_id']}, Text: {chunk['text'][:50]}...")
    print("-" * 40)