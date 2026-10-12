# Oracle 2026 — conversion AVB et réserve sur les features

> Suite autorisée le 12 octobre : les features AVB et les rangs communs ont été
> [réparés puis les scores recalculés](oracle_tp_sl_grid_20261012.md). Les deux
> contrôles TOP10 2026 terminent désormais en mode strict, sans créance inconnue.
> Ce document conserve le scénario antérieur, aux scores contaminés ; ne pas
> le confondre avec les nouveaux résultats.
> La grille finale est désormais terminée : 72 portefeuilles stricts, aucune
> créance non valorisée. Les erreurs de volume BAND sont corrigées séparément
> avec les preuves archivées ; voir le nouveau rapport pour les valeurs actuelles.

## Conclusion du 12 octobre 2026

Le raccordement de recherche permet de terminer **six scénarios LONG** :
ancien et nouveau modèle, TOP10/20/50. Les trois contrôles stricts du nouveau
modèle restent bloqués par le produit et la date inconnus du paiement des
fractions. **Ce n'est ni une validation prédictive 2026, ni une parité courtier
certifiée, ni un rendement complet du patrimoine du nouveau modèle.**

Une réserve supplémentaire est confirmée : les features AVB figées contiennent
une fausse baisse le 13 juillet. Les corriger dans les prix d'exécution seulement
ne répare pas les scores déjà calculés. Aucun modèle, score archivé, configuration
de production, batch, ordre courtier ou donnée SQL n'a été modifié.

## Périmètre conservé

- Même univers et classement figé que la [comparaison initiale](oracle_barrier_comparison_top10_20_50_20261012.md).
- Toujours LONG : ancien classement d'amplitude et nouvelle tête LONG.
  Aucun PnL SHORT, aucun abaissement du seuil directionnel.
- Même capital 4 000 USD, sizing natif, coûts et contraintes ; SL fixe 7 %,
  TP fixe 20 %, sans trailing, expiry à l'ouverture de la 21e séance depuis
  l'entrée J+1. La fusion ne redémarre pas l'horloge de détention.
- Décisions 02/01/2026–03/09/2026, sorties finales jusqu'au 05/10/2026.
- Aucun titre retiré, aucune vente fictive avant radiation, aucun futur résultat
  utilisé pour remplacer un candidat inconnu.

## Événement et collecte bornée

