# Priorité des bougies daily US — 24 octobre 2026

```yaml
market_data:
  daily_bars_preferred_source: eodhd  # eodhd | alpaca_sip
  bars_provider: alpaca             # téléchargement, réglage distinct
```

La préférence départage les lignes de `stock_bars_daily` pour un même symbole
et une même séance. `eodhd` correspond à la provenance SQL `eodhd_eod`.
Si les deux existent, conserver la ligne préférée **entière** : OHLC, volume,
VWAP, ajustement et métadonnées proviennent du même enregistrement. Si seule
l'autre existe, la conserver. Ne pas remplir une date absente, moyenner deux
volumes ou supprimer des données en base. L'ordre SQL ne décide pas du choix.

La préférence ne change ni `bars_provider`, ni les téléchargements B3, ni le
flux SIP des quotes temps réel/historiques, ni le fournisseur des bougies
intraday 5 minutes. CN/FR gardent leurs contrats spécifiques. Une requête de
recherche qui impose explicitement un fournisseur ou une archive scellée
conserve ce périmètre, pour ne pas transformer rétroactivement ses résultats.

## Raccordements

- ML : loaders par symbole, SPY et panel univers, pour training et predict ;
  la provenance physique reste disponible dans `bar_data_source` lorsqu'un
  appel legacy utilise `data_source=stock_bars_daily`.
- Backtest standard et ses consommateurs du filtre source partagé : choix
  avant classement/fenêtrage SQL, préflight compatible avec les deux sources.
- Repository de bougies US, screener, préselection selector/benchmark,
  filtre dip, filtre Oracle×ATR et pics de parcours de l'étude.
- LLM : historique prix fourni à l'analyse et évaluateur. Le contexte frais
  sélectionne **après** le filtre de disponibilité avant cutoff et **avant**
  la limite de 21 séances ; une révision future ne masque pas une ligne alors
  disponible. Ses contrôles de continuité/provenance restent stricts.

Le lecteur `risk_management/db_io.py` et les points d'entrée risque/watcher
font partie du contrat de code scellé des grilles encore actives. Ils ne sont
pas modifiés ici : leur raccordement global prix/ATR/ADV/corrélation reste à
faire après la fin de ces grilles ou par un adaptateur versionné explicitement
qualifié. Le contrôle des nouvelles entrées garde pour cette raison son
blocage strict des séances dupliquées : il ne faut pas autoriser un titre avec
des données nettoyées si le sizing risque relit encore deux sources. Le
paramètre ne doit donc pas être présenté comme couvrant déjà
**tous** les lecteurs SQL du projet. Les scripts historiques scellés et audits
de comparaison fournisseur ne sont volontairement pas réécrits.

## Incident vérifié

Le 24 octobre, ML Predict du modèle `model-factory-20261016180250-3b0515`, signal
du 23 octobre, échouait avant le LLM : SPY avait deux sources du 12 au 16 octobre
2026. Le chargement donnait 761 lignes au lieu de 756 séances, et le garde-fou
des facteurs refusait les dates répétées. Il n'a pas été désactivé.

Après sélection : 756 dates SPY uniques ; les cinq dates concurrentes sont
EODHD ; panel SPY/AAPL 1 508 lignes sans doublon ; calcul des facteurs SPY
contre SPY terminé (bêta ≈ 1). Contrôle READ ONLY, aucune prédiction persistée,
aucun appel GPT/DeepSeek, aucune suppression SQL. Le calcul du premier lot
Oracle (25 titres demandés, 23 disponibles au signal, 183 colonnes) passe aussi
sans doublon ni erreur de facteurs ; cela ne valide pas encore la couverture
de l'univers entier. Les nouvelles prédictions
doivent être relancées explicitement ; aucun ancien résultat n'est réécrit.

Tests : règle dans les deux sens, repli sur source seule, ligne entière,
indépendance à l'ordre, absence de remplissage, SQL avant LIMIT, chargements
ML benchmark/panel, ambiguïtés rejetées et maintien des contrôles de facteurs.

Validation finale : **512 tests ciblés passent, un ignoré** (sélecteur dip
optionnel), un avertissement pandas déjà présent sur une date invalide de
test. Les empreintes des sources scellées des trois runs grille/mensuel sont
encore valides après ces changements. Compilation et `git diff --check` OK.

La suite plus large `tests/test_backtesting.py` a aussi été exécutée : douze
tests CLI échouent avec la configuration courante. Le premier échec a été
reproduit avec le chargeur original de HEAD exécuté en mémoire : cascade
activée sans `batch_diagnostics.backtest_batch_id`. Il ne prouve donc pas une
régression de sélection de source ; les douze échecs ne sont pas déclarés
corrigés ici. Les tests ciblés du loader backtest passent.
