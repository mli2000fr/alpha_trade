# Oracle US — contrôle après retrait de KNTK et AMTB

## Conclusion

Le retrait de KNTK et AMTB élimine les trois maxima initialement observés,
mais **ne suffit pas à qualifier tout l'historique d'entraînement**. DEC
présente un raccordement de split incohérent dans la base actuelle ; TALO et
INDV conservent de grandes ruptures même après relecture fournisseur.

Pas de nouvel entraînement, de correction SQL ni de retrait supplémentaire
de symbole. L'exclusion de KNTK/AMTB n'est pas étendue implicitement à d'autres
titres. Un seuil de grande variation n'est pas un détecteur infaillible d'erreur.

## Périmètre réellement recalculé

7 octobre 2026 : balayage des **1 796 titres** de
`config/univers/univers_filtred_tradable.txt`, empreinte
`efcb290da4b9d5953256eeb39f8d93ee501b22514be6c5ab075213df393701ce`.

- **4 964 562 barres** lues sur `alpha_trade`, 2012-12-27 à 2024-12-31.
- Classement des features à partir de 2016-01-01, préchauffage conservé.
- Formules de prix ajustés partagées et segmentation WFRD/CHRD existante.
- Trois features : rendement journalier, gap overnight, volatilité 20 séances.
- Ce n'est **pas** un recalcul complet des 173 features du batch Oracle.
- 23 observations dépassent 100 % en valeur absolue de rendement ou gap,
  sur 17 titres ; précédemment 27 observations sur 19 titres.
- Le champ `suspects=[]` du rapport signifie qu'aucune ligne du classement
  ne dépasse le seuil interne **100 en unités de rendement** (10 000 %).
  Il ne signifie donc pas « absence d'anomalie » : les 23 variations de plus
  de 100 % restent à examiner.

## Maxima après exclusion

| Feature | Avant exclusion | Après exclusion | Nouvelle origine |
|---|---:|---:|---|
| Rendement journalier | 45 499 | 19,070423 | DEC / 2023-12-05 |
| Gap overnight | 47 749 | 18,894366 | DEC / 2023-12-05 |
| Volatilité 20 séances | 10 173,887636 | 4,267116 | DEC / 2023-12-21 |

Les valeurs sont des ratios, pas des pourcentages. Un rendement de 19,07
correspond à environ +1 907 %. Les maxima restants ne sont pas pour autant
des observations économiquement valides.

## Relecture bornée des trois premières ruptures

Une fenêtre de ±20 jours calendaires a été relue pour chaque événement,
avec la liste complète des splits. Les réponses ont été archivées avec leurs
empreintes, puis converties par l'adaptateur split-only actuel. Six requêtes
par exécution, deux exécutions réalisées ; aucune collecte massive supplémentaire.
Les mêmes valeurs d'événement ont été retrouvées aux deux passages.

| Titre / date | Clôtures locales avant → après | Rendement local | Clôtures reconstruites avant → après | Rendement reconstruit |
|---|---:|---:|---:|---:|
| DEC / 2023-12-05 | 0,852 → 17,10 | +1 907,04 % | 17,04 → 17,10 | +0,3521 % |
| TALO / 2016-06-13 | 0,52272727 → 4,7625 | +811,09 % | 0,52272727 → 4,7625 | +811,09 % |
| INDV / 2022-11-28 | 3,13 → 21,03 | +571,88 % | 3,13 → 21,03 | +571,88 % |

### DEC : défaut de raccordement split fortement étayé