Le [8-K officiel de clôture](https://investors.avalonbay.com/sec-filings/all-sec-filings/content/0001104659-26-097833/tm2623381d1_8k.htm)
confirme l'échange de **1 AVB contre 2,793 actions du survivant**, effectif le
17 août 2026, AVB suspendu avant l'ouverture ; le ticker devient VMRK le 18 août.
Le 17 août, le titre du survivant est encore négocié sous EQR. L'identité interne
VMRK utilisée par le replay distingue ce ticker de négociation dans l'audit.

Quatre GET supplémentaires bornés : barres SIP `adjustment=split` AVB, EQR,
VMRK et métadonnées publiques VMRK. Réponses et checksums sont archivés dans
`successor-evidence`. Les barres sont observées aujourd'hui : il ne s'agit pas
d'une preuve de leur version publiée historiquement. Deux dates de recouvrement
EQR/VMRK sont identiques en OHLC ; les 37 séances de queue nécessaires sont présentes.
**Aucune barre AVB n'est fabriquée après sa radiation.**

## Correction de base de prix, sans correction SQL

Le rapprochement indépendant porte sur 657 séances AVB :

| Partie de l'archive | Séances | Action dans le replay |
| --- | ---: | --- |
| Prix AVB d'origine | 632 | Inchangés |
| Prix déjà divisés par 2,793, du 13/07 au 14/08/2026 | 25 | OHLC × 2,793 ; volume ÷ 2,793 |

On ne multiplie surtout pas toute la série. Le facteur est qualifié date par
date par comparaison des quatre prix avec Alpaca. Une différence résiduelle
de low de 0,335 % le 03/06/2026 est conservée et documentée ; les autres ancres
de cette séance coïncident. Les flux ne sont donc pas déclarés identiques.

Au jour de fusion seulement, quantité × 2,793 et prix d'entrée/SL/TP ÷ 2,793,
une fois. Le coût d'origine est réparti entre actions entières livrées et
créance de fraction. Les protections suivent le chemin de la position AVB,
pas les anciens hauts d'une position EQR sans rapport. Les gaps conservent
la convention native de fill à l'ouverture lorsqu'un stop est franchi.

## Fractions et limites de parité

Le [contrat de fusion, §4.8](https://www.sec.gov/Archives/edgar/data/915912/000110465926064781/tm2615292d1_ex2-1.htm)
prévoit la vente groupée des fractions par l'agent d'échange puis distribution
du produit net. **Le prix réel et la date de crédit ne sont pas qualifiés.**

- `STRICT` : refuse une créance de fraction non qualifiée avant conversion.
- `UNVALUED_RECEIVABLE` : n'échange que les actions entières ; la fraction
  reste une créance séparée, valeur et date `NULL`, cash utilisable zéro.
- Il n'y a ni paiement à zéro supposé, ni écriture en perte définitive,
  ni arrondi supérieur, ni pouvoir d'achat créé avec une valeur estimée.
- Les trois nouveaux scénarios ont chacun une créance de 0,884352206 action
  du successeur, avec coût d'origine alloué de 60,106707 USD.
- Le remplacement des protections est simulé atomiquement à l'ouverture,
  non observé chez le courtier. Les lots co-détenus ambigus restent refusés.

La [documentation Alpaca](https://docs.alpaca.markets/us/docs/mandatory-corporate-actions)
signale que des ordres GTC peuvent être annulés lors d'opérations sur titres.
Une [réponse officielle Alpaca](https://forum.alpaca.markets/t/corporate-actions-handeling/19325)
précise aussi que les comptes paper ne mettent pas en œuvre ces opérations.
Le replay local n'est pas présenté comme une reproduction de ces événements paper.

## Résultats de scénario, pas validation du modèle

Rendements du cash et des positions entières ; **créance de fraction exclue**
pour le nouveau modèle. Les taux du tableau ne sont pas un rendement complet
de son patrimoine. Aucun seuil n'est adapté à ces résultats.

| N | Ancien au 03/09 | Ancien après sorties | Nouveau au 03/09 | Nouveau après sorties | DD ancien / nouveau |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | +4,46 % | +6,11 % | +15,86 % | +18,60 % | −11,00 % / −6,22 % |
| 20 | +0,53 % | −1,01 % | +15,06 % | +17,47 % | −10,76 % / −6,22 % |
| 50 | +4,74 % | +4,53 % | +15,06 % | +17,47 % | −10,76 % / −6,22 % |

Réconciliation du cash, après allocation explicite du coût de la créance :
erreur absolue maximale inférieure à 10⁻¹¹ USD. Cela ne valorise pas la créance.
Les trois cas stricts restent bloqués ; aucun rendement complet du nouveau
modèle n'est annoncé. Les résultats 2025 ne sont pas recalculés dans ce travail.

## Réserve prédictive majeure : features AVB contaminées

Le 13/07/2026, l'archive de features donne :

| Mesure | Archive figée | Prix AVB en unité d'origine |
| --- | ---: | ---: |
| Rendement quotidien | −63,6942 % | +1,4022 % |
| Gap d'ouverture | −63,9069 % | +0,8080 % |

Les features de momentum, ATR et volatilité sont affectées, avec des fenêtres
glissantes et potentiellement des rangs transversaux. Le nouveau classement
sélectionne AVB sur 13 dates pour TOP10 et 14 pour TOP20/50, toutes pendant
la période de base mixte ; l'ancien ne le sélectionne pas dans ces trois TOP.
La position convertie avait été achetée le 23 juillet. **Le problème n'est donc
pas uniquement un ticker manquant à la fusion : la sélection amont est réservée.**

Les scores n'ont pas été recalculés, conformément au protocole figé. Le verdict
qualifié est `LIFECYCLE_SCENARIOS_COMPLETED_PREDICTIVE_VALIDATION_NOT_QUALIFIED`.
Un rejeu distinct avec features puis rangs/scores recalculés sur prix cohérents
sera nécessaire avant toute conclusion de supériorité 2026. Cela peut conserver
les modèles entraînés ; aucune nécessité de réentraîner n'est démontrée ici.

## Peut-on retirer AVB ?

Pour les nouvelles entrées, l'exclusion depuis le 17/08/2026 est légitime :
AVB est radié. Elle ne supprime pas les positions acquises auparavant.
Une exclusion de tout l'historique est possible comme **expérience séparée**,
annoncée explicitement et appliquée aux deux modèles ; elle ne constitue pas
la réparation du test initial, et les anciens rangs construits avec AVB resteraient
à qualifier. Aucun fichier d'univers n'est modifié par cette remédiation.

## Code, tests et suivi

Scripts de recherche :
`us_oracle_merger_ledger.py`, `us_oracle_merger_replay.py`,
`us_oracle_merger_feature_audit.py`. Les hooks du driver ne s'activent que pour
le ledger de recherche spécialisé ; contrats existants conservés par défaut.
Tests spécifiques : 15 réussis, couvrant conversion unique, fraction non
valorisée, refus strict, conservation cash/SL/TP/expiry, gap SL, ticker 1:1,
volume absent, base mixte, prix inexpliqués, alias divergent et queue absente.
Suite ciblée complète modèle/audit/comparaison/replay : **145 tests réussis**,
sans couverture globale imposée ; les warnings pandas/numpy restent signalés.

### Le gain 2025 vient-il simplement du TP à 20 % ?

Non : l'ancien et le nouveau utilisent déjà tous deux `FixedBarrierLedger`,
qui fixe le SL à 7 % et le TP à 20 % du fill. Le même driver applique la même
expiry et les mêmes contraintes. L'ancien avec TP 20 % est donc déjà le
comparateur des chiffres 2025 ; aucun test supplémentaire n'est nécessaire
pour cette question. Le résultat favorise la sélection du nouveau dans ce
replay, mais ne démontre pas l'effet causal du seul nouveau label : paramètres
d'apprentissage différents, année déjà examinée et réserves de données.

```powershell
Get-Content artifacts/research/us_oracle_barrier_comparison/merger-replay-20261012-v1/progress.json
```

- [Rapport final qualifié — à lire en priorité](../../artifacts/research/us_oracle_barrier_comparison/merger-replay-20261012-v1/reviewed-report.md).
- [Synthèse qualifiée JSON](../../artifacts/research/us_oracle_barrier_comparison/merger-replay-20261012-v1/reviewed-report.json).
- [Preuve de contamination des features](../../artifacts/research/us_oracle_barrier_comparison/merger-replay-20261012-v1/feature-lineage-audit.json).
- [Protocole et rapprochement prix](../../artifacts/research/us_oracle_barrier_comparison/merger-replay-20261012-v1/protocol.json).

Les rapports initiaux et leurs échecs restent archivés. Les sorties complètes
de ce scénario restent en V1. Ne pas lancer deux processus dans le même dossier.
