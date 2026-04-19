"""
Script d'entrée unique pour lancer l'ingestion et l'application des corporate actions (équivalent à 'python -m corporate_actions run').
"""
from common.utils import configure_root_logging
from corporate_actions.cli import _run_all, _build_parser
import logging
import sys

def main():
    configure_root_logging(
        level=logging.INFO,
        log_path="corporate_actions.log",
        fmt="%(asctime)s %(levelname)-8s %(name)s -- %(message)s",
    )
    # Injecte 'run' si aucune sous-commande n'est présente
    if len(sys.argv) == 1 or sys.argv[1] not in {"sync", "apply", "status", "run"}:
        sys.argv.insert(1, "run")
    parser = _build_parser()
    args = parser.parse_args()
    _run_all(args)

if __name__ == "__main__":
    main()

