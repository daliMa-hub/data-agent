import uuid
from dataclasses import asdict
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.core.log import logger
from app.conf.meta_config import MetaConfig
from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 value_es_repository: ValueEsRepository,
                 metric_qdrant_repository: MetricQdrantRepository):

        self.meta_mysql_repository: MetaMySQLRepository = meta_mysql_repository
        self.dw_mysql_repository: DWMySQLRepository = dw_mysql_repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        self.embedding_client: HuggingFaceEndpointEmbeddings = embedding_client
        self.value_es_repository: ValueEsRepository = value_es_repository
        self.metric_qdrant_repository: MetricQdrantRepository = metric_qdrant_repository

    async def _save_tables_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfo]:
        """
        核心逻辑：把 YAML 的配置和 dw 库的“真实情况”合并，生成完整的字段元数据，写进 meta 库的 table_info 和 column_info 表。
        最后返回 column_infos，因为下一步 Qdrant 向量化需要它。
        :param meta_config:
        :return:
        """
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []

        for table in meta_config.tables:
            # table -> table_info
            # ① 创建 TableInfo 对象
            table_info = TableInfo(id=table.name,
                                   name=table.name,
                                   role=table.role,
                                   description=table.description, )
            table_infos.append(table_info)

            # 查询字段类型
            # ② 去 dw 库查真实字段类型（比如 VARCHAR(255)）
            column_types = await self.dw_mysql_repository.get_column_types(table.name)

            for column in table.columns:
                # 查询字段取值示例
                # ③ 去 dw 库查真实取值示例（比如 brand 列的 "华为", "苹果"）
                column_values = await self.dw_mysql_repository.get_column_values(table.name, column.name)

                # column -> column_info
                # ④ 创建 ColumnInfo 对象（合并 YAML 配置 + dw 库真实信息）
                column_info = ColumnInfo(id=f"{table.name}.{column.name}",
                                         name=column.name,
                                         type=column_types[column.name],
                                         role=column.role,
                                         examples=column_values,
                                         description=column.description,
                                         alias=column.alias,
                                         table_id=table.name)
                column_infos.append(column_info)

        # ⑤ 批量写入 meta 库
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_infos)
            await self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos   # ← 返回给后面的 Qdrant 向量化用

    async def _save_columns_to_qdrant(self, column_infos: list[ColumnInfo]):
        """核心逻辑：对于每一个字段，把它的字段名、描述、所有别名都分别转成向量。每个向量后面挂载
        payload（完整的字段元数据）。这样用户无论搜“商品名称”、“产品”还是“商品的完整显示名称”，Qdrant
        都能命中同一个字段。"""

        await self.column_qdrant_repository.ensure_collection()

        # ① 准备所有要向量化的"文本片段"
        points: list[dict] = []
        for column_info in column_infos:
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.name,
                'payload': asdict(column_info),
            })

            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.description,
                'payload': asdict(column_info),
            })

            for alia in column_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(column_info),
                })

        # 向量化
        # ② 批量调用 BGE 模型，把文本转成向量
        embeddings: list[list[float]] = []
        embeddings_texts = [point['embedding_text'] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embeddings_texts), embedding_batch_size):
            batch_embedding_texts = embeddings_texts[i:i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            embeddings.extend(batch_embeddings)

        # ③ 向量 + 标签一起存入 Qdrant
        ids = [point['id'] for point in points]
        payloads = [point['payload'] for point in points]
        await self.column_qdrant_repository.upsert(ids, embeddings, payloads)

    async def _save_values_to_es(self, meta_config: MetaConfig):
        """
        核心逻辑：只处理你标了 sync: true 的维度字段（如 brand、province）。
        去 dw 库查出它们的真实枚举值，灌入 ES 建倒排索引。这样用户说“华为”时，ES 能精确命中 brand = '华为'
        :param meta_config:
        :return:
        """
        await self.value_es_repository.ensure_index()

        value_infos: list[ValueInfo] = []
        for table in meta_config.tables:
            for column in table.columns:
                if column.sync:  # ← 只处理 YAML 里 sync: true 的字段
                    # 去 dw 库查这个字段的真实值
                    current_column_values = await self.dw_mysql_repository.get_column_values(table.name, column.name, 1000000)
                    current_values_infos = [ValueInfo(id=f"{table.name}.{column.name}.{current_column_value}",
                                                      value=current_column_value,
                                                      column_id=f"{table.name}.{column.name}") for
                                            current_column_value in
                                            current_column_values]
                    # 包装成 ValueInfo
                    value_infos.extend(current_values_infos)

        # 批量写入 ES
        await self.value_es_repository.index(value_infos)

    async def _save_metrics_to_meta_db(self, meta_config: MetaConfig)->list[MetricInfo]:
        """
        核心逻辑：把指标的定义写入 metric_info 表，同时把指标和字段的关联关系写入 column_metric 表。
        这样 Agent 以后就知道“GMV 这个指标需要用 order_amount 字段，而且可以按 brand、month 等维度来看”
        :param meta_config:
        :return:
        """
        metric_infos: list[MetricInfo] = []
        column_metrics: list[ColumnMetric] = []

        for metric in meta_config.metrics:
            # metric -> MetricInfo
            # ① 创建 MetricInfo 对象
            metric_info = MetricInfo(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)

            # ② 为每个 relevant_column 创建 ColumnMetric 关联
            for column in metric.relevant_columns:
                # column -> ColumnMetric
                column_metric = ColumnMetric(
                    column_id=column,  # 如 "fact_order.order_amount"
                    metric_id=metric.name,  # 如 "GMV"
                )
                column_metrics.append(column_metric)

            # ③ 批量写入 meta 库
            async with self.meta_mysql_repository.session.begin():
                self.meta_mysql_repository.save_metric_infos(metric_infos)
                self.meta_mysql_repository.save_column_metrics(column_metrics)

            return metric_infos

    async def _save_metrics_to_qdrant(self, metric_infos: list[MetricInfo]):
        """
        核心逻辑：和字段向量化完全对称。把指标的名称、描述、别名全部转成向量，存入 Qdrant 的指标专用集合。
        这样用户说“成交总额”、“订单总额”、“平均单价”时，Qdrant 都能命中对应的指标定义
        :param metric_infos:
        :return:
        """
        await self.metric_qdrant_repository.ensure_collection()

        # 逻辑和 _save_columns_to_qdrant 完全一样
        # 只是处理的素材从 "字段" 变成了 "指标"
        points: list[dict] = []
        for metric_info in metric_infos:
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.name,
                'payload': asdict(metric_info),
            })

            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.description,
                'payload': asdict(metric_info),
            })

            for alia in metric_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(metric_info),
                })

        # 批量向量化 → 存入 Qdrant
        embeddings: list[list[float]] = []
        embeddings_texts = [point['embedding_text'] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embeddings_texts), embedding_batch_size):
            batch_embedding_texts = embeddings_texts[i:i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            embeddings.extend(batch_embeddings)

        ids = [point['id'] for point in points]
        payloads = [point['payload'] for point in points]
        await self.metric_qdrant_repository.upsert(ids, embeddings, payloads)

    async def build(self, config_path: Path):
        # 1. 读取配置文件
        context = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
        logger.info("加载配置文件成功")


        # 2 处理"表"相关的三类知识
        if meta_config.tables:
            # 2.1 将表信息和字段信息保存至meta数据库
            column_infos = await self._save_tables_to_meta_db(meta_config)
            logger.info("保存表信息和字段信息到数据库成功")

            # 2.2 对字段信息建立向量索引
            await self._save_columns_to_qdrant(column_infos)
            logger.info("为字段信息建立向量索引成功")

            # 2.3 为指定的维度字段建立全文索引
            await self._save_values_to_es(meta_config)
            logger.info("为指定的维度字段取值建立全文索引成功")

        # 3 处理"指标"相关的两类知识
            # 3.1 将指标信息保存meta数据库
            metric_infos = await self._save_metrics_to_meta_db(meta_config)
            logger.info("保存指标信息到meta数据库成功")

            # 3.2 对指标信息建立向量索引
            await self._save_metrics_to_qdrant(metric_infos)
            logger.info("为指标信息建立向量索引成功")



