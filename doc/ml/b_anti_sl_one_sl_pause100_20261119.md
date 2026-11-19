# B + anti-SL TOP10 — un SL déclenche une pause de 100 séances

Demande du 19 novembre 2026 : vérifier si l'on réduit les pertes répétées du même titre en suspendant ses nouveaux achats après **un seul stop exécuté**, au lieu d'attendre deux ou trois pertes.

## Comparaison figée

Deux comptes continus 4 000 $, 2021–1er octobre 2026, sans remise à zéro annuelle :

- REFERENCE : reproduction du témoin B + anti-SL TOP10, attendu +303,52 %/DD intraday −34,98 % ; publication seulement après égalité de toutes les transactions et courbes quotidiennes/intraday, tolérance 1e−8.
- ONE_SL_PAUSE100 : même stratégie, avec interdiction de nouvel achat du titre après chaque sortie STOP ou STOP_GAP effectivement exécutée dans **ce compte**.

La séance du stop reste bloquée dès que le stop est connu, ainsi que les **100 séances NYSE suivantes**. Réentrée admissible à la 101e séance suivante, sous réserve des autres contrôles. Les weekends/jours fériés ne comptent pas. Une sortie open11 ne déclenche pas cette pause. Aucun arrêt général du portefeuille ; les autres titres restent admissibles.

Un stop intrabar n'est connu qu'à la clôture de sa bougie 5 minutes ; un stop sur gap est connu à son prix d'ouverture observé. Double vérification de l'interdiction : préouverture puis revalidation native juste avant l'achat, pour bloquer un stop sur gap connu seulement à cette ouverture. Aucune utilisation des futurs stops du témoin pour piloter la variante.

## Périmètre de sélection

Pour isoler le coût/bénéfice de la pause, les deux comptes utilisent les **8 992 mêmes candidats archivés** : TOP10 % Oracle H10, univers 1 790/TOP179, puis TOP10 LONG B29, score >0,50/AUC calibration ≥0,50, veto anti-SL44 sans remplissage.

Le titre en pause est refusé **après cette sélection et à l'exécution**, sans promotion d'autres candidats. **Ce test ne reclasse pas l'univers avant Oracle.** Cette convention a été annoncée au lancement. L'ancien essai « deux SL dans 30 séances → pause100 avant Oracle », sur T0/B sans anti-SL, est distinct : ses chiffres ne sont pas réutilisés comme résultat de cette nouvelle règle.

Pas de nouveau fit ni recalibrage. Les modèles annuels causaux, variables et seuils antérieurs sont inchangés. La pause utilise les ordres réellement exécutés ; une occasion qui n'a pas été achetée ne peut pas déclencher de pause.

## Portefeuille et prix

Position entière complète, entrée daily J+1 sans confirmation, SL5 %, aucun TP/trailing/renforcement, sortie open11. Risque par entrée 1,25 %, poids maximal 20 %, vingt positions, minimum 50 $, plafond nouvelles entrées 1×/capacité margin 2×. Contrôles natifs de concentration conservés, y compris leur convention de pertes brutes. Sans B4/DD, budget vol20, filtre de régime, facteurs/corrélation/secteurs supplémentaires.

Frais 8 points de base par achat/vente, financement natif inclus. Mêmes matrices daily et archives 5m que les contrôles validés le 19 novembre ; liens locaux aux fichiers figés et empreintes. Aucun téléchargement, lecture/écriture SQL, appel LLM ou broker, changement de modèle/batch/configuration de production.

Les limites ne disparaissent pas : univers contemporain, prix révisés, intraday incomplet/repli OHLC, réserves de labels/prix héritées et aucun nouveau holdout indépendant. Une pause peut empêcher une perte mais aussi un rebond rentable. Il faut rejouer capital et réallocations ; soustraire les pertes des trades exclus ne donne pas le rendement de la variante.

## Vérifications

Six tests ciblés passent : disponibilité temporelle, un seul SL suffit, échéance exacte à 100 séances suivantes, STOP_GAP à l'ouverture, autres sorties sans pause, aucun remplacement/rang modifié, adaptation désactivée identique au moteur natif, stop réel qui bloque l'achat de la séance suivante dans le moteur complet. Commande ciblée : `python -X utf8 -m pytest tests/test_b_one_sl_pause_20261119.py -q --no-cov` ; la couverture globale du projet n'est pas évaluée par ce sous-ensemble.

Le bilan rapprochera équité/PnL/frais/positions ouvertes, pauses et ventes réelles, absence d'achat pendant les pauses, reproduction du témoin, rendement/DD/taux gagnant/exposition/années et fenêtre fin2024–avril2025. Les occasions signalées mais non achetées seront distinguées des vrais trades du témoin ou de la variante.

## Suivi

Archives : `artifacts/research/us_b_one_sl_pause/20261119-v1`.

- `protocol.json` : règle et sources figées.
- `progress.json` : coordinateur des deux cas.
- `cases/REFERENCE/progress.json` et `cases/ONE_SL_PAUSE100/progress.json` : séance courante sur 1 443.
- `logs/` : sorties propres aux deux processus.
- `cases/*/result/pause-triggers.json` : stop réellement exécuté, disponibilité et séance de reprise.
- `selection-decisions.json`, `execution-vetoes.json` : refus avant achat.
- Bilan prévu : `comparison.csv`, `annual-comparison.csv`, `capital-curves.csv`, `capital-comparison.png`, `final-status.json` et revue complémentaire des détentions/prix.

Les deux calculs et contrôles sont terminés. Le témoin reproduit ses archives : transactions, équité daily et intraday, à 1e−8 près. Les résultats ci-dessous sont ceux du replay complet ; le reçu intermédiaire `variant-pre-review.json` est conservé mais n'est pas le bilan final.

