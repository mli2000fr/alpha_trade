# conftest.py
#
# Le sys.path hack a été supprimé (fix P1 — Engineering Quality).
# Le projet est maintenant installable via : pip install -e ".[dev]"
# ce qui enregistre tous les packages dans l'environnement et rend
# toute manipulation manuelle de sys.path inutile.
#
# Si vous voyez des ModuleNotFoundError en lançant pytest :
#   cd C:\Users\PC MLI\PycharmProjects\alpha_trade
#   pip install -e ".[dev]"
