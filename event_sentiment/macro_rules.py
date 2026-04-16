from dataclasses import dataclass

from event_sentiment.models import MacroImpactRecord, NormalizedNewsArticle, SentimentRecord


@dataclass(frozen=True, slots=True)
class MacroRule:
    macro_event_type: str
    keywords: tuple[str, ...]
    positive_cues: tuple[str, ...]
    negative_cues: tuple[str, ...]
    sector_weights: dict[str, float]


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
    def __init__(self, rule_version: str = "macro_rules_v1") -> None:
        self.rule_version = rule_version

    def classify(self, article: NormalizedNewsArticle, sentiment: SentimentRecord) -> list[MacroImpactRecord]:
        text = " ".join(part for part in [article.headline, article.summary or "", article.content or ""] if part).lower()
        records: list[MacroImpactRecord] = []

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

            intensity = min(1.0, 0.25 * len(set(hits)) + 0.35 * abs(sentiment.sentiment_net_score) + 0.40 * sentiment.sentiment_confidence)

            for sector, weight in rule.sector_weights.items():
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
            break

        return records

