"""Command line entry point: `chemready` or `python -m chemready`.

chemready              show the version and a safe settings summary
chemready serve        start the web app (http://127.0.0.1:8000)
chemready seed-demo    create the demo account with fictional SDS files
"""

import argparse

from pydantic import ValidationError

from chemready import __version__
from chemready.config import Settings, get_settings


def _summary(settings: Settings) -> None:
    private = "yes" if settings.allows_private_data else "no (public SDS only)"
    print(f"Environment:           {settings.environment}")
    print(f"Model provider:        {settings.llm_provider}")
    print(f"Private files allowed: {private}")
    print(f"Database:              {settings.database_path}")


def main(argv: list[str] | None = None) -> None:
    """Print the version and a safe summary of the settings (never secrets), or run a command."""
    parser = argparse.ArgumentParser(prog="chemready")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="start the web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("seed-demo", help="create the demo account with fictional SDS files")
    args = parser.parse_args([] if argv is None else argv)

    print(f"ChemReady {__version__}")
    try:
        settings = get_settings()
    except ValidationError as error:
        print("Settings are not valid:")
        for issue in error.errors():
            print(f"  - {issue['msg']}")
        raise SystemExit(1) from None

    if args.command == "serve":
        import uvicorn

        uvicorn.run("chemready.app.main:app_factory", factory=True, host=args.host, port=args.port)
    elif args.command == "seed-demo":
        from chemready.demo.seed import seed_demo

        print(seed_demo(settings))
    else:
        _summary(settings)


def cli() -> None:
    """Entry point for the installed `chemready` command."""
    import sys

    main(sys.argv[1:])


if __name__ == "__main__":
    cli()
