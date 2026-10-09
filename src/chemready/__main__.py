"""Command line entry point: `chemready` or `python -m chemready`."""

from chemready import __version__


def main() -> None:
    """Print the installed version, to prove the package is set up."""
    print(f"ChemReady {__version__}")


if __name__ == "__main__":
    main()
