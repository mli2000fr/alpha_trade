# Sprint 5 France — finalisation du GO limité 2018–2026

Date de décision : 3 octobre 2026.

## Verdict

Le rejeu officiel ESMA, la collecte des radiés récents auprès de l'historique public Euronext et la construction du manifeste sont terminés. Le verdict est :

```text
GO_RESEARCH_J1
```

Le gate anti-survivance pré-enregistré passe avec 36 radiés sur 330 titres admissibles, soit 10,91 %. Ce GO reste strictement limité à la recherche avec disponibilité J+1. Les preuves PIT historiques, les actions sur titres économiques et le transport TLS du POC ne satisfont pas le contrat canonique.

Aucune table canonique n'a été alimentée, aucun modèle n'a été entraîné et aucun backtest de production France n'a été autorisé.

## Contrats de validation

La politique versionnée est `config/markets/fr_sprint5_limited.yaml`, version `fr_s5_limited_v1`. Deux niveaux sont séparés :

1. `CANONICAL_STRICT` exige une identité et un MIC officiels, un prix officiellement vérifié, une preuve de disponibilité historique PIT et une validation économique des actions sur titres.
2. `RESEARCH_J1` accepte une hypothèse conservatrice selon laquelle la barre J n'est utilisable qu'à J+1, mais exige encore une barre valide, un intervalle ESMA action/MIC non ambigu, aucune journée Delta manquante, une corroboration indépendante du prix et aucune histoire de split fournisseur non validée.

Le niveau `RESEARCH_J1` ne permet ni serving, ni paper, ni live. Il ne rend pas les rendements économiques prêts : dividendes, droits, fusions et autres opérations restent séparés.

## ESMA FIRDS 2018–2026

La chaîne annuelle est `COMPLETED` jusqu'au 1er octobre 2026. Le dernier contrôle utilise le Full officiel du 26 septembre 2026 :

| Contrôle | Résultat |
| --- | ---: |
| Archives indexées et traitées | 5 604 / 5 604 |
| Fichiers indexés manquants | 0 |
| Versions FIRDS rejouées | 4 139 |
| Couples actifs dans le Full | 345 |
| Couples actifs reconstruits au même instant | 345 |
| Divergences | 0 |
| Anomalies nouvelles en 2026 | 0 |

La correction CFI exclut d'un Full `FULINS_E` les instruments ayant quitté la famille action, sans supprimer leur historique. Le cas déclencheur était `BE0974269012 / XPAR`, passé de `ESVUFR` à `CBMIXX` le 11 juillet 2025.

## Couverture barres–référence

Le rapport `artifacts/fr/esma_firds/replay_2018/bar_coverage_2018_2026.json` porte sur les 490 candidats préqualifiés :

| Catégorie | Barres |
| --- | ---: |
| ISIN courant avec MIC cible action observé | 772 282 |
| Barres invalides ou volume nul | 25 786 |
| Journée sans publication Delta | 9 925 |
| Aucun MIC cible observé pour l'ISIN courant | 2 361 |
| CFI sorti de la famille action | 97 |
| Avant le premier Full | 1 503 |

Cette jointure est diagnostique. Le manifeste final utilise les versions CFI au jour considéré et est donc plus strict que cette synthèse historique par intervalles.

## Contre-vérification indépendante des prix

Yahoo a été interrogé pour les 490 candidats sur 2018–2026 :

| Résultat | Titres |
| --- | ---: |
| Historique reçu et comparé | 325 |
| Échec | 165 |
| Échecs concernant des radiés | 163 |
| Échecs concernant des actifs | 2 |

Yahoo est une corroboration indépendante gratuite, pas une preuve officielle ni une archive PIT. Les exports Euronext officiels disponibles sont également intégrés sur leurs fenêtres exactes ; toute date présentant un écart de champ est exclue de la preuve de prix.

## Manifeste instrument/date

Le générateur est `service/fr/sprint5_limited_manifest.py`. Les sorties se trouvent dans `artifacts/fr/sprint5_limited_2018_2026/` :

- `bar_manifest.jsonl.gz` : une décision par symbole et séance ;
- `report.json` : synthèse, empreintes des entrées, motifs de rejet et couverture annuelle ;
- `research_j1_symbols.txt` : titres possédant au moins une ligne de recherche admissible ;
- `canonical_strict_symbols.txt` : vide tant qu'aucune ligne ne satisfait toutes les preuves strictes.

Empreinte SHA-256 du manifeste produit :

```text
e8c13cb669792ebbc4128bf51a5be23baa68204e0f8f40f218a514599ee9a66a
```

Le manifeste contient 811 954 barres :

| Décision | Barres |
| --- | ---: |
| `RESEARCH_J1_ELIGIBLE` | 561 001 |
| `REJECTED` | 250 953 |
| `CANONICAL_STRICT_ELIGIBLE` | 0 |

Le sous-ensemble J+1 comporte 330 titres et 2 209 séances. Sa largeur quotidienne est de 71 titres au minimum, 257 en médiane, 292 au percentile 95 et 305 au maximum.

