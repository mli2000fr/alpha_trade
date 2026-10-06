"""Compatibilité : utiliser dataIntegrityEngine.cn_provider_ingestion.

Ce module historique reste exécutable pour les scripts externes, mais toute la
logique multi-fournisseurs est désormais centralisée dans le nouveau runner.
"""

from dataIntegrityEngine.cn_provider_ingestion import (
    CnBatchRunError,
    execute,
    load_job,
    main,
)

__all__ = ["CnBatchRunError", "execute", "load_job", "main"]


if __name__ == "__main__":
    main()
