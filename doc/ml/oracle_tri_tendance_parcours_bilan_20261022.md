# TOP10 Oracle parcours — trier la tendance pendant vingt séances

## Conclusion

**Audit terminé : aucun tri univarié stable validé, aucun modèle entraîné.**
La question a bien été changée : l'objectif n'est plus le seul rendement à H20,
mais la progression moyenne pendant les vingt séances, sa persistance et le
recul contraire avant son sommet. Le meilleur indicateur en découverte donne
un résultat intéressant en 2025–2026, mais échoue en validation 2022 et à la
correction des essais multiples. Il n'est donc pas promu ni optimisé après coup.

Référence : [protocole figé](oracle_tri_tendance_parcours_protocole_20261022.md).

## Ce qui a réellement été testé

- Dix premiers scores **Oracle parcours CatBoost**, sans ATR/GPT/consensus,
  avant toute qualification future. Pas le TOP20 % de l'univers.
- Historique OOF 2018–juillet 2023 ; modèles annuels `437ed1`, `102eca`, `bc35a7`
  pour 2024/2025/2026. Aucun poids recalculé ou modèle remplacé.
- **19 490 candidats**, 1 949 décisions, 324 titres apparus au TOP10 de l'univers
  amont de 1 790. Ce ne sont pas 324 titres seulement dans l'univers initial.
- Toutes les comparaisons se font à l'intérieur du même TOP10, sur les mêmes
  dates complètes. Reclassement puis sélection de trois ou cinq titres ; acheter
  les dix après reclassement ne changerait pas l'ensemble acheté.
- Dix-huit variables titre/force relative sondées ; cinq variables marché
  communes à une date et rang/score Oracle en témoins. **25 colonnes examinées**,
  pas les 173 features du modèle amont. Pas de recherche de TP/SL ou de backend.

### Cible et interprétation

Entrée théorique open J+1 ; pour chaque clôture jusqu'à J+20, calcul du pourcentage
par rapport à cette entrée. La cible principale est la **moyenne de ces vingt
pourcentages**, pas le rendement du dernier jour, ni une vente au plus haut.

Exemple : rester à +20 % pendant dix-neuf clôtures puis revenir à zéro donne une
aire moyenne de +19 %. Rester à zéro dix-neuf clôtures puis monter à +20 % donne
+1 %. Même rendement final/maximum, mais persistance différente.

Mesures obligatoires séparées : part des clôtures au-dessus de l'entrée,
maximum de clôture et son délai, recul sur les clôtures avant le premier maximum,
excursions intraday et bornes du recul avant le jour du sommet. L'ordre HIGH/LOW
du même jour est inconnu ; il n'a pas été inventé. Les clôtures évitent cette
ambiguïté pour la mesure principale de recul préalable.

Une aire positive n'implique pas une hausse monotone, un SL tenable ni un bénéfice
capturable. Aucun capital, sizing, levier, coût, emprunt ou stop n'est simulé :
**aucun chiffre ci-dessous n'est une performance de portefeuille**.

## Couverture

| Partition | Candidats initiaux hors purge | Dates initiales | Dates TOP10 entièrement qualifiées |
|---|---:|---:|---:|
| Découverte 2018–2021 | 8 600 | 860 | 718 |
| Validation 2022 | 2 300 | 230 | 214 |
| Contrôle 2023 partiel | 1 280 | 128 | 128 |
| 2024 | 2 520 | 252 | 252 |
| 2025 | 2 500 | 250 | 250 |
| 2026 mature | 1 730 | 173 | 161 |

S'ajoutent 420 candidats de bord purgés (21 décisions à chaque frontière), plus
140 candidats récents immatures au cutoff du cache. Total évalué pour les
statistiques principales : **17 230 observations / 1 723 dates / 317 titres**.

Le cache récent s'arrête au 9 octobre : les décisions évaluables 2026 vont du
2 janvier au **10 septembre**. Les quatorze dates immatures sont relatives à
ce cutoff archivé, pas une affirmation de maturité au 22 octobre sans prix.
Douze candidats 2026 échouent aux contrôles à J ; leurs douze dates complètes
sont écartées, sans substitution TOP11. L'historique compte 175 contrôles J
non qualifiés et deux chemins incomplets, avant l'exclusion des autres membres
de leurs dates. Les motifs individuels restent dans `dataset.parquet`.

Les prix sont les **anciens caches EODHD split**, sans téléchargement ni correction
de prix : ce test n'est pas une comparaison SIP/EODHD. Les features utilisent
le générateur adj_close/close archivé ; la cible n'ajoute pas de dividendes aux
OHLC split. Univers survivant, vintages fournisseur et lineage amont non certifiés
PIT strict ; les années récentes ont déjà été observées auparavant.

## Meilleure sonde de découverte — diagnostic, pas signal sélectionné

Le ratio **volatilité20 / volatilité60**, faible d'abord, arrive premier sur
2018–2021. Son orientation reste ensuite inchangée. Ce n'est pas une nouvelle
donnée : c'est une autre utilisation d'une feature déjà présente.

| Période | IC quotidien de classement, sens figé | Gain d'aire TOP3 face à Oracle | Gain d'aire TOP5 face à Oracle |
|---|---:|---:|---:|
| Découverte | +0,0534 | +0,540 point | +0,053 point |
| Validation 2022 | **−0,0674** | **−0,902 point** | **−1,425 point** |
| Contrôle 2023 partiel | +0,0435 | −0,737 point | +0,799 point |
| 2024 | −0,0337 | +0,096 point | +0,043 point |
| 2025 | +0,1101 | +1,972 point | +1,179 point |
| 2026 partielle | +0,0880 | +1,307 point | +1,539 point |

