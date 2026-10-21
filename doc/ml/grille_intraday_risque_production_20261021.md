# Grille ×1 avec protections de portefeuille de production

## GO et état du21octobre2026

**V2 terminée : 576/576 simulations réussies, zéro échec, tous les audits
et empreintes revérifiés. Durée 21 min 23 s.** 187 tests, les quatre cas
précédemment en échec et quatre pilotes LONG/SHORT 2025/2026 passent aussi.
Suite du dernier test : sans levier×1,4000USD
indépendants par année,2025 et2026 jusqu'au30septembre,144politiquesLONG et
144SHORTparannée. Référence `20261021-1x-v1` et anciens calculs conservés.

Nouveau dossier :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2`.

La v1 a fini **PARTIAL_FAILED : 572 cas audités, 4 en échec**. Des différences
d'arrondi d'environ 4e-12 USD étaient interprétées comme un nouveau creux B4,
réinitialisant l'hystérésis et faisant diverger l'allocation de 50 % à 10 %.
Les résultats v1 et leurs sources exactes sont conservés. La v2 recalcule
**tous les cas**, sans fusionner les 572 anciens avec les quatre réparés.
Les données, régimes et paramètres de risque v1 sont repris à l'identique,
sans recharger les réglages YAML actuels ni optimiser sur les rendements.
Voir [le correctif numérique et ses preuves](remediation_numerique_b4_20261021.md).

### Bilan v2 vérifié

Profil LONG de comparaison déjà suivi, **SL7/trailing15/H20/sansTP** :

| Période | Rendement sans B4 → avec B4 | DD maximal sans B4 → avec B4 | Capital final avec B4 | Capital moyen engagé avec B4 |
| --- | ---: | ---: | ---: | ---: |
| 2025 | +33,15 % → +16,25 % | 30,68 % → 26,93 % | 4 649,86 USD | 2 317,86 USD |
| 2026 au 30 septembre | +31,67 % → +31,67 % | 20,88 % → 20,88 % | 5 266,82 USD | 2 784,57 USD |

Capital initial de 4 000 USD **indépendant par année**, coûts compris et
positions ouvertes valorisées : sept en fin 2025, aucune en fin 2026. B4 ne
déclenche pas sur ce profil LONG 2026. En 2025, un déclenchement et 78 séances
dégradées ; aucune sortie forcée car plus de ligne éligible à cet instant.

LONG positifs : **25/144 en 2025, 128/144 en 2026, 23 profils positifs sur les
deux périodes**. SHORT : **0/144 positifs par année**. DD réduit face au témoin
apparié dans 100/144 LONG 2025 et 9/144 LONG 2026 ; ce n'est pas systématique.
Le seuil de DD20 % n'est pas un plafond garanti : 420/576 comptes dépassent
20 % de DD mesuré intraday. Le bilan ne démontre ni une protection dure ni
une amélioration universelle du couple rendement/risque.

Parmi les profils observés, LONG SL7/trailing15/H15/sansTP donne
+20,91/+21,73 %, DD26,61/19,14 %. C'est le meilleur minimum de rendement annuel
sur cette grille LONG, **choisi après lecture des résultats**, pas un champion
validé sur holdout. [Bilan détaillé et métriques demandées](grille_intraday_risque_production_resultats_20261021.md).

Le pilote démontre des déclenchements et des effets réels : sur SHORT2025,
un trip,143séances dégradées et une sortie forcée ; sur LONG2025, un trip et
78séances dégradées. Aucun ordre fictif n'est créé lorsqu'il ne reste aucune
position à l'ouverture après les stops. Ce n'est pas encore le résultat de grille.

## Composants effectivement raccordés

- **`risk_management.circuit_breaker.CircuitBreaker` réel**, état B4 persistant
  par compte annuel, fonctions partagées `backtesting.adaptive_breaker`.
- **`RiskCheckerImpl.check_position_size` réel**, avant chaque entrée, avec les
  positions détenues, l'equity et le breaker. Quantités bookées vérifiées contre
  l'approbation, pas seulement une ligne de log indiquant un contrôle.
- Facteur B4 appliqué réellement **une seule fois** aux quantités, arrondies
  vers le bas. Même PositionSizer/ConstraintChecker et comptabilité natifs.
- Sur transition `just_tripped`, liquidation si activée de la fraction prévue
  du **nombre de positions**, pires PnL latents d'abord, convention du passage
  `Executor.run`.50%ne signifie ni50%de chaque ligne ni50%du capital. Fills
  natifs avec frais/emprunt, aucune sortie gratuite au close futur.
- Configuration effective obtenue par **`load_risk_config` canonique**, preset
  explicite `capital_2001_5000`, options `prod_force_close_*` de config.yaml,
  puis figée avant calcul. Aucun seuil réglé d'après ces pertes historiques.

Valeurs obtenues : **DD20%, pertejour3%, B4, fenêtre252séances, recovery92%,
allocation dégradée paramétrée6%, force-close activé50%**. B4 possède sa propre
échelle, dont un plancher10% ; ne pas assimiler le6%du preset au facteur B4.
Le preset ne change pas automatiquement de tranche lorsque l'equity varie.

### Périmètre : couche portefeuille, pas tout PortfolioBuilder

Les cibles individuelles de la grille restent fixes pour isoler cet effet :
4%de risque SL planifié, cible complète≤50%equity puis moitié, au plus environ
25%par entrée. **Ce ne sont pas tous les paramètres de sizing du preset de
production.** Le checker utilise ces paramètres de stratégie explicites. La
configuration complète canonique et les surcharges sont enregistrées.

Données/signaux/frais/SL/trailing/H/TP/trackers/emprunt/maintenance/calendrier
restent identiques à la référence×1. Les contrôles de quotes contemporaines,
secteurs/corrélations, permissions et événements complets de PortfolioBuilder
ne sont pas certifiés par ce replay. **Pas de parité historique intégrale live.**

## Réserves trouvées dans le code actuel

1. Sous B4, **`is_active()` retourne False** pour laisser agir l'allocation
   adaptative. Le statut peut signaler la perte journalière3%, mais **ce chemin
   ne crée pas un arrêt strict3%**. Le replay garde cette sémantique et compte
   ces observations ; il n'invente pas une protection dure supplémentaire.
2. Le passage Executor examiné calcule/journalise **`allocation_scale` sans
   y redimensionner les quantités**. Le nouveau replay raccorde explicitement
   cette valeur aux quantités approuvées/bookées. Ce n'est donc pas une preuve
   de reproduction inchangée de bout en bout du chemin live.

Ces constats concernent les passages audités, pas d'éventuels services externes
non examinés. **La v2 corrige uniquement les comparaisons monétaires B4/B4a
dans `backtesting.adaptive_breaker`, fonction partagée avec le risque de
production.** Pas de changement de configuration, d'exécuteur, de câblage
live ou de persistance. Le raccordement du facteur aux quantités live et
une éventuelle protection journalière stricte restent des travaux séparés.

## Chronologie, fenêtres et données

Une évaluation par **vraie séance NYSE à son ouverture régulière**, après les
protections de gap/TP/échéance connues, avant nouvelles entrées. Valorisation
aux opens simultanés observés ; jamais à la clôture future du jour. Le PnL
latent à cet open détermine les positions à couper. L'exécution immédiate à
cet open reste une hypothèse de fill, sans certification de quotes/latence.

Régime SPY via `compute_regime` partagé, SMA50/SMA200 sur prix ajustés archivés,
**séance précédente uniquement**, avec200séances complètes. **437/437séances
ont un régime disponible**, pas de neutre fictif. Les données sont archivées/
révisables : pas preuve de réception de l'application à chaque date historique.

Fenêtre252 en **closes quotidiennes**, jamais en barres5m ou appels répétés à
`status()`. Streak B4 une fois par séance ; les closes du portefeuille alimentent
seulement les séances suivantes. La politique/seuils actuels d'octobre2026 sont
appliqués rétrospectivement, sans prétendre prouver les paramètres live de2025.

Le contrôle global est **quotidien**, pas un watcher intraday continu. Les
protections des positions continuent d'être rejouées sur chaque barre5m.
**Un seuil20%ne garantit pas un DDmax20%** : pic quotidien et DDmesuré5m,
gaps/délais/liquidation partielle peuvent entraîner un dépassement. Aucune
troncature artificielle de l'equity au seuil, ni retouche après observation.

## Audits, résultats et suivi

187 tests : stabilité des seuils monétaires B4/B4a et du creux, détection des
vraies baisses, non-régression bit à bit B0–B3 contre les sources v1 conservées,
breaker réel/parités B0/B4 existantes, trip/récupération/rechute,
cadence quotidienne/fenêtre, pertejour nonbloquante B4, réduction réelle de
parts entières, sorties avec coûts, absence d'alertes/ordres, non-régressions.

Chaque cas : reconstruction distincte cash/frais/emprunt/valorisations5m,
sorties scalaires et priorité des protections, **snapshots d'ouverture risque
reconstruits depuis les trades/opens**, rejeu de trace B4, contexte antérieur,
nombre et choix des sorties, quantités approuvées/bookées. Même assistant,
pas revue humaine indépendante.

- `progress.json` et logs : avancement et reprise par cas terminé scellé.
- `annual-summary.partial.csv`, puis `annual-summary.csv` : mêmes mesures
  demandées que×1/×2, dont DD, rendement/capital, taux gagnant, gains/pertes
  moyens, détention gagnants/perdants, capital moyen/max engagé, coûts.
- `comparison-risk-vs-baseline.csv` : **mêmes politiques** avec/sans overlay,
  trips, sorties forcées, séances dégradées et pertes journalières observées.
- `cases/*/production-risk-events.json` : equity/pic, positions, régime/asof,
  allocation et sorties ; `audit.json` conserve les vérifications/compteurs.
- `production-risk.json`, `risk-regimes.parquet`, protocole/empreintes :
  paramètres/entrées figés ; `final-review.json` après576cas réussis vérifiés.

```powershell
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2/progress.json
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2/stderr.log -Tail 20
```

Le calcul est terminé ; aucune relance n'est nécessaire. Pour reprendre après
arrêt confirmé, utiliser le même module avec `--output` v2 et `--workers 2` ;
les sources et entrées figées doivent toujours correspondre aux empreintes.
Les cas terminés scellés sont repris, pas ceux dont l'audit a échoué.

Pas de SQL, API/LLM/fournisseur, ordre, entraînement, modèle ou batch modifié.
Toujours213campagnes sélectionnées pour leur couverture complète,119/94parannée,
72titres et les biais/limites du [protocole parent](grille_intraday_sans_levier_20261021.md).
Comparaison exploratoire, aucun GO live automatique.
