from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


def get_embedding_function():
    # Chroma's bundled all-MiniLM-L6-v2 (ONNX, runs locally, no API key,
    # no torch dependency). Fine for a small, curated corpus like ours.
    return DefaultEmbeddingFunction()
