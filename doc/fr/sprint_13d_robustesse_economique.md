# Sprint 13-D — Robustesse économique exploratoire figée

## Statut et conclusion

Expérience terminée le 4 octobre 2026 : **96/96 cellules exécutées, zéro blocage**.
Les 24 cellules baseline reproduisent exactement les métriques du Sprint 13-C.
**Aucune des quatre variantes Oracle n'est rentable sur les deux folds**, même
dans le scénario nominal avec fiscalité inconnue non appliquée. Aucun candidat
n'est promu au shadow/live ; aucun réglage de production n'est changé.

Ce travail est une sensibilité après observation du développement, **pas une
confirmation indépendante**. Les preuves strictes manquantes ne sont pas
remplacées par ce rejeu. La période réservée 2026 n'est pas consultée.

## 1. Protocole écrit avant les calculs

Source : `artifacts/fr/research/provider_exploratory_13b/exploratory-20261004-v8`.
Le script vérifie les hashes des résultats archivés, des implémentations et
des sources de réparation, puis le protocole initial et les intentions figées.
Un dossier neuf est obligatoire. Le protocole 13-D est écrit avant le premier
rejeu, avec les hashes du code et des entrées.

| Variante | Entrée | Budget par nouvelle position | Sortie |
|---|---|---|---|
| baseline | Ouverture originale | Capital à l'ouverture / 8 | Clôture H5 originale |
| delay_1 | Ouverture de la séance suivante | Capital à l'ouverture / 8 | Même clôture H5 originale |
| cap_10pct | Ouverture originale | Minimum du budget baseline et 10 % du capital à l'ouverture | Même clôture H5 |
| delay_1_cap_10pct | Séance suivante | Même plafond de 10 % | Même clôture H5 originale |

Le retard raccourcit donc la détention de cinq à quatre intervalles de séance.
Ce n'est **pas** un nouveau H5 démarrant après le retard. Le classement et les
informations disponibles restent ceux du signal initial : aucune confirmation
de prix ni nouveau score à la date retardée, aucun filtre rétrospectif.

Le plafond porte sur le **budget d'entrée frais inclus**, calculé avec les
positions valorisées à l'ouverture et les créances de dividende. Ce n'est pas
un plafond permanent après un bond de cours : aucun rééquilibrage forcé n'est
introduit. Une forte variation peut porter l'exposition au-delà de 10 %.

Trois politiques : Oracle TOP20 LONG, ATR TOP20 LONG et contrôle uniforme
figé. Deux folds indépendants, capital initial de 4 000 EUR chacun, huit
positions maximum, titres entiers, sans SHORT, marge ou empilement.
Deux scénarios fiscaux × deux scénarios de coûts × quatre variantes × trois
politiques × deux folds = 96 cellules.

La sélection des titres est conservée, mais les **trades exécutés ne sont pas
nécessairement les mêmes** : le retard change la durée d'occupation du
portefeuille, le cash et les arrondis. Il ne faut pas interpréter les résultats
comme le simple changement de prix d'entrée des 168 trades initiaux.

## 2. Résultats nets nominaux

Scénario `unknown_untaxed` : les éligibilités fiscales positives connues restent
taxées ; seule l'éligibilité inconnue n'est pas taxée dans cette hypothèse.
Ce n'est pas une décision juridique d'exonération.

| Politique | Variante | Fold 6 | Fold 7 |
|---|---|---:|---:|
| Oracle | baseline | −23,89 % | +63,81 % |
| Oracle | delay_1 | −27,91 % | +93,46 % |
| Oracle | cap_10pct | −20,03 % | +49,40 % |
| Oracle | delay_1_cap_10pct | −24,13 % | +69,38 % |
| ATR | baseline | −35,22 % | +52,42 % |
| ATR | delay_1 | −37,81 % | +74,26 % |
| ATR | cap_10pct | −29,85 % | +41,13 % |
| ATR | delay_1_cap_10pct | −32,84 % | +57,22 % |
| Uniforme | baseline | −13,23 % | −10,42 % |
| Uniforme | delay_1 | −28,44 % | −0,46 % |
| Uniforme | cap_10pct | −11,48 % | −7,36 % |
| Uniforme | delay_1_cap_10pct | −22,47 % | +1,13 % |

Fold 6 : décisions du 29 juillet 2024 au 23 janvier 2025, fin de tape le
30 janvier. Fold 7 : décisions du 24 janvier au 23 juillet 2025, tape prolongée
jusqu'au 1er octobre pour payer les créances. Les métriques quotidiennes
incluent cette queue de cashflows. Ne pas additionner ces deux portefeuilles
comme un unique historique de richesse continue.

