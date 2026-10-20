"""Start the Praetor Web Console (browser UI on localhost).

Runs:  python examples/web_console.py
Then open http://127.0.0.1:8756 in a browser.

Set PRAETOR_OPENROUTER_KEY first to connect a cloud model. The console
binds to localhost only — it is a local tool, not a public service, and
your key never leaves the environment.
"""
import os

from praetor.server.app import DEFAULT_PORT, serve


def main() -> None:
    serve(
        host=os.environ.get("PRAETOR_CONSOLE_HOST", "127.0.0.1"),
        port=int(os.environ.get("PRAETOR_CONSOLE_PORT", str(DEFAULT_PORT))),
    )


if __name__ == "__main__":
    main()
