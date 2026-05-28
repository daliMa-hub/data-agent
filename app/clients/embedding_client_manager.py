from typing import Optional
from langchain_openai import OpenAIEmbeddings
from app.clients.tei_embedding_client import TEIEmbeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import EmbeddingConfig, app_config

class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.client: Optional[HuggingFaceEndpointEmbeddings] = None
        self.config = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = TEIEmbeddings(self._get_url() + "/embed")
        # self.client = HuggingFaceEndpointEmbeddings(model=self._get_url())
        # self.client = OpenAIEmbeddings(
        #     model=self.config.model,
        #     openai_api_base=self._get_url() + "/v1",
        #     openai_api_key="not-needed"  # 本地服务不需要真密钥，但不能为空
        # )

embedding_client_manager = EmbeddingClientManager(app_config.embedding)