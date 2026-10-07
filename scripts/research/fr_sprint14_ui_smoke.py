"""Headless Streamlit consultation smoke against the actual FR research archives."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from streamlit.testing.v1 import AppTest
    for page in ("pipeline", "diagnostic", "backtest"):
        app = AppTest.from_string(
            f"from ihm.services.fr_research_market import render_fr_research_view\nrender_fr_research_view('{page}')"
        ).run(timeout=30)
        if app.exception:
            raise RuntimeError(f"FR {page}: {app.exception[0].message}")
        if app.error:
            raise RuntimeError(f"FR {page}: {app.error[0].value}")
        print(f"FR {page}: rendered without exception; tables={len(app.dataframe)}", flush=True)


if __name__ == "__main__":
    main()
