# Filtre de rentabilité après Oracle parcours — TP10/SL10

> Version initiale conservée. Avant tout label/fit/replay, l'utilisateur a choisi
> **TP15/SL7** : lire le [protocole actif amendé](oracle_path_profit_filter_tp15_sl7_20261015.md).
> Les valeurs TP10/SL10 ci-dessous décrivent uniquement la préparation initiale,
> sans changement des anciens résultats.

## Décision du point 2

GO du 15 octobre 2026 : **audit de non-doublon et préparation du protocole**,
avant tout nouvel entraînement. Travail préparatoire terminé, statut
`PREPARED_NOT_TRAINED`. Aucun résultat prédictif ou gain économique nouveau.

**Le principe n'est pas nouveau dans α-Trade.** E3 et le challenger d'entrée du
13 octobre prédisaient déjà un résultat de trade net, y compris les expirations
profitables. Ne pas présenter « passer du rendement H20 au chemin » ou « compter
les expirations positives » comme une découverte absente de ces expériences.

Il reste une différence vérifiable pour une **réplication bornée** : conditionner
un seul filtre LONG par le classement CatBoost de l'Oracle **parcours actuel**,
sur ses **20 premiers titres**, avec le contrat TP10/SL10 utilisé dans les
[témoins GPT appariés](news_gpt_comparaison_long_tp10_sl10.md).
Ce n'est ni un TOP20 % de l'univers, ni un nouvel Oracle, ni une preuve que la
direction devient prédictible. Le verdict de l'audit est
`PARTIAL_DUPLICATE_BOUNDED_REPLICATION_ONLY`.

## Ce qui a déjà été tenté

