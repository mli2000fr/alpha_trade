"""Client FRED minimal pour les séries macro utilisées par le régime marché."""

from .clientFred import FredFetchError, fetch_series_observations

__all__ = ["FredFetchError", "fetch_series_observations"]


