def main() -> None:
    """Arranca la API local mediante `uv run cauce-oposiciones`."""
    import uvicorn

    uvicorn.run("cauce_oposiciones.api:app", host="127.0.0.1", port=8000)
