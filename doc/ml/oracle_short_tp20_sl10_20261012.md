# Oracle SHORT forcé — TP 20 % / SL 10 %, 12 octobre 2026

## Objet et protocole avant simulation

Répondre à la demande de rendement SHORT uniquement, sans entraîner un nouveau
modèle ni modifier les réglages PAPER/LIVE. Six cas annoncés : 2025 et 2026,
chacun sur TOP10, TOP20 et TOP50. Le classement est décroissant sur la tête
`proba_short_tp_before_sl` du modèle figé
`model-factory-20261011221400-867a1e`. Ce n'est ni un tri sur les mouvements
futurs ni la vente en SHORT des candidats de la tête LONG.

- Même archive commune réparée que la grille LONG :
  `artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1`.
- 2025 : décisions jusqu'au 31 décembre ; 2026 : jusqu'au 3 septembre.
  Les positions disposent de leur queue de sortie de vingt séances.
- Capital initial 4 000 USD par année et par sélection ; pas de concaténation
  des années réinitialisées. Comptabilité marge simulée, en USD.
- Entrée à l'ouverture J+1. TP = prix exécuté × 0,80 ; SL = prix exécuté × 1,10.
  Trailing OFF ; rachat à l'ouverture de la 21e séance depuis l'entrée.
- Les seuils d'apprentissage restent TP20/SL7 : SL10 est une variante de sortie,
  pas un nouveau modèle. Le score n'est pas certifié comme probabilité calibrée.
- Actions entières seulement. Le percentile transversal de la tête SHORT sert
  au sizing natif, comme pour les scénarios LONG ; il ne représente pas une
  probabilité nouvelle. Les caps de positions SHORT, corrélations, concentrations,
  confirmations, minimums et budgets de portefeuille restent actifs.
- Le contrôle initial conserve les permissions de régime : SHORT en
  `capital_preservation` seulement. Il donne **zéro position TOP10 2026**,
  2 séances CP autorisées sur 169 séances de décision ; retour nul sur cash.
  Ce résultat ne mesure pas la rentabilité de la tête SHORT.
- Le scénario principal **SHORT forcé** ajoute donc une permission explicite,
  `--allow-short-normal`, pour cette recherche seulement : SHORT autorisé en
  `normal` aussi, mais pas en `close_only`/`cash_only` ou si les entrées sont
  interdites. Caps, contraintes et logique de régime restants sont conservés.
  C'est un contrefactuel, pas l'exécution de la politique de production actuelle.
  Les séances effectivement autorisées sont comptées ; aucun réglage live changé.
- Pas de remplacement d'un candidat inadmissible par le rang suivant ; aucune
  exclusion fondée sur son futur rendement. Le parcours détenu incomplet bloque
  le cas, au lieu de donner une performance sur les seules réussites.

## Comptabilité et conventions de sortie

La vente initiale crédite le cash, mais la valeur du titre vendu constitue une
dette : le produit de vente n'est pas un gain. Le rachat débite le cash.
La performance est calculée sur l'équité après les coûts des deux côtés et
l'emprunt, puis contrôlée contre les flux de chaque position.

Un gap défavorable remplit le SL au prix d'ouverture, pas au stop théorique.
Un gap favorable remplit conservativement le TP à son prix limite. Si une barre
quotidienne touche SL et TP sans ordre intrajournalier connu, le SL est prioritaire.
Les réductions de régime sont arrondies à l'action entière inférieure et archivées.

Le premier contrôle forcé V1/V2 a détecté RARE : 9 actions approuvées devenaient
8,999999999 lors des partial fills synthétiques, puis 8 au commit. Ces contrôles
ont échoué, sans PnL final. Les partial fills SHORT sont désormais en actions
entières (par exemple 5 puis 4), sans arrondi tolérant masquant une quantité perdue.
Les partial fills LONG historiques conservent leur comportement par défaut.

Le champ historique natif `return_pct` SHORT utilise une convention réciproque
`100 × (entrée / sortie − 1)`, arrondie à quatre décimales. Il est conservé, sans
modifier le helper partagé. Le replay ajoute `entry_notional_return_pct` :
`100 × (1 − sortie / entrée)`. Ainsi une hausse de 100 à 110 implique −10 %
du notionnel d'entrée ; une baisse à 80 implique +20 %, avant coûts. Le PnL cash
et le rendement du portefeuille ne sont pas calculés depuis le champ réciproque.

## Limites : simulation exploratoire, pas SHORT historique certifié

La disponibilité historique à l'emprunt n'est pas démontrée pour tout l'univers.
Elle est **supposée disponible** dans ce scénario. Le taux natif de **0,3 %/an**,
au prorata des séances sur 252, est une hypothèse et non un relevé de taux.
Les locates, rappels, coût réel variable et paiements compensateurs de dividendes
ne sont pas modélisés. Les prix ajustés fournisseur ne sont pas des fills bruts
broker ; les secteurs actuels sont non PIT et la macro n'est pas certifiée par
vintage de publication. Les coûts natifs simulés ne constituent pas une facture
réelle. Ces réserves peuvent changer sensiblement le résultat SHORT.

Une position détenue au passage d'une conversion AVB/EQR non qualifiée côté
prêteur entraîne FAILED. Le traitement LONG des titres reçus et fractions cash
n'est pas réutilisé pour inventer une obligation SHORT. Les identités retirées
ne sont plus vendues après leur date de retrait observable.

**Aucune promotion en production, ordre broker, écriture SQL, requête fournisseur
ou entraînement.** Les anciens résultats LONG et leurs protocoles sont conservés.
Les nouveaux inputs, sources et outputs reçoivent leurs propres empreintes SHA256.

## Lancement et suivi

