"""Independent, default-off utility victim selection mod."""

from ._version import __version__

__all__ = ["__version__", "register"]


def register() -> None:
    from .plugin import register as activate

    activate()
