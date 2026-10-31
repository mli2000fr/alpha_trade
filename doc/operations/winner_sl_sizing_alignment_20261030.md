# Winner : alignement du sizing et contrôle des SL — 30/10/2026

Évolution ultérieure de la même journée :
[interrupteur du nombre de titres par secteur et nouvelles relances](sector_ticker_limit_20261030.md).
Les résultats ci-dessous décrivent le passage précédant cette désactivation.

## Comportement corrigé

Lorsque `winner_pyramiding.enabled=true`, `load_risk_config` impose désormais :

- `fixed_stop_pct=winner_pyramiding.stop_loss_pct` ;
- des quantités entières ;
- pas de TP ATR appliqué à la place des protections Winner.

Le sizing, le risque par action et `stop_price_initial` utilisent cette distance
fixe. Le SL courant est **5 %**, le TP Winner **18 %**, sans trailing ni
renforcement. Une protection LLM ne remplace pas le SL Winner lorsqu'il est
activé. Winner désactivé conserve le comportement usuel du module risque.

`PositionSizer` autorise le calcul de distance fixe sans exiger un ATR pour
cette seule opération ; les autres qualifications des données restent actives.
Le cap de risque du sizer Kelly utilise aussi `stop_distance`, même si Kelly
reste interdit pour cette stratégie de rang Oracle non calibré.

Le résumé risque expose `sizing_stop_basis` et `sizing_fixed_stop_pct`.
L'ancien libellé technique `sizing_method=atr` reste compatible ; il faut lire
le nouveau champ pour distinguer les distances fixe et ATR.

## Protection détenue : interférence historique supprimée

Le watcher historique pouvait traiter une entrée déjà gérée par une campagne
Winner et remplacer son OCO par un trailing issu de sa propre configuration.
Les chemins de promotion du stop et d'armement des protections manquantes
ignorent désormais les triplets `(account_id, broker_mode, symbol)` appartenant
aux campagnes actives. Winner conserve la responsabilité de leur SL/TP.

Audit broker + campagnes : **19 lots détenus, tous qualifiés après correction**.
L'écart réel concernait OKTA/default : ancien OCO annulé et trailing natif 7 %
actif, alors que la campagne gelée demandait SL5/TP18. Hors séance régulière,
après verrou du compte et arrêt du service identifié, l'annulation du trailing
a été confirmée avant de restaurer un OCO natif : **stop 211,50 $ / TP 262,70 $**
pour une action achetée à 222,63 $. Les IDs ont été persistés dans le journal
OMS et la campagne avec une opération de réparation durable. Les 18 autres
lots n'ont pas été modifiés. Les stops sont comparés à chaque prix d'exécution
de lot, et non à une moyenne de position pouvant agréger plusieurs achats.

Les trois campagnes d'achat déjà ouvertes de test2 (BAND, COHU, SIMO) ont bien
une politique gelée à SL5 : le stop sera calculé sur leurs remplissages réels.
Aucun de ces achats n'a été annulé, redimensionné ou soumis une deuxième fois.

## Relances 11/12

| Compte | Étape 11 | Étape 12 |
| --- | --- | --- |
| default | BAND accepté à 7 actions ; COHU, SIMO, UCTT refusés pour nombre de titres par secteur | aucun ordre : revalidation BAND réduit 6 actions (après réserve de coûts) à zéro pour `max_tickers_per_sector atteint` |
| test1 | BAND 107 et COHU 106 retenus après réduction au poids maximal ; SIMO et UCTT refusés par limite sectorielle | BAND 107, limite 53,16 $, accepté par Alpaca et non rempli ; COHU bloqué par corrélation native |
| test2 | pas de relance des achats déjà acceptés | trois ordres existants conservés ; SL des positions détenues vérifiés |

Le minimum preset de default est bien **50 $**. La revalidation finale peut
conserver un plancher de régime plus strict (70 $ dans le snapshot observé) ;
ce n'est pas le motif du refus BAND, dont le montant proposé dépasse ces deux
planchers. Le motif générique `CAMPAIGN_RISK_OR_CAPACITY_EXHAUSTED` de l'étape
12 masque ici le détail ; le journal du checker précise le plafond sectoriel.

Les services default/test1 ont été rechargés avant exécution. Le redémarrage
test2 a d'abord manqué son heartbeat à cause d'un certificat fournisseur non
chargé ; l'interpréteur résiduel a été identifié puis relancé avec le bundle CA
vérifié du projet. Les **trois watchers sont vérifiés sains** au bilan final.
TLS est resté activé. L'échec distinct des notifications SMTP reste présent.

## Validation et preuves

112 tests ciblés réussis : sizing, Kelly, politique Winner, protections,
entrée standard, quantités entières et absence de collecte intraday inutile.
Deux tests élargis de télémétrie CLI restent bloqués sur leur contexte de
compte/mode incompatible avant le sizing ; leurs fixtures ne sont pas modifiées.

- `artifacts/operations/options_accounts_blackout_disabled/20261030T071303Z-3a444641/`
  contient le bilan, les confirmations broker et `winner_stop_final_verification.json`.
- `artifacts/operations/winner_stop_alignment/20261030T071139Z-56bffad2/`
  contient les audits avant/après, l'ancienne protection, la réparation OKTA et
  les preuves des services.
- Sélection partagée : `opt-1090d71f5dfa4fd2ae2b026b5510a0cc`.
- Risque default : `695411af1115494b`, exécution `affb4c50c89443e2`.
- Risque test1 : `fd5bbad724214739`, exécution `5dc7c8c0822a4d1a`.

Les anciennes décisions et leurs claims sont conservés. Aucun contrôle de
corrélation, concentration, budget, disponibilité des données ou drawdown n'a
été désactivé pour obtenir un ordre.
