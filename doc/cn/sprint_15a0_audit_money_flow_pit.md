# Sprint 15-A0 — Audit des flux de capitaux CN point-in-time

**État au 27 septembre 2026 : `NO_GO_HISTORICAL_FREE` pour la variante B1 du Sprint 16 ; `GO_PROSPECTIVE_PILOT` uniquement pour une collecte expérimentale.** Cet audit n'active ni collecteur, ni schéma de production, ni entraînement, ni backtest.

## Décision

Le besoin 15A est une série quotidienne **par titre** de flux acheteur/vendeur, idéalement ventilée par taille d'ordre et connue à la date de décision. Les volumes et prix BaoStock déjà disponibles ne sont pas des flux signés. Le Chaikin Money Flow calculé avec OHLCV n'est pas une preuve indépendante de flux institutionnel.

Eastmoney, via l'API employée par AKShare, est accessible depuis cette machine, mais n'a renvoyé que **120 séances récentes** sur quatre titres Shanghai/Shenzhen. En septembre 2026, cette source ne reconstruit pas les années 2018–2025 des folds Walk-Forward CN. Son classement de fonds est une photographie courante, pas une archive quotidienne consultable à date arbitraire. Tushare documente une profondeur plus grande, mais son accès n'est actuellement pas utilisable depuis la France dans ce projet et exige des points/quotas. La famille 15A n'est donc pas prête pour le ML historique.

Cette décision ne ferme ni 15B–15D ni l'audit distinct de la Dragon/Tiger List : ses achats institutionnels sont événementiels, et non une série quotidienne dense.

## Contrat de données à démontrer

| Élément | Exigence avant feature ML | Risque si absent |
|---|---|---|
| Identité | `instrument_id`, marché, fournisseur, méthode et changements de code/radiations | Faux historique ou biais de survivance |
| Session | Séance CN, état suspension et univers tradable PIT | Faux zéro de flux |
| Mesure | Achats, ventes, flux net, unité/devise et seuils des tailles d'ordres | Comparaison incompatible |
| Disponibilité | Heure de publication, première observation, `available_at` conservateur | Fuite temporelle |
| Révisions | Version brute, hash, observation et corrections traçables | Valeur révisée injectée dans le passé |
| Couverture | Titres actifs/radiés, années, boards, tailles et événements | Biais de sélection |
| Normalisation | Flux/turnover de même séance et unité ; z-score basé sur le passé connu | Fuite ou erreur d'échelle |

Un « flux principal » Eastmoney est une **classification fournisseur** par transactions/ordres, pas l'identité vérifiée d'investisseurs institutionnels. Ne pas mélanger cette méthode avec `moneyflow` Tushare ni avec les achats institutionnels attribués de Dragon/Tiger.

## Inventaire du projet

- `config/univers_cn/canonical_full_2018_2025.txt` compte 5 405 titres au format `sh.`/`sz.`.
- Une recherche dans `service/`, `modelFactory/`, `database/`, `config_cn.yaml` et `batch_cn.yaml` n'a pas trouvé de collecteur ou de table CN pour le flux signé quotidien par titre. La mention `cmf_20` dans `modelFactory/features.py` est un indicateur dérivé des prix/volumes, pas cette source.
- Les folds OOS et les modèles Sprints 10–14 ne doivent pas être enrichis rétroactivement avec des snapshots observés en 2026.

## Smoke réel du 27 septembre 2026

Requête **en lecture seule** vers `https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get`, avec `klt=101`, `fields2=f51..f65` et `lmt=0`. Elle a été exécutée depuis Windows avec le magasin de certificats système. Le `requests` de l'environnement Python échouait à vérifier la chaîne TLS locale, tandis que `Invoke-WebRequest` réussissait : aucune vérification TLS n'a été désactivée.

| Segment / titre | HTTP | Lignes | Première séance | Dernière séance |
|---|---:|---:|---|---|
| Shanghai `sh.600519` | 200 | 120 | 2026-04-03 | 2026-09-24 |
| Shenzhen `sz.000001` | 200 | 120 | 2026-04-03 | 2026-09-24 |
| ChiNext `sz.300750` | 200 | 120 | 2026-04-03 | 2026-09-24 |
| STAR `sh.688981` | 200 | 120 | 2026-04-03 | 2026-09-24 |

