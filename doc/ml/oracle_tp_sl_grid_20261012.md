# Oracle — réparation 2026 et grille TP/SL, 12 octobre 2026

## Demande et protocole figé avant simulations

Suite distincte du 12 octobre : [replay SHORT forcé TP20/SL10](oracle_short_tp20_sl10_20261012.md),
six cas exploratoires avec emprunt supposé et permission SHORT NORMAL ajoutée
en recherche. Cette suite ne remplace pas la présente grille LONG ni ne qualifie
une disponibilité historique à l'emprunt.

Comparaison **LONG uniquement**, des deux modèles déjà figés et des nombres
de titres TOP10, TOP20, TOP50. Le nouveau modèle n'est pas réentraîné pour chaque
couple : son objectif d'apprentissage reste TP20 avant SL7. Les variantes
ci-dessous ne modifient que les protections exécutées après le fill J+1.

| Profil | TP | SL |
| --- | ---: | ---: |
| Référence commune, recalculée | 20 % | 7 % |
| Variante 1 | 10 % | 10 % |
| Variante 2 | 20 % | 10 % |
| Variante 3 | 10 % | 7 % |
| Variante 4 | 20 % | 5 % |
| Variante 5 | 25 % | 7 % |

Les cinq variantes demandées font **60 portefeuilles** : 5 × 2 années × 2 modèles
× 3 nombres. La référence ajoute 12 portefeuilles, soit **72 cas au total**.
Tous sont annoncés avant d'en examiner les rendements ; ne pas publier seulement
le meilleur couple. Cette exploration n'est pas un nouveau holdout vierge.

- 2025 : décisions 02/01–31/12, sorties finales jusqu'au 30/01/2026.
- 2026 : décisions 02/01–03/09, sorties finales jusqu'au 05/10/2026.
- Capital de 4 000 USD réinitialisé par cas ; mêmes secteurs actuels acceptés,
  huit positions maximum, contraintes et sizing natifs, coûts et cash.
- Sizing ATR natif **inchangé** : varier le stop exécuté ne signifie pas une
  taille recalculée pour maintenir un risque de perte identique par position.
- Entrée J+1 ; aucune direction future utilisée ; classement à J par score.
- Aucun trailing ; sortie à l'ouverture de la 21e séance depuis l'entrée.
- Gap SL au prix d'ouverture ; TP limité à son prix limite selon le moteur
  conservateur ; collision quotidienne traitée par la convention native.
- Pas de changement en production, entraînement, calibrateur, ordre courtier
  ou écriture SQL. Les scores réparés sont exclusivement une archive de recherche.

## Réparation AVB effectuée avant la grille

Les 25 dates dont l'unité avait été divisée par 2,793 sont restaurées dans les
prix et les volumes de recherche ; 632 autres dates AVB restent inchangées.
Pour régénérer les features, le warm-up AVB/SPY depuis le 27/12/2012 est archivé
en lecture seule. Les métadonnées de screener figées sont conservées, pas relues
dans leur version SQL plus récente. Les autres features de base restent celles
de l'archive commune initiale.

Contrôles terminés :

- 380 lignes × 129 features AVB avant le 13/07/2026 : aucun écart hors correction.
- Regénération des features AVB sur les mêmes 405 clés ; mêmes clés d'admission
  de l'ensemble scoré, sans filtrage sur les résultats futurs.
- Rangs transversaux recalculés sur tout l'univers quotidien commun, puis
  nouvelle inférence avec les mêmes binaires entraînés ; aucun réentraînement.
- 747 961 lignes, 419 séances : **les trois séries de scores 2025 restent
  identiques**. En 2026, 3 646 scores de l'ancien, 39 de la tête LONG nouvelle
  et 1 969 de la tête SHORT changent (correction locale et rangs communs).
- AVB n'est plus sélectionné dans TOP10/20/50 par le nouveau modèle, alors
  qu'il apparaissait sur 13/14/14 dates contaminées. **Il n'a pas été retiré de
  l'univers.** L'ancien n'avait pas de sélection AVB et n'en a toujours pas.

La grille ne se substitue pas au rapport initial : elle possède des nouveaux
inputs, scores, checksums et sorties. V1 et V2 de la préparation conservent des
échecs de préflight, respectivement sur la sérialisation de l'identité VMRK et
l'index du benchmark ; aucun portefeuille n'y a été exécuté. V3 est préparé.

