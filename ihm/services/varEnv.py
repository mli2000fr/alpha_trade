import io
import os
import csv
import json
from pathlib import Path

import streamlit as st  # À commenter si utilisé hors Streamlit
# --- Version Streamlit-friendly ---
def get_var_env_streamlit() -> io.BytesIO:
    """
    Prépare un export CSV des variables d'environnement autorisées, en mémoire (BytesIO),
    pour téléchargement via Streamlit. Ne crée pas de fichier sur disque.
    """
    variables = dict(os.environ)
    conf_list = get_conf_var_env()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Variable", "Valeur"])
    if isinstance(conf_list, list) and conf_list:
        for nom in conf_list:
            valeur = variables.get(nom, "")
            writer.writerow([nom, valeur])
    else:
        for nom, valeur in variables.items():
            writer.writerow([nom, valeur])
    # Encodage en bytes pour Streamlit.download_button
    return io.BytesIO(output.getvalue().encode("utf-8"))


def get_conf_var_env() -> list:
    """
    Lit le fichier `conf/var_env.json` (ou `config/var_env.json` en secours)
    depuis la racine du projet et retourne la liste des noms de variables
    d'environnement. En cas d'erreur ou si le fichier est absent, retourne
    une liste vide.
    """
    # Recherche robuste du fichier conf/var_env.json en remontant l'arborescence
    start = Path(__file__).resolve().parent
    conf_path = None
    for ancestor in [start] + list(start.parents):
        for candidate_dir in ("conf", "config"):
            candidate = ancestor / candidate_dir / "var_env.json"
            if candidate.exists():
                conf_path = candidate
                break
        if conf_path is not None:
            break

    if conf_path is None:
        return []

    try:
        with conf_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except Exception:
        return []

# Fonction placeholder pour charger / appliquer des variables d'environnement
def set_var_env(csv_bytes: bytes, apply: bool = True) -> dict:
    """
    Parse le contenu CSV passé en bytes. Le CSV est attendu avec une entête
    ("Variable","Valeur").

    Validation : seules les clés présentes dans `conf/var_env.json` sont
    considérées pour l'application.

    Si `apply` est True, les paires (nom, valeur) valides sont écrites dans
    `os.environ` pour la durée du processus. La fonction retourne un dict :
      {
        'applied': {nom: valeur, ...},
        'skipped': [nom, ...]  # noms présents dans le CSV mais non listés dans la conf
      }

    En plus, les noms appliqués sont affichés via print() (logs serveur).
    """
    try:
        text = csv_bytes.decode("utf-8") if isinstance(csv_bytes, (bytes, bytearray)) else str(csv_bytes)
    except Exception:
        text = str(csv_bytes)

    reader = csv.reader(text.splitlines())
    applied: dict[str, str] = {}
    skipped: list[str] = []

    # Liste autorisée depuis la configuration
    allowed = set(get_conf_var_env() or [])

    for i, row in enumerate(reader):
        if i == 0:
            # skip header
            continue
        if not row:
            continue
        var_name = row[0].strip()
        var_value = row[1].strip() if len(row) > 1 else ""
        if not var_name:
            continue
        if allowed and var_name not in allowed:
            skipped.append(var_name)
            continue
        # Apply
        applied[var_name] = var_value
        print(var_name)
        if apply:
            try:
                os.environ[var_name] = var_value
            except Exception:
                # ignore failures to set env
                pass

    return {"applied": applied, "skipped": skipped}

# Exemple d'utilisation :
if __name__ == "__main__":
    chemin = get_var_env()
    print(f"Variables d'environnement exportées dans {chemin}")
