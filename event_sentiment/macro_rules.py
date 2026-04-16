from dataclasses import dataclass
from typing import NamedTuple

from event_sentiment.models import MacroImpactRecord, NormalizedNewsArticle, SentimentRecord


@dataclass(frozen=True, slots=True)
class MacroRule:
    macro_event_type: str
    keywords: tuple[str, ...]
    positive_cues: tuple[str, ...]
    negative_cues: tuple[str, ...]
    sector_weights: dict[str, float]


class IntensityWeights(NamedTuple):
    """
    Pondération des trois composantes du calcul d'intensité macro.
    Somme = 1.0 recommandée mais non imposée (permet des calibrations libres).

    w_keywords   : poids sur le nombre de mots-clés uniques matchés (signal de pertinence)
    w_net_score  : poids sur |sentiment_net_score| (signal de tonalité FinBERT)
    w_confidence : poids sur la confiance FinBERT (signal de fiabilité du modèle)

    Valeurs par défaut calquées sur le comportement historique du code.
    Pour calibrer empiriquement, calculer la corrélation intensité → réaction marché J+1
    sur les dates de FOMC / CPI historiques via backtesting.
    """
    w_keywords: float = 0.25
    w_net_score: float = 0.35
    w_confidence: float = 0.40


MACRO_RULES = (
    MacroRule(
        macro_event_type="monetary_policy",
        keywords=("fomc", "fed", "powell", "rate hike", "rate cut", "hawkish", "dovish"),
        positive_cues=("rate cut", "dovish", "easing", "pause"),
        negative_cues=("rate hike", "hawkish", "tightening"),
        sector_weights={
            "Technology": 1.0,
            "Real Estate": 0.9,
            "Communication Services": 0.7,
            "Utilities": 0.4,
            "Banks": -0.4,
        },
    ),
    MacroRule(
        macro_event_type="inflation_employment",
        keywords=("cpi", "ppi", "inflation", "payrolls", "employment", "jobless claims"),
        positive_cues=("cooling inflation", "softer inflation", "lower-than-expected"),
        negative_cues=("hot inflation", "higher-than-expected", "sticky inflation"),
        sector_weights={
            "Technology": 0.9,
            "Consumer Defensive": 0.3,
            "Real Estate": 0.8,
            "Banks": -0.2,
            "Energy": -0.1,
        },
    ),
    MacroRule(
        macro_event_type="geopolitics",
        keywords=("war", "sanction", "missile", "tariff", "conflict", "ceasefire"),
        positive_cues=("ceasefire", "de-escalation", "deal"),
        negative_cues=("war", "sanction", "escalation", "attack"),
        sector_weights={
            "Energy": 0.8,
            "Industrials": 0.3,
            "Technology": -0.4,
            "Consumer Cyclical": -0.6,
        },
    ),
    MacroRule(
        macro_event_type="fiscal_policy",
        keywords=("tax bill", "stimulus", "budget", "spending bill", "infrastructure"),
        positive_cues=("stimulus", "infrastructure spending", "tax credit"),
        negative_cues=("shutdown", "austerity", "spending cut"),
        sector_weights={
            "Industrials": 0.8,
            "Materials": 0.6,
            "Consumer Cyclical": 0.5,
        },
    ),
    MacroRule(
        macro_event_type="energy_commodities",
        keywords=("oil", "gas", "opec", "crude", "commodity shock", "refinery"),
        positive_cues=("supply increase", "inventory build"),
        negative_cues=("supply disruption", "output cut", "price spike"),
        sector_weights={
            "Energy": 1.0,
            "Industrials": -0.3,
            "Consumer Cyclical": -0.5,
            "Transportation": -0.7,
        },
    ),
)


class MacroRuleEngine:
    def __init__(
        self,
        rule_version: str = "macro_rules_v1",
        intensity_weights: IntensityWeights | None = None,
    ) -> None:
        self.rule_version = rule_version
        self.intensity_weights = intensity_weights or IntensityWeights()

    def _compute_intensity(self, hits: list[str], sentiment: SentimentRecord) -> float:
        """
        Calcule l'intensité de l'impact macro sur [0, 1].

        Formule : w_keywords * unique_hits_norm + w_net_score * |net| + w_confidence * confidence
        où unique_hits_norm = min(1.0, unique_hits / 3) pour saturer à 3 mots-clés distincts.

        Les poids sont configurables via IntensityWeights (voir calibration empirique).
        """
        iw = self.intensity_weights
        unique_hits_norm = min(1.0, len(set(hits)) / 3.0)
        raw = (
            iw.w_keywords * unique_hits_norm
            + iw.w_net_score * abs(sentiment.sentiment_net_score)
            + iw.w_confidence * sentiment.sentiment_confidence
        )
        return min(1.0, max(0.0, raw))

    def classify(self, article: NormalizedNewsArticle, sentiment: SentimentRecord) -> list[MacroImpactRecord]:
        """
        Classifie un article selon TOUTES les règles macro applicables (multi-match).

        IMPORTANT — fix du `break` original :
        Un article multi-thème (ex. "Fed rate hike + oil spike") génère maintenant
        des MacroImpactRecord pour CHAQUE règle déclenchée (monetary_policy ET
        energy_commodities), avec des impacts sectoriels distincts.

        La déduplication (article_id, sector, macro_event_type) est gérée en aval
        par l'upsert en base via ON DUPLICATE KEY UPDATE.
        """
        text = " ".join(part for part in [article.headline, article.summary or "", article.content or ""] if part).lower()
        records: list[MacroImpactRecord] = []
        seen_event_sector: set[tuple[str, str]] = set()  # déduplication en mémoire

        for rule in MACRO_RULES:
            hits = [kw for kw in rule.keywords if kw in text]
            if not hits:
                continue

            if any(cue in text for cue in rule.positive_cues):
                direction = "positive"
                sign = 1.0
            elif any(cue in text for cue in rule.negative_cues):
                direction = "negative"
                sign = -1.0
            else:
                net = sentiment.sentiment_net_score
                direction = "positive" if net > 0.05 else "negative" if net < -0.05 else "neutral"
                sign = 1.0 if direction == "positive" else -1.0 if direction == "negative" else 0.0

            intensity = self._compute_intensity(hits, sentiment)

            for sector, weight in rule.sector_weights.items():
                dedup_key = (rule.macro_event_type, sector)
                if dedup_key in seen_event_sector:
                    continue  # même (type, secteur) déjà ajouté par une règle précédente
                seen_event_sector.add(dedup_key)

                impact_score = max(-1.0, min(1.0, sign * intensity * weight))
                records.append(
                    MacroImpactRecord(
                        article_id=article.article_id,
                        trade_date=article.effective_trade_date,
                        sector=sector,
                        macro_event_type=rule.macro_event_type,
                        impact_direction=direction,
                        impact_score=impact_score,
                        macro_event_intensity=abs(impact_score),
                        rule_version=self.rule_version,
                        rule_hits={"keyword_hits": hits},
                        explanation_text=(
                            f"{rule.macro_event_type} | hits={hits} | direction={direction} | intensity={intensity:.4f}"
                        ),
                    )
                )

        return records

