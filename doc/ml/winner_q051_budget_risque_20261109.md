# Q051 H10 0,50 : conserver le rendement en réduisant le DD

GO utilisateur du 9 novembre 2026. Même témoin continu 2021–01/10/2026 à
+206,51 %, DD intraday −36,89 %, 4 000 USD initiaux. Aucun changement de
production ; simulations isolées en mémoire et données archivées en lecture seule.

## Trois règles figées avant les nouveaux résultats

| Variante | Changement par rapport au témoin |
| --- | --- |
| STATIC75 | Risque par entrée 0,90 % au lieu de 1,25 %, poids maximal 15 % au lieu de 20 %, plafond des achats 0,75× au lieu de 1× |
| VOL20 | Budget de volatilité annualisée du portefeuille projeté après achat ≤20 %, covariance sur 60 rendements journaliers entièrement connus la veille ; réduction seule de la quantité native |
| REGIME_VOL20 | Même budget VOL20 + filtre de nouvelles entrées SPY : clôture précédente strictement >98 % de SMA200 |

Les trois gardent : TOP10 % Oracle → TOP5 LONG, score>0,50/AUC≥0,50,
six modèles annuels H10, mêmes 6 073 candidatures archivées, entrée journalière
J+1, position complète, SL5, sans TP/trailing/renforcement, sortie open11.
B4/DD15 et liquidation globale off ; aucune pause arbitraire ajoutée. Limites
de quantité entière, capital partagé, répétition/cooldowns et minimum 50 USD
conservés, facteurs/corrélation/limites sectorielles off. Frais 8 bps par opération,
financement annuel 6,5 %. Compte margin capacité 2× mais achats bornés par le
plafond de risque de la variante. Aucun reset annuel ni renflouement fictif.

### Ce que fait exactement VOL20

L'approbation native dimensionne d'abord l'entrée. L'adaptateur de recherche
calcule les poids des positions réellement détenues et ordres en attente,
rapportés à l'equity observable, puis ajoute le candidat à sa quantité native.
Covariance empirique annualisée ×252 sur les 60 dernières séances de rendements,
strictement antérieures à l'ouverture. Aucune donnée future ni retour ffill.
Le seuil de 20 % est une volatilité prévue annualisée, pas un DD maximal de 20 %.

Si le risque projeté dépasse le budget, résolution de l'équation quadratique de
variance pour plafonner la seule quantité du candidat. Les contrôles natifs sont
ensuite réexécutés sur cette quantité réduite : pas de contournement du minimum,
du capital, de la concentration ou d'un refus natif. Si le risque des positions
existantes dépasse déjà le budget, aucune nouvelle entrée n'est autorisée.
Historique incomplet ou invalide : refus de l'entrée documenté, pas de covariance
ou probabilité inventée. Les positions détenues ne sont jamais liquidées par ce
budget : elles gardent leur SL5/open11. L'allocation redevient possible dès que
les données observées et le risque prévu le permettent. Aucun facteur >1.

L'adaptateur est installé uniquement dans chaque processus de recherche sur
`approve_daily_open` ; il appelle le code natif original, ne modifie ni le moteur
de comptabilité ni les règles de sortie, et est restauré en sortie de contexte.
Le code du replay, de risque et des exécutions de production reste inchangé.
Les décisions sont conservées dans `result/portfolio-risk-decisions.csv`.

## Validation et critères

Avant les variantes, un replay témoin complet avec adaptateur inactif doit
reproduire neuf indicateurs du témoin archivé : capital final, rendement, DD,
trades, gagnants, perdants, frais, financement et exposition moyenne. Tolérance
monétaire 1e−6 USD / relative 1e−10, sans correction de prix ou résultat.
Échec du témoin → arrêt de la campagne, aucune variante publiée.

Huit tests passent : absence d'effet des prix futurs, prise en compte des
covariances et ordres en attente, refus des historiques incomplets, quantité
toujours ≤approbation native, contrôle natif après réduction et reproduction
des fills/cash avec adaptateur off ; sélection et sorties des trois variantes
inchangées ; filtre de régime antérieur et abstention cohérents.

Comparaison au témoin et à SPY sur la même fréquence de clôture journalière.
SPY prix seuls, sans dividendes/frais/levier, +103,56 %, DD daily −25,36 % dans
les mêmes cours archivés. Le témoin a un DD daily −36,80 %, son DD intraday étant
−36,89 %. Les deux DD seront publiés pour les variantes ; pas d'assimilation.
Critère explicite : rendement le plus élevé parmi les variantes dont le DD daily
est au plus aussi sévère que SPY sur cette période. Si aucune ne satisfait ce
critère, le résultat est négatif, sans retoucher les seuils après coup.
Bilans annuels et trimestre de perte examinés pour voir si l'avantage dépend
uniquement de 2022 ou d'une concentration de gains. Ce n'est pas une garantie
future de DD≤SPY : stops, gaps et variations de corrélations peuvent le dépasser.

