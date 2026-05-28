from typing import TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo

class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]

class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str

class DBInfoState(TypedDict):
    dialect: str
    version: str

class DataAgentState(TypedDict):
    query: str  # 用户输入的查询
    keywords: list[str] # 从用户查询中提取的关键词

    retrieved_columns: list[ColumnInfo]  # 检索到的字段信息
    retrieved_metrics: list[MetricInfo] # 检索到的指标信息
    retrieved_values: list[ValueInfo]  #检索到的取值信息

    table_infos: list[TableInfoState] # 从字段信息中整理出的表信息
    metric_infos: list[MetricInfoState] # 从指标信息中整理出的指标信息

    date_info: DateInfoState # 日期信息
    db_info: DBInfoState    # 数据库信息

    sql: str 
    error: str  # 校验sql时出现的错误信息
