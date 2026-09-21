class TushareError(RuntimeError):
    """Erreur de base du connecteur Tushare."""


class TushareAuthenticationError(TushareError):
    """Token absent ou refusé."""


class TushareQuotaError(TushareError):
    """Quota local ou fournisseur atteint."""


class TushareResponseError(TushareError):
    """Réponse réseau ou schéma fournisseur invalide."""
