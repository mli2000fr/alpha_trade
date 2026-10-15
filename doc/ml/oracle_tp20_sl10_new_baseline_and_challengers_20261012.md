# Nouveau modèle TP20/SL10 : baseline puis trois expériences séparées

## Périmètre figé le 12 octobre 2026

Demande : modèle `model-factory-20261012183840-6d6569`, training borné au
31 décembre 2023 ; baseline annuelle 2024, 2025, 2026 avant les challengers.
Le rapport d'entraînement est `completed`, 1 790 titres, 173 features,
TP20/SL10/20 séances. Les deux têtes restent indépendantes et non calibrées
entre elles. Le dernier fold archivé utilisable est `2023-01-05`, sélectionné
avec les labels de validation disponibles au plus tard le 4 janvier 2023 :
ce n'est pas un refit implicite de tout 2023. On réutilise exactement ses poids.

Répertoire courant : `artifacts/research/us_oracle_tp20_sl10_new/20261012-v6`.
Statut : **baseline seule terminée : neuf cas vérifiés, zéro échec**.
Instruction historique du 12 octobre : terminer 2026, remettre les résultats,
**puis s'arrêter**. Ce point a été respecté. **Nouveau GO du 13 octobre : lancer
les trois challengers ci-dessous, un par un, avec ce même modèle.**
La réduction progressive d'exposition est explicitement exclue.
Le suivi courant est [le protocole de campagne du 13 octobre](oracle_challengers_20261013.md).
Les trois expériences sont maintenant terminées,36 nouveaux replays audités.
Filtre inactif au seuil0,50 ; sortie quotidienne meilleure en2025 mais
dégrade les gains ailleurs ; personnalisation TP/SL non robuste.
La baseline ci-dessous et les poids Oracle ne sont pas remplacés.
Les résultats antérieurs avec TP20/SL7 ne sont pas remplacés.

## Résultats de la baseline v6 — clôture du 12 octobre

**LONG uniquement, TP20/SL10, sans trailing, 4 000 USD réinitialisés par cas.**
2026 couvre les décisions jusqu'au 3 septembre, avec dénouement des dernières
positions ensuite ; pas une performance de toute l'année 2026.

| Année | TOP | Capital final $ | Gains $ | Pertes $ | Gagnants % | Perdants % | Rendement % | DD max % |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 10 | 3909,61 | 2438,56 | −2528,95 | 37,97 | 62,03 | −2,26 | −11,01 |
| 2024 | 20 | 4657,43 | 2888,44 | −2231,01 | 44,08 | 55,92 | +16,44 | −8,46 |
| 2024 | 50 | 4657,43 | 2888,44 | −2231,01 | 44,08 | 55,92 | +16,44 | −8,46 |
| 2025 | 10 | 3519,63 | 849,96 | −1330,34 | 32,97 | 67,03 | −12,01 | −17,45 |
| 2025 | 20 | 3718,87 | 1246,30 | −1527,43 | 37,93 | 62,07 | −7,03 | −16,24 |
| 2025 | 50 | 3757,96 | 1368,78 | −1610,82 | 37,50 | 62,50 | −6,05 | −16,26 |
| 2026 | 10 | 5148,37 | 2959,17 | −1810,81 | 51,43 | 48,57 | +28,71 | −8,66 |
| 2026 | 20 | 4857,15 | 2820,63 | −1963,48 | 48,25 | 51,75 | +21,43 | −9,10 |
| 2026 | 50 | 4857,15 | 2820,63 | −1963,48 | 48,25 | 51,75 | +21,43 | −9,10 |

Les six cas 2024/2025 reproduisent **exactement** les trades et compteurs de v1.
Les TOP20/TOP50 2024 et 2026 ont les mêmes trades exécutés sous les contraintes
de portefeuille, pas seulement un capital final arrondi identique. Les
sélections plus larges ne signifient pas vingt ou cinquante positions ouvertes.
Le TOP10 2026 contient 140 positions closes : 72 gagnantes, 68 perdantes ;
profit factor 1,63, net +1 148,37 USD, intérêts nuls. Sept legs sortent sous le
stop sur gap : les pertes ne sont pas artificiellement plafonnées à 10 %.

`completion-audit.json` vérifie les neuf cas, les inputs/modèles/code, les
protections et la chronologie, les portefeuilles entièrement clos et la
réconciliation cash. Les données et identités sont raccordées localement ;
aucun SQL écrit, aucun ordre broker, aucun réentraînement de l'Oracle.
Résultat exploratoire : la perte 2025 demeure, donc pas de robustesse annuelle
ni de promotion automatique démontrée. **Arrêt après remise de cette baseline**
le 12 octobre ; reprise des challengers autorisée séparément le 13 octobre.
Leurs résultats ne doivent pas être confondus avec cette baseline immuable.

## Baseline économique

- LONG uniquement, rang décroissant de la tête LONG à J, TOP10 primaire,
  TOP20/TOP50 secondaires. Aucun rendement futur dans la sélection.