## Exécution et historique

Programme : `scripts/research/us_winner_q051_risk_budget_20261109.py`.
Adaptateur : `scripts/research/us_q051_portfolio_risk_policy_20261109.py`.
Dossier : `artifacts/research/us_winner_q051_risk_budget/20261109-v1`.
Journal : `artifacts/research/launch-q051-risk-budget-20261109-v1.log`.
Suivi : `progress.json`, puis `BASELINE/progress.json` et
`STATIC75`, `VOL20`, `REGIME_VOL20` chacun avec `progress.json` et `result/`.
Témoin d'abord ; trois processus de variantes en parallèle après PASS.
Import IHM séquentiel à la fin de chaque réussite :

- `20261109_continu_Q051_050_STATIC75_v1`
- `20261109_continu_Q051_050_VOL20_v1`
- `20261109_continu_Q051_050_REGIME_VOL20_v1`

Comparaison globale `comparison.csv`, `report.json`, benchmark SPY, bilans annuels,
trades, coûts, capital engagé, risque 5m et courbes sont conservés. Les résultats
anciens restent intacts. Les modèles annuels et prix sont ceux de
`us_winner_continuous_q051_q088/20261108-v2`, vérifiés par empreintes.

Limites : analyse rétrospective après de nombreux essais sur ces années, pas de
validation indépendante sur données inédites. Secteurs actuels, version actuelle
des cours historiques et couverture 5m incomplète ; repli OHLC adverse-first
conservé. Pas de parité live certifiée. Aucun appel fournisseur/LLM, entraînement,
écriture SQL, transfert ou ordre réel.

## Résultats finaux — 9 novembre 2026, vérifiés à 01h39 Paris

Les neuf indicateurs du témoin sont reproduits exactement : validation PASS.
Les trois variantes sont terminées sans échec et importées dans l'historique IHM.
Aucune covariance manquante lors des décisions candidates : VOL20 2 608
décisions, 2 342 réductions ; REGIME_VOL20 2 281 décisions, 2 030 réductions.

| Variante | Capital final USD | Rendement | DD clôtures quotidiennes | DD intraday | Trades | Taux gagnant | Capital engagé moyen USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Témoin Q051_050 | 12 260,32 | +206,51 % | −36,80 % | −36,89 % | 1 234 | 35,01 % | 5 461,32 |
| STATIC75 | 9 200,50 | +130,01 % | −27,39 % | −27,40 % | 1 242 | 34,86 % | 3 661,64 |
| VOL20 | 8 272,99 | +106,82 % | −23,40 % | −24,29 % | 1 081 | 35,62 % | 2 492,61 |
| REGIME_VOL20 | 9 039,00 | +125,98 % | −23,40 % | −24,29 % | 940 | 36,17 % | 2 396,13 |
| SPY prix seuls | 8 142,50 | +103,56 % | −25,36 % | non disponible | — | — | — |

VOL20 et REGIME_VOL20 satisfont le critère historique daily DD pas pire que SPY ;
REGIME_VOL20 a le meilleur rendement de ces deux cas. STATIC75 conserve un peu
plus de rendement, mais échoue sur ce critère. Le budget+regime perd 80,53 points
de rendement contre le témoin et améliore son DD daily de 13,40 points. Les DD
identiques des deux budgets ne signifient pas des courbes identiques : leur pire
épisode peut être commun avant que le filtre de régime les différencie.
`quarterly-comparison.csv` conserve aussi les rendements des trimestres sans reset
de portefeuille. Les bilans annuels natifs restent dans chaque `result/`.

C'est un compromis observé après plusieurs essais sur les mêmes années, pas un
contrôle indépendant ni une garantie de DD futur. Le rendement de SPY exclut ses
dividendes, tandis que les frais et financement des stratégies sont inclus ;
ne pas présenter cette différence comme un alpha net certifié contre SPY total
return. Les trois bilans natifs restent `INCOMPLETE_COVERAGE`, repli daily OHLC
explicite conservé, et la configuration de production n'a pas changé.
# Raccordement à l’écran de backtest — 9 novembre 2026

Le profil **Volatilité 20 % + régime** devient le choix initial du menu
« Profil de paramètres du backtest ». Il reprend Q051 seuils 0,50 : TOP10 %
Oracle → TOP5 LONG per-symbol, entrée quotidienne à l’ouverture J+1,
SL5 %, sans TP/trailing/renforcement, sortie open11, plafond de risque 1×,
capacité margin 2× et B4/DD15 désactivé.

