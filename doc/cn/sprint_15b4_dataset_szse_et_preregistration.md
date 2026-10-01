# Sprint 15-B4 — Dataset quotidien Shenzhen et pré-enregistrement

28 septembre 2026. Suite de [15-B3](./sprint_15b3_qualification_blocages.md).

**État au 29 septembre 2026 : collecte complète 2018–2025 et audit final terminés. 1 942 séances, aucun échec, audit PASS_COLLECTION_AUDIT_PROXY_ONLY.** Aucune performance directionnelle n'est mesurée et aucun modèle n'est entraîné dans cette tranche. La préparation des features reste une étape distincte.

## 1. Pourquoi ce périmètre

La collecte concerne uniquement les actions de Shenzhen (`XSHE`) dans `CN_A`. Les observations sont des archives officielles de financement sur marge et prêt de titres. Shanghai est exclu : ses listes historiques exhaustives et les résidus par titre ne sont pas qualifiés.

Les archives n'ont pas de preuve de vintage historique. Le dataset porte donc systématiquement :

```yaml
historical_vintage_proven: false
strict_ml_allowed: false
training_ready: false
```

Ce n'est pas un remplacement des tables canoniques et ce n'est pas un dataset de production. Une collecte réussie ne démontre ni une direction prédictible ni un backtest PIT strict.

## 2. Protocole fixé avant les résultats

Le [fichier de pré-enregistrement](../../config/research_cn/sprint15b4_szse_margin.yaml) définit :

- données : 2018-01-01 à 2025-12-31 ;
- horizon principal : H20, labels `cn_oracle_labels_v1` existants, sans recalculer les déciles sur Shenzhen seulement ;
- population future de test : événements TOP20 de l'Oracle CN OOF H20, restreints aux actions Shenzhen éligibles et disposant des données nécessaires ;
- tâches : D1 versus D10 et D10 versus le reste ;
- développement : 2022H1 à 2024H2 ; confirmation historique : 2025H1 et 2025H2 ;
- purge et embargo de 20 séances ; validation de 126 séances et historique minimal de 504 séances ;
- modèles proposés pour l'étape d'évaluation : logistique et LightGBM, avec plafonnement et seed fixés ;
- une baseline prix et trois extensions financement : flux, encours, combinaison.

Les semestres 2025 ont déjà été consultés dans d'autres recherches CN : ils **ne constituent pas un holdout global vierge**. Toute future conclusion doit mentionner cette limite. La collecte B4 ne filtre pas sur les futurs labels ni sur les futurs scores Oracle : elle conserve le périmètre éligible observé pour rendre les comparaisons ultérieures possibles.

Les variantes additionnelles sont limitées à :

| Famille | Variables prévues | Construction ultérieure |
|---|---|---|
| Flux | achats financés / montant d'échanges ; moyenne sur 5 séances | Même devise CNY ; fenêtre avant décision, aucun zéro imputé |
| Encours | variation relative du financement sur 5 et 20 séances | Encours initial strictement positif, séances consécutives valides, pas de pont arbitraire sur une absence |
| Combinée | les quatre variables précédentes | Aucun ajout guidé par le semestre de confirmation |

Le collecteur calcule uniquement le ratio journalier lorsque les données sont utilisables. Les moyennes, variations, raccordements aux labels et évaluation OOF feront l'objet d'une étape séparée après contrôle du backfill complet.

Normalisation et éventuelle calibration devront être apprises uniquement sur train/validation. Le contrôle taille utilise un proxy historique de montant d'échanges, pas les capitalisations actuelles. Une classification sectorielle non datée ne sera pas utilisée : faute de secteur PIT, elle sera omise dans les deux bras.

### Critères de décision préfixés

- au moins 60 dates, 500 observations et 20 symboles par fold ;
- différence d'AUC minimale de 0,015 face à la baseline évaluée sur **exactement les mêmes lignes** ;
- gain positif sur au moins 6 des 8 semestres, et les deux semestres de confirmation historique ;
- uplift de précision D10 d'au moins 0,02 sur le TOP20 directionnel ;
- veto : ne pas éliminer plus de 30 % des gagnants de référence ;
- bootstrap par mois, 1 000 répétitions, alpha familial 5 % et 12 hypothèses préfixées ;
- borne ajustée de l'intervalle du gain strictement positive ;
- résultats séparés avant/après le 11 juillet 2024, sans confondre prêt de titres et régime de `转融券`.

