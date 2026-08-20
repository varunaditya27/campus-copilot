from functools import lru_cache

from groq import Groq

from app.core.config import GROQ_API_KEY


@lru_cache
def get_groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)
