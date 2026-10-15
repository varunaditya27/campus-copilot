from functools import lru_cache

from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
from tokenizers import Tokenizer

# The embedding model reads at most this many tokens; anything longer is cut
# off, so text beyond it cannot influence semantic search.
EMBEDDING_WINDOW = 256


@lru_cache
def _tokenizer() -> Tokenizer:
    # Make sure the model files (which include the tokenizer) are downloaded.
    ONNXMiniLM_L6_V2()._download_model_if_not_exists()
    tokenizer = Tokenizer.from_file(str(ONNXMiniLM_L6_V2.DOWNLOAD_PATH / "onnx" / "tokenizer.json"))
    # Chroma's own use pads and truncates; counting needs the true length.
    tokenizer.no_padding()
    tokenizer.no_truncation()
    return tokenizer


def count_tokens(text: str) -> int:
    """How many tokens the embedding model sees in this text."""
    return len(_tokenizer().encode(text, add_special_tokens=False).ids)