Pour `sh.600519`, `lmt=0`, `1000` et `10000` ont tous renvoyé ces 120 lignes. Un essai supplémentaire avec `830799` a renvoyé `data=null` ; ce code n'appartient pas à l'univers `sh.`/`sz.` vérifié et ne prouve **rien** sur la couverture Beijing. Ce smoke établit la profondeur constatée, pas la couverture statistique des 5 405 titres.

Chaque ligne observée contient la date `f51` et 14 valeurs `f52`–`f65`. Les noms et unités métier doivent être alignés avec la documentation AKShare et vérifiés auprès du fournisseur avant canonicalisation. Ni heure historique de publication ni vintage « tel qu'observé au jour J » ne figurent dans cette réponse ; le **gate PIT reste donc ouvert**, indépendamment de la limite à 120 séances.

## Sources et limites

| Source | Données plausibles | Profondeur / accès établi | Verdict A0 |
|---|---|---|---|
| BaoStock | OHLCV et référence | Prix déjà disponibles ; pas de flux signé par titre validé | Ne couvre pas 15A |
| AKShare → Eastmoney, flux individuel | Flux nets principal, super-large, large, moyen, petit et ratios | 120 séances sur quatre titres, accès réel depuis la France | Prospectif seulement ; pas 2018–2025 |
| AKShare → Eastmoney, classement | Classement actuel 1/3/5/10 jours | Pas d'historique as-of à date arbitraire documenté | Ne remplace pas la série |
| AKShare → Eastmoney, flux marché | Agrégats marché | Pas par titre | Contexte, pas 15A |
| Tushare `moneyflow` | Achats/ventes par taille, historique annoncé depuis 2010 | Points/quotas nécessaires ; aucun échantillon réel accessible/validé ici | Réexaminer si accès légal et PIT prouvés |
| Dragon/Tiger institutionnel | Transactions attribuées sur événements publiés | Sous-ensemble non dense | À auditer en 15D |

Sources : [AKShare — données de flux actions](https://akshare.akfamily.xyz/data/stock/stock.html), [implémentation AKShare de l'endpoint](https://github.com/akfamily/akshare/blob/main/akshare/stock/stock_fund_em.py), [Tushare — `moneyflow`](https://tushare.pro/document/2?doc_id=170), [BaoStock](https://www.baostock.com/). Ce sont des constats au jour de l'audit, pas des garanties de stabilité, licence de redistribution ou disponibilité point-in-time.

## Gate de sortie du NO-GO

1. Obtenir une source licite accessible depuis la France avec série **par titre et séance** couvrant les folds 2018–2025, y compris titres radiés ; mesurer la couverture par année, board et capitalisation.
2. Obtenir le dictionnaire des unités, seuils d'ordres, sens acheteur/vendeur, changements de méthode, suspensions et calendrier. Ne pas inférer « institutionnel » de l'intitulé « principal ».
3. Prouver la disponibilité PIT : heure de publication, corrections et valeurs accessibles avant décision. Sans vintage historique, collecter prospectivement, sans injecter ces observations dans Sprint 16 historique.
4. Conserver les bruts et comparer un petit panel à une source indépendante ; quantifier doublons, trous, outliers, révisions et discordance des totaux.
5. Ensuite seulement pré-enregistrer les features J-1/J-5/J-10, ratio turnover, surprise et divergence prix/flux, puis l'ablation B1 vs B0 et les gates OOF. La réussite de collecte ne prouve pas la valeur directionnelle.

**Suite conseillée :** auditer 15B/15C/15D séparément. Pour 15A, ne pas acheter ni bâtir de pipeline lourd avant échantillon historique 2018–2025 et preuve PIT. Une collecte Eastmoney prospective bornée peut accumuler des vintages futurs sous statut `RESEARCH_ONLY`.
