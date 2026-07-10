from clean_app.infrastructure.config.settings import Settings
from clean_app.presentation.api.dependencies import build_container


def run_cli() -> None:
    """Run the CLI application to check and index trips."""
    settings = Settings.from_env()
    container = build_container(settings)

    print("Fetching and checking trips catalog...")
    try:
        trips = container.trip_repository.get_all()
        print(f"Successfully loaded {len(trips)} trips from repository.")

        indexed = container.vector_store.count()
        print(f"Current vector store database count: {indexed} trips indexed.")

        if indexed == 0:
            print("Vector store is empty. Indexing trips now...")
            res = container.index_trips.execute()
            print(f"Indexed {res.indexed_count} trips. Total in store: {res.total_in_store}")

    except Exception as e:
        print(f"Error checking trips catalog: {e}")