Les options propres au replay exposent désormais le budget de volatilité
annualisée du **portefeuille** (20 %, covariance sur 60 séances antérieures)
et le régime SPY (clôture J > 98 % de SMA200). Elles sont transmises par
la commande de lancement au moteur Winner. La quantité approuvée par le
risque natif peut seulement diminuer ; un refus natif n’est jamais contourné.
Les positions détenues ne sont pas liquidées par ces nouvelles options.
Un historique incomplet refuse l’achat concerné. Ces réglages nécessitent
l’entrée journalière J+1, sans renforcement pour le budget de volatilité.

Le bouton **Voir les courbes et leur comparaison**, sous « Réappliquer le
profil choisi », ouvre les trois courbes historiques Q051 / volatilité 20 %
+ régime / SPY, les chiffres et les modèles annuels. Les DD sur clôtures
sont distingués des DD intraday. Le profil ne choisit pas automatiquement
les six modèles annuels et ne change pas les dates déjà saisies. Le graphique
est une archive de référence, pas le résultat de modifications du formulaire.

Aucun réglage de production, de compte réel ou de modèle n’a été modifié.
Les tests vérifient le formulaire, sa commande, le parseur, le moteur natif,
la causalité des données, la composition du régime avec le filtre options
et l’identité du calcul de volatilité avec l’expérience initiale.

## Extension demandée : cinq variantes supplémentaires

Campagne : `artifacts/research/us_winner_vol20_extensions/20261109-v1`.
Période continue du 01/01/2021 au 01/10/2026, 4 000 $ initiaux,
mêmes modèles annuels H10, frais 8 pb/opération et financement annuel 6,5 %.

| Variante | TOP Oracle | Per-symbol | Plafond achats | B4/DD15 | Vol.20 % + régime |
|---|---:|---|---:|---|---|
| Vol.20 % + régime ×2 | 10 % | TOP5 LONG, score >0,50/AUC ≥0,50 | 2× | Non | Oui |
| Vol.20 % + régime sans per-symbol | 10 % | Aucun | 1× | Non | Oui |
| Q051 sans per-symbol | 10 % | Aucun | 1× | Non | Non |
| Q088 sans per-symbol | 20 % | Aucun | 2× | Oui | Non |
| Q088 sans per-symbol + vol.20 %/régime | 20 % | Aucun | 2× | Oui | Oui |

« Sans per-symbol » transmet **tous** les candidats du TOP Oracle au risque,
dans l’ordre du score d’amplitude, sans seuil de score LONG ni d’AUC,
sans restriction TOP5/TOP10. Maximum 20 positions simultanées ; les autres
contraintes du profil sont conservées. Les prix originaux restent inchangés.
Les couples titre/date non encore archivés sont lus dans SQL existant en
lecture seule et figés avant les quatre variantes élargies. Aucun appel
fournisseur, GPT, nouvel entraînement, ordre ou écriture SQL.

Les cinq variantes sont terminées, sans échec technique, et importées dans
l’historique IHM. `comparison.csv`, les bilans annuels et
`charts/capital-comparison.png`/`.svg` sont disponibles. Le graphique inclut
SPY et les deux témoins antérieurs ; les courbes protégées 1×/2× se superposent.

| Variante | Capital final USD | Rendement | DD daily | DD intraday | Trades | Taux gagnant | Capital engagé moyen USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vol.20 % + régime ×2 | 9 039,00 | +125,98 % | −23,40 % | −24,29 % | 940 | 36,17 % | 2 396,13 |
| Vol.20 % + régime sans per-symbol | 3 946,64 | −1,33 % | −43,16 % | −43,39 % | 2 544 | 31,13 % | 1 838,31 |
| Q051 sans per-symbol | 10 675,29 | +166,88 % | −74,61 % | −74,62 % | 1 908 | 26,78 % | 4 868,67 |
| Q088 sans per-symbol | 13 877,42 | +246,94 % | −56,91 % | −58,36 % | 4 994 | 30,50 % | 9 973,14 |
| Q088 sans per-symbol + vol/régime | 4 171,49 | +4,29 % | −39,26 % | −39,89 % | 3 638 | 32,57 % | 2 229,87 |

Le plafond 2× ne change aucun résultat financier du profil protégé 1× : la
limite de volatilité reste contraignante avant le plafond des achats. Retirer
per-symbol dégrade le DD sur ces règles ; avec vol/régime, le rendement devient
proche de zéro. Cela ne constitue pas une preuve générale d’efficacité
directionnelle du modèle : le nombre, l’ordre et la composition des candidats
changeraient simultanément (TOP179/358 contre TOP5 LONG).

Aucune nouvelle variante n’améliore simultanément rendement et DD du profil
protégé de référence. Les cinq sorties natives restent `INCOMPLETE_COVERAGE`
avec protections OHLC daily en secours : une campagne techniquement terminée
n’est pas une couverture intraday certifiée. SPY reste hors dividendes/frais.

