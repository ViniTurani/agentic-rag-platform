import asyncio

import uvicorn

from .dependencies import init_milvus
from .settings import Settings


def main() -> None:
    settings = Settings.get()
    asyncio.run(init_milvus())
    uvicorn.run(
        app="app:create_app",
        factory=True,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=settings.WORKERS,
        use_colors=True,
    )


if __name__ == "__main__":
    main()
