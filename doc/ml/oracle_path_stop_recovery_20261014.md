# Oracle parcours TOP5 — diagnostic des sorties au SL5

## Protocole borné — GO du 14 octobre 2026

Question : le stop fixe à 5 % interrompt-il des trajectoires qui atteignent
ensuite +20 %, et quelles pertes supplémentaires faudrait-il supporter ?
Un retour ultérieur à +20 % ne prouve ni qu'un stop plus large aurait survécu,
ni qu'un portefeuille serait plus rentable. **Diagnostic uniquement**, aucun
entraînement, nouvel ordre, SQL, batch ou réglage de production modifié.

Source : portefeuilles `FIXED_REFERENCE` de
`artifacts/research/us_oracle_path_protection_selector/20261014-v1`.
LONG TOP5 en ordre de score, nouveaux Oracles CatBoost annuels fournis :

| Année | Modèle |
| --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 partiel | `model-factory-20261014113232-bc35a7` |

Entrées/sorties réellement exécutées par le portefeuille simulé, pas tous les
candidats théoriques : SL5, trailing15, TP20, frais/risque natifs, plafond levier2.
2026 décisions jusqu'au 30 septembre ; prix disponibles jusqu'au 9 octobre.
Ni renforcement, ni liquidation artificielle à H20 dans ces portefeuilles.
Ne pas substituer les anciens modèles supprimés aux nouveaux.

## Convention figée avant le calcul

- Population principale : sorties `initial_stop` et `initial_stop_gap_open`.
  Les trailing stops sont comptés séparément, jamais assimilés au SL initial.
- Fenêtres **20 séances depuis l'entrée incluse**, puis sensibilité60 : ce
  n'est pas20/60 séances supplémentaires après le stop. Pas de fenêtre raccourcie.
- Récupération : HIGH >=120 % du fill réel, **strictement après la séance de
  sortie** ; sensibilité CLOSE >=120 %. La chronologie du HIGH/LOW du jour du
  stop ne peut pas être reconstruite avec une barre quotidienne.
- Recul avant le premier HIGH cible : LOW minimal depuis l'entrée ; borne sans
  LOW du jour cible et borne l'incluant, car son ordre intraday est inconnu.
  Recul supplémentaire sous−5 % en points, pas depuis un sommet différent.
- Sensibilité purement mécanique : TP20 touché après le stop observé avant
  tout SL10 depuis l'entrée, sans trailing, coûts ni sizing. Gaps à l'open,
  collision intraday conservatrice stop d'abord. **Ce n'est pas un backtest**.
- ATR20 à J : moyenne glissante des20 true ranges sur prix ajustés du générateur.
  Chaque ATR archivé est revérifié sur le préfixe de prix se terminant à J.
  Distance effective =5 % du fill / ATR exprimé dans les unités du close J.
  Trois tranches préfixées : <1 ATR, [1,2[ ATR, >=2 ATR, aucune optimisation.
- Qualité commune de toute la fenêtre : OHLCV positifs, cohérents, non remplis,
  identité stable ; ruptures connues et corporate actions réservées.
  Données manquantes/immatures exclues du taux qualifié, motifs affichés ; aucune
  substitution par un autre titre et aucune conclusion sur leur récupération.
- Stops à la dernière séance ou plus tard que la fenêtre : motif séparé,
  pas de suivi post-stop possible dans cette fenêtre.
- Sensibilité aux répétitions : sélection chronologique des entrées par symbole
  espacées d'au moins20/60 séances, sans regarder le succès de récupération.
  Ce sous-échantillon reste dépendant des régimes ; pas une validation indépendante.

Le diagnostic porte sur les lots clos : les positions encore détenues ne
sont pas inventées comme gagnantes ou perdantes. Les prix ajustés actuels,
l'univers de survivants, les secteurs actuels, dividendes incomplets et les
hypothèses de coûts/marge des archives restent des réserves.

## Artefacts et arrêt

Commande :

```powershell
python -u -m scripts.research.us_oracle_path_stop_recovery --output artifacts/research/us_oracle_path_stop_recovery/20261014-v1
```

`protocol.json` et empreintes sources avant calcul ; `stopped-lots.parquet`,
`closed-lot-atr.parquet`, `atr-strata.csv`, `report.json`, `completion-audit.json`
et `progress.json`. Vérification des sources existantes sans les réécrire.

Aucune variante ATR de portefeuille ne sera lancée automatiquement. Selon ce
diagnostic, une expérience ultérieure pourrait comparer une règle ATR **figée
à l'entrée**, stop jamais élargi ensuite, quantité adaptée au même budget de
risque, TP20/trailing15 et coûts inchangés. Le diagnostic ne choisit pas un
coefficient ATR optimal sur les pertes ni ne promet une meilleure rentabilité.
