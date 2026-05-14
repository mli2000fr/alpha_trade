import importlib.util
from pathlib import Path
import subprocess
import sys

from common.windows_sleep_guard import prevent_windows_sleep


PROJECT_ROOT = Path(__file__).resolve().parent
STREAMLIT_APP = PROJECT_ROOT / "ihm" / "app.py"


def _streamlit_is_available() -> bool:
    return importlib.util.find_spec("streamlit") is not None

if __name__ == "__main__":
    try:
        if not _streamlit_is_available():
            print(
                "[ERREUR] Streamlit n'est pas installé dans l'environnement Python courant "
                f"({sys.executable})."
            )
            print("[INFO] Installez-le avec : python -m pip install streamlit")
            print("[INFO] Ou installez les dépendances du projet : python -m pip install -r requirements.txt")
            sys.exit(1)
        with prevent_windows_sleep():
            subprocess.run([
                sys.executable, "-m", "streamlit", "run", str(STREAMLIT_APP)
            ], check=True, cwd=str(PROJECT_ROOT))
    except FileNotFoundError:
        print("[ERREUR] Impossible de lancer Streamlit. Vérifiez l'interpréteur Python utilisé.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERREUR] Lancement Streamlit échoué: {e}")
        sys.exit(e.returncode)

