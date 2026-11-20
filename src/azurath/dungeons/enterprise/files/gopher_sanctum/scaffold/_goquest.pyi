"""Type stubs for the Go-built extension: lets IDEs and type checkers see inside the .so."""

def bonus(base: int, rank: str, /) -> int:
    """Multiply base by the rank's bonus (S=3, A=2, B=1.5, C=1).

    Raises ValueError for unknown ranks.
    """