Oracle reste supérieur à ATR dans ces huit comparaisons nominales. Face au
contrôle uniforme, il reste inférieur sur le fold 6 pour baseline et cap,
presque à égalité mais supérieur avec delay seul (+0,53 point), et inférieur
avec delay+cap. L'avantage n'est donc pas uniforme entre périodes/références.

### Stress et fiscalité inconnue appliquée

| Variante Oracle | Fold 6 | Fold 7 |
|---|---:|---:|
| baseline | −37,49 % | +34,95 % |
| delay_1 | −44,09 % | +50,56 % |
| cap_10pct | −32,86 % | +25,25 % |
| delay_1_cap_10pct | −39,63 % | +35,55 % |

Les commissions, spread et slippage sont doublés dans le stress ; le taux
fiscal ne l'est pas. Les taux TTF historiques suivent le profil existant, avec
règlement T+2 supposé. « Net » signifie net des quatre composantes modélisées,
pas net de toute fiscalité personnelle ou étrangère.

## 3. Risque, rotation et concentration

Drawdown maximum Oracle : baseline 27,90 % / 25,25 % ; plafond 10 %
23,51 % / 20,96 % (folds 6/7). Le plafond réduit le risque et les gains mais
ne crée pas de direction profitable. Avec retard+plafond : 27,13 % / 20,93 %.
Sans retard, 168 trades fermés par cellule ; avec retard, 208. La détention
plus courte libère plus tôt la capacité et augmente les frais fixes totaux.

Concentration du fold 7 Oracle nominal :

| Variante | PnL net | Meilleur trade net | PnL moins ce trade, attribution seulement |
|---|---:|---:|---:|
| baseline | 2 552,46 EUR | 2 674,89 EUR | −122,43 EUR |
| delay_1 | 3 738,58 EUR | 2 843,37 EUR | +895,22 EUR |
| cap_10pct | 1 976,04 EUR | 2 121,05 EUR | −145,00 EUR |
| delay_1_cap_10pct | 2 775,24 EUR | 2 200,86 EUR | +574,38 EUR |

Le retard ne fait donc pas disparaître toute contribution positive hors meilleur
trade dans le fold 7, contrairement à la baseline. Mais le meilleur trade
reste dominant et le fold 6 reste perdant. La soustraction est une attribution,
**pas un backtest excluant le titre** : aucun capital n'est réalloué et aucun
nouveau candidat n'est introduit dans ces chiffres.

## 4. Implémentation et reproduction

`service/fr/robustness_engine_13d.py` est une copie isolée du moteur exploratoire
13-B avec une seule option de budget d'entrée. Le moteur archivé 13-B et le
moteur strict 12-B ne sont pas modifiés. Le runner `service/fr/robustness_13d.py`
transforme causalement les dates d'entrée, conserve les dates finales originales,
refait entièrement le portefeuille cash, ses dividendes et ses frais, puis
vérifie exactement les 24 baselines. Prix/événements inconnus détenus bloquent
la cellule ; aucun titre n'est éliminé parce que son futur est incomplet.

```powershell
python -u -m service.fr.robustness_13d --source artifacts/fr/research/provider_exploratory_13b/exploratory-20261004-v8 --output artifacts/fr/research/robustness_13d/nouveau-dossier
```

Résultats finaux : `artifacts/fr/research/robustness_13d/fixed-20261004-v2` contient
`protocol.json`, `progress.json`, `report.json` et les 96 ledgers. Le rapport
inclut coûts, exposition, drawdown, Sharpe, trades, attributions et comparaisons
appariées pour chaque scénario. Aucun entraînement, réseau ou écriture SQL.

Les tests vérifient la reproduction du moteur initial, l'absence de mutation,
les dates et l'information causale, la sortie initiale, les bornes du plafond,
le budget frais inclus et la réconciliation cash/trades.
**60 tests ciblés passent**, dont huit nouveaux tests 13-D. Ce résultat ne
signifie pas que toute la suite de l'application a été exécutée.

## 5. Décision et suite

**NO-GO de promotion**, sans rejet du modèle d'amplitude. On n'a pas validé une
politique LONG H5 profitable stable, ni une nouvelle capacité D1/D10. Ne pas
choisir `delay_1` sur son +93,46 % puis le présenter comme une confirmation.
Ne pas ajuster le retard, le plafond ou les filtres sur les pertes du fold 6.

Sprint 13-D exploratoire est terminé. La clôture stricte reste conditionnée aux
[preuves et benchmark manquants](TODO_sprint_12_reste_a_faire.md). La période
2026 demeure réservée ; aucune activation shadow/live ni passage automatique
au sprint suivant.

Voir aussi [Sprint 13-C](sprint_13c_reparations_decision_economique.md) et
[planning FR](sprint_planning_integration_marche_francais.md).
