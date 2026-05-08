"""Heuristique de pertinence article → symbole (Niveau 2 / 3).

Le pipeline FinBERT produit **un score de sentiment par article**, ensuite
propagé à tous les tickers fournis par le provider news. Quand le provider
tagge un article avec plusieurs symboles peu pertinents, ce comportement
introduit du bruit dans :class:`news_ticker_map` puis dans les features
journalières.

Ce module fournit :

* :class:`RelevanceWeights` : pondération configurable des composantes ;
* :func:`score_article_symbol` : fonction pure, déterministe, sans I/O,
  qui retourne un :class:`RelevanceResult` (score ∈ [0, 1] + composantes
  pour audit) ;
* la constante :data:`RELEVANCE_VERSION` versionnant l'heuristique.

Le score est consommé par :mod:`event_sentiment.ingestion` (mode
``"scored"`` du ``provider_ticker_relevance_mode``) et stocké dans
``news_ticker_map.relevance_score`` / ``news_ticker_map.relevance_components``.
Il est ensuite utilisé downstream comme **poids** dans
:func:`event_sentiment.aggregation.build_ticker_daily_features`
(``COALESCE(relevance_score, 1.0)``).

L'heuristique reste volontairement simple, déterministe, sans dépendance
ML supplémentaire. Niveau 4 (sentiment article+symbol via FinBERT
contextualisé) est documenté comme évolution future hors périmètre.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

#: Version de l'heuristique. Stockée dans ``relevance_components`` pour
#: pouvoir backfill / re-scorer un sous-ensemble si la formule évolue.
RELEVANCE_VERSION = "v1"

#: Suffixes corporatifs retirés avant matching « nom dans headline ».
_CORPORATE_SUFFIXES = (
    "incorporated",
    "corporation",
    "company",
    "limited",
    "holdings",
    "group",
    "plc",
    "inc",
    "corp",
    "ltd",
    "co",
    "sa",
    "ag",
)

_TOKEN_SPLIT_RE = re.compile(r"[\s,.;:()\[\]{}\"'!?/\\|*&^%$#@~`<>+=-]+")


@dataclass(frozen=True, slots=True)
class RelevanceWeights:
    """Pondération des composantes (somme normalisée à 1.0 dans la formule).

    Les valeurs par défaut donnent la priorité aux signaux les plus
    discriminants : présence du nom société dans le headline et présence
    explicite du ticker dans le texte.
    """

    name_in_headline: float = 0.45
    name_in_summary: float = 0.10
    ticker_in_text: float = 0.30
    primary_bonus: float = 0.15
    #: Pénalité maximale appliquée quand l'article tagge beaucoup de tickers.
    #: Le facteur effectif vaut ``min(1, log(N) / log(MAX))`` × ce poids.
    multi_ticker_penalty: float = 0.20
    #: Plafond de tickers au-delà duquel la pénalité est saturée.
    multi_ticker_saturation: int = 25
    #: Plancher de score retenu (utile pour ne jamais filtrer durement
    #: un article tagué primary par le provider).
    minimum_score: float = 0.05


DEFAULT_WEIGHTS = RelevanceWeights()


@dataclass(frozen=True, slots=True)
class RelevanceResult:
    """Résultat d'un scoring (score ∈ [0, 1] + composants pour audit)."""

    score: float
    components: dict[str, Any] = field(default_factory=dict)


def _normalise_company_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9 &]", " ", str(name)).strip().lower()
    if not cleaned:
        return None
    tokens = [t for t in cleaned.split() if t]
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return " ".join(tokens) or None


def _text_contains(haystack: str, needle: str) -> bool:
    """Recherche d'un *needle* dans un texte avec frontières de mots.

    On tolère les variantes ``$AAPL`` et ``AAPL,`` grâce à un split
    générique sur la ponctuation.
    """
    if not haystack or not needle:
        return False
    tokens = {t for t in _TOKEN_SPLIT_RE.split(haystack.lower()) if t}
    needle = needle.lower().lstrip("$")
    if needle in tokens:
        return True
    # Multi-mot ⇒ recherche substring sur frontières mot
    if " " in needle:
        pattern = r"\b" + re.escape(needle) + r"\b"
        return re.search(pattern, haystack.lower()) is not None
    return False


def _ticker_variants(symbol: str) -> Iterable[str]:
    base = symbol.upper().strip()
    if not base:
        return ()
    return (base, f"${base}")


def score_article_symbol(
    *,
    symbol: str,
    headline: str,
    summary: str | None = None,
    content: str | None = None,
    is_primary: bool = False,
    company_name: str | None = None,
    ticker_count: int = 1,
    weights: RelevanceWeights | None = None,
) -> RelevanceResult:
    """Calcule un score [0, 1] de pertinence article → ``symbol``.

    Pure-Python, déterministe, sans I/O. Le score est borné, et le
    dictionnaire ``components`` retourne le détail des contributions
    (utile pour :mod:`news_ticker_map.relevance_components`).
    """
    w = weights or DEFAULT_WEIGHTS
    headline_text = headline or ""
    summary_text = summary or ""
    content_text = content or ""
    full_text = " ".join(filter(None, [headline_text, summary_text, content_text]))

    normalised_name = _normalise_company_name(company_name)
    name_in_headline = bool(
        normalised_name and _text_contains(headline_text, normalised_name)
    )
    name_in_summary = bool(
        normalised_name and not name_in_headline and _text_contains(summary_text, normalised_name)
    )
    ticker_in_text = any(_text_contains(full_text, v) for v in _ticker_variants(symbol))

    # Score additif borné. Chaque composante contribue selon son poids
    # (les poids ne sont pas forcément ∑=1 ; on borne le total à [0,1]).
    score = 0.0
    if name_in_headline:
        score += w.name_in_headline
    if name_in_summary:
        score += w.name_in_summary
    if ticker_in_text:
        score += w.ticker_in_text
    if is_primary:
        score += w.primary_bonus

    # Pénalité multi-ticker : croît logarithmiquement avec ticker_count
    # jusqu'à saturation. Pour ticker_count <= 1, pas de pénalité.
    saturation = max(2, int(w.multi_ticker_saturation))
    safe_count = max(1, int(ticker_count))
    if safe_count > 1:
        ratio = math.log(safe_count) / math.log(saturation)
        penalty = w.multi_ticker_penalty * min(1.0, ratio)
    else:
        penalty = 0.0
    score -= penalty

    score = max(w.minimum_score, min(1.0, score))

    return RelevanceResult(
        score=float(round(score, 6)),
        components={
            "version": RELEVANCE_VERSION,
            "name_in_headline": name_in_headline,
            "name_in_summary": name_in_summary,
            "ticker_in_text": ticker_in_text,
            "is_primary": bool(is_primary),
            "ticker_count": int(ticker_count),
            "multi_ticker_penalty": float(round(penalty, 6)),
            "company_name_resolved": bool(normalised_name),
            "weights": {
                "name_in_headline": w.name_in_headline,
                "name_in_summary": w.name_in_summary,
                "ticker_in_text": w.ticker_in_text,
                "primary_bonus": w.primary_bonus,
                "multi_ticker_penalty": w.multi_ticker_penalty,
                "multi_ticker_saturation": w.multi_ticker_saturation,
                "minimum_score": w.minimum_score,
            },
        },
    )

