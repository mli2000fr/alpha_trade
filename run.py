import sys
import subprocess

if __name__ == "__main__":
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "ihm/app.py"
        ], check=True)
    except FileNotFoundError:
        print("[ERREUR] Streamlit n'est pas installé. Faites: pip install streamlit")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERREUR] Lancement Streamlit échoué: {e}")
        sys.exit(e.returncode)

