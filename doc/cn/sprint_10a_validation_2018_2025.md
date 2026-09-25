# Sprint 10-A — Validation des labels Oracle CN_A 2018–2025

## Verdict

`PASS_LABELS_PRICE_ONLY` sur les huit années et les quatre horizons H5, H10,
H15 et H20. Le [rapport d'audit](../../artifacts/cn/labels/sprint10a_audit_2018_2025.json)
vérifie les empreintes SHA des 32 Parquet, la population source, l'unicité des
clés, le marché `CN_A`, la disponibilité future des cibles, la validité des
déciles et la couverture des trajectoires arrivées à maturité. Son champ
`errors` est vide. Il n'y a eu ni entraînement ni backtest dans ce sprint.

| Horizon | Candidats | Trajectoires mûres | Labels valides | Valides / mûres |
|---|---:|---:|---:|---:|
| H5 | 8 278 367 | 8 247 546 | 8 220 379 | 99,67 % |
| H10 | 8 278 367 | 8 221 871 | 8 172 672 | 99,40 % |
| H15 | 8 278 367 | 8 196 197 | 8 125 313 | 99,14 % |
| H20 | 8 278 367 | 8 170 522 | 8 078 224 | 98,87 % |

Une trajectoire *mûre* possède les séances futures et la séance à laquelle
le label pourrait être mis à disposition. La distinction est essentielle en
2025 : les données source s'arrêtent au 31 décembre 2025. Ainsi H20 y a
1 118 551 labels valides sur 1 134 205 trajectoires mûres (98,62 %), mais
sur 1 242 050 candidats au total (90,06 %). Les 102 710 horizons futurs et
5 135 séances de disponibilité absents en fin de période sont censurés,
jamais convertis en rendements nuls.

## Quarantaine et classement H20

Sur les huit années, H20 comporte 77 325 trajectoires avec suspension ou
statut contradictoire, 14 871 événements de facteur non vérifiés et 102
barres manquantes. Un facteur vérifié par le `pre_close` reste au contraire
dans la coupe. Les limitations de prix dérivées sont des indicateurs de
qualité d'exécution : elles ne suppriment pas rétrospectivement les fortes
hausses ou baisses du classement Oracle.

Les dix déciles H20 contiennent chacun environ 808 000 labels valides ; D1
en compte 806 989 et D10 808 665. Cette répartition équilibrée résulte de
la **définition** des déciles intra-date, non d'un pouvoir prédictif. Les
labels mesurent un retour de prix ajusté de l'ouverture de J à la clôture de
J+H. Ils ne prouvent ni l'exécutabilité à l'ouverture ni la rentabilité après
T+1, limites de prix, coûts et liquidité.

## Contrôles exécutés

- Construction annuelle 2018–2025, chaque année avec les mêmes quatre
  horizons et le même SHA de code de calcul.
- Audit consolidé : 8 années trouvées, 32 empreintes Parquet conformes,
  aucune clé doublonnée, aucun marché US, aucun label disponible avant
  l'issue, aucun décile attribué à une cible invalide. Chaque combinaison
  année/horizon dépasse le seuil préfixé de 95 % des trajectoires mûres.
- Tests ciblés des Sprints 8, 9 et 10-A : 31 réussis ; analyse statique Ruff
  et compilation Python réussies.
- Réexécution de 2018 : même empreinte d'entrée et mêmes quatre SHA Parquet ;
  les artefacts existants n'ont pas été écrasés.

Reproduire l'audit :

```powershell
F:\projets\.venv\Scripts\python.exe -m dataIntegrityEngine.cn_sprint10a_audit
```

## Gate pour le Sprint 10-B

Le gate **de construction des labels** est franchi. Le prochain sprint doit
pré-enregistrer, avant entraînement, les fenêtres walk-forward, les baselines,
les métriques OOS H5/H10/H15/H20 et les seuils GO/NO-GO. Ne pas utiliser la
bonne couverture ni l'équilibrage mécanique des déciles comme preuve que
l'Oracle distingue les mouvements extrêmes ou leur sens.

Le [contrat détaillé](./sprint_10a_labels_oracle_cn.md) définit l'origine
temporelle, les facteurs, la quarantaine et la disponibilité des labels.
