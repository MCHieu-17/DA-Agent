"""Explicit migration for the separate operational database."""
from service.queue import initialize

if __name__ == "__main__":
    initialize()
