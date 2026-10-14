import uvicorn

from backend.api.rest_server import app
from backend.config import NODE_PORT


async def start_api_server():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=NODE_PORT + 500,
        log_level="info"
    )

    server = uvicorn.Server(config)

    await server.serve()