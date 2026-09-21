from pathlib import Path 

def load_documents_from_directory(directory_path: str):
    """
    Load documents from a specified directory.

    Returns:
        list: A list of loaded documents.
    """
    documents = []
    for path in Path(directory_path).rglob('*.md'):
        text = path.read_text(encoding='utf-8')
        documents.append({
            'text': text,
            "source": str(path)
        })
    
    return documents

if __name__ == "__main__":
    docs = load_documents_from_directory("docs")
    print(f"Loaded {len(docs)} documents from the 'docs' directory.")

    for doc in docs:
        print(f"Source: {doc['source']}")
        print("-" * 40)
    