## Résultat

| Mesure | Référence B + anti-SL | Un SL → pause 100 séances |
| --- | ---: | ---: |
| Capital final valorisé | 16 140,82 $ | 4 497,60 $ |
| Rendement cumulé | +303,52 % | +12,44 % |
| DD maximal intraday | −34,98 % | −36,93 % |
| Trades clôturés | 1 356 | 807 |
| Taux gagnant | 38,13 % | 35,44 % |
| Capital brut engagé moyen | 7 069,05 $ | 2 613,87 $ |
| Exposition brute / équité, moyenne | 84,57 % | 59,30 % |
| Gain moyen des trades gagnants | 119,38 $ | 72,53 $ |
| Perte moyenne des trades perdants | −59,42 $ | −38,92 $ |

**Variante non retenue dans ce protocole sans remplacement** : rendement nettement inférieur et DD global plus mauvais. Aucun seuil de pause n'est modifié après lecture du résultat et aucun changement de production n'est appliqué.

469 pauses effectivement déclenchées sur **305 titres**. 6 169 occurrences candidat/date bloquées dans la liste figée ; ce ne sont pas 6 169 trades qui auraient tous été achetés sans pause. Les refus de capital, les positions déjà détenues et les contraintes natives restent en place.

## Période de baisse ciblée et déplacement du DD

Entre le **6 novembre 2024 et le 4 avril 2025**, rendement du compte : **−34,08 %** pour le témoin, **−17,93 %** pour la pause100. DD de clôture sur cette fenêtre : −34,08 % et −21,41 %. Les capitaux de départ de cette fenêtre diffèrent déjà (12 764,63 $ et 4 906,01 $), à cause des années antérieures ; comparer les rendements normalisés, pas seulement les pertes en dollars.

Le mécanisme réduit effectivement les répétitions dans cette fenêtre : AGYS passe de trois stops à un ; ROAD de cinq à un, DECK et PRIM de trois à un chacun. Les dates et quantités initiales peuvent différer, car tout le portefeuille est rejoué. Cela ne permet pas d'attribuer chaque écart de PnL à un seul trade supprimé.

Le pire DD de la variante est désormais entre le **22 février 2021 et le 24 octobre 2022**, contre novembre2024–avril2025 pour la référence. Améliorer uniquement la crise observée ne suffit donc pas à améliorer le risque global.

| Année, compte continu | Référence | Pause100 |
| --- | ---: | ---: |
| 2021 | −7,41 % | −4,50 % |
| 2022 | +48,60 % | −11,18 % |
| 2023 | +74,96 % | +55,24 % |
| 2024 | +16,00 % | −14,80 % |
| 2025 | −14,49 % | −5,68 % |
| 2026 au 1er octobre | +68,99 % | +6,26 % |

## Coût des occasions manquées

822 trades effectivement achetés par le témoin se trouvent dans les pauses réellement connues du compte variante à leur date d'entrée : **315 gagnants et 507 perdants**, soit environ 60,93 % des gagnants et 60,43 % des perdants du témoin. La règle n'est donc pas sélective sur cette mesure. Leurs PnL nets de frais totalisent **+9 957,40 $** dans le témoin.

Ce montant est un diagnostic des occasions du témoin, **pas le capital que l'on ajoute ou retire au compte variante**. La variante dispose d'autres quantités et de capital libéré, qui permet aussi d'acheter certains candidats que le témoin ne pouvait financer ; ses 807 trades ne s'obtiennent pas en soustrayant simplement 822 aux 1 356 du témoin.

## Revue finale

- Six tests ciblés passent. Sources figées inchangées, modèles/scores/frais et configuration native de portefeuille identiques.
- Équité finale rapprochée avec trades, valorisation ouverte, frais et financement : erreurs <2e−10 $. Quantités BUY/SELL rapprochées, pas de survente, positions finales conformes, vingt positions maximum respectées.
- Chaque pause est liée à un stop effectivement exécuté dans son propre compte ; toutes les dates de reprise sont à 101 séances du déclenchement. Aucun achat pendant une pause connue. Aucun stop futur du témoin n'entre dans la décision de la variante.
- Réserve héritée BIDU : un écart de label première séance dans le témoin ; zéro dans la variante sur ses 805 trades à label connu. Pas de recalibrage ou modification des prix pour faire disparaître cet écart.
- Écran supplémentaire : volume daily nul le 18 juin 2026 pour ALNT/GNRC/QTWO effectivement détenus dans la variante. Ouvertures et extrêmes corroborés dans le cache 5m existant ; ALNT68/QTWO77 bougies, GNRC78, clôtures légèrement différentes du daily. Aucun prix substitué, aucune certification exhaustive ou indépendante des données. Preuves `volume-screen-review.json` ; ces réserves n'étaient pas couvertes par le seul écran de symboles signalés auparavant.
- Historique déjà exploré, univers contemporain, intraday partiel/repli OHLC, prix révisés et dividendes/corporate actions non exhaustivement certifiés. Résultat exploratoire, pas de parité live.

Fichiers finaux : `completion.json`, `final-status.json`, `comparison.csv`, `annual-comparison.csv`, `window-comparison.csv`, `max-dd-episodes.csv`, `window-symbol-trades.csv`, `opportunity-diagnostics.json`, `reference-opportunities-during-variant-pauses.csv` et reçus de pauses/exposition/volume. Aucun entraînement, fournisseur/LLM, SQL, ordre ou configuration de production modifiés.

![Comparaison globale et zoom](../../artifacts/research/us_b_one_sl_pause/20261119-v1/capital-comparison-and-zoom.png)
