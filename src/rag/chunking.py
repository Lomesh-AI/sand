from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_documents(documents, chunk_size=1000, chunk_overlap=200):
    """
    Chunk documents into smaller pieces.

    Args:
        documents (list): A list of documents to be chunked.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.

    Returns:
        list: A list of chunked documents.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    chunks = []

    for doc in documents:
        texts = splitter.split_text(doc['text'])
        for i, text in enumerate(texts):
            chunks.append({
                "text":text, 
                "source": doc['source'],
                "chunk_id": i
            })
    
    return chunks