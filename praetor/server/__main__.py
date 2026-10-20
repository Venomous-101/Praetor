"""`python -m praetor.server` starts the Praetor Web Console."""
import os

from praetor.server.app import DEFAULT_PORT, serve

if __name__ == "__main__":
    serve(
        host=os.environ.get("PRAETOR_CONSOLE_HOST", "127.0.0.1"),
        port=int(os.environ.get("PRAETOR_CONSOLE_PORT", str(DEFAULT_PORT))),
    )
