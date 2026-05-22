# 01 — Global scorecard

## Note globale

| Dimension | Note /10 | Commentaire synthétique |
|---|---:|---|
| Niveau amateur sérieux | 9,0 | L’application dépasse largement un projet amateur : modules complets, DB, IHM, tests, risk/exécution. |
| Niveau indépendant avancé | 7,5 | Très bon niveau pour une plateforme personnelle/indépendante ambitieuse. |
| Niveau professionnel buy-side / prop swing | 5,8 | Les briques existent, mais orchestration, tests de parité, runbooks et gouvernance ne sont pas encore assez robustes. |
| Niveau institutionnel très mature | 4,2 | Il manque certification process, contrôle de changement, SLO, séparation stricte envs, observabilité centralisée et validation indépendante. |

**Note globale consolidée : 6,8 / 10.**

**Niveau de confiance : moyen-élevé** pour les axes audités par lecture directe du code ; moyen pour les modules non explorés ligne à ligne exhaustivement.

## Score par domaine obligatoire

| Module / domaine | Note /10 | Risque principal |
|---|---:|---|
| documentation | 6,5 | Reste de contradictions historiques, notamment `dataIntegrityEngine.md`. |
| configuration | 6,8 | Paramètres non consommés ou trop optimistes selon capital. |
| dataIntegrityEngine | 7,0 | Transition EODHD globalement réelle mais sanitation/versioning encore perfectibles. |
| database | 6,7 | Schémas utiles, mais PK incompatible avec cohabitation `data_source` documentée. |
| service/providers | 7,0 | EODHD/Alpaca/Finnhub structurés, mais fallback runtime incomplet. |
| screener | 7,0 | Logique utile, dépend fortement qualité volume/quotes. |
| selector | 7,2 | Filtres stricts riches ; risque d’univers vide ou de dépendance aux snapshots quotes/earnings. |
| event_sentiment | 6,3 | Potentiel, mais complexité et valeur alpha à prouver ; risque bruit/latence. |
| modelFactory | 6,2 | Gouvernance multi-modèles intéressante, mais risque d’overfitting et artefacts lourds. |
| risk_management | 7,1 | Bon sizing/contraintes, mais calibration empirique et live equity doivent rester verrouillés. |
| execution_engine | 7,4 | Garde-fous sérieux ; manque industrialisation opérateur et réconciliation continue mature. |
| corporate_actions | 7,0 | Convention saine ; apply dépendant des snapshots et provider CA à surveiller. |
| backtesting | 6,8 | Bonnes briques PIT, mais parité live non automatique. |
| ihm | 7,0 | IHM riche et globalement alignée ; complexité UX et processus long réseau. |
| observabilité / run summaries / logs | 6,7 | Nombreux signaux, mais dispersion et absence d’incident cockpit unique. |
| sécurité / readiness production | 6,2 | Live preflight fort ; secrets/CI/ops encore à institutionnaliser. |
| qualité logicielle globale | 6,8 | Bon volume tests et typage progressif ; dette doc/config et mocks E2E à renforcer. |

## Positionnement

- **Positionnement actuel** : application indépendante avancée, quasi-pro sur certaines briques (`execution_engine`, conventions OHLCV, IHM de pilotage), mais non pro-grade complet.
- **Verdict** : **pro-grade partiel**.
- **Go-live recommandé** : uniquement après correction des P0/P1 et au moins un cycle paper multi-semaines vérifié.

## Comparaison qualitative

| Référence | Alpha Trade aujourd’hui |
|---|---|
| Script trading personnel | Très au-dessus. |
| Plateforme indépendante sérieuse | Au-dessus de la moyenne, mais exigeante à opérer. |
| Desk swing professionnel | Certaines briques approchent, mais contrôle opérationnel insuffisant. |
| Institutionnel mature | Encore loin : manque gouvernance, monitoring central, validation indépendante, CI sécurité complète. |

