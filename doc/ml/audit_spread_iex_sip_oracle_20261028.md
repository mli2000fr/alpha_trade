# Audit IEX/SIP sur les premiers titres Oracle — 28 octobre 2026

## Question et protocole figé

Peut-on utiliser gratuitement le spread **IEX** pour les contrôles de nouvelles
entrées d'Alpha Trade, à la place du spread consolidé SIP ? Il s'agit d'une
qualification des données, sans backtest économique ni nouveau filtre optimisé.

Modèle : `model-factory-20261016180250-3b0515`, Oracle parcours H20.
Univers : `config/univers_batch/univers_filtred_tradable.txt`, 1 790 symboles.
Classement : score Oracle décroissant puis symbole croissant, sans réordonner
par prix, spread, résultat futur ou couverture IEX. TOP10/20/50 emboîtés.

Les trois séances de cotations terminées pour lesquelles ce modèle possède
un classement enregistré avant l'ouverture suivante sont :

| Signal | Cotations auditées | Scores disponibles / univers |
|---|---|---|
| 16 octobre | 19 octobre | 1 743 / 1 790, soit 97,37 % |
| 23 octobre | 26 octobre | 1 647 / 1 790, soit 92,01 % |
| 26 octobre | 27 octobre | 1 647 / 1 790, soit 92,01 % |

Les deux derniers classements sont incomplets au regard des 95 % du protocole
du modèle. Ils représentent les TOP **existants** du parcours opérationnel,
pas une reconstitution complète de l'univers. Leur analyse de qualité de quote
ne donne aucune autorisation de trading. Isoler aussi le 19 octobre dans le bilan.
Le signal du 27 est exclu : sa séance suivante, le 28, n'est pas encore terminée.

Trois instants par séance : **09h35, 12h00, 15h55 New York**. Pour chaque symbole
et flux, prendre la dernière quote depuis l'ouverture jusqu'à l'instant fixé,
sans reprendre un prix postérieur. Les deux flux sont comparés au même cutoff,
avec leurs dates d'événement distinctes et leur âge propre.

450 couples de quotes, 900 requêtes logiques historiques, 62 titres distincts.
Les observations répétées ne constituent pas 450 occasions indépendantes.

## Contrôles comparés

Spread maximum existant : **50 points de base = 0,50 %**. Aucun seuil ajusté
après observation. Comparaisons séparées :

- Risque : fraîcheur maximale de 300 secondes.
- Pré-soumission : fraîcheur maximale de 30 secondes.
- Winner : fraîcheur maximale de 60 secondes et tailles bid/ask positives.

Les autres contrôles de portefeuille et du risque ne sont pas simulés. Une
quote qui passe ces critères ne signifie pas qu'un achat aurait été accepté,
exécuté ou rentable. Le contrôle de spread est actuellement désactivé à
l'étape 11 ; ses résultats sont donc contrefactuels. Les contrôles d'exécution
restent distincts.

Statuts séparés : absente, invalide, périmée, tailles invalides, spread trop
large, acceptée, erreur technique fournisseur. Aucune absence convertie en
zéro, aucune date de collecte substituée à la date de quote. Pas de fallback.

## Traçabilité et exécution

Script : `scripts/research/us_oracle_iex_sip_quote_audit.py`.
Archives : `artifacts/research/us_oracle_iex_sip_quote_audit/20261028-v1/`.

```powershell
.venv\Scripts\python.exe -u -m scripts.research.us_oracle_iex_sip_quote_audit --output artifacts/research/us_oracle_iex_sip_quote_audit/20261028-v1
```

`plan.json` fige l'univers, les classements, les contrats/empreintes des modèles,
les instants et paramètres. `oracle_scores.parquet` contient la lecture SQL
UTC/READ ONLY. `raw/` conserve les réponses HTTP sans clés ni en-têtes secrets.
`pairs.csv` contient les comparaisons ; `report.json` les compteurs et distributions.
`seal.json` scelle les artefacts. `progress.json` suit la progression locale.

Reprise explicite avec `--resume`, mêmes entrées/empreintes : les réponses déjà
archivées ne sont pas redemandées, une erreur n'est pas transformée en succès.
Un nouveau dossier est nécessaire pour une nouvelle collecte. Les trois dates
avec 62 titres forment un échantillon opérationnel borné, pas une certification
de tout l'univers, de toutes les heures ou des conditions de latence en direct.

Seuls des GET Alpaca historiques sont appelés, bornes de fin antérieures de plus
de quinze minutes. Une erreur de droit/quota/réseau arrête la collecte ; le bilan
est alors incomplet. Les autorisations temps réel ne sont pas déduites de cet accès.

Aucun SQL écrit, aucune inférence ni modification de modèle, aucune analyse
LLM, aucun ordre, aucun changement des fournisseurs utilisés en production.

## Résultats

