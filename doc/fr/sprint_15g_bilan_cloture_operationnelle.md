# Sprint 15-G — Bilan de clôture opérationnelle FR

État vérifié le **6 octobre 2026**, fuseau Europe/Paris.

## Verdict

`CLOSURE_WITH_RESERVES_NOT_FULL_GO` : bilan de livraison établi, mais le gate
opérationnel complet du Sprint 15 n'est **pas** satisfait. Il n'est pas possible
de transformer une seule soirée de collecte en semaine d'exploitation prouvée.
Ce bilan ne valide ni stratégie économique, ni serving, ni trading FR.

Rapport reproductible :
`artifacts/fr/research/sprint15_closure/closure-20261006.json`.
Il provient du service `service/fr/operational_closure_15g.py`, qui lit les
rapports, la configuration et les logs locaux sans réseau, SQL, notifications
ou changement de tâche Windows. Ce n'est **pas** un nouveau batch de contrôle
quotidien, et il ne réintroduit pas `fr_pit_quality_daily` retiré par l'utilisateur.

```powershell
python -m service.fr.operational_closure_15g --as-of 2026-10-06
```

Sans `--output`, affiche seulement le bilan. Pour archiver une nouvelle revue,
utiliser un nouveau nom sous `artifacts/fr/research/sprint15_closure/` :
le service refuse d'écraser un rapport existant. Les conclusions manuelles
sur reprise réelle et publication SQL restent conservatrices et doivent être
réexaminées avant une qualification future.

## Preuves acquises

| Périmètre | Preuve | Limite |
|---|---|---|
| Catalogue et IHM FR | 13 sections, catalogue séparé, neuf tâches Windows FR trouvées | Installation n'est pas preuve d'exécution quotidienne |
| Barres EODHD | Run complet du 05/10 : 294 réponses, 1 744 barres persistées | FAILED : deux réponses vides et huit alertes de couverture |
| Actions EODHD | Run complet du 05/10 : 588/588 appels reçus, SUCCESS | Valeurs fournisseur, pas preuve officielle de toutes les modalités économiques |
| AMF/DILA | Rapports complets SUCCESS du 05/10 | Observation récente, pas validation directionnelle ni PIT historique |
| ESMA | Deux passages réels de qualification 15-E | Pas une semaine de tâche planifiée ; périmètre 330 ISIN figés |
| Sauvegarde DB | RESTORE_VERIFIED, qualification `20261005T191341-42dd10c5` | Preuve historique de structure/compteurs, pas audit juridique du contenu actuel |
| Sauvegarde artefacts | EXTRACTION_VERIFIED, `20261005T193256-a4610757` | 14 448 fichiers, 61 268 388 163 octets ; qualification antérieure aux suppressions de quarantaine |
| Notifications | Logs barres/actions/DILA : acceptation SMTP et Telegram ; Telegram ERROR sur échec barres | Acceptation/envoi journalisé ne prouve pas lecture ou réception finale dans la boîte utilisateur |
| MiFIR options | Run SUCCESS du 06/10, collecte partielle distincte | Ne qualifie pas NBBO, greeks, IV, open interest ni toutes les options FR |

Les deux réserves de droits existantes restent inchangées : INPI
`BLOCKED_INPI_RETENTION`, consensus Yahoo `BLOCKED_YAHOO_AUTOMATED_ACCESS`.
Borrow et options complètes restent `PENDING_PROVIDER`. Ces familles ne sont
pas nécessaires pour maintenir une collecte minimale de prix en recherche,
mais ne doivent pas être annoncées comme livrées/qualifiées pour ML.

## Échec des barres : réserve réelle, pas bug prouvé

Le dernier run complet porte la fenêtre **28/09–05/10/2026**.
Deux vérifications EODHD supplémentaires, sans persistance et sans toucher
au batch, ont confirmé zéro barre pour `LHYFE.PA` et `PERR.PA` sur cette fenêtre.
Le traitement fait donc correctement échouer les réponses vides sur une
fenêtre où le calendrier XPAR attend des séances. Aucun prix n'est inventé,
aucun titre n'est retiré silencieusement pour obtenir un statut SUCCESS.

