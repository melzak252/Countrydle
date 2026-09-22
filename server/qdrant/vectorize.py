from typing import List
from openai import OpenAI


def get_embedding(text: str, model: str, *, request_timeout: float | None = None) -> List[float]:
    print(f"Generating embedding for text (length: {len(text)}) using model '{model}'...")
    client = OpenAI(timeout=request_timeout, max_retries=0) if request_timeout is not None else OpenAI()
    text = text.replace("\n", " ")
    embedding = client.embeddings.create(input=[text], model=model).data[0].embedding
    print("Embedding generated successfully.")
    return embedding


def get_bulk_embedding(texts: List[str], model: str) -> List[List[float]]:
    print(f"Generating bulk embeddings for {len(texts)} texts using model '{model}'...")
    client = OpenAI()
    texts = [text.replace("\n", " ") for text in texts]
    response = client.embeddings.create(input=texts, model=model)
    embeddings = [data.embedding for data in response.data]
    print(f"Successfully generated {len(embeddings)} bulk embeddings.")
    return embeddings
