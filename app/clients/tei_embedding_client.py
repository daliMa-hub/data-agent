import requests
from typing import List
from langchain_core.embeddings import Embeddings

class TEIEmbeddings(Embeddings):
    """HuggingFace TEI 原生嵌入客户端"""
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url  # 例如 "http://localhost:8081/embed"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = requests.post(
            self.endpoint_url,
            json={"inputs": texts},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        # TEI 返回的格式通常是 List[List[float]]，直接返回
        return response.json()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]