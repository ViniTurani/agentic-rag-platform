import uvicorn

from app.settings import Settings


def main() -> None:
	settings = Settings.get()
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