Ces règles sont enregistrées, **pas exécutées par le collecteur**. Les détails de l'évaluation, notamment l'intégrité des prédictions Oracle OOF et les paramètres logistiques explicites, devront être audités avant toute performance. Une modification du protocole exige une version/campagne distincte, pas un changement silencieux du dataset en cours.

## 3. Ce que le collecteur fait réellement

Service : [cn_szse_margin_dataset.py](../../service/market/cn_szse_margin_dataset.py).

Pour chaque séance ouverte du calendrier CN :

1. télécharge la liste datée `1834_xxpl / tab1` ;
2. télécharge le détail daté `1837_xxpl / tab2` ;
3. conserve chaque XLSX et son reçu réel, URL, hash, observation actuelle ;
4. contrôle les indicateurs Y/N, codes uniques, nombres entiers non négatifs et identité encours financement + valeur prêt = encours combiné ;
5. retient les titres financement **ou** prêt éligibles, puis joint le référentiel historique actions XSHE ;
6. exclut les ETF et autres instruments hors de ce référentiel, les introductions futures et les titres radiés avant la séance ;
7. consulte les barres CN de la même séance, avec le montant `amount` en CNY ;
8. écrit une partition `YYYY-MM-DD.jsonl.gz` et met à jour le journal.

Le référentiel utilise les dates de cotation/radiation selon la convention déjà retenue par l'application. La journée de radiation est inclusive dans ce contrôle de présence ; cela n'affirme pas que le titre était effectivement négociable ce jour-là. L'exécution CN devra encore appliquer ses propres gates d'univers, de suspension et de limites.

La base `alpha_trade_cn` est consultée via `cn_primary` **en lecture seule au niveau des opérations du service**. Aucune requête de modification n'est envoyée, aucune nouvelle table, migration ou tâche planifiée n'est créée.

Les sources SZSE datées ne contiennent pas de colonne date dans le détail exporté testé : la date est celle de la requête conservée. La concordance de la réponse avec la date demandée repose sur le contrat de l'endpoint et les contrôles du pilote, pas sur une preuve de date interne inexistante.

## 4. Valeurs manquantes et qualité

Chaque ligne conserve :

- `instrument_id`, code local et séance source ;
- les quatre indicateurs de liste/autorisation du jour ;
- les six mesures officielles, sans substitution ;
- statut `OBSERVED`, `OBSERVED_ZERO` ou `ELIGIBLE_WITHOUT_OBSERVATION` ;
- montant d'échanges CNY et ratio de financement si exploitable ;
- dates observée/disponible enregistrées sur la barre canonique ;
- proxy de disponibilité de recherche et motifs de qualité.

Une absence de ligne éligible donne `measures=null`, pas six zéros. Un zéro explicitement observé reste un zéro. Une barre absente, un montant nul/non positif, un statut non négocié ou un proxy manquant empêche de produire le ratio utilisable.

Les horodatages canoniques enregistrés sur les barres sont préservés ; ils ne sont pas réinterprétés comme preuve de vintage historique. Le ratio appartient à la **recherche sous archives/proxy**, pas au serving PIT strict.

Les encours du résumé et du détail n'ont pas le même périmètre, comme établi en B3. Aucun multiplicateur ne corrige les encours observés pour les faire rejoindre le résumé.

## 5. Disponibilité en séances

La règle principale reste la clôture de la **deuxième séance ouverte suivant la séance source**. Une décision à cette clôture ou avant ne doit pas lire la mesure ; une entrée à l'ouverture doit attendre une séance ultérieure.

Les retards 3 et 5 séances sont préfixés comme sensibilités, sans sélectionner après coup celui qui donne le meilleur test. Le collecteur enregistre le proxy principal ; les sensibilités sont à construire avant les futures évaluations.

En fin de calendrier, une observation sans deux séances futures conserve un proxy `null` et `CALENDAR_PROXY_UNAVAILABLE`. Elle est collectée mais exclue des features à la décision. Aucun jour futur fictif n'est créé.

Un retard ne supprime pas le risque d'une correction ultérieure d'archive. C'est pourquoi aucun résultat produit ici ne pourra être nommé « PIT historique certifié ».

## 6. Reprise, intégrité et suivi

Répertoire complet : `artifacts/research/cn_margin_lending/sprint15b4_szse_daily/`.

