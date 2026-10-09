"""Command line entry point: `chemready` or `python -m chemready`."""

from pydantic import ValidationError

from chemready import __version__
from chemready.config import get_settings


def main() -> None:
    """Print the version and a safe summary of the settings (never secrets)."""
    print(f"ChemReady {__version__}")
    try:
        settings = get_settings()
    except ValidationError as error:
        print("Settings are not valid:")
        for issue in error.errors():
            print(f"  - {issue['msg']}")
        raise SystemExit(1) from None

    private = "yes" if settings.allows_private_data else "no (public SDS only)"
    print(f"Environment:           {settings.environment}")
    print(f"Model provider:        {settings.llm_provider}")
    print(f"Private files allowed: {private}")
    print(f"Database:              {settings.database_path}")


if __name__ == "__main__":
    main()
