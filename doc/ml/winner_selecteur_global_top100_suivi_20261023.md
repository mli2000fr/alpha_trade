# Suivi du sélecteur global TOP100

Run : `artifacts/research/us_winner_global_selector/20261023-v1/`.
Protocole : [contrat figé avant entraînement](winner_selecteur_global_top100_protocole_20261023.md).

## État au lancement

Le contrôle initial des grilles donnait149/3000comptes1x et20/3000comptes2x,
tous deuxRUNNING, aucune erreur. Contrôle ultérieur :157/3000 et49/3000,
toujoursRUNNING. Ce sont des instantanés, pas les compteurs finaux.
Ne pas arrêter, modifier ni relancer ces calculs pour préparer le modèle.

TOP100 figé :234 500lignes sur2345séances,817titres distincts, rangs avant
couverturefuture. Après espacement et purge de maturité :

| Split | Ancres candidates avant qualité des prix |
| --- | ---: |
| Apprentissage TOP100,2017–2024 |7082|
| Validation TOP10,2025 |138|
| Test TOP10,2026au30septembre |123|

Au total7343ancres,747titres.182907occasions réservées pour chevauchement
intra-titre,39330horsTOP10 primaire d'évaluation et4920labels nonmûrs au cutoff
du split. Les7343ancres ne sont pas7343observations de marché indépendantes :
les titres peuvent partager les mêmes périodes/chocs. Sixsimulations par
ancre ne multiplient pas par six l'effectif indépendant.

Douze tests unitaires passent. Smoke de **126comparaisons vectoriel/scalaires**
sur vraiesbarres SIP passé. Il teste le résolveur, pas un avantage appris.

La construction est lancée, un seul processus de recherche/fit CPU, pendant
que les quatreworkers des deuxgrilles continuent. En début de passage le
processus attendait la fin complète du rattrapage2018 (23223/23270tranches,
0échec au snapshot), puis reprend automatiquement. Aucun nouveau téléchargement
Alpaca/EODHD, aucun appelGPT, aucun SQLwrite ouordre. Ne pas interpréter
`WAITING_2018_CATCHUP` comme un modèle entraîné ou comme un nouveau blocageAPI.

## Déroulement et contrôle

`progress.json` distingue attente, `DATASET_READ_ONLY`, fitLightGBM, insuffisance
et échec. Les snapshots sont effectués parsymbole en transactionsSQL READONLY
libérées entre symboles. `symbols/<ticker>/snapshot.json` lie les fichiersbruts ;
`parts/<ticker>.json` compte les ancres qualifiées/réservées et audits de sorties.
Une reprise vérifie et ignore les parties déjà scellées.

Si l'effectif **après** qualification est inférieur à500/50/30, le run s'arrête
avec statut explicite, sans entraîner artificiellement unmodèle. Sinon fitglobal
sur2017–2024 seulement. Prix/volume titre et contexteSPY ; macro révisable et
secteursactuelsnonPIT exclus des prédicteurs. Aucun identifianttitre/année.

Le modèle et le constant choisi sur2025 sont figés dans `model/fit.json`
avant évaluation2026. Sorties finales attendues :

- `model/selector.txt` : poidsLightGBM recherche ;
- `model/fit.json` : profildefeatures, compteurs et comparateur2025 ;
- `unit-comparison.csv` : métriques unitaires, pas PnLannuelportefeuille ;
- `validation-test-decisions.parquet` : décisions et prédictions traçables ;
- `report.json` : verdict, comparaison, bootstrap mensuel et limites.

Ce premier modèle choisit SL/TP/trailing/horizon parmi sixprofils figés.
Confirmation, fractioninitiale, renforcement et budgetrisque ne sont pas appris.
Le résultat peut êtreNO_GO même si les poids ont été entraînés. Pas d'activation
automatique en live/PAPER ni de nouveau réglage après lecture de2026.

### Reprise effectivement constatée après la fin de2018

Le rattrapage2018 est ensuite passé **COMPLETED23270/23270**,0échec,
4838réponsesvides,0rejet ;27023762barres soumises enUPSERT, pas un décompte
de nouvelleslignesuniques. Les réponsesvides ne certifient pas des séances
complètes. Le sélecteur a quittéWAITING et produit ses premières parties :
snapshotà72/747titres,218ancres qualifiées,541réservées. Ce n'est ni le nombre
final d'apprentissage ni un fit terminé.

Contrôle simultané des rapports de comptes :171/3000en1x,56/3000en2x,
aucun `failure.json` ; workers annuels actifs. Le résuméglobal1x est moins
récent que les fichiers `year-2017.json`/`year-2019.json` : pour ce contrôle,
les rapports de cas terminés et les états annuels ont servi de référence,
pas un compteurglobal périmé. Aucun processus relancé pour ce décalage.

Logs : `log/winner-global-selector-top100-20261023-v1.stdout.log` et
`log/winner-global-selector-top100-20261023-v1.stderr.log`.

Reprise pendant la construction, une fois le processus précédent arrêté :

```powershell
python -u -m scripts.research.us_winner_global_selector_20261023 --phase all
```

Verrou exclusif du dossier. Ne pas relancer un fit déjà scellé : un amendement
demande un nouveau protocole/dossier, pas l'écrasement des résultats existants.
