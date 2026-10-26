# Winner TOP20 — investigation de l'écart des dates de départ

Demande du 25 octobre 2026 : ne pas attribuer sans preuve l'écart de rendement
au seul démarrage six mois plus tôt ; investiguer et rejouer le nécessaire.

## Constats vérifiés avant les replays

Même politique effective de chaque campagne dans les deux comptes : LONG,
position complète, SL5 %, sans TP ni trailing, vingt séances de détention,
vente à l'ouverture de la 21e, pas de renforcement. Même jeu d'archives du
TOP20, mêmes frais de 8 pb par jambe, même moteur historique isolé et même
correctif de périmètre pré-ouverture. Aucun changement de modèle ou de prix.

| Compte | Capital initial | Capital fin 2019 | Capital fin 2024 | Rendement 2020–2024 |
| --- | ---: | ---: | ---: | ---: |
| Continu depuis juillet 2019 | 4 000 $ | 7 980,17 $ | 23 810,29 $ | +198,37 % sur le capital fin 2019 |
| Neuf depuis janvier 2020 | 4 000 $ | 4 000 $ | 5 178,78 $ | +29,47 % |

Le +495,26 % inclut les six mois de 2019. Même ramené à 2020–2024, l'écart
reste considérable : les seuls intérêts composés ne sont donc pas une
explication suffisante. Six positions sont héritées : AM, CPRX, NBR, REZI,
SM, UNFI. Les plans en attente, le budget de risque et les historiques
de concentration/B4 sont également différents.

Exemple de divergence : NBR est déjà détenu depuis décembre dans le compte
continu et sort le 6 janvier 2020 à l'ouverture. Le compte neuf entre le
6 janvier après confirmation et subit son stop le 7. Le PnL total d'un trade
commencé en 2019 ne doit PAS être assimilé à son gain depuis janvier 2020.

En 2022 : 275 achats dans le compte continu, 75 dans le compte neuf ;
64 contre 2 407 refus `CAMPAIGN_RISK_OR_CAPACITY_EXHAUSTED`. Ce sont des
tentatives de campagnes, pas des titres indépendants. Le motif générique
ne suffit pas à affirmer que tous les refus viennent du drawdown.

## Protocole borné : trois replays, un témoin existant

1. `CONTROL_FULL_REPRODUCTION` : reproduire juillet 2019–décembre 2024.
   Vérifier chaque clôture et chaque flux achat/vente/financement contre
   le témoin scellé, puis toute la courbe cinq minutes. Tout écart arrête
   l'étude : aucune attribution causale avant parité.
2. `FRESH_2020_MATCHED_CAPITAL` : même départ neuf de janvier 2020 que le
   témoin à 4 000 $, mais dépôt de 7 980,1667511581745 $, sans positions,
   plans ni mémoire héritée. Isole l'effet du capital, y compris arrondis,
   notionnel minimal et plafonds. Comparer les rendements et non les seuls
   dollars finaux. Pas de multiplication linéaire d'un résultat existant.
3. `WARM_RESET_GUARD_ONLY` : même compte continu jusqu'au 31 décembre 2019,
   puis réinitialiser seulement l'état B4 à la clôture effectivement observée
   et au régime déjà connu. Garder strictement cash, titres, quantités, plans,
   ordres, coûts et historique de concentration. Empreintes de l'état du compte
   identiques avant/après. Vérifier le préfixe 2019 contre le témoin.

Le troisième cas est une intervention diagnostique unique, **pas une règle
de production ni une optimisation du reset du drawdown**. Ses effets sont
conditionnels au portefeuille hérité. Les contributions ne sont pas additives :
les entrées suivantes changent à leur tour capital, concentration et risque.

Le témoin neuf à 4 000 $ est repris sans recalcul après vérification de ses
empreintes. Les trois nouveaux comptes sont exécutés successivement pour
ne pas multiplier la charge des nombreuses grilles encore en cours.

## Instrumentation et vérifications

Hooks uniquement dans le processus de recherche ; décisions natives renvoyées
sans modification. Détail de chaque réapprobation : allocation B4, equity,
budget figé/courant, pouvoir d'achat, quantité admise et motif exact du vérificateur
de contraintes, dont le minimum notionnel. Synthèse quotidienne des pics et
allocations, courbe du breaker, compte diagnostique au 31 décembre.

Audit indépendant : dépôt explicite (pas de constante 4 000 pour le cas 7 980),
cash partagé, frais, actions entières, stocks finaux, chaque sortie scalaire
SL/horizon sur bougies brutes, chaque entrée avec deux confirmations terminées,
chronologie, données des positions détenues, rendement et drawdown recalculés.

Le dimensionnement extérieur SL3/FULL du protocole multi-profils est conservé,
puis réduit une seule fois à la vraie politique SL5. Ne pas le remplacer
silencieusement par un autre sizing. Les paramètres actuels du YAML ne sont
pas utilisés : l'ancien contrat reste dix entrées sur 180 jours.

## Exécution et lecture

Module : `scripts.research.us_winner_start_state_audit_20261025`, phases
`prepare` puis `run`. Racine :
`artifacts/research/us_winner_start_state_audit/20261025-v1`.

- `initial-evidence.json` : constats scellés, pas un verdict causal.
- `progress.json` : compte et dernière séance terminée.
- `cases/<compte>/report.json` : résultat seulement après audit.
- `risk-decisions.parquet`, `guard-daily.json`, `breaker-5m.parquet` : explication
  des blocages et transitions. Les contrôles de contraintes sont observés sans
  les réexécuter une deuxième fois.
- `checkpoint-20191231.json` : preuve diagnostique de l'état, **pas un format
  qualifié de reprise technique**.
- `report.json` racine : synthèse seulement après les trois comptes audités.

Pas de SQL, collecte, LLM, entraînement, ordre ni modification en production.
Limites héritées : filtrage de couverture J..J+40 dépendant du futur, secteurs
actuels non PIT, hypothèses OHLC cinq minutes sans quotes historiques certifiées,
échantillon déjà exploré. Même une parité exacte ne transforme pas +495 % en
promesse de rendement ni en validation indépendante.

**État initial : protocole préparé ; résultats causaux en attente des replays.**
