# Sprint 10-C2 — Audit des prix indépendants du fold 3

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Conclusion au 3 octobre 2026

Une source **officielle, gratuite et effectivement téléchargée** permet de
trancher une grande partie des désaccords de clôture du 19 octobre 2020.
Cela ne suffit pas à qualifier le fold 3 : aucun manifeste, panel, label,
modèle, table ou masque d'admission n'a été modifié. Aucun entraînement lancé.

## Anomalie documentée par la place de marché

Euronext décrit un incident le 19 octobre 2020, l'annulation de transactions
après 17 h 30 et la correction des clôtures. Les fournisseurs de données ont
été invités à réaligner leurs données. Il existe donc une explication
documentaire à vérifier, plutôt qu'une raison de préférer automatiquement
Yahoo ou EODHD.

- [Communiqué officiel](https://www.euronext.com/en/news/more-info-about-19-october-2020-market-status).
- [Fichier officiel des clôtures corrigées](https://live.euronext.com/media/516/download).

Le téléchargement HTTPS a retourné HTTP 200 avec le type XLSX. Le fichier
contient trois feuilles : actions, ETF et indices. Nous utilisons uniquement
`Equities_closing_prices_1910202`, 906 lignes de données et cinq colonnes :
ISINCode, MIC, CURRENCY, Symbol Index, Last Adjusted Closing Price.
Le terme « Adjusted » appartient à l'en-tête officiel ; nous ne l'assimilons
pas automatiquement à la série `adjusted_close` d'un fournisseur.

## Périmètre et méthode

Les 84 titres sont sélectionnés à partir du diagnostic gelé du fold 3 :
au moins une fenêtre feature ou label contient le 19 octobre 2020 avec le
motif `INDEPENDENT_PRICE_CORROBORATION_MISSING`. Ce ne sont pas 84 nouveaux
titres choisis en fonction d'un résultat ML.

1. Lire les identités de recherche vérifiées du Sprint 6-C.
2. Retenir le MIC observé actif à cette date, et non simplement le MIC actuel.
3. Rapprocher le fichier officiel sur **ISIN + MIC + EUR** ; aucun choix
   arbitraire d'une ligne si une identité est ambiguë.
4. Relire la clôture du cache Yahoo et celle de l'archive EODHD existante.
   Aucun nouvel appel Yahoo, aucune réécriture de ses données.
5. Comparer à la tolérance préexistante de **0,0001 EUR**. Ne pas l'élargir
   pour obtenir une meilleure couverture.
6. Vérifier séparément les désaccords open/high/low et volume. La source
   officielle de clôture ne contient pas ces champs.

## Résultats du rapprochement

| Résultat de clôture | Titres |
| --- | ---: |
| EODHD concorde avec l'officiel, Yahoo non | 78 |
| Les deux concordent | 4 |
| Aucun des deux ne concorde | 2 |
| Clôture officielle absente ou MIC ambigu | 0 |
| **Total audité** | **84** |

Parmi ces mêmes titres, **48** présentent également un désaccord entre
EODHD et Yahoo sur au moins un des champs open/high/low, et **83** sur le volume.
Un prix de clôture corroboré n'est donc pas une barre OHLCV entièrement validée.
Les quatre concordances de clôture ne sont pas une contradiction du diagnostic :
une barre peut être rejetée pour un autre champ ou par une preuve de couverture
incomplète. Il faut conserver cette distinction.

### Deux cas non résolus

| Titre | Clôture officielle EUR | EODHD | Yahoo |
| --- | ---: | ---: | ---: |
| SAN.PA | 85,72 | 85,2542 | 84,97577667 |
| SW.PA | 61,64 | 44,8452 | 44,97612381 |

Ces différences demandent une vérification des conventions de séries et des
actions sur titres. Une série historique retraitée peut ne pas être comparable
directement au prix diffusé en 2020. **La cause n'est pas démontrée ici** :
ne pas remplacer ces valeurs par l'officiel sans définir et vérifier la
convention de prix pour toute la série. Ne pas utiliser un ratio de correction
inventé à partir d'une seule journée.

## Ce qui bloque encore et prochaines actions

1. **OHLCV du 19 octobre 2020** : demander une référence officielle complète,
   incluant les transactions annulées/corrections et la convention de volume.
   Le XLSX trouvé ne justifie que les clôtures.
2. **Autres dates de prix** : traiter notamment le 27 janvier 2021 et les
   24–25 janvier 2022, puis toutes les autres dates listées dans les fenêtres
   du diagnostic. Les 84 titres ne couvrent pas tous les désaccords du fold.
3. **Conventions de séries** : vérifier SAN et SW avant toute réparation.
4. **ESMA** : conserver le blocage des six publications manquantes déjà
   documentées dans [10-C1](sprint_10c1_reparation_fold3.md). Une correction
   de clôture ne prouve pas le statut historique de cotation.
5. **Reconstruction seulement après preuves** : produire de nouveaux
   manifestes/panels/labels, comparer avant/après, puis requalifier le fold
   avec les seuils inchangés. Les sources gelées restent conservées.

Les archives Bnains déjà explorées restent une référence secondaire non
officielle ; elles ne doivent pas devenir silencieusement une preuve de
négociabilité PIT. Aucun nouvel achat, contact externe ou abonnement n'a été engagé.

## Reproductibilité et fichiers

Script : `modelFactory/fr_official_close_audit.py`.
Test : `tests/test_fr_official_close_audit.py`.

Rapport de référence :
`artifacts/fr/research/official_close_audit/euronext-20201019-audit-20261003-final/report.json`.
Le XLSX brut est conservé dans ce même répertoire. Le rapport contient les
84 rapprochements et les SHA256 du XLSX, des diagnostics, des identités,
du code, des caches Yahoo et des payloads EODHD.

SHA256 du XLSX :
`e42ebf4f81e8b9baf67136b80e61f99ef034bf254831290f21facf9dd59635c6`.

Les dossiers sans suffixe, `v2` et `v3` sont des traces intermédiaires ; seule `final`
est la référence complète (le premier essai avait sélectionné zéro titre,
avant correction du nom du motif et ajout d'une protection contre un audit vide).

```powershell
python -m modelFactory.fr_official_close_audit --workbook artifacts/fr/research/official_close_audit/euronext-20201019-audit-20261003-final/official_closes_20201019.xlsx --output artifacts/fr/research/official_close_audit/nouvelle_execution
```

Le répertoire de sortie doit être nouveau. L'audit lit les preuves existantes,
ne consulte pas la base et ne change pas les règles du serving/backtest.
Onze tests ciblés passent : rapprochement de clôture, audit fold 3 et
qualification de l'historique OOF. Ce n'est pas une exécution de toute la suite.