- Univers statique exact du modèle, 1 790 titres. Pas de nouvelle suppression
  d'un titre parce que son rendement ou son chemin futur manque.
- 4 000 USD par cas, réinitialisés chaque année ; plafond natif huit positions,
  limites sectorielles, concentration, gaps, cash et régime conservés.
- Entrée open J+1, TP20/SL10 depuis le fill réel simulé, trailing OFF,
  expiration open de la 21e séance détenue.
- Collision quotidienne stop d'abord, gap stop au véritable open ; une perte
  peut donc dépasser 10 %. Un gap TP conserve le prix limite conservateur.
- 2024 et 2025 : décisions sur l'année, dernières sorties en janvier suivant.
  2026 : décisions jusqu'au 3 septembre, derniers dénouements au 5 octobre.
  Ne pas appeler ce dernier chiffre « performance annuelle complète 2026 ».
- Les coûts canoniques et intérêts éventuels sont appliqués par le ledger,
  pas un calcul indépendant qui somme des rendements de titres.

Fichiers `baseline-2024.json`, `baseline-2025.json`, `baseline-2026.json`,
`baseline-report.json` et `baseline-report.md` ; chaque cas contient aussi
`trades.parquet`, `daily.parquet`, décisions, exécutions et progress.json.
Chiffres : capital initial/final, gains/pertes après coûts, net, nombre de
positions gagnantes/perdantes/neutres, pourcentages, rendement, DD maximal,
profit factor, intérêts, réconciliation cash et capital marqué à la date coupe.
Les legs de réduction d'une même position sont regroupés avant win rate.
Les gains/pertes de positions et le net du compte peuvent différer des intérêts.

## Réserves communes, non masquées

Recherche exploratoire, pas certification PAPER/LIVE. Univers de survivants,
secteurs actuels non PIT déjà acceptés, OHLC ajustés actuels fournisseur,
publication par champ macro/selector non certifiée. Les années 2024–2026 ont
déjà été examinées dans d'autres expériences et ne sont pas des tests vierges.

Les corrections documentées AVB/EQR/VMRK et volumes BAND/GPRE/ATEX des archives
qualifiées sont réutilisées localement pour le replay. La version initiale v1
présentait une différence entre features et prix corrigés. La remédiation v5
reconstruit les features affectées à partir des caches pleine précision et
recalcule les rangs transversaux ; les canaris pré-correction restent identiques.
Les scores 2024/2025 sont inchangés. Les scores 2026 ont été régénérés avec les
poids figés : AVB ne figure plus dans les sélections TOP10/20/50 après correction,
sans suppression du titre. Les empreintes et écarts sont conservés dans
`correction-audit.json` et `remediation-inputs.json`.
Les chemins détenus manquants, identité ambiguë et créance non valorisée font
échouer le cas ; ils ne sont ni imputés ni escamotés.

### Raccordement de TOELY à TELWY (v6)

Le référentiel de corporate actions Alpaca confirme le changement de nom/CUSIP
TOELY → TELWY le 17 septembre 2026 (889110102 → 889110201), puis le split 5:1
TELWY le 7 octobre. Ce n'est pas une fusion avec paiement de rompus : la
conversion conserve quantité, coût, barrières et échéance du lot initial.
Le split est déjà neutralisé dans la base de prix ajustée commune ; il n'est
pas appliqué une deuxième fois aux positions.

Les réponses EODHD du successeur sont archivées et leurs empreintes vérifiées.
Les 11 séances de recouvrement concordent avec le prédécesseur : écart OHLC
maximal inférieur à 0,003 %, volume inférieur à 0,047 %. Les 17 séances du
17 septembre au 9 octobre sont présentes, avec volumes positifs. Aucun prix
du successeur n'est injecté avant son changement de ticker, malgré l'historique
retrospectivement raccordé par le fournisseur. Les volumes EODHD sont conservés
sur la même base que l'archive : pas de seconde multiplication par cinq.

`lifecycle.json` décrit les preuves, la normalisation et les réserves. La
migration atomique des protections est **simulée**, pas certifiée à partir
d'ordres historiques d'un courtier. Le volume OTC n'a pas de certification
indépendante et les frais propres à une corporate action de compte ne sont
pas observés. Ces réserves excluent toute affirmation de parité LIVE complète.
Le snapshot d'actif Alpaca actuel déclare TOELY inactif/non négociable, sur OTC.
Le raccordement économique local ne démontre donc pas l'exécutabilité
historique de chaque entrée par Alpaca et ne contourne aucun garde LIVE.
Les anciennes versions échouées sont conservées. La v6 ne modifie ni SQL,
ni l'univers, ni les scores v5, ni les modèles : seulement le raccordement local
des prix et du lifecycle manquants. 108 tests ciblés passent avant le recalcul.

## Protocole des trois challengers, dans cet ordre

