import logging


def setup_logging(level: str = "INFO") -> None:
    """Configura mensajes legibles para ejecución local."""
    logging.basicConfig(
        level=level.upper(),
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
