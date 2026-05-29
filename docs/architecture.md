# Architecture

Data Agent is organized around two workflows:

- **Offline metadata construction**: builds structured metadata, vector indexes, and value indexes.
- **Online Text-to-SQL querying**: uses retrieved metadata to generate and execute SQL from a natural-language question.

## 1. Online Query Workflow

The online workflow starts from `POST /api/query` and streams intermediate progress through Server-Sent Events.

```text
User question
  -> FastAPI router
  -> QueryService
  -> LangGraph workflow
  -> SSE progress and result stream
```

The LangGraph workflow is defined in `app/agent/graph.py`.

```text
extract_keywords
  -> recall_column
  -> recall_value
  -> recall_metric
  -> merge_retrieved_info
  -> filter_table / filter_metric
  -> add_extra_context
  -> generate_sql
  -> validate_sql
  -> correct_sql if validation fails
  -> run_sql
```

## 2. State and Context

`DataAgentState` stores the information accumulated during a query:

- `query`: original user question
- `keywords`: extracted and expanded keywords
- `retrieved_columns`: recalled schema fields
- `retrieved_metrics`: recalled business metrics
- `retrieved_values`: recalled dimension values
- `table_infos`: merged table and field context
- `metric_infos`: selected metric context
- `date_info` and `db_info`: extra generation context
- `sql` and `error`: generated SQL and validation error

`DataAgentContext` provides runtime dependencies to each node:

- embedding client
- Qdrant repositories
- Elasticsearch repository
- MySQL metadata repository
- MySQL data warehouse repository

## 3. Retrieval Design

The project uses multi-route recall and heterogeneous retrieval rather than a single document-style RAG index.

| Knowledge type | Retrieval method | Storage | Why |
|---|---|---|---|
| Schema fields | Dense semantic retrieval | Qdrant | Field names, aliases, and descriptions require semantic matching. |
| Business metrics | Dense semantic retrieval | Qdrant | Metric names and aliases such as GMV / sales amount are semantic. |
| Dimension values | Full-text retrieval | Elasticsearch | Values such as regions, brands, and member levels are closer to entity matching. |
| Table relationships | Structured lookup | MySQL meta DB | Primary keys, foreign keys, and table metadata need exact lookup. |

This is best described as **heterogeneous hybrid retrieval for structured data agents**. It is different from classic document RAG hybrid search, where BM25 and dense retrieval are fused over one homogeneous document corpus.

## 4. SQL Generation and Validation

The SQL generation node receives:

- user question
- filtered table schema
- selected metric definitions
- date information
- database dialect and version

The generated SQL is validated through `EXPLAIN` before execution. If validation fails, the error message is passed to a correction node, which asks the LLM to repair the SQL.

## 5. Offline Metadata Construction

The metadata builder is implemented in `app/services/meta_knowledge_service.py`.

It performs four main tasks:

1. Read `conf/meta_config.yaml`.
2. Save table and column metadata into the MySQL metadata database.
3. Vectorize field and metric names, descriptions, and aliases into Qdrant.
4. Index selected dimension values into Elasticsearch.

This offline stage is what makes the online agent less dependent on direct model guessing.

## 6. Current Scope

The current data warehouse is a compact retail prototype. It is useful for demonstrating:

- schema linking
- metric grounding
- value mapping
- SQL validation
- agent workflow observability

For a stronger research version, the next step would be to add a standardized evaluation set with execution accuracy, SQL validity, schema-linking accuracy, and evidence-binding accuracy.
