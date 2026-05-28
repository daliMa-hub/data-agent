# Data Agent

Metadata-enhanced Text-to-SQL data query agent for retail data warehouse scenarios.

## Features

- FastAPI query service with SSE streaming responses.
- LangGraph-based NL2SQL workflow: keyword extraction, schema/value/metric retrieval, context merging, SQL generation, validation, correction, and execution.
- Metadata-enhanced retrieval with MySQL, Qdrant, and Elasticsearch.
- Lightweight web UI at `/` for interactive debugging.

## Setup

1. Install dependencies.

```powershell
uv sync
```

2. Prepare local config.

```powershell
Copy-Item conf\app_config.example.yaml conf\app_config.yaml
```

Then edit `conf/app_config.yaml` with your local database, embedding, Elasticsearch, Qdrant, and LLM settings.

3. Start backend services with Docker if needed.

```powershell
cd docker
docker compose up -d
```

The compose file starts MySQL, Elasticsearch, Kibana, Qdrant, and a Hugging Face TEI embedding service. MySQL uses demo credentials by default:

```text
user: atguigu
password: data_agent_password
```

You can override them with environment variables such as `MYSQL_USER` and `MYSQL_PASSWORD`.

4. Build metadata knowledge.

```powershell
.venv\Scripts\python.exe -m app.scripts.build_meta_knowledge -c conf\meta_config.yaml
```

5. Run the API and UI.

```powershell
.venv\Scripts\uvicorn.exe app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/`.
