"""Helpers de pages pour l'IHM Streamlit Alpha Trade."""
from __future__ import annotations

from collections.abc import Callable


def run_page_if_standalone(module_name: str, render_func: Callable[[], None]) -> None:
	"""Exécute le rendu quand le fichier de page est lancé directement par Streamlit.

	Cas visé : accès direct via `/execution`, `/corporate_actions`, etc.
	Quand la page est importée depuis `ihm/app.py`, rien n'est exécuté ici.
	"""
	if module_name == "__main__":
		render_func()