**COMPLETED** : 900 réponses HTTP 200 archivées, zéro erreur technique, 450
couples comparables. Douze tests passent. Une seconde implémentation du même
assistant a vérifié les empreintes, les identités des requêtes, les spreads,
les âges et les décisions : **4 500 cellules contrôlées**, sept sources figées
inchangées. Ce n'est pas une revue humaine indépendante.
Preuve : `independent_recomputation.json`, sans réécrire le sceau original.

### Critères du watcher : quote ≤60 secondes, tailles positives, spread ≤0,50 %

| Cohorte | Observations | Acceptées SIP | Acceptées IEX | Refus IEX parmi acceptées SIP | Part refusée |
|---|---:|---:|---:|---:|---:|
| TOP10 | 90 | 60 | 21 | 39 | 65,00 % |
| TOP20 | 180 | 128 | 35 | 93 | 72,66 % |
| TOP50 | 450 | 316 | 92 | 224 | 70,89 % |

Aucun cas IEX accepté/SIP refusé sur cet échantillon. Parmi les 224 refus
supplémentaires TOP50 : **220 pour spread trop large, quatre pour fraîcheur**.
Les six observations sans quote concernent les deux flux ; elles ne sont ni
des erreurs HTTP ni des quotes réputées valides à spread zéro.

La différence persiste sur la seule séance dont le classement Oracle dépasse
95 % de couverture, le **19 octobre** : TOP20, SIP 45 acceptées contre IEX 10
sur 60, soit 35 refus supplémentaires ; TOP50, SIP 105 contre IEX 36 sur 150,
soit 69 refus supplémentaires (**65,71 %** des acceptées SIP).

| Séance, TOP50 | SIP accepté | IEX accepté |
|---|---:|---:|
| 19 octobre | 105 / 150 | 36 / 150 |
| 26 octobre | 106 / 150 | 23 / 150 |
| 27 octobre | 105 / 150 | 33 / 150 |

### Autres seuils de fraîcheur déjà présents

Toujours plafond de spread 0,50 %. Ces critères de quote n'intègrent pas les
autres décisions de liquidité/risque ni un ordre réel.

| Critère | Cohorte | SIP accepté | IEX accepté | IEX refuse / SIP accepte |
|---|---|---:|---:|---:|
| Risque, ≤300 s | TOP20 | 128 / 180 | 35 / 180 | 93 |
| Risque, ≤300 s | TOP50 | 316 / 450 | 92 / 450 | 224 |
| Pré-soumission, ≤30 s | TOP20 | 127 / 180 | 34 / 180 | 93 |
| Pré-soumission, ≤30 s | TOP50 | 314 / 450 | 91 / 450 | 223 |

### Amplitude de l'écart de données

Sur les quotes présentes et valides, sans remplacer les absences par zéro :

| Cohorte | Quotes par flux | Spread médian IEX | Spread médian SIP |
|---|---:|---:|---:|
| TOP10 | 90 | 12,89 % | 0,28 % |
| TOP20 | 180 | 7,05 % | 0,27 % |
| TOP50 | 444 | 6,18 % | 0,27 % |

Ce sont les médianes propres à chaque flux sur les mêmes observations avec
prix valides. Pour les **412 couples TOP50 frais à ≤60 s des deux côtés**,
l'excès de spread IEX moins SIP est médian à **517,56 points de base**, soit
**5,18 points de pourcentage**. L'écart absolu médian de milieu de fourchette
est d'environ 60 points de base (**0,60 % du mid SIP**). Il ne faut donc pas
présenter le mid IEX comme le même prix de référence consolidé.

Exemple **CCOI, 19 octobre à 12h00 New York** :

| Flux | Bid | Ask | Spread | Âge |
|---|---:|---:|---:|---:|
| IEX | 7,73 $ | 8,82 $ | 13,17 % | 12,84 s |
| SIP | 7,73 $ | 7,76 $ | 0,39 % | 23,63 s |

Les deux quotes sont fraîches ; seule la fourchette SIP passe le seuil existant.
Le problème n'est donc pas réductible à une latence ou à un manque de quotes.

## Conclusion

**IEX écarté comme remplacement direct du spread consolidé pour les entrées
Oracle de ce parcours.** Sa fourchette élargie provoquerait de nombreux refus
supplémentaires, sans démonstration qu'ils améliorent les trades. Une hausse
des seuils jusqu'à faire passer IEX constituerait une autre politique à tester,
pas une correction neutre de fournisseur.

Cette conclusion reste bornée à trois séances, 62 titres et trois horaires.
Deux classements sont incomplets ; les observations sont répétées/corrélées.
Il ne s'agit pas d'une preuve sur tous les titres US ou d'une mesure de PnL.
Le même sens du résultat sur le 19 octobre qualifié renforce néanmoins le
constat pratique pour notre sélection actuelle.

Aucune activation IEX, aucun assouplissement du watcher, aucun changement du
fournisseur live, des barres historiques ou du contrôle étape 11 déjà désactivé.