IC = corrélation de Spearman entre rang du score connu à J et rang de la cible,
calculée chaque jour puis moyennée. **Ce n'est pas une AUC ni un taux de trades
gagnants.** Un petit gain de moyenne sur trois titres peut coexister avec un IC
négatif sur l'ordre des dix, comme en 2024.

### Résultats récents, sans les transformer en confirmation réussie

| Année / taille | Aire moyenne Oracle | Aire après tri | Clôtures positives Oracle → tri | Recul préalable Oracle → tri |
|---|---:|---:|---:|---:|
| 2025 / TOP3 | 1,772 % | 3,744 % | 53,33 → 58,73 % | 4,228 → 4,540 % |
| 2025 / TOP5 | 1,908 % | 3,087 % | 53,31 → 57,10 % | 3,971 → 4,289 % |
| 2026 / TOP3 | 2,142 % | 3,449 % | 54,02 → 57,06 % | 4,715 → 4,177 % |
| 2026 / TOP5 | 2,278 % | 3,817 % | 53,57 → 57,41 % | 4,706 → 4,224 % |

2025 améliore aire/persistance mais **augmente le recul préalable** : l'objectif
d'un parcours plus facile à tenir n'est donc pas satisfait dans cette année.
2026 améliore les trois agrégats ; cela ne répare pas les échecs précédents.

Intervalles descriptifs block63 du gain d'aire : TOP3 2025 [+0,701 ; +3,330],
2026 [+0,362 ; +3,774] points ; TOP5 2025 [+0,418 ; +2,014], 2026
[+1,165 ; +2,677]. Ces intervalles n'annulent ni le choix parmi des essais,
ni la réserve d'années déjà examinées, ni les ruptures de régime.

La sélection peut se concentrer sur les mêmes titres : maximum 7,47 %/7,92 %
des observations TOP3/TOP5 2025 sur un seul titre, 7,25 %/6,09 % en 2026.
Le contrôle global à une décision toutes les 21 séances n'a que 12 dates en
2025 et sept en 2026 : trop peu pour affirmer une réplication indépendante.
En TOP5 2026, le gain d'aire subsiste dans ce petit contrôle, mais le recul
préalable augmente de 0,053 point au lieu de diminuer.

Le classement SHORT miroir reste un diagnostic distinct : aire moyenne négative
en 2024–2026. Aucun bénéfice SHORT ou probabilité directionnelle n'est déduit.

## Gates et décision

Sur les dix-huit sondes, **aucune** ne passe la sélection avant confirmation.
La meilleure p maxT est **0,629**, pour le ratio de volatilité ; toutes dépassent
0,05. La deuxième sonde en découverte, volatilité60 élevée, passe de +0,0515
d'IC à −0,0469 en validation et −0,0494 en 2026. Aucun seuil, signe, poids,
horizon ou feature n'a été changé après lecture des périodes récentes.

Verdict : `NO_STABLE_UNIVARIATE_PATH_TREND_RANKING`.
**Pas de ranker entraîné, de filtre déployé, de backtest ou de recherche de
meilleur paramètre.** Cela clôt cet audit univarié précis, pas toute possibilité
d'apprendre des interactions ou d'exploiter ultérieurement de nouvelles preuves
consensus/news réellement disponibles. Une telle suite demanderait un nouveau GO.

## Vérifications et fichiers

- **29 tests passent** : métriques, chronologie, purge, absence de remplacement,
  sélection indépendante des résultats futurs, identité/source/qualité, dates
  archivées, bornes intraday et cent chemins synthétiques contre calcul scalaire.
- Revue technique séparée : **19 161 parcours** recalculés, vingt métriques chacun,
  **34 448 IC quotidiens**, **300 politiques** et gates pré-confirmation vérifiés.
- Audit statistique séparé : les dix-huit p maxT et douze intervalles d'aire de
  la sonde principale reproduits indépendamment, mêmes blocs/seed figés.
- **498 contrôles de préfixe** récents ; historique issu du dataset audité qui
  conservait toutes les lignes, indépendamment du label TP15/SL7 non utilisé ici.
- Deux formulations du même assistant, **pas revue humaine indépendante**.
- Empreintes entrées/sorties recontrôlées ; zéro entraînement, SQL, API, LLM,
  ordre, téléchargement, changement de batch, modèle ou configuration production.

Canonique : `artifacts/research/us_oracle_path_trend_ranking/20261022-v2/`.
Fichiers : `protocol.json`, `observable-top10.parquet`, `dataset.parquet`,
`prefix-checks.json`, `report.json`, `final-audit.json`, `statistics-audit.json`.

V1 a échoué **avant calcul de cible/résultat**, lors de la sérialisation d'un
`fold_start` mélangeant `datetime.date` et Timestamp. Son manifeste est conservé.
V2 normalise uniquement la représentation de cette date à la lecture, avant
calcul ; mêmes dates calendaires, rangs, prix, métriques, critères et périodes.
Le code V1 gelé et ses empreintes n'ont pas été réécrits.

Sources de calcul : `scripts/research/us_oracle_path_trend_ranking_20261022.py`
et adaptateur `us_oracle_path_trend_ranking_dates_20261022.py`. Les deux auditeurs
suffixés `_audit_20261022` et `_statistics_audit_20261022` sont séparés. Le rapport
final est lié par SHA256 aux deux audits ; ne pas écraser le dossier pour une suite.