## Source indépendante des titres radiés

Le collecteur `service/fr/euronext_delisted_reference.py` interroge l'historique public du site Euronext. Il découvre le MIC de chaque ISIN, reproduit la requête du navigateur, déchiffre la réponse publiée par le site, normalise les OHLC et compare chaque séance avec l'archive EODHD. Une date n'est corroborée que si les quatre prix sont présents et concordent à 0,1 % près.

Résultat au 3 octobre 2026 :

| Mesure | Résultat |
| --- | ---: |
| Radiés récents candidats | 34 |
| Radiés ayant au moins une séance exacte | 34 |
| Taux de couverture du lot ciblé | 100 % |
| Séances OHLC exactes conservées | 5 733 |
| Journées présentant au moins un écart | 2 187 |
| Archives normalisées et empreintes SHA-256 | 34 |

Les archives auditables sont dans `artifacts/fr/euronext_delisted_reference/normalized/`. Le rapport `artifacts/fr/euronext_delisted_reference/report.json` conserve, pour chaque titre, l'ISIN, le MIC, l'URL de page, la fenêtre, les dates exactes, les écarts, l'empreinte de la réponse chiffrée et celle de l'archive normalisée.

La source publique ne remonte qu'environ deux ans. Elle ne remplace donc pas une archive historique Euronext licenciée. Elle couvre toutefois les radiés récents nécessaires au gate pré-enregistré, sans extrapoler les dates non concordantes.

### Limite TLS du POC

Le magasin `certifi` de l'environnement virtuel ne reconnaît pas la chaîne locale, tandis que Windows valide la page Euronext. La collecte a donc été exécutée avec l'option explicite `--insecure-tls`, sans identifiant ni secret. Le rapport porte `tls_verified=false`.

Conséquences :

- les lignes comptent comme corroboration indépendante pour `RESEARCH_J1` ;
- elles ne comptent pas comme preuve officielle canonique ;
- une promotion future impose de corriger la chaîne CA et de recollecter avec validation TLS active.

## Gate anti-survivance

Sur les 330 titres admissibles :

| Statut fournisseur actuel | Titres |
| --- | ---: |
| Actifs | 294 |
| Radiés | 36 |
| Part des radiés | 10,91 % |

Les 36 radiés comprennent les 34 nouvellement corroborés par Euronext et les 2 déjà corroborés précédemment. La politique exige au moins 20 radiés et 10 % de radiés dans le sous-ensemble admissible : les deux conditions passent.

Le verdict produit est donc :

```text
GO_RESEARCH_J1
```

Ce verdict autorise une recherche historique contrôlée. Il ne signifie ni `GO_CANONICAL_STRICT`, ni aptitude live, ni disponibilité pour le serving.

## Motifs de rejet encore présents

| Motif | Barres |
| --- | ---: |
| Corroboration indépendante absente | 230 628 |
| Barre invalide ou volume nul | 25 786 |
| Journée Delta manquante | 10 072 |
| Aucun MIC action actif observé | 3 045 |
| Avant le premier Full | 1 514 |
| CFI non-action | 164 |
| Plusieurs MIC actifs ambigus | 14 |

Les actions sur titres économiques, la preuve PIT historique stricte et le transport TLS Euronext restent insuffisants pour une promotion canonique. `canonical_strict_symbols.txt` demeure vide.

## Ce qui est autorisé

Le sous-ensemble J+1 peut désormais servir à :

- entraîner et évaluer un modèle de recherche France avec séparation temporelle stricte ;
- construire des folds incluant explicitement les radiés disponibles ;
- mesurer Oracle Extreme et les diagnostics D1/D10 en mode recherche ;
- exécuter des replays économiques après contrôle séparé des actions sur titres ;
- comparer les résultats avec et sans radiés pour mesurer le biais résiduel.

Il reste interdit de :

- publier ces données dans les tables canoniques ;
- utiliser ce manifeste en live, paper trading ou serving ;
- considérer les rendements économiques comme validés lorsque l'action sur titre ne l'est pas ;
- étendre une corroboration à des dates non présentes dans `corroborated_dates`.

## Commandes reproductibles

Collecte Euronext des radiés récents :

```powershell
python -u -m service.fr.euronext_delisted_reference --cutoff 2024-10-03 --minimum-rows 1 --insecure-tls
```

Le mode `--insecure-tls` est uniquement le contournement documenté de ce poste. Il doit être supprimé après correction du magasin CA.

Construction du manifeste :

```powershell
python -u -m service.fr.sprint5_limited_manifest --history artifacts/fr/esma_firds/replay_2018/history_2026_observed_v2.json --yahoo-report artifacts/fr/yahoo_daily_reference/limited_490_2018_2026.json --euronext-delisted-report artifacts/fr/euronext_delisted_reference/report.json --output-root artifacts/fr/sprint5_limited_2018_2026
```

Le Sprint 5 est maintenant **clos avec un GO limité à la recherche J+1 sur 2018–2026**. Le gate anti-survivance pré-enregistré passe, mais aucune promotion canonique ou production n'est autorisée.