| Expérience / sources relues | Ce qui est commun | Différence réelle avec ce protocole | Résultat conservé |
| --- | --- | --- | --- |
| [E3-A](shared_directional_oracle_events.md#e3--deux-têtes-de-rentabilité-conditionnelles-au-chemin), `modelFactory/path_aware_directional.py` et `modelFactory/labeling.py` | Filtre conditionnel Oracle, gains nets LONG/SHORT, expirations positives | Ancien Oracle terminal TOP20 %, deux têtes, SL 2,5 ATR, TP 3 ATR plafonné à 7 %, expiration au close, pas de protection le jour d'entrée | LONG AUC 0,541 mais lift économique −0,064 point ; NO_GO |
| [E3-A2](path_aware_economic_utility.md), `modelFactory/path_aware_utility.py` | Résultat économique conditionnel | Régression d'utilité avec pénalité de risque ; pas ce seul filtre binaire | Pas d'avantage stable |
| [Challenger d'entrée du 13/10](oracle_challengers_20261013.md), `scripts/research/us_oracle_challengers.py` | Petit LightGBM, probabilité de gain net, prochain open, seuil 0,50 et expirations positives | Oracle TP-avant-SL TP20/SL10 et ses deux scores ; TOP10 primaire ; coûts unitaires plats approximés | AUC validation 0,50021 ; aucune entrée au seuil fixé |
| [Oracle TP avant SL](oracle_barrier_training.md), `modelFactory/oracle_barrier/labels.py` | Course de barrières depuis l'open J+1 | Cible « TP avant SL » : une expiration bénéficiaire sans TP vaut zéro ; deux côtés indépendants ; ce n'est pas la cible de gain net | Ne pas confondre son score avec une probabilité de bénéfice |
| [Séparabilité du 14/10](oracle_path_filtre_entree_separabilite_20261014.md) | Oracle parcours et features de J | Audit univarié, TP20 avant SL10, Oracle amont LightGBM ; pas de classifieur multivarié de gain net | Aucune séparation univariée stable |
| [Sélecteur de protections du 14/10](oracle_path_selecteur_protections_20261014.md) | Modèles annuels CatBoost actuels, mêmes 24 variables causales préparées | TOP5, trois profils, SL5/trailing, horizon de 60 séances ; choix de protections et non acceptation d'entrée | NO_GO ; profil LARGE presque toujours choisi |

Ces échecs ne prouvent pas l'impossibilité de tout signal, mais interdisent de
relancer ces mêmes formulations sous un nouveau nom. Aucun balayage de cinq
horizons, de multiples TP/SL, de plusieurs familles de modèles ou de nouveaux
seuils de confiance GPT n'est prévu ici.

## Données effectivement vérifiées

Audit local sans accès SQL ni fournisseur. Les empreintes des données/prix et
poids utilisés sont vérifiées sur leurs **octets bruts** ; aucun ancien manifeste
n'est modifié ou rendu plus permissif. Le problème de conversion LF/CRLF du
précédent replay n'est pas contourné : cette préparation lie les sources relues
à leurs octets actuels et vérifie séparément les données immuables.

### Historique hors échantillon

Archives :
`artifacts/research/us_oracle_path_protection_dataset/20261014-v1/folds` et
`artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path`.

- Dix folds causaux, du 5 juillet 2018 au 7 juillet 2023.
- **2 152 562 scores observables**, avant exclusion selon la qualité future.
- Comparaison aux **2 146 823 anciens scores OOF** sur leur sous-population :
  écart maximal **zéro**, contrôlé à nouveau sur chaque fold.
- **25 200 candidats**, 1 260 séances, 293 titres distincts apparus au TOP20.
- Univers amont figé de 1 790 titres, pas un univers historique sans biais de survie.
- 72 tranches de prix existantes, **3 409 276 lignes** : empreintes et présence
  des champs OHLCV, identité, source, ajustement et `is_filled` vérifiées.

| Année historique | Séances | Candidats avant labels et contrôles |
| --- | ---: | ---: |
| 2018 partielle | 124 | 2 480 |
| 2019 | 252 | 5 040 |
| 2020 | 253 | 5 060 |
| 2021 | 252 | 5 040 |
| 2022 | 251 | 5 020 |
| 2023 jusqu'au 7 juillet | 128 | 2 560 |

Le nouveau fichier `historical-top20.parquet` ne conserve que date, symbole,
score, fold et rang. Ni rendement futur, ni label, ni filtre de qualité future.
Il est reconstruit depuis **tout** le pool observable ; les anciens fichiers
OOF contenant seulement les labels qualifiés ne définissent pas le TOP.

Les anciens résultats TOP5 à 60 séances ne sont **pas** recyclés comme des labels
TOP20 TP10/SL10. La matrice complète des nouvelles features et les nouvelles
cibles restent à construire et à qualifier.

### Périodes récentes déjà explorées

| Année | Modèle annuel demandé | Fold réellement utilisable | Candidats bruts / admissibles à J |
| --- | --- | --- | ---: |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 | 5 040 / 5 040 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 | 5 000 / 5 000 |
| 2026 au 30/09 | `model-factory-20261014113232-bc35a7` | 2025-12-10 | 3 740 / 3 718 |

689 séances, 13 780 candidats, 13 758 admissibles à J. Backend, poids, profil
de features et disponibilité des labels du fold antérieure à la première
décision vérifiés. La date de fin demandée pour une campagne annuelle ne suffit
pas à prouver la causalité : c'est le **fold sélectionné** qui est contrôlé.

Les 22 rejets de 2026 restent des rejets à J, pas des perdants supprimés après
coup ; pas de remplacement par le rang 21. Tous les candidats et motifs sont
à conserver. Les années récentes ont déjà été vues : **ce ne sont pas des
holdouts vierges**, même avec un nouveau nom de modèle.

## Contrat fixé pour l'éventuel filtre

Spécification versionnée :
`config/research/oracle_path_profit_filter_tp10_sl10.json`.
Cette configuration de **recherche** n'est lue par aucun batch ou pipeline live.

### Cible : le trade, pas la direction du maximum futur

- Signal après clôture J ; entrée à l'open de la séance suivante J+1.
- Ordre de référence de **1 600 USD évalué au close J**, quantité fractionnaire
  `1600 / close_J`. C'est un ticket standard pour comparer les exemples,
  **pas** le sizing des futurs portefeuilles.
- Gap d'entrée absolu >3 % : ordre non exécuté, cible inconnue, pas une perte.
- TP +10 % et SL −10 % du fill, sans trailing, protections dès la séance d'entrée.
- Surveillance J+1…J+20 ; expiration à l'open J+21 après vingt séances détenues.
- Gap défavorable : prix d'ouverture, perte possiblement supérieure à 10 %.
  Gap au-dessus du TP : prix limite du TP, pas amélioration fictive au gap.
- Double contact OHLC sans ordre connu : scénario conservateur SL d'abord,
  avec indicateur d'ambiguïté conservé ; ne pas prétendre connaître la séquence.
- Résultat net strictement positif = 1, négatif ou nul = 0. Une expiration à
  +4 % peut donc être gagnante même sans avoir atteint le TP.
- Chemin incomplet, immature ou changement d'identité non qualifié : `NULL`
  avec motif, jamais transformé en zéro ni remplacé par le prochain titre.
- Disponibilité conservatrice **J+22 pour toutes les issues**, même les TP précoces.

**Pas de raccourci « rendement brut −16 bps = PnL natif ».** Le futur labeler
devra utiliser les fills et coûts transactionnels du moteur natif dans un replay
isolé, puis vérifier une parité sur cas synthétiques et exemples réels. Le
prototype de cibles n'est pas encore implémenté ni déclaré conforme.

La cible inclura une hypothèse explicite de financement de référence : 50 % du
notionnel réellement rempli, taux 6,5 %/an ACT/360, nombre de nuits calendaires
entre entrée et sortie. Cette charge est standardisée, **pas** le débit du compte
réel. Résultat cible = proceeds de sortie − outlay d'entrée − coûts natifs −
financement de référence, rapporté au notionnel rempli. Éviter de déduire deux
fois les frais déjà présents dans les cash-flows.

Cela mesure la rentabilité d'un **trade théorique standardisé**, pas le PnL
exact de chaque future décision : celui-ci dépend du capital, du sizing,
des autres positions, du régime et du financement effectivement consommé.
Seul le replay de portefeuille pourra trancher ce second point.

### Entrées du modèle

24 colonnes fixées : 16 variables titre de prix/volume/volatilité, sept variables
prix SPY/force relative et le rang Oracle. La liste exacte est dans le JSON.
Réutilisation des calculs `decision_features` déjà préparés ; contrôle sur
préfixes arrêtés à J avant tout apprentissage. Historique propre de 121 séances
titre avec identité stable et de 201 séances benchmark, variables finies.

Pas de GPT, texte/news non qualifié PIT, consensus, secteur courant, identifiant
du titre, année, VIX/VXN/MOVE sans preuve de publication, ou données de J+1.
Les variables « régime » de ce petit filtre sont calculées sur les **prix SPY**,
pas des observations macro prétendument connues à une heure non documentée.
Le score Oracle absolu reste hors des inputs, son rang est conservé ; les 173
features de l'Oracle amont gardent leurs réserves de lineage historiques.

Ce filtre ne reçoit aucune nouvelle famille d'information directionnelle.
Un éventuel échec ne serait pas réparé en ajoutant opportunément une variable
qui explique les pertes de 2026 après les avoir vues.

### Apprentissage et séparation chronologique proposés

| Période | Rôle | Disponibilité exigée |
| --- | --- | --- |
| OOF 2018–2021 | Fit du petit filtre | Labels strictement avant le 01/01/2022 |
| 2022 | Validation / early stopping | Labels strictement avant le 01/01/2023 |
| 2023 OOF partielle | Contrôle sans retouche | Labels strictement avant le 01/01/2024 |
| 2024–septembre 2026 | Comparaison exploratoire externe | Aucune influence sur fit, seuil, features ou choix de paramètres |

La purge porte sur la date de disponibilité complète J+22, pas seulement J.
Tout résultat encore immature en 2026 reste inconnu ; la dernière date évaluable
sera calculée depuis la bande de prix figée, pas présumée égale au 30 septembre.

Un seul LightGBM binaire, profondeur 3, sept feuilles, au maximum 150 itérations,
early stopping 15, seed 20261015 ; pas de recherche d'hyperparamètres ni de
comparaison de backends. Poids total égal par séance dans le fit. Seuil **0,50**,
pas de recalibrage ou refit après lecture des périodes externes. Une probabilité
constante égale à la prévalence pondérée du fit sert de témoin statistique.

Gates préparés avant tout label/fit de cette réplication : couverture et deux
classes suffisantes ; AUC moyenne quotidienne ≥0,53 ; Brier meilleur que le
témoin constant ; 20–80 % de candidats acceptés ; lift net apparié aux mêmes
dates positif avec borne basse bootstrap par blocs de 63 séances >0. Les tailles
minimales et 999 tirages sont fixés dans le JSON. Même exigence sur le contrôle
2023 ; **aucune retouche** si un gate échoue. Ces gates restent exploratoires,
pas une certification d'indépendance de chemins H20 qui se recouvrent.

Le lift diagnostique compare le rendement unitaire moyen des acceptés à celui
du pool initial évaluable **aux mêmes dates où le filtre accepte**, dates à poids
égal ; rapport séparé du nombre de dates sans acceptation et de la couverture.
Il n'est pas assimilé au rendement d'une stratégie en cash les autres jours.
Les blocs se forment sur le calendrier complet puis conservent ces mesures
appariées ; les exemples n'ont pas le statut de trades indépendants.

### Portefeuille ultérieur, seulement si les gates passent

Deux bras : acheter tous les candidats admissibles, ou appliquer le filtre.
Toujours LONG TP10/SL10, pas de changement des protections. Même ordre Oracle,
pas de reclassement par probabilité ni remplacement des refus.

Contrat des témoins du point 1 : 4 000 USD par an, levier d'entrée maximal x2,
cap position 40 %, risque `0,4 × SL` avant gardes natives, pas de renforcement,
mêmes régimes/risque/coûts/événements/financement et mêmes queues de cohorte.
Un problème de données sur une position détenue fera échouer le replay ; il ne
permettra pas de supprimer le perdant. Comparer bornes civiles **et** queues,
gains/pertes, DD, taux gagnant, trades, positions ouvertes, coûts, financement,
exposition et concentration. Mêmes règles ne signifient pas même exposition.

Un bon taux gagnant ou une AUC légèrement supérieure à 0,50 ne suffira pas à
promouvoir le filtre. Aucun mécanisme d'activation live n'est livré ici.

## Livrables, tests et suite bornée

Préparateur : `scripts/research/us_oracle_path_profit_filter_protocol.py`.
Tests : `tests/test_us_oracle_path_profit_filter_protocol.py`.
Dossier vérifié : `artifacts/research/us_oracle_path_profit_filter/20261015-protocol-v1`.

- `protocol.json` : copie immuable de la spécification ;
- `non-duplication.json` : anciens essais, points communs et différences ;
- `historical-top20.parquet` : population avant tout label ;
- `manifest.json` : entrées/poids/prix/sources et leurs empreintes ;
- `readiness.json` : inventaire et étapes explicitement non réalisées ;
- `report.json` : `PREPARED_NOT_TRAINED`, zéro fit/cible/PnL calculé.

Vérification finale séparée : **235 entrées** et les cinq sorties liées au
rapport revérifiées par SHA256 ; égalité de la spécification copiée, bornes de
dates, clés uniques, 20 lignes par séance et ordre score/symbole contrôlés.
**31 tests ciblés passent** : 15 de préparation (absence de futur dans le TOP,
causalité des folds, purge et empreintes), plus les 16 tests existants de
comparaison/protections TP10/SL10. Ils ne valident pas un nouveau labeler encore
absent. Première tentative de tests bloquée par les permissions du répertoire
temporaire Windows ; reprise autorisée réussie, sans changement fonctionnel.

```powershell
python -u -m scripts.research.us_oracle_path_profit_filter_protocol --output artifacts/research/us_oracle_path_profit_filter/20261015-protocol-v1
```

La reprise recontrôle sources, spécification et sorties sans réécrire les
résultats ; une modification impose un nouveau dossier. Première tentative
préparatoire arrêtée sur une vérification trop littérale du backend : la valeur
matérielle du contrat est `catboost_cpu`, son `training_backend` est `catboost`.
Le préparateur contrôle maintenant les deux champs **et** le poids du fold,
sans toucher aux modèles ou à leur contrat. Aucun label/fit/backtest n'avait
été calculé lors de cet arrêt.

**Prochaine action après nouveau GO** : implémenter et valider les cibles
TP10/SL10 et leur parité native, construire les features J du TOP20 et vérifier
couverture/purge. Lancer alors le seul petit fit si ces contrôles passent ;
arrêter si les gates de validation/contrôle échouent. Ne pas partir directement
sur des backtests 2024–2026 ni sur de nouveaux seuils GPT.

Les prix historiques ajustés actuels, l'univers survivant et le lineage de
l'Oracle amont ne constituent pas une preuve PIT complète. Les secteurs/macro
du futur portefeuille conservent aussi leurs réserves ; dividendes et marge
historiques ne sont pas entièrement qualifiés. Une confirmation prospective
vraiment nouvelle serait nécessaire avant de prétendre avoir un filtre exploitable.
