# Qualification options FR — premier passage univers et unités

## Résultat du 6 octobre 2026 (séance du 5 octobre)

Le GO portait sur l'audit de la collecte partielle et la qualification des quantités,
pas sur l'activation du besoin options complet. Le runner a effectué une collecte
réelle, sans SQL ni modèle modifié. La commande Python directe utilisée pour cet
audit n'envoie pas de notification ; les passages Windows habituels restent notifiés
par le launcher commun.

| Mesure | Résultat |
|---|---:|
| Titres actifs vérifiés examinés | 294 |
| Titres avec transaction acceptée | 42 (14,29 %) |
| Sans transaction acceptée | 252 |
| Transactions sources (options + futures Paris) | 40 514 |
| ISIN sources résolus FIRDS | 993 |
| Transactions options de l'univers acceptées | 1 240 |
| Séries effectivement échangées retenues | 611 |
| Échecs de collecte | 0 |
| Lignes exclues pour annulation dans l'univers | 6 |
| Doublons exacts retirés | 0 |

Une seconde exécution réelle dans la même journée a rendu `SUCCESS` avec
294 demandés, 42 reçus, **0 nouvellement persisté**, zéro échec : même snapshot
réutilisé, pas de duplication de l'échantillon métier. Cela ne valide pas encore
la gestion de corrections reçues à une date ultérieure.

La résolution de 993 ISIN ne signifie pas 993 actions ni 993 options de l'univers.
La couverture 42/294 mesure uniquement une activité observée acceptée, **pas** la
proportion d'actions ayant des options cotées. Le fichier ne fournit pas un inventaire
exhaustif des séries non échangées. Les 252 absences ne sont pas remplies par zéro OI.

Les plus gros contributeurs sont Schneider (221 lignes), BNP (99), LVMH (94),
Danone (93), Renault (89), Société Générale (74), Saint-Gobain (52) et AXA (48).
Un apprentissage futur devra tenir compte de cette concentration et de la sélection
de grandes valeurs ayant des options actives.

## Unités : ce que la documentation prouve, et ne prouve pas

La [spécification officielle Optiq 2.6.1](https://www.euronext.com/sites/default/files/euronext_cash_and_derivatives_markets_-_optiq_files_specifications_-_v2...._2.pdf),
pages 76–77 du PDF (index 75–76), décrit `MifidQuantity` comme une quantité de
l'instrument, éventuellement nominale ou monétaire. Elle distingue les champs
de mesure des matières premières/émissions (`MiFIDQtyinMsrmtUnitNotation` et
`MifidQuantityMeasurementUnit`).

**Correction d'interprétation :** ces deux champs vides ne prouvent pas que la
quantité des options est invalide. Ils ne constituent pas non plus une attestation
du nombre de contrats. La spécification consultée est ancienne (2019), et ne
suffit pas à établir la correspondance exacte du CSV public courant.

Les 1 240 quantités acceptées sont positives et entières : c'est compatible avec
des nombres de contrats, mais pas une vérification indépendante. Les multiplicateurs
FIRDS constatés sont :

| Multiplicateur | Lignes |
|---|---:|
| 100 | 1 140 |
| 10 | 90 |
| 101 | 4 |
| 102 | 6 |

Les valeurs 101/102 nécessitent une preuve de deliverable/ajustement ; leur seule
présence ne prouve pas un ajustement correctement documenté. Aucune conversion
automatique quantité × 100, prime/notionnel, ou ratio put/call certifié n'est ajoutée.
`quantity_unit_qualified=false`, `put_call_contract_volume_ratio=null` et
`ml_eligible=false` restent imposés.

## Qualification technique reproductible

Service : `service/fr/mifir_options_qualification.py`, lecture hors ligne d'un
snapshot existant. Il vérifie les jointures, les clés de transactions acceptées,
la disponibilité et les quantités ; il mesure couverture, concentration, quantités
fractionnaires, mécanismes de marché, multiplicateurs et cas non standard.
Il ne modifie ni les snapshots sources ni la base et ne promeut aucune donnée.

```powershell
python -m service.fr.mifir_options_qualification --snapshot <chemin_du_snapshot.json>
```

Preuve auditée :
`artifacts/fr/operations/fr_options_mifir_trade_sync/snapshots/be2f4ad4668484fcac984d07aefe35ae39443572cbedc92e6d3516f7a07aa385.json`.

Rapport :
`artifacts/fr/research/options_mifir_qualification/7cee5d2a5353216bfd64c1f378421fe0d47d97d49781e64b7efafde4c2646ad6.json`.

Verdict : `PARTIAL_COLLECTION_VALIDATED_UNITS_NOT_QUALIFIED`. Aucun défaut de
jointure ni doublon accepté détecté. Ce n'est ni une certification de complétude
du feed ni une preuve de disponibilité historique avant collecte.

Validation logicielle : 51 tests ciblés passent (qualification hors ligne,
collecteur quotidien, POC et runner opérationnel FR).

## Suite et blocages exacts

1. Accumuler plusieurs séances réellement observées ; ne pas simuler demain avec
   un second téléchargement identique aujourd'hui.
2. Obtenir une définition Euronext actuelle explicite de la quantité du CSV public
   pour les options XMON, puis confronter des séries et une séance identiques à
   une mesure indépendante autorisée des volumes en contrats. La piste Excel
   abandonnée n'a pas été réintroduite.
3. Qualifier les contrats à multiplicateurs non standard et les changements entre
   snapshots, notamment leurs deliverables et dates d'effet.
4. OI et bid/ask demeurent absents de cette source. Aucun fournisseur supplémentaire
   n'est déclaré accessible ou gratuit sans nouveau test et revue de ses droits.

`fr_options_mifir_trade_sync` peut continuer à collecter en quarantaine.
`fr_options_snapshot` reste désactivé : ces contrôles ne satisfont pas encore
le besoin complet. Voir [collecte quotidienne](options_mifir_collecte_quotidienne.md).