Huit alertes de séances manquantes concernent `ACAN.PA`, `ALBOU.PA`,
`ALMER.PA`, `ALVIN.PA`, `ARTO.PA`, `MLCHE.PA`, `MLHK.PA`, `MLNMA.PA`.
Une absence peut relever de la source, du statut du titre ou d'absence de
transaction ; ne pas la déclarer suspension/radiation sans preuve.

Pour lever cette réserve : vérifier pour chaque titre l'ISIN, le symbole
fournisseur, la place et le statut à ces dates, puis disponibilité fournisseur.
Si une correction d'alias est prouvée, la tracer/versionner avant de reprendre.
Si une exclusion économique est prouvée, la dater explicitement ; ne pas
changer les intervalles historiques du titre à partir de son seul statut actuel.
Après réparation, reprise de la même fenêtre et contrôle des résultats.
Attention : `--resume` sur une nouvelle journée vise une nouvelle fenêtre,
pas nécessairement celle du run échoué du 05/10.

## Gates non démontrés et travail restant

1. **Semaine de fonctionnement** : cinq séances XPAR distinctes clôturées,
   runs complets sans anomalies inexpliquées. Plusieurs relances le même jour,
   un smoke ou une fenêtre J−7/J ne prouvent pas cinq jours d'exploitation.
   Le rapport au 06/10 considère les séances 29/09, 30/09, 01/10, 02/10 et 05/10.
2. **Reprise après interruption réelle** : tests unitaires de reprise présents,
   mais essai opérationnel d'arrêt/reprise non démontré. Le faire sur une racine
   de qualification distincte, hors tâche planifiée, sans tuer un batch existant.
   Vérifier checkpoints, archives et absence de doublons métier après reprise.
3. **Notifications** : confirmer côté destinataire mail/Telegram ; compléter
   la preuve pour les collecteurs sans log de launcher et les sauvegardes.
   Ne pas envoyer de fausses alertes en production pour simuler un échec.
4. **Publication quotidienne SQL** : les collecteurs de marché produisent
   principalement des fichiers versionnés. Il manque un raccordement qualifié
   vers staging SQL FR puis promotion contrôlée, avec dates d'observation,
   corrections et identité. Aucun branchement au loader historique sans adapter
   son contrat. Tables/migrations/SQL de référence et tests à prévoir ensemble.
5. **Restauration après évolution du périmètre** : les qualifications acquises
   ne garantissent pas le contenu des futures sauvegardes. Les anciens backups
   n'ont pas été purgés lors des suppressions de quarantaine demandées ; ne pas
   réintroduire des données suspendues en restaurant automatiquement ces archives.

Ces points ne nécessitent pas tous un fournisseur payant : semaine et réception
exigent une observation réelle ; publication/reprise exigent du travail technique ;
les réserves de source/statut exigent des preuves, pas une baisse des contrôles.

## Tests et modifications de cette tranche

**116 tests ciblés passent**, couvrant le nouveau bilan, EODHD quotidien,
collecteurs/runner FR, référentiel, sauvegarde et séparation des catalogues/IHM.
Les tests du bilan refusent de qualifier cinq relances comme une semaine,
un smoke, une alerte, un échec ou un run US ; ils utilisent le jour Paris et
ne confondent pas fenêtre de rattrapage et date réelle de collecte.
Ce n'est pas un résultat de toute la suite applicative.

Aucun modèle, donnée SQL, calendrier d'exploitation, tâche Windows ou statut
de collecteur n'a été modifié. La vérification ciblée EODHD était en lecture
seule. Les seuls nouveaux fichiers sont l'outil de bilan, ses tests et ce bilan,
avec mise à jour des documents décrivant l'état courant.

## Étape suivante

Terminer les réserves opérationnelles ci-dessus ; à défaut conserver ce statut
avec réserves. Le **Sprint 16-A** peut être préparé séparément : manifeste de
modèle/univers/horizon, interface de données qualifiées, préflight de fraîcheur
et refus explicite des données absentes ou sources suspendues. Aucun GO shadow
réel n'est implicite : le manque de données quotidiennes utilisables doit bloquer
une prédiction, jamais la compléter avec des données futures ou un fallback US.