Le contrôle préalable exécute TOP10 2026 dans un dossier distinct. La campagne
complète exécute les six cas avec deux processus et archives séparées.

```powershell
python -u -m scripts.research.us_oracle_short_replay --inputs artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1 --output artifacts/research/us_oracle_barrier_comparison/short-forced-grid-20261012-v1 --workers 2 --allow-short-normal
Get-Content artifacts/research/us_oracle_barrier_comparison/short-forced-grid-20261012-v1/progress.json
```

Un cas termine en `COMPLETED_EXPLORATORY`, pas en validation broker. Le rapport
compare rendement net, drawdown, gagnants/perdants, capital final et coût d'emprunt.
Un cas FAILED ne fournit pas un PnL final. Une reprise vérifie les empreintes des
cas déjà terminés ; une modification du protocole exige un nouveau dossier.

## Résultats

Campagne `short-forced-grid-20261012-v1` terminée : **6/6
COMPLETED_EXPLORATORY, aucun échec**, empreintes des inputs et outputs vérifiées.
347 positions / 347 jambes de sortie auditées : stops et objectifs ancrés au
fill, gaps, collisions, échéances, quantité entière, charges d'emprunt, PnL cash.
Erreur cash maximale 2,73 × 10⁻¹² USD. TOP10 2026 reproduit exactement le contrôle
V3 sur les clés de trade, prix, quantité et PnL (hors identifiants synthétiques).
**240 tests ciblés passent** (198 risque/ledger/protections et 42 bridges/exécution).

| Année | TOP tête SHORT | Gagnants / perdants | Taux gagnant | Rendement net | DD max | Capital final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 10 | 14 / 21 | 40,00 % | +1,54 % | −5,19 % | 4 061,43 USD |
| 2025 | 20 | 15 / 22 | 40,54 % | +1,21 % | −5,19 % | 4 048,57 USD |
| 2025 | 50 | 15 / 22 | 40,54 % | +1,21 % | −5,19 % | 4 048,57 USD |
| 2026 | 10 | 24 / 53 | 31,17 % | −14,50 % | −16,09 % | 3 420,18 USD |
| 2026 | 20 | 25 / 53 | 32,05 % | −14,10 % | −16,11 % | 3 435,90 USD |
| 2026 | 50 | 30 / 53 | 36,14 % | −10,64 % | −15,91 % | 3 574,40 USD |

Le régime de recherche permet une entrée SHORT sur 250 séances de décision en
2025 et 169 en 2026 ; cela ne signifie pas une position chaque jour. Les autres
garde-fous, les budgets et les actions entières limitent les trades. Le cap natif
est de **cinq positions SHORT simultanées**, contre huit positions totales ; le
scénario n'achète/vend pas simultanément tous les TOP10/20/50. L'exposition brute
moyenne/equity est de 8,14–8,63 % en 2025 et 25,55–27,64 % en 2026.
TOP20 et TOP50 produisent exactement les mêmes trades en 2025 (comparaison des
clés, quantités, prix et PnL), mais pas en 2026.

| Année | TOP | Gains des gagnants | Pertes des perdants | PnL net | Emprunt inclus |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 10 | +532,73 USD | −471,30 USD | +61,43 USD | 1,09 USD |
| 2025 | 20 | +539,02 USD | −490,46 USD | +48,57 USD | 1,15 USD |
| 2025 | 50 | +539,02 USD | −490,46 USD | +48,57 USD | 1,15 USD |
| 2026 | 10 | +892,50 USD | −1 472,32 USD | −579,82 USD | 2,30 USD |
| 2026 | 20 | +908,22 USD | −1 472,32 USD | −564,10 USD | 2,33 USD |
| 2026 | 50 | +1 046,72 USD | −1 472,32 USD | −425,60 USD | 2,47 USD |

Ces PnL sont nets des coûts simulés et du taux d'emprunt supposé, pas des
obligations non modélisées. L'intérêt sur cash débiteur est nul dans ces cas.
2026 : TOP10 et TOP20 ont 50 sorties stop, dont 7 gaps, sur respectivement 77 et
78 positions ; ils n'ont que 12 TP. TOP50 a les mêmes 50 stops et 15 TP sur 83
positions. Le SL10 ne garantit donc pas une perte maximale de 10 % sur un gap.

À titre de contexte, les replays LONG TP20/SL10 précédents rapportaient
TOP10 +12,39 % / +18,93 %, TOP20 +10,34 % / +22,10 %, TOP50 +8,81 % / +22,10 %
sur 2025 / 2026. **Ce n'est pas une ablation isolant seulement le signe** : tête
de sélection différente, cap SHORT de cinq positions, actions entières et
permission NORMAL ajoutée pour la recherche. Il ne faut pas soustraire ces
résultats pour prétendre démontrer une probabilité directionnelle calibrée.

Conclusion : **NO_GO_FORCED_SHORT_PROMOTION_TP20_SL10**. Petit gain exploratoire
en 2025, perte nette en 2026 ; aucun avantage stable ni GO live. Pas de réglage
du modèle ou des seuils après observation des pertes.

- [Protocole figé](../../artifacts/research/us_oracle_barrier_comparison/short-forced-grid-20261012-v1/protocol.json).
- [Rapport complet et hypothèses](../../artifacts/research/us_oracle_barrier_comparison/short-forced-grid-20261012-v1/report.json).
- [Tableau de résultats](../../artifacts/research/us_oracle_barrier_comparison/short-forced-grid-20261012-v1/report.md).
- [Contrôle natif sans permission NORMAL : cash seul](../../artifacts/research/us_oracle_barrier_comparison/short-smoke-20261012-v1/report.json).
- [Contrôle SHORT forcé final](../../artifacts/research/us_oracle_barrier_comparison/short-forced-smoke-20261012-v3/report.json).