| Fichier | Rôle |
|---|---|
| `state.json` | Contrat, progression et compteurs par séance |
| `reference_snapshot.json` | Copie datée du calendrier et du référentiel utilisés |
| `YYYY-MM-DD_eligible.xlsx` | Liste brute |
| `YYYY-MM-DD_detail.xlsx` | Relevé brut |
| `*.receipt.json` | URL, SHA-256 et observation réelle |
| `YYYY-MM-DD.jsonl.gz` | Partition de recherche, une ligne par action éligible |
| `.lock` | PID et démarrage ; interdit deux collecteurs sur le même dossier |

La reprise vérifie les partitions terminées et leurs bruts avant de les sauter. Les jours en échec sont retentés en relançant la même commande. Les valeurs numériques et les fichiers déjà reçus ne sont pas silencieusement écrasés.

Le contrat verrouille : empreinte du YAML, version du collecteur, plage et liste des séances, empreinte du snapshot de référence. Une différence exige un autre répertoire. Une correction du code après démarrage ne doit donc pas être appliquée silencieusement au milieu d'un dataset.

Un cache incomplet ou altéré déclenche un arrêt/échec explicite. Ne pas supprimer une empreinte pour contourner ce contrôle. Conserver les fichiers pour diagnostic et utiliser un nouveau dossier si une recollecte est nécessaire.

Un arrêt brutal peut laisser `.lock`. Avant de le déplacer, vérifier que le PID indiqué ne tourne plus et qu'aucun processus n'utilise ce dossier. Le service ne retire pas automatiquement un verrou supposé orphelin.

Le journal écrit `RUNNING`, `COMPLETED` ou `FAILED` par séance. L'état global final distingue `COMPLETED_COLLECTION_PROXY_ONLY` et `PARTIAL_FAILURE`. `data_coverage_gate_passed` vérifie la couverture sur au moins 95 % des jours à au moins 95 % des actions éligibles, sans échec de collecte ; il ne valide pas les features roulantes, les labels ou le ML. `training_ready` reste faux.

## 7. Résultat du contrôle et anomalie corrigée

Smoke final : 25 au 29 juin 2018, dossier `sprint15b4_smoke_v2`.

- 5 séances terminées, 0 échec ;
- 2 125 lignes actions éligibles, toutes observées ;
- 2 003 lignes avec ratio journalier exploitable ;
- 0 séance sans proxy ; gate de couverture passé ;
- seconde exécution : mêmes partitions et compteurs, sans nouveaux téléchargements ni doublons ;
- **24 tests ciblés passent**, contrôle de style réussi.

Le premier smoke avait révélé, à la reprise, une sérialisation incorrecte des lignes de calendrier SQL. La sérialisation explicite en paires date/clôture et un test de non-régression corrigent ce défaut. Les premiers artefacts du dossier `sprint15b4_smoke` restent conservés, mais **ne doivent pas servir à la collecte finale**.

Les 122 lignes sans ratio exploitable restent conservées avec leurs motifs de qualité. Ce n'est ni un manque de données de marge ni une preuve d'un défaut de fournisseur.

## 8. Lancement du backfill complet

Le plan local compte **1 942 séances, au maximum 3 884 requêtes** hors retries. Le temps total dépend du site ; le smoke final a pris environ 30 secondes pour cinq séances. Prévoir un run de plusieurs heures, sans garantir ce délai.

Depuis `F:\projets`, une ligne :

```powershell
python -u -m service.market.cn_szse_margin_dataset
```

La même commande reprend le dataset. Ne lancer qu'une instance sur le même répertoire ; pas besoin d'entraînement ni de relancer les modèles.

Vérifier le plan sans collecte :

```powershell
python -u -m service.market.cn_szse_margin_dataset --plan-only
```

Progression :

```powershell
$b4State = Get-Content F:\projets\artifacts\research\cn_margin_lending\sprint15b4_szse_daily\state.json -Raw | ConvertFrom-Json
$b4Items = @($b4State.sessions.PSObject.Properties | ForEach-Object { $_.Value })
[pscustomobject]@{
    Etat = $b4State.status
    Terminees = @($b4Items | Where-Object status -eq 'COMPLETED').Count
    Echecs = @($b4Items | Where-Object status -eq 'FAILED').Count
    EnCours = @($b4Items | Where-Object status -eq 'RUNNING').Count
    Total = $b4State.contract.planned_sessions
}
```

À la fin, transmettre le statut et `summary`. Une collecte terminée n'active rien en production.

## 9. Bilan final du backfill et de l'audit

