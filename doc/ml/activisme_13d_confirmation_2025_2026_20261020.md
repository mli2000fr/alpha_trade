# Activisme 13D — confirmation sur 2025 et janvier–septembre 2026

## Conclusion

**Terminé. L’avantage observé sur les sept cas de 2024 ne se confirme pas de
façon stable sur 2025–2026. Aucune promotion en production.**

Les interventions ont été sélectionnées et documentées avant le calcul de leurs
rendements. Même règle LONG, mêmes horizons et coûts que l’étude 2024 : ni
nouveau filtre choisi après les pertes, ni sélection du meilleur horizon.

| Année de dépôt | Horizon, séances entrée comprise | Admis | Évaluables | Prix inconnus | Non échus au 30/09/2026 | Positifs / négatifs | Net moyen par occasion | SPY mêmes dates, net | Écart moyen à SPY |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 20 | 10 | 9 | 1 | 0 | 4 / 5 | **−0,94 %** | −1,24 % | +0,29 point |
| 2025 | 60 | 10 | 9 | 1 | 0 | 1 / 8 | **−6,67 %** | +2,22 % | −8,89 points |
| 2026, jusqu’au 30 septembre | 20 | 9 | 5 | 3 | 1 | 1 / 4 | **−13,50 %** | −2,96 % | −10,54 points |
| 2026, jusqu’au 30 septembre | 60 | 9 | 3 | 3 | 3 | 1 / 2 | **+2,97 %** | +6,80 % | −3,83 points |

Les moyennes portent uniquement sur les issues qualifiées. Les inconnus restent
dans le nombre d’admis : **ce n’est pas une estimation du rendement des dossiers
manquants**, ni une couverture exhaustive de toutes les campagnes historiques.
Les mêmes entrées aux deux horizons ne sont pas des observations indépendantes.

Le chiffre positif de 2026 à 60 séances n’est pas une validation : seulement
trois issues, dont CODI à +41,38 %, contre deux pertes. La médiane vaut
**−14,35 %**, et la moyenne reste sous SPY. En 2025, la médiane est −5,81 %
à 20 séances et −5,90 % à 60 ; en 2026, −16,08 % à 20 séances.

Il s’agit de rendements par occasion, sur un notionnel indépendant, **pas de
rendements annuels d’un portefeuille partagé**. Le résultat 2024 déjà observé
(+4,16 % / +8,97 % aux horizons 20/60) reste conservé, sans le présenter comme
une nouvelle confirmation hors échantillon.

## Dossiers et résultats individuels

Tous les nombres ci-dessous sont nets des coûts hypothétiques figés.

| Année | Titre | Entrée | Net 20 séances | Net 60 séances |
|---|---|---|---:|---:|
| 2025 | CAE | 18 février | −9,48 % | −4,03 % |
| 2025 | SIG | 28 février | +11,64 % | +16,55 % |
| 2025 | TDC | 24 mars | −15,27 % | −5,90 % |
| 2025 | ANTX | 8 mai | Prix inconnus | Prix inconnus |
| 2025 | CNNE | 10 juin | +6,27 % | −6,52 % |
| 2025 | BILL | 5 septembre | +8,19 % | −0,32 % |
| 2025 | STAA | 23 septembre | −6,37 % | −8,30 % |
| 2025 | ACHC | 2 octobre | −7,12 % | −40,81 % |
| 2025 | PBT | 13 octobre | +9,45 % | −2,21 % |
| 2025 | TIPT | 13 novembre | −5,81 % | −8,49 % |
| 2026 | EMPD | 4 février | Prix inconnus | Prix inconnus |
| 2026 | SEER | 23 février | Prix inconnus | Prix inconnus |
| 2026 | CODI | 26 février | −23,04 % | +41,38 % |
| 2026 | PAR | 5 mars | −31,96 % | −18,12 % |
| 2026 | LODE | 26 mars | Prix inconnus | Prix inconnus |
| 2026 | ALKT | 30 juin | +6,66 % | −14,35 % |
| 2026 | UMH | 12 août | −3,07 % | Non échu |
| 2026 | HGV | 17 août | −16,08 % | Non échu |
| 2026 | MTN | 17 septembre | Non échu | Non échu |

« Non échu » s’entend **à la borne de prix figée du 30 septembre 2026**, pas
nécessairement à la date où le lecteur consulte ce document. Sorties requises :
MTN 14 octobre / 10 décembre, UMH H60 4 novembre, HGV H60 9 novembre.
Aucune extension de la borne pour améliorer le résultat.

Les identités historiques des quatre titres sans prix sont confirmées, mais
**ANTX, EMPD, SEER et LODE n’ont pas de barres dans la bande de recherche
normalisée utilisée**. Cela ne signifie pas qu’aucun fournisseur ne pourrait en
fournir. Aucun nouvel appel à une API de prix, remplissage ou remplacement par
un autre titre n’a été effectué.