Le [rapport officiel intermédiaire 2024, note 10](https://ir.div.energy/financial-information/sec-filings/content/0001922446-24-000006/dec-20240815.htm)
confirme un regroupement de 20 actions anciennes pour une nouvelle au
5 décembre 2023. L'endpoint de splits renvoie `1/20` à cette même date.
Le facteur explique exactement 0,852 × 20 = 17,04.

Le volume précédent devient 3 500 / 20 = 175, conformément à l'ajustement
inverse prix/volume. Le gap reconstruit vaut −3,169 %, contre +1 889,44 %
localement. Cela ne permet pas d'attribuer le défaut à une version précise
de l'importeur ni de certifier chaque prix historique.

**Suite pertinente :** inventaire complet des lignes DEC avant l'événement,
parité des deux tables et plan de correction ciblé ; ne pas modifier uniquement
la clôture du 4 décembre ni effacer le symbole automatiquement.

### TALO : relecture identique, histoire du prédécesseur à qualifier

Le [communiqué de Stone Energy du 1er juin 2016](https://www.prnewswire.com/news-releases/stone-energy-corporation-announces-1-for-10-reverse-stock-split-300277736.html)
annonce le regroupement 1:10 avec cotation ajustée le 13 juin 2016. L'émetteur
actuel conserve une [page officielle des formulaires fiscaux historiques](https://www.talosenergy.com/investor-relations/filings-and-reports/tax-information/default.aspx),
incluant cette opération et la sortie de faillite de février 2017.
Le [communiqué Talos du 10 mai 2018](https://www.talosenergy.com/investor-relations/news/news-details/2018/Talos-Energy-Inc-Completes-The-Previously-Announced-Strategic-Combination-Between-Talos-Energy-LLC-And-Stone-Energy-Corporation/default.aspx)
situe le début du symbole TALO après la combinaison avec Stone.

Le fournisseur renvoie un split `1/10` au 2016-06-13 et `22/125` au
2017-03-01, mais sa reconstruction conserve le saut. **La présence d'un
split dans la réponse n'assure pas la cohérence des OHLC fournis.** Il faut
qualifier les prix et conversions SGY/prédécesseur/successeur, pas ajouter
aveuglément un second facteur ou considérer la rupture comme un vrai alpha.

### INDV : réserve ADR / délai de cotation / prix figés

Le jour précédent a un volume local nul et une clôture de 3,13 ; la journée
du saut a un volume de seulement 600. La relecture reproduit ces valeurs.
Le [communiqué officiel de septembre 2022](https://www.indivior.com/latest/category/news/2022/indv-2022-gm-approval)
annonce le regroupement 5:1 au 10 octobre 2022 : ce n'est pas la date de la
rupture examinée, le 28 novembre.

La [FAQ officielle relative à la cotation US](https://www.indivior.com/admin/resources/dam/id/1189/FINAL_Additional_US_Listing_FAQ.pdf)
documente une cotation Nasdaq prévue en juin 2023 et le maintien du nombre
d'actions lors de cette cotation. Ne pas traiter automatiquement un historique
US de 2022 comme des actions Nasdaq INDV contemporaines : alias OTC/ADR,
ratios et stale prices restent à vérifier. Ce contexte n'établit pas que le
saut est faux à lui seul, mais empêche de le promouvoir comme mouvement validé.

## Artefacts et reproduction

Racine :
`artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded-20261007-v1/`.

- `protocol.json`, `progress.json`, `report.json` : scan terminé.
- `feature-maxima.parquet`, `large-jumps.parquet` : observations auditées.
- `events-v2/` : fenêtres locales, réponses brutes, splits, reconstruction,
  hashes et rapport des trois événements.
- `events/` : premier passage ; v2 corrige la sérialisation des scalaires et
  distingue identité inconnue (`null`) d'une identité connue inchangée.

```powershell
python -m scripts.research.us_oracle_feature_outliers --universe config/univers/univers_filtred_tradable.txt --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded-NEW
python -m scripts.research.us_oracle_remaining_price_events --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded-NEW/events
python -m pytest tests/test_us_oracle_feature_outliers.py tests/test_us_oracle_price_repair_plan.py tests/test_us_oracle_repair_qualification.py tests/test_us_oracle_remaining_price_events.py --no-cov -q
```

Quinze tests ciblés passent. Aucun changement des modèles, des batchs,
des sorties/règles de risque ni des lignes SQL. Ces constats ne démontrent
pas que les prix expliquent à eux seuls les pertes de 2024 ou l'échec D1/D10.

## Décision ultérieure : exclusion DEC / TALO / INDV

L'utilisateur a choisi de retirer ces trois titres des fichiers d'univers US
plutôt que de réparer/qualifier leurs historiques à ce stade. Cette décision
succède au contrôle ci-dessus : les résultats restent ceux des **1 796 titres**,
et ne sont pas des résultats recalculés après cette nouvelle exclusion.

| Fichier sous `config/` | Avant | Après | Titres retirés |
|---|---:|---:|---|
| `univers/univers_filtred.txt` | 2 694 | 2 691 | DEC, INDV, TALO |
| `univers/univers_filtred_tradable.txt` | 1 796 | 1 793 | DEC, INDV, TALO |
| `univers/univers_filtred_equities.txt` | 1 796 | 1 793 | DEC, INDV, TALO |
| `univers_batch/univers_filtred_tradable.txt` | 1 796 | 1 793 | DEC, INDV, TALO |
| `univers_bis/ticket_backtest.txt` | 938 | 937 | TALO |
| `univers_bis/ticket_live.txt` | 938 | 937 | TALO |
| `univers_bis/ticket_mid_cap.txt` | 938 | 937 | TALO |
| `univers_bis/200_ticket_recherche.txt` | 200 | 199 | INDV |
| `univers_bis/univers_filtred_2016.txt` | 2 256 | 2 254 | INDV, TALO |

Les 24 fichiers texte de ces trois répertoires ont été vérifiés : aucune
présence de **KNTK, AMTB, DEC, TALO ou INDV** ; tous les autres symboles et
leur ordre sont conservés. Maintenir ces exclusions lors du renouvellement
des fichiers tant que leurs historiques restent réservés.

Aucune correction ni suppression SQL, aucun effacement de modèle/prédiction,
aucune intervention sur les processus en cours. Ces exclusions s'appliquent
aux traitements qui relisent les fichiers, pas aux anciennes archives, sources
SQL ou listes explicites. Elles ne réparent pas les modèles déjà entraînés et
ne constituent pas une preuve de qualité de tous les titres restants.

Le contrôle suivant a été terminé sur les **1 793 titres restants** :
voir [audit des discontinuités restantes](us_oracle_remaining_discontinuities_audit.md).
Il identifie trois raccordements prioritaires BASFY/PECO/FBRT, sans nouveau retrait.
