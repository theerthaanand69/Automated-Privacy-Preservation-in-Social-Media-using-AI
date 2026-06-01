import os
from pathlib import Path

import uvicorn


BASE_DIR = Path(__file__).resolve().parent
RELOAD_ENABLED = os.getenv("UVICORN_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=RELOAD_ENABLED,
        reload_dirs=[str(BASE_DIR)] if RELOAD_ENABLED else None,
        reload_excludes=[
            str(BASE_DIR / ".venv311"),
            str(BASE_DIR / "venv"),
            str(BASE_DIR / "__pycache__"),
            str(BASE_DIR / "dataset"),
            str(BASE_DIR / "runs"),
            str(BASE_DIR / "uploads"),
        ] if RELOAD_ENABLED else None,
    )