## Comment l’échantillon a été construit

Index SEC trimestriels complets, puis dédoublonnage des codéclarants par accession
avant la sélection. Une accession est un dépôt, pas une société indépendante.

| Période | Accessions initiales distinctes dans les index | Route du mapping courant | Sondage hors route | Originaux sélectionnés |
|---|---:|---:|---:|---:|
| 2025 Q1–Q4 | 269 / 273 / 278 / 295, soit 1 115 | 23 / 12 / 34 / 21, soit 90 | 40 | 130 |
| 2026 Q1–Q3 | 288 / 286 / 270, soit 844 | 28 / 19 / 15, soit 62 | 30 | 92 |

**222 originaux obtenus et extraits**, chacun avec une décision et ses clauses
sources exactes. Le sondage ajoute dix accessions hors route par trimestre,
par plus petit SHA256 de l’accession, sans prix ni résultat futur.

La lecture de SUBJECT COMPANY évite **26 fausses attributions** : un CIK indexé
peut être celui du déclarant, pas celui de la société visée. Il reste
126 dossiers visant une cible de l’univers actuel, plus 70 du sondage, soit
196 dossiers cibles à qualifier. Les 19 admissions résultent d’une intervention
explicite ; le reste n’est pas automatiquement une occasion directionnelle.

Le mapping de départ reste celui de **1 790 titres actuels**. Le sondage hors
route ne reconstitue ni un univers historique PIT ni le recensement des radiés.
Les quatre absents des prix soulignent justement cette limite. L’étude ne
prétend donc pas mesurer l’effet de l’activisme sur toutes les sociétés cotées.

## Qualification documentaire et identités

La grille exige une action précise : lettre publique, demande spécifique déjà
faite, nomination annoncée explicitement, coopération ou opposition à une vente.
Les simples « peut discuter / pourrait nommer », participations ordinaires,
financements, transferts et acquisitions de contrôle restent hors groupe.

Des sous-types sont conservés plutôt que confondus : nomination consensuelle CAE,
plan de nomination annoncé BILL, demandes privées TDC/SEER/ALKT, oppositions
STAA/TIPT, coopération LODE, demande de représentation HGV et nominations MTN.
HGV n’est pas présenté comme une nomination formellement déposée, ni BILL comme
une liste de candidats déjà remise. Les offres de rachat/privatisation ne sont
pas assimilées à une campagne activiste minoritaire.

**PBT est un trust de redevances : unités de beneficial interest, pas actions
ordinaires d’une entreprise opérationnelle.** Son projet de transformation et
sa classe cotée sont explicitement signalés, sans exclusion décidée après PnL.

Quatre dossiers restent réservés, indépendamment de leurs prix : BTMD et SBLK
(nomination d’un administrateur sans preuve suffisante d’une intervention
actuelle), SCWO (lettre future non certifiée remise), GPI (discussion préliminaire
de siège). Ils ne sont ni promus pour augmenter le nombre de cas, ni déclarés
automatiquement exempts de toute intervention.

Les 19 identités admises sont qualifiées avant les prix : rapports annuels
10-K/20-F/40-F strictement antérieurs au dépôt, puis deux compléments séparés :

- **PBT** : couverture du 10-K déposé le 14 mars 2025, clause exacte
  « Units of Beneficial Interest PBT New York Stock Exchange ». Le lecteur
  inline-XBRL initial était trop restrictif pour cette couverture HTML classique.
- **EMPD** : le dernier rapport annuel portait encore Volcon/VLCN. Le 10-Q
  déposé le **10 novembre 2025**, antérieur au 13D du 3 février 2026, établit
  la nouvelle identité et le ticker EMPD.

Le premier rapport automatique, 17 identités confirmées sur 19, est conservé.
Le complément `identity-qualified-v1.json` le complète sans l’écraser et sans
changer les admissions. Même assistant pour la revue documentaire et les
contrôles : **pas une seconde revue humaine indépendante**.

## Calendrier et calcul économique inchangés

- LONG uniquement ; première ouverture NYSE complète strictement après la
  **date de dépôt**, acceptation SEC aussi vérifiée avant cette ouverture.
- Blocage de réentrée du même **CIK** pendant 60 séances, appliqué avant la
  qualité future des prix et de part et d’autre du changement d’année.
- Sortie à la clôture des 20e/60e séances, **séance d’entrée comprise**.
- 1 000 USD notionnels indépendants par entrée ; unités fractionnaires sur
  prix ajustés, pas remplissage d’ordres historiques certifié.
- 1 USD par ordre exécuté ; spread 5 bps + slippage 5 bps **par jambe**, sur
  les montants d’entrée et de sortie. Stress : 25 bps au total par jambe.