Les nouvelles barres VMRK et le ratio officiel AVB restent disponibles dans
le ledger de recherche. Chaque cas essaie d'abord le mode strict. Une créance
de fraction non valorisée peut déclencher seulement un scénario séparé
`UNVALUED_RECEIVABLE`, explicitement marqué sans rendement complet du patrimoine.
Toute autre erreur reste un échec. Aucun paiement de fraction n'est inventé.

Les secteurs non PIT, ajustements actuels, disponibilité historique non certifiée
de la macro et du screener restent des réserves. La réparation d'AVB ne certifie
ni tout le marché, ni la parité de fills réels d'un courtier. Les dividendes
implicites dans les ajustements ne sont pas certifiés comme événements cash
historiques. Les protections sur barres quotidiennes ne prouvent pas l'ordre
intrajournalier des touches : la convention native conservatrice est conservée.

## Exécution et suivi

La première grille `tp-sl-grid-20261012-v1` a révélé un volume BAND nul le
18/06/2026 dans certains parcours plus longs (SL10). Elle reste conservée,
avec ses échecs ; ses sorties 2026 ne sont pas le résultat final. Une version
`repaired-volume-grid-20261012-v1` applique trois corrections déjà archivées
et qualifiées, sans changer les OHLC : BAND 0 → 1 997 781, GPRE 0 → 3 495 268,
ATEX 0 → 801 820, toutes le 18/06/2026. Aucun volume n'est fabriqué ; LBRDK,
dont le volume nul a été reproduit par le fournisseur, n'est pas corrigé.

Les features des trois titres sont régénérées, puis les rangs communs et les
scores avec les mêmes modèles. Canary antérieur au 18/06 : 365 dates × 129
features **par titre**, sans écart. Les scores 2025 restent exactement identiques.
En 2026, 172 scores de l'ancien changent ; aucun score des deux nouvelles têtes
ne change. Ces corrections observées en octobre restent **non PIT**.

La grille finale `tp-sl-grid-20261012-v2` réutilise uniquement les 36 cas 2025,
après comparaison exacte des prix/features scorées/macro, warm-up et sorties
jusqu'au 30/01/2026. Les 36 cas 2026 repartent tous de zéro, pas seulement les
échecs, pour appliquer la même version de données à chaque variante.

Deux cas de contrôle TOP10 2026 sont exécutés avant la grille complète. Les
processus de recherche partagent des inputs immuables, mais écrivent dans des
dossiers distincts. La reprise ignore les cas terminés ; un échec repart avec
un nouveau ledger complet, sans inventer un checkpoint portefeuille.

```powershell
python -u -m scripts.research.us_oracle_barrier_exit_grid --inputs artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1 --output artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2 --workers 3
Get-Content artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/progress.json
```

Le rapport expose pour chaque cas le rendement valorisé à la coupe de décision,
celui après fermeture de la cohorte, le drawdown, les positions closes, coûts,
réconciliation cash, motifs de sortie et réserves de lifecycle. Les années ne
sont pas concaténées avec un capital réinitialisé silencieusement en plein run.

- [Réparation et checksums des inputs](../../artifacts/research/us_oracle_barrier_comparison/repaired-feature-grid-20261012-v3/prepared.json).
- [Corrections de volume et inférence figée](../../artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1/prepared.json).
- [Preuve de réutilisation des 36 cas 2025](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/reuse-2025.json).
- [Progression de la grille finale](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/progress.json).
- [Rapport de la grille, mis à jour par cas](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/report.md).
- [Réserves du premier rejeu AVB, désormais historique](oracle_merger_replay_2026_20261012.md).

## Résultat final — terminé

**72/72 cas complets en mode strict, zéro échec, zéro créance de fraction non
valorisée.** La première version termine avec 66 cas complets / 6 échecs BAND ;
elle n'est ni effacée, ni publiée comme résultat final. La version finale V2
est complète et ses empreintes sont vérifiées après tous les calculs.

Le contrôle final séparé des sorties vérifie **14 119 transactions** : niveaux TP/SL
ancrés au fill réel, durée maximale et expiry, cash et sources. Écart maximal de
réconciliation : 6,37 × 10⁻¹² USD. 881 transactions sortent sous le niveau SL,
notamment lors de gaps : le rendement n'est pas artificiellement plafonné au
stop. Les six références 2025 reproduisent exactement les résultats antérieurs.
**168 tests ciblés réussis**, sans test ignoré ; avertissements pandas de
concaténation et corrélations constantes sur fixtures connus, sans échec.

### TOP10 — ancien et nouveau modèle, protections identiques

Rendement net simulé de la cohorte close, capital initial 4 000 USD ; les
queues de sorties dépassent la date de fin des décisions.

