# 09 — Verdict final

## Verdict

Alpha Trade est une plateforme de swing trading US **prometteuse et déjà très avancée**, mais elle n’est pas encore quasi institutionnelle. Elle contient plusieurs briques de qualité professionnelle : provider EODHD daily, convention split-only, risk/execution structurés, preflight live, IHM de supervision, corporate actions et backtesting PIT avancé. Le principal problème n’est pas l’absence de fonctionnalités ; c’est la **cohérence opérationnelle totale** : docs encore contradictoires, fallback configuré mais non réel, lineage source daily ambigu, parité backtest/live opt-in et exploitation encore locale.

## Note globale

**6,8 / 10**

Niveau de confiance : **moyen-élevé**.

## Positionnement

| Référence | Positionnement |
|---|---|
| Amateur sérieux | Très au-dessus. |
| Indépendant avancé | Niveau élevé, exploitable avec discipline. |
| Desk swing professionnel | Partiel : bonnes briques, mais gouvernance/ops insuffisantes. |
| Institutionnel mature | Encore loin : manque contrôle de changement, observabilité centralisée, CI complète, validation indépendante. |

## Usage recommandé aujourd’hui

- **Recherche/backtest** : oui, avec prudence sur source et PIT.
- **Paper trading** : oui, très recommandé pour valider cycles 1→14.
- **Live petit capital** : seulement après corrections P0/P1, avec limites strictes.
- **Live significatif** : non recommandé avant S0–S6 minimum et plusieurs semaines paper sans incident.

## Décision finale

Verdict : **pro-grade partiel**.

Ce n’est pas un jouet ni un simple prototype. C’est un système sérieux qui a franchi une partie importante du chemin. Mais pour devenir réellement pro-grade, il doit maintenant réduire sa dette d’alignement : moins de clés mortes, moins de runbooks contradictoires, plus de tests contractuels inter-modules, et une orchestration exploitable comme un système de production, pas seulement comme une IHM lançant des scripts.

