from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
from server.routes import create_router


def create_app(db, recorder, transcriber, summarizer) -> FastAPI:
    app = FastAPI(title="CallScribe", version="0.1.0")

    router = create_router(db, recorder, transcriber, summarizer)
    app.include_router(router, prefix="/api")

    static_dir = config.BASE_DIR / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
