"""Application entry point."""

import sys

from clean_app.presentation.cli import run_cli


def main() -> None:
    """Run the CLI or API depending on arguments."""
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        from clean_app.presentation.api.run import run_api

        run_api()
        return
    run_cli()


if __name__ == "__main__":
    main()