Le run lancé par l'utilisateur est terminé ; le verrou a été libéré. L'audit indépendant [cn_szse_margin_dataset_audit.py](../../service/market/cn_szse_margin_dataset_audit.py) lit les partitions sans modifier les sources et produit [audit_report.json](../../artifacts/research/cn_margin_lending/sprint15b4_szse_daily/audit_report.json).

| Année | Séances | Lignes éligibles | Observations présentes | Lignes sans motif de qualité du collecteur |
|---|---:|---:|---:|---:|
| 2018 | 243 | 103 270 | 103 265 | 98 923 |
| 2019 | 244 | 137 817 | 137 814 | 137 429 |
| 2020 | 243 | 197 472 | 197 472 | 197 136 |
| 2021 | 243 | 231 352 | 231 352 | 231 046 |
| 2022 | 242 | 294 510 | 294 510 | 294 059 |
| 2023 | 242 | 404 349 | 404 349 | 404 057 |
| 2024 | 242 | 423 310 | 423 310 | 422 903 |
| 2025 | 243 | 437 595 | 437 595 | 433 320 |
| **Total** | **1 942** | **2 229 675** | **2 229 667** | **2 218 873** |

Couverture des observations : **99,999641 %**. Ce dénominateur désigne les actions Shenzhen historiquement présentes et éligibles à la marge/prêt, pas toutes les actions CN ni tous les événements Oracle.

Contrôles réussis :

- toutes les séances prévues sont terminées et leurs compteurs concordent avec les partitions ;
- empreintes de configuration, collecteur, référentiel, partitions et 3 884 sources XLSX vérifiées, reçus concordants ;
- aucun doublon instrument/séance, aucune ligne du détail hors de la liste éligible retenue ;
- dates de cotation/radiation, identité des instruments, nombres et identité des encours contrôlés ;
- proxies recalculés à partir du calendrier figé ; aucune disponibilité historique certifiée inventée ;
- **35 tests ciblés réussissent**, contrôle de style réussi.

### Absences et exclusions à conserver

Huit observations manquent ; elles restent nulles, jamais imputées à zéro :

- `002085` (instrument 3784) : 16 au 20 avril 2018, cinq séances ;
- `000021` (3044) : 19 et 20 août 2019 ;
- `002421` (4175) : 19 août 2019.

Les 30 et 31 décembre 2025 n'ont pas de proxy calculable : le calendrier figé ne contient pas les deux séances futures requises. Cela concerne 3 651 lignes, exclues à la décision. Ne pas fabriquer des dates futures.

Les motifs de qualité comptent 7 154 lignes sans montant utilisable ou non négociées, huit observations absentes et 3 651 proxies absents. Ces compteurs peuvent se recouper : ne pas les additionner comme des lignes distinctes.

### Ratio atypique à isoler avant les features

Une ligne supplémentaire a un ratio supérieur à 1 :

| Séance | Code | Instrument | Achats financés CNY | Montant de la barre CNY | Ratio |
|---|---|---:|---:|---:|---:|
| 2024-08-26 | 300957 | 5949 | 85 670 025 | 58 016 137,85 | 1,4766585 |

Sa cause n'est **pas établie** par cet audit : archive, périmètre ou montant canonique doivent être rapprochés avant réintégration. Ne pas plafonner le ratio à 1 ni corriger arbitrairement les bruts. Cette ligne est signalée dans le rapport ; elle n'est pas encore exclue physiquement du dataset figé et figure dans le compteur de 2 218 873 ci-dessus. La prochaine étape devra la mettre en quarantaine dans la vue de features, avec propagation aux fenêtres concernées.

Reproduire l'audit, sans téléchargement ni écriture en base :

```powershell
python -u -m service.market.cn_szse_margin_dataset_audit
```

## 10. Prochaine tranche : Sprint 15-B5

**B4 est clôturé pour la collecte et son audit**, pas pour la validité ML. `training_ready=false` et `strict_ml_allowed=false` restent inchangés.

La suite proposée est de construire les fenêtres de 5/20 séances sans traverser les absences ou anomalies, puis les jointures as-of avec les événements Oracle OOF H20 et les labels CN. Les mêmes lignes devront servir à la baseline prix et aux extensions financement. Contrôler les retards 2/3/5 séances, l'intégrité OOF et les paramètres logistiques avant toute évaluation pré-enregistrée. Aucune conclusion D1/D10 ne peut être tirée des seuls chiffres de couverture.
