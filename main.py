from fastapi import FastAPI

from app.api.frontend import register_frontend
from app.api.routers.query_router import query_router

app = FastAPI()

app.include_router(query_router)
register_frontend(app)
