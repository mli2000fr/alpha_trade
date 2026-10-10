# TOP10 réel H20 : ne conserver que les futurs positifs, SL initial 7 %

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Objectif et protocole — 7 octobre 2026

Suite du [TOP10 réel des deux signes](us_realized_top10_fixed_sl7.md).
Simulation **doublement clairvoyante** : on connaît les dix plus grandes
amplitudes futures H20, puis on sait écarter leurs rendements négatifs.
Elle mesure le potentiel économique d'une direction correcte, pas la capacité
d'un modèle à distinguer D1/D10 et pas une stratégie de production.

Pour chaque date, figer d'abord les dix titres ayant les plus grandes valeurs
absolues du rendement H20 close J → close J+20. Appliquer ensuite la qualité
locale des endpoints, puis le filtre **rendement strictement positif**. Ne pas
reclasser dix nouveaux positifs et ne pas remplacer les négatifs par le
onzième titre. L'ordre d'origine et sa priorité synthétique sont conservés.
Un positif n'est pas nécessairement D10 et une cible H20 positive ne garantit
pas un trade gagnant après gap d'entrée, stop ou autres sorties.

## Couverture

- Univers : 1 798 titres avec labels archivés.
- 419 dates classables jusqu'au 3 septembre 2026.
- 4 190 occurrences initiales du TOP10 réel.
- 4 189 qualifiées : KLAC du 20 mai 2026 reste non qualifié, sans remplacement.
- **3 133 positives conservées**, 1 056 négatives retirées.

Les dates suivantes sans H20 observable n'ont pas de nouvelle sélection réelle.
Les positions continuent à être suivies jusqu'au 30 septembre 2026. Ce test
ne peut donc être comparé naïvement à un run dont la sélection quotidienne
continuerait sur ces dernières dates.

## Portefeuille conservé

Capital 4 000 USD, huit positions maximum, sizing ATR et règles de risque/régime
inchangés. Stop initial à 93 % du fill réel, coûts conservés. Refus intégral
des ordres devenus incompatibles avec le budget à l'ouverture ; pas de resize.
Quatre variantes :

1. TP + trailing, sans échéance fixe ;
2. TP + trailing, échéance vingt séances après l'entrée ;
3. sans TP ni trailing, stop initial seul, échéance vingt séances après entrée ;
4. sans TP, avec trailing, échéance vingt séances après entrée.

Les gains ne sont pas plafonnés par un TP dans les deux dernières variantes.
Le stop 7 % n'est pas une garantie de perte maximale en cas de gap ou de coûts.
Le trailing reste ATR lorsqu'actif ; seul le stop initial est fixé à 7 %.

## Reproductibilité et limites

Réutilisation du fichier brut archivé de la campagne réelle précédente :
`realized-top10-sl7-20261007-v2/bars-raw.parquet`. Son empreinte et celles des
labels sont vérifiées avant calcul. Même macro et mêmes secteurs actuels non
PIT ; mêmes corrections fournisseur de volume BAND/GPRE, sans ajout inventé.
Pas de requête SQL avec `--market-archive`, aucune écriture SQL, entraînement,
intervention sur les batches existants ou configuration live.

Le score `1-rang/1000` est un support de priorité synthétique utilisant le futur,
**pas une probabilité Oracle prédite**. Les pondérations sensibles au score
restent donc conditionnées à cette convention. Le changement de sélection
modifie également les chemins de portefeuille : comparer les résultats complets,
pas soustraire simplement les pertes d'un ancien run.

Les contrôles de volume, prix et identité sur positions détenues restent actifs.
L'ancien ATEX à volume nul n'est pas réparé ici. Si une variante s'arrête, son
résultat est marqué FAILED, sans rendement complet. Les autres repartent dans
un ledger indépendant : leur calcul n'est pas contaminé par le run arrêté.

## Tests, lancement et suivi

17 tests ciblés passent, dont deux nouveaux sur le filtre positif appliqué
**après** le classement, l'absence de remplacement, la conservation des rangs
et l'exclusion des endpoints invalides et rendements nuls. Le smoke de trois
séances termine les quatre variantes avant le lancement complet.

Commande exécutée :

```powershell
python -u -m scripts.research.us_concentrated_realized_top10 --output artifacts/research/us_concentrated_replay/realized-positive-top10-sl7-20261007-v1 --positive-only --market-archive artifacts/research/us_concentrated_replay/realized-top10-sl7-20261007-v2 --continue-after-variant-error
```

Surveillance globale :

```powershell
Get-Content artifacts/research/us_concentrated_replay/realized-positive-top10-sl7-20261007-v1/progress.json
Get-Content log/batch/realized-positive-top10-sl7-20261007-v1/stderr.log -Tail 10 -Wait
```

Chaque variante possède un `progress.json` quotidien. Le rapport racine agrège
les quatre tentatives : `COMPLETED` seulement si les quatre réussissent, sinon
`PARTIAL_FAILED`. Les échecs restent explicites. `entry_rejections.json` archive
les refus de budget qui sont distincts des erreurs de qualité des données.
Au moment de rédaction, le calcul complet est lancé, sans rendement final validé.
