# Grille B4 : seuil de déclenchement 15 % contre 20 %

## GO et état

21 octobre 2026 : l'utilisateur a modifié le preset `capital_2001_5000` à
`risk_max_drawdown_pct: 0.15`, puis demandé de rejouer la grille.
**198 tests passent ; quatre pilotes LONG/SHORT 2025/2026 passent les audits.
Grille complète de 576 simulations lancée, bilan encore à attendre.**

Nouveau dossier :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1`.
Témoin corrigé 20 % conservé intégralement :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2`.

## Un seul changement expérimental

La configuration effective a été résolue via `load_risk_config(equity=4000,
preset_key='capital_2001_5000')`. Le seul champ de contrôle différent du témoin
est `max_portfolio_drawdown_pct`, **0,20 → 0,15**. Les autres champs B4 ainsi
que l'activation et la fraction des liquidations sont vérifiés identiques.
Une autre différence entraîne un refus, pas une modification silencieuse du
contrat. Les empreintes de `config.yaml` et `config/capital_presets.yaml` sont
figées avec le nouveau protocole. Ce script ne modifie aucun réglage utilisateur.

Le précédent runner lisait volontairement le profil historique figé à 20 % :
le relancer après modification YAML n'aurait donc pas suffi. Le nouveau module
`scripts.research.us_intraday_protection_grid_dd15` prépare le profil à 15 %,
puis réutilise sans les modifier les workers, le ledger et les audits du run
20 %. Le code numérique B4 corrigé reste exactement le même.

Tous les fichiers de données préparées du témoin sont repris byte-identiques,
notamment barres, calendrier, candidats, contexte antérieur et régimes. Le profil
canonique de référence est conservé sauf ce seuil dans les champs de contrôle
et dans sa représentation d'audit. Ce n'est pas un rechargement de tout le sizing
de production. Aucune modification après observation des résultats du pilote.

## Contrat conservé

- **144 politiques LONG + 144 SHORT**, chacune en 2025 et en 2026 au 30 septembre,
  soit 576 comptes annuels. SL3/5/7, trailing OFF/10/15/20, H5/10/15/20,
  TP OFF/10/20 ; sorties et entrées inchangées.
- 4 000 USD indépendants par année, plafond d'admission **×1**, mêmes tailles,
  frais, emprunt SHORT supposé, financement, maintenance et valorisation MTM.
- Même cohorte conditionnelle 213 campagnes / 72 titres, pas tout le TOP10
  historique ; réserves de survivants et de complétude future inchangées.
- B4 quotidien à l'ouverture après protections connues, régime SPY antérieur,
  fenêtre 252 séances, mêmes hystérésis, allocation et reprise.
- Même force-close éventuel : 50 % du nombre de positions, pires PnL latents
  d'abord ; ni 50 % du capital ni arrêt intraday garanti.

**15 % est un seuil de déclenchement, pas une garantie de DD maximal à 15 %.**
Le chemin B4 ne crée toujours pas de hard halt sur la perte journalière 3 %.
Le raccordement intégral PortfolioBuilder/secteurs/corrélations/quotes/fills
historiques reste non qualifié. Les périodes déjà vues ne deviennent pas un
nouveau holdout. [Limites et protocole 20 %](grille_intraday_risque_production_20261021.md).

## Contrôles

`tests/test_us_intraday_protection_grid_dd15.py` vérifie le changement unique,
l'immuabilité du profil témoin, les refus de changements confondants et de
liquidation, la protection des anciens dossiers, la restauration de l'orchestrateur
et le déclenchement effectif plus tôt du vrai composant de risque. Les tests
numériques B4 et les non-régressions précédentes sont rejoués : **198 PASS**,
rapport `artifacts/tmp/pytest-dd15-20261021-v1.xml`.

Pilote : `artifacts/research/us_intraday_protection_grid/smoke-risk-dd15-20261021-v1`.
4/4, zéro échec, `PASS_PRODUCTION_RISK_CASH_EXITS` pour chaque cas. Un pilote
ne suffit pas pour conclure au meilleur seuil ; aucun profil choisi sur son PnL.
Vérifications du même assistant, pas seconde revue humaine indépendante.

## Résultats attendus et suivi

- `annual-summary.csv` : tous les résultats à 15 %, mêmes mesures demandées
  de rendement, capital final, DD, gagnants/perdants, gains/pertes moyens,
  détention et capital moyen utilisé.
- **`comparison-dd15-vs-dd20.csv`** : appariement exact des mêmes politiques,
  mesures 15/20 et différences, déclenchements, sorties forcées et séances dégradées.
- `comparison-risk-vs-baseline.csv` : conserve aussi la comparaison à l'absence
  de B4 de la grille ×1 initiale.
- `final-review.json` : audit technique commun des 576 cas ;
  **`threshold-review.json`** : vérification finale dédiée au seuil et au tableau
  apparié, attendue en `PASS_DD15_VS_DD20_GRID_REVIEW`.

```powershell
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1/progress.json
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1/stderr.log -Tail 20
```

Ne pas démarrer de seconde instance. En cas d'arrêt confirmé, reprise via
`python -u -m scripts.research.us_intraday_protection_grid_dd15 --workers 2`.
Les sources/configurations figées doivent conserver leurs empreintes ; pas
de réutilisation des résultats 20 % comme s'ils avaient été recalculés à 15 %.
Durée indicative : une vingtaine de minutes d'après la grille précédente,
variable selon le travail du compte et la machine.

Aucun entraînement, appel fournisseur/LLM, SQL écrit, ordre, modèle ou batch
modifié. Pas de sélection automatique du seuil pour le live à la fin du calcul.
