"""FastAPI app factory with lifespan management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VecSmith orchestrator starting")
    yield
    logger.info("VecSmith orchestrator shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="VecSmith",
        description="Text-to-SVG generation pipeline",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()


def main():
    import os

    import uvicorn

    host = os.environ.get("VECSMITH_HOST", "0.0.0.0")
    port = int(os.environ.get("VECSMITH_PORT", "8080"))

    uvicorn.run(
        "src.orchestrator.app:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