Les données d'ajustement viennent des TOP50 **OOF honnêtes** du modèle, rangés
avant qualification future des labels. Fit 2018–2021, validation en 2022 ;
les labels dont la disponibilité franchit la coupe sont purgés. Aucun seuil,
profil, paramètre ou early stopping n'est ajusté sur 2024–2026. LightGBM petits
arbres, seed fixe, validation chronologique, modèles enregistrés séparément.
Pas de réentraînement ou remplacement de l'Oracle utilisateur.

Les features candidates sont fixées : momentum, force relative, volatilité,
ATR, drawdown, position dans le range, RSI, volume relatif, marché SPY et les
deux scores Oracle/différence. Pas de VIX rétrospectivement comblé, consensus
inexistant avant sa collecte ni information future transformée en feature.
Les labels de trades unitaires déduisent les coûts plats canoniques : ce sont
des proxys d'apprentissage, pas la parité exacte des coûts de taille/portefeuille.
Les conclusions économiques viennent exclusivement des replays complets.

### 1. Filtre d'entrée

Cible : trade unitaire TP20/SL10 positif net de coûts approximés. Classifieur
binaire, seuil de probabilité figé **0,50**. Filtrer après le TOPN ; ne pas
remplacer un refus par le rang N+1. TP/SL, expiry, sizing et risque de baseline
inchangés. Aucun filtre Oracle LONG/SHORT automatique : stratégie LONG.

### 2. Modèle quotidien de sortie

États uniquement après avoir survécu aux protections intraday. Features : âge,
PnL courant, MFE/MAE observés, distance SL/TP et features prix/marché du jour ;
scores Oracle d'entrée conservés comme en apprentissage. Poids par trade pour
ne pas compter vingt états comme vingt trades indépendants.
Cible : avantage KEEP jusqu'à la sortie TP/SL/temps de référence par rapport
à une vente au prochain open. Sortie si l'avantage prédit est négatif, sans
réglage sur les tests. Décision close J, exécution open J+1. **SL10 reste dur**,
TP20 reste actif : ni annulation d'un stop déjà touché ni extension de la perte
par une prédiction de récupération. Priorité open : événements/expiry, stops,
transitions de régime, puis sortie apprise. Histoires transmises limitées à J.

### 3. TP/SL personnalisés et sizing

Choix parmi trois couples prédéfinis : TP10/SL7, TP20/SL10, TP25/SL10.
Régression du rendement unitaire approximé divisé par le SL ; choix du meilleur
score **prédit**, jamais du meilleur profil réellement observé dans le test.
Choix arrêté à J avant l'open, puis barrières ancrées au fill de J+1.
Quantité plafonnée par le budget de risque du moteur divisé par
`close_J × SL × 1,03`, et jamais augmentée au-delà des contraintes déjà approuvées.
Le facteur 1,03 couvre le gap d'entrée maximal accepté, pas les gaps de sortie.
Risque au fill vérifié, protections auditées et cash réconcilié.
Contrôle supplémentaire **TP20/SL10 avec exactement la même règle de sizing**
avant de comparer les barrières personnalisées. Cela sépare l'effet sizing de
l'effet choix de profil. Un profile est figé pour la vie du trade, pas élargi
pendant une perte. Trailing OFF et durée vingt séances conservés.

## Critères de lecture

Ne pas optimiser uniquement le taux gagnant. Par année et TOPN, comparer net,
DD, gains sacrifiés, pertes éliminées, trades conservés, exposition et coûts.
Le filtre peut réduire tellement l'activité qu'une amélioration du win rate
ne vaut plus économiquement ; une absence de trade n'est pas un gain démontré.
Les trois expériences sont séparées : pas d'empilement des gagnants a posteriori.
Une erreur de baseline bloque le lancement des challengers ; une erreur de
challenger bloque le suivant. Aucune promotion ou écriture SQL automatique.

## Suivi et reprise

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_tp20_sl10_new\20261012-v6\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_tp20_sl10_new\20261012-v6\BASELINE\2026-TOP10\progress.json
```

Préparation OOF seule : `fit-data/progress.json`, sans entraînement. Ne pas
lancer simultanément deux writers de baseline/expériences sur la même racine.
Les cas terminés sont relus avec empreintes ; les cas failed repartent avec
ledger neuf, jamais avec des décisions/positions partiellement mutées.
La version du code/config et les inputs sont figés ; changement significatif
exige une nouvelle version de campagne, pas un assouplissement du protocole.

Commande de reprise de la baseline, **uniquement après arrêt de l'autre writer** :

```powershell
python -u -m scripts.research.us_oracle_tp20_sl10_campaign --output artifacts/research/us_oracle_tp20_sl10_new/20261012-v6 --phase baseline
```

Ne pas lancer l'ancien `--phase experiments` ni `--phase all` sur la baseline v6.
La campagne autorisée utilise `scripts.research.us_oracle_challengers` dans
une nouvelle racine ; gestion des profils et scores du symbole d'entrée,
ordres de sortie différés à travers un changement de ticker et garde de
disponibilité de tous les labels, y compris l'open d'expiration, sont testées
séparément. Les fichiers de la baseline v6 ne sont pas remplacés.
