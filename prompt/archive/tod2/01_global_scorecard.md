# 01 — Global scorecard

## Note globale

| Dimension | Note /10 | Commentaire synthétique |
|---|---:|---|
| Niveau amateur sérieux | 9,2 | L’application dépasse très nettement un projet amateur : modules riches, DB, IHM, tests, risk/exécution et garde-fous live crédibles. |
| Niveau indépendant avancé | 8,4 | Niveau élevé pour une plateforme indépendante ambitieuse, désormais pilotable avec une vraie discipline opérateur. |
| Niveau professionnel buy-side / prop swing | 6,9 | Plusieurs briques approchent un niveau quasi pro, mais orchestration, CI sécurité versionnée et runbooks incidents restent incomplets. |
| Niveau institutionnel très mature | 5,2 | Il manque encore séparation stricte des environnements, workflow CI bloquant, monitoring centralisé et validation indépendante complète. |

**Note globale consolidée : 7,8 / 10.**

**Niveau de confiance : moyen-élevé** pour les axes audités par lecture directe du code ; moyen pour les modules non explorés ligne à ligne exhaustivement.

## Score par domaine obligatoire

| Module / domaine | Note /10 | Risque principal |
|---|---:|---|
| documentation | 7,7 | Documentation largement réalignée, mais quelques traces historiques et runbooks incident restent à industrialiser. |
| configuration | 7,8 | Configuration désormais plus honnête et mieux alignée au runtime ; validation globale des contrats de clés à poursuivre. |
| dataIntegrityEngine | 7,8 | Socle daily/quotes/earnings/fondamentaux plus robuste ; versioning source et monitoring qualité restent perfectibles. |
| database | 7,5 | Schémas et conventions mieux alignés ; le versioning multi-source daily n’est toujours pas natif. |
| service/providers | 7,6 | Providers mieux clarifiés et routage plus explicite, mais sans vraie résilience cross-provider centralisée. |
| screener | 7,6 | Plus exploitable avec diagnostics et garde-fous historiques ; dépend toujours fortement de la qualité upstream. |
| selector | 7,9 | Chaîne de filtres riche et plus explicable ; risque résiduel de dépendance aux snapshots quotes/earnings. |
| event_sentiment | 7,1 | Gouvernance et exploitation améliorées, mais la valeur alpha reste coûteuse et doit continuer à être prouvée. |
| modelFactory | 7,2 | Gouvernance multi-modèles et championing crédibles ; risque d’overfitting et dette MLOps encore présents. |
| risk_management | 7,9 | Presets, gate ML et exécutabilité petits comptes sont nettement plus robustes. |
| execution_engine | 8,4 | Module le plus mature : preflight live, token d’approbation, plan immuable et garde-fous opérateur solides. |
| corporate_actions | 7,9 | Sync/apply mieux durcis et plus auditables ; dépendance aux snapshots broker encore structurante. |
| backtesting | 7,8 | Profil `production-parity` et replays renforcent nettement la crédibilité, malgré une parité encore non totalement automatique partout. |
| ihm | 8,0 | Cockpit beaucoup plus complet côté exécution, supervision, conformité et ops ; orchestration toujours locale. |
| observabilité / run summaries / logs | 7,8 | Corrélation workflow, supervision ops et contrôle coverage améliorent nettement l’exploitation incident. |
| sécurité / readiness production | 7,6 | Runtime live sérieusement durci ; principal manque restant : workflow CI sécurité versionné et runbooks exhaustifs. |
| qualité logicielle globale | 7,7 | Régressions et AppTests ciblés solides ; la chaîne mypy/CI complète reste encore à homogénéiser. |

## Positionnement

- **Positionnement actuel** : application indépendante avancée, avec plusieurs briques quasi pro (`execution_engine`, OHLCV, backtesting parity, IHM ops, garde-fous live), mais encore non pro-grade complet.
- **Verdict** : **pro-grade partiel avancé**.
- **Go-live recommandé** : paper/simulation intensifs OK ; live pilote très discipliné envisageable ; live plus ambitieux à différer tant que la CI sécurité versionnée manque.

## Comparaison qualitative

| Référence | Alpha Trade aujourd’hui |
|---|---|
| Script trading personnel | Très au-dessus. |
| Plateforme indépendante sérieuse | Au-dessus de la moyenne, mais exigeante à opérer. |
| Desk swing professionnel | Certaines briques approchent, mais contrôle opérationnel insuffisant. |
| Institutionnel mature | Encore loin : manque gouvernance, monitoring central, validation indépendante, et workflow CI sécurité complet/versionné. |