- Pas de TP, SL, trailing, levier, cash partagé ou rotation de portefeuille.
- SPY mêmes dates, mêmes coûts ; comparaison appariée, pas causalité ou
  portefeuille bêta-couvert. Les données ajustées ne remplacent pas une
  certification du lifecycle complet des opérations sur titres.

Pour le rendement brut `r`, le rendement net utilisé est :

```text
net = r − 2 / 1000 − 0,001 × (2 + r)
```

Stress net moyen : 2025 **−1,24 % / −6,96 %** ; 2026 **−13,78 % / +2,66 %**,
aux horizons 20/60. Les coûts supplémentaires ne changent pas la conclusion.

Plusieurs lettres/campagnes précèdent leur 13D : CNNE décembre 2024, UMH juillet
2026, notamment. L’expérience mesure l’entrée après dépôt, **pas la première
annonce mondiale**. Les originaux ont été téléchargés en octobre 2026 : leur
réception locale historique n’a pas été inventée.

## Rapport avec Oracle

Scores annuels PATH_H20 CatBoost de recherche déjà figés, dernière clôture NYSE
avant l’entrée. Aucun entraînement ou changement de champion ici.

Parmi les cas économiquement évaluables, **aucun TOP10** ; quatre appartenances
au TOP20 % en 2025, trois en 2026. Les trois cas H60 évaluables de 2026 sont
déjà ces trois cas TOP20 %, pas six occasions différentes. Le contexte Oracle
absent reste inconnu, pas « hors TOP » ; le dernier score 2026 disponible dans
cette archive précède le dépôt MTN.

**Cette piste ne résout donc pas la direction du TOP10 Oracle.** Les observations
rares ne justifient ni un modèle dédié, ni un filtre automatique LONG/SHORT.

## Archives, audit et reproductibilité

Racine : `artifacts/research/us_activist_13d/confirmation-2025-2026-20261020-v1/`.

- `protocol.json`, `selection.json` : critères, plafonds, index complets et
  sélection sans prix ; index 2025 déjà acquis réutilisés.
- `http/`, `documents.json`, `extraction.json`, `review/` : reçus, URL, originaux,
  horodatages réels, empreintes et extractions des 222 dossiers.
- `doc/ml/sources/activist_13d_confirmation_review_20261020.json` : toutes les
  décisions, motifs et clauses exactes ; `review-frozen-v1/` : gel avant prix.
- `replay-confirmation-final-v1/` : protocole, prix sources, contexte Oracle,
  entrées du calcul, `event-results.csv`, `report.json` et `audit.json`.

L’audit technique reconstitue la sélection, reparse les originaux, vérifie les
citations/identités, les dates, le blocage par CIK, les maturités, les inconnus,
les prix/rangs archivés et recalcule séparément les coûts/rendements et les
agrégats. Il ne constitue pas une revue humaine indépendante des décisions.

Les scripts `us_activist_13d_confirmation*.py` et leurs tests sont séparés des
modules 2024 scellés. Le calcul effectif est `us_activist_13d_confirmation_final` :
il préserve les inconnus/non-échus en `null` JSON, jamais NaN ni zéro. L’ancienne
fonction `confirmation_replay.replay` n’est pas le point d’entrée de ce bilan.
Les sorties sont immuables ; ne pas relancer dans un dossier déjà rempli.

Audit : `PASS_EXPLORATORY_2025_2026_WITH_COVERAGE_RESERVES`. Les **222 originaux**
ont été reparsés, les **19 identités** contrôlées et les **38 lignes
événement/horizon** conservées : 26 évaluables, huit inconnues, quatre non
échues. Les 26 calculs titre/SPY et 2 000 barres ajustées archivées sont
rapprochés. Un audit technique passant ne signifie pas un signal rentable.

**265 nouvelles requêtes SEC**, toutes HTTP 200, **136 155 856 octets lus** ;
les quatre index 2025 réutilisés ne sont pas comptés comme nouveaux appels.
TLS vérifié, contact SEC réel déclaré, appels sériels espacés de 0,6 seconde,
plafonds de taille/durée/requêtes et arrêt sur refus, sans contournement.

**43 tests ciblés**, couvrant aussi les études antérieures. Aucune écriture SQL,
modification de modèle, univers, configuration métier ou batch ; aucun appel
LLM, entraînement, ordre, nouvel appel de prix ou calcul laissé en cours.

## Suite

Clôturer cette expérience comme **non confirmée sur 2025–2026**, sans optimiser
un nouveau filtre sur ses pertes. Une couverture de prix des quatre dossiers
manquants ou une revue réellement indépendante pourrait compléter l’étude,
mais ne garantit pas d’inverser son résultat. Aucun déploiement automatique.

Voir [l’extension 2024](activisme_13d_elargissement_20261020.md) et le
[registre des expériences](experiences_done.md).