| TP / SL | 2025 ancien | 2025 nouveau LONG | 2026 ancien | 2026 nouveau LONG |
| --- | ---: | ---: | ---: | ---: |
| **20 % / 7 % — référence** | −5,42 % | +7,33 % | +9,03 % | +21,20 % |
| 10 % / 10 % | −8,67 % | +11,25 % | +6,82 % | +14,24 % |
| 20 % / 10 % | −7,64 % | +12,39 % | +16,09 % | +18,93 % |
| 10 % / 7 % | −9,20 % | +11,12 % | −1,91 % | +2,94 % |
| 20 % / 5 % | −10,26 % | +17,11 % | +4,71 % | +11,21 % |
| 25 % / 7 % | −6,80 % | +2,05 % | +7,82 % | +17,82 % |

### Nouveau LONG — grille complète TOP10/20/50

| Année | TP / SL | TOP10 | TOP20 | TOP50 |
| ---: | --- | ---: | ---: | ---: |
| 2025 | 20 % / 7 % — référence | +7,33 % | +12,05 % | +17,37 % |
| 2025 | 10 % / 10 % | +11,25 % | +11,76 % | +10,55 % |
| 2025 | 20 % / 10 % | +12,39 % | +10,34 % | +8,81 % |
| 2025 | 10 % / 7 % | +11,12 % | +13,50 % | +8,67 % |
| 2025 | 20 % / 5 % | +17,11 % | +10,30 % | +15,59 % |
| 2025 | 25 % / 7 % | +2,05 % | +11,49 % | +18,18 % |
| 2026 | 20 % / 7 % — référence | +21,20 % | +20,04 % | +20,04 % |
| 2026 | 10 % / 10 % | +14,24 % | +13,66 % | +13,66 % |
| 2026 | 20 % / 10 % | +18,93 % | +22,10 % | +22,10 % |
| 2026 | 10 % / 7 % | +2,94 % | +1,50 % | +1,56 % |
| 2026 | 20 % / 5 % | +11,21 % | +12,96 % | +11,46 % |
| 2026 | 25 % / 7 % | +17,82 % | +17,94 % | +17,94 % |

### Interprétation bornée

- Le nouveau classement LONG bat l'ancien dans **35 des 36 comparaisons
  appariées** (2 années × 3 nombres × 6 profils). L'exception : TOP50 2026,
  TP10/SL7, ancien +3,40 % contre nouveau +1,56 %. L'avantage observé ne vient
  donc pas seulement du fait d'appliquer un TP20 à un modèle et pas à l'autre.
- Les paramètres d'apprentissage diffèrent : ce n'est **pas** une ablation
  prouvant que le seul changement de label explique tout l'écart.
- Aucun couple ne domine tous les nombres et les deux périodes. TOP10 nouveau :
  meilleur 2025 demandé TP20/SL5, mais référence TP20/SL7 meilleure en 2026.
  TOP20/50 nouveau : TP20/SL10 atteint +22,10 % en 2026, mais pas le meilleur
  rendement 2025. Le meilleur profil constaté n'est pas un optimum prospectif.
- Réduire le TP à 10 % n'améliore pas systématiquement le rendement : TP10/SL7
  se dégrade fortement en 2026 malgré des résultats 2025 positifs.
- TOP20 et TOP50 identiques dans certains cas : il s'agit d'une liste de
  **candidats**, pas du nombre de positions. Limites de risque/capital/secteurs
  et positions déjà détenues peuvent conduire au même portefeuille exécuté.
- Cette grille **ne valide pas le choix automatique LONG/SHORT** ni une
  promotion live. Aucun réglage de production n'a été changé.

### Audit, résultats détaillés et reproductibilité

- [Toutes les comparaisons et drawdowns](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/summary.md).
- [Audit final, ratios, comptages et hash des sources/fichiers de transactions](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/summary.json).
- [Rapport brut, rendements à la coupe et après la queue](../../artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2/report.json).

```powershell
python -u -m scripts.research.us_oracle_barrier_grid_summary --root artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2
python -m pytest --no-cov tests/test_oracle_barrier.py tests/test_oracle_barrier_top10_audit.py tests/test_us_oracle_barrier_comparison.py tests/test_us_oracle_barrier_comparison_summary.py tests/test_us_oracle_merger_ledger.py tests/test_us_oracle_merger_prices.py tests/test_us_oracle_barrier_exit_grid.py tests/test_us_oracle_barrier_grid_summary.py tests/test_us_oracle_barrier_volume_prepare.py tests/test_us_concentrated_live_portfolio.py -q -o addopts=
```
