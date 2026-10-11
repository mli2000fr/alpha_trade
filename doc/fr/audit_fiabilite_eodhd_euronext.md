# Fiabilité EODHD France — comparaison élargie avec Euronext

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Protocole du 3 octobre 2026

Objectif : mesurer une **concordance de données** sur plusieurs titres et
plusieurs dates, pas optimiser un modèle ou remplacer le fournisseur.
Les archives EODHD, la base, les données gelées et les batchs restent inchangés.

### Sélection avant les comparaisons

- 40 titres actifs tirés sans remise dans les identités vérifiées du Sprint 6-C,
  triées par symbole, générateur Python `Random(20261003)`.
- 10 radiés tirés sans remise dans les 34 titres radiés du contrôle Euronext
  précédent, triés par symbole, générateur `Random(20261004)`.
- La liste est sauvegardée dans `sample.json` avant tout rapprochement.
- Un échec de récupération n'est pas remplacé par un titre plus facile.

Ce n'est pas un sondage représentatif de tous les titres français : les pools
proviennent des travaux de qualification précédents. Les actifs et radiés
doivent être présentés séparément. Le nombre de lignes est pondéré par la
durée de l'historique disponible, donc les longs historiques pèsent davantage.

### Sources et couverture

Euronext : historique public de la fiche ISIN/MIC, fenêtre demandée du
3 octobre 2024 au 2 octobre 2026, bornée par la restriction publique retournée
par chaque fiche. Aucune tentative de contourner la limite. Paramètre du
site `adjusted=Y`, archivé explicitement ; aucune assimilation automatique à
la convention EODHD. Pages HTML et réponses historiques brutes conservées.

EODHD : archives locales `artifacts/fr/eodhd/backfill_2016`, sans nouvel appel
ni écriture. Les dates hors de la fenêtre Euronext ne sont pas des absences
de référence, elles sont simplement hors périmètre de cet audit.

La collecte nouvelle vérifie TLS avec les certificats de confiance système.
Le précédent contrôle des radiés indiquait `tls_verified=false` ; nous ne
reprenons donc pas ses résultats comme nouvelle preuve réseau vérifiée.
Sa liste sert uniquement à fixer l'échantillon, puis les sources sont relues.

### Mesures et dénominateurs

1. Nombre de dates communes et dates présentes dans une seule source.
2. Parmi les dates communes, distinguer les OHLC manquants/non finis/non
   positifs des quatre prix disponibles de part et d'autre.
3. Comparaison stricte : différence absolue au plus **0,0001 EUR**.
4. Diagnostic pratique séparé : différence relative au plus **10 bps = 0,1 %**.
   Ce seuil ne change pas les gates canoniques préexistants.
5. Mesurer chaque champ et les journées dont les quatre OHLC concordent.
6. Volumes : égalité exacte uniquement lorsque les deux valeurs sont connues.
   Un volume manquant reste manquant, pas zéro. Mesure diagnostique, sans
   présumer une convention identique de consolidation ou d'ajustement.
7. Présenter les résultats par année, par actif/radié et par titre.

Une divergence ne suffit pas à déclarer « EODHD faux » : il faut vérifier
ISIN/MIC, type de prix, actions sur titres, transactions annulées, volume
de place versus consolidé et éventuelle absence de transaction. Une ligne
Euronext affichée sans OHLC ne constitue pas une nouvelle transaction.
Inversement une concordance ne valide pas le statut de négociabilité PIT.

Les dates 2026 ne servent qu'à contrôler la qualité des données, pas à choisir
un modèle ou un seuil directionnel. Les résultats de la journée d'incident
du 19 octobre 2020 restent une étude distincte :
[rapport 10-C2](sprint_10c2_audit_prix_independants.md).

## Exécution et traçabilité

Script : `modelFactory/fr_eodhd_euronext_sample_audit.py`.
Tests : `tests/test_fr_eodhd_euronext_sample_audit.py`.
Répertoire : `artifacts/fr/research/eodhd_euronext_sample/audit-50-20261003`.

- `sample.json` : sélection complète fixée avant collecte ;
- `progress.json` : résultats disponibles après chaque titre ;
- `*.page.html`, `*.encrypted.json`, `*.history.html` : sources Euronext ;
- `*.differences.json` : toutes les différences, sans troncature des exemples ;
- `report.json` : bilan final et hashes des sources comparées.

**Attention :** la première collecte avait déjà démarré avec l'ancien lecteur
de colonnes par position. Le tableau actuel contient Date/Open/High/Low/Last/
Close/Number of shares. L'ancien lecteur confondait Last et Close et prenait
Close pour le volume. La collecte continue uniquement pour conserver les
sources ; ses mesures initiales ne sont pas la référence de cet audit.
Le nouveau lecteur utilise les en-têtes et un test distingue Last, Close et
un volume formaté avec séparateurs de milliers. Les sources seront relues
automatiquement hors réseau après la collecte : **seul le rapport
`header_checked/report.json` est utilisable pour la conclusion**.
L'ancien lecteur partagé n'a pas été modifié pendant ce contrôle ; ses
anciens diagnostics nécessitent une revue séparée avant réutilisation.

```powershell
python -m modelFactory.fr_eodhd_euronext_sample_audit --output artifacts/fr/research/eodhd_euronext_sample/nouvel_audit
```

Le répertoire doit être nouveau. Le script n'effectue aucune réparation ou
écriture SQL. Une relance indépendante ne doit pas mélanger ses nouveaux
documents avec les sources d'une exécution précédente.

## Résultats

La collecte initiale est terminée, mais seuls 13/50 titres ont été récupérés ;
les autres restent des échecs de collecte, non des erreurs EODHD. La relecture
des en-têtes a également été corrigée pour les prix avec séparateur de milliers.
Le rapport complet relu est `header_checked_v2/report.json` dans le répertoire
de cet audit. Il remplace comme référence la relecture `header_checked` avortée.
Cette couverture réduite limite toute généralisation. L'étude est maintenant
séparée des opérations de réparation du [Sprint 10-C3](sprint_10c3_reparation_fold7.md).

Collecte en cours à la création initiale de ce protocole. Les résultats chiffrés seront
ajoutés après présence du rapport final ; ne pas assimiler un compteur de
progression à une conclusion sur la fiabilité globale du fournisseur.

## Reprise des échecs — 4 octobre 2026

Les 37 échecs de la collecte initiale sont des délais réseau ou réponses
Euronext HTTP500/504. Ils ne démontrent pas des prix EODHD incorrects. Aucun
processus initial ne tournait encore lors de la vérification.

Une reprise du **même échantillon fixé de50titres** est lancée dans
`artifacts/fr/research/eodhd_euronext_sample/audit-50-20261004-retry2`.
Les13succès antérieurs sont relus avec les en-têtes corrigés, à partir des
réponses brutes déchiffrées ; leurs hashes Euronext/EODHD sont vérifiés. Aucun
nouveau tirage, aucune modification de la période ou des tolérances.
Les autres titres disposent de deux tentatives maximum, temporisées de3secondes.
Les archives et rapports initiaux ne sont pas écrasés. Aucun SQL/correction
canonique, modèle ou batch existant touché.

```powershell
python -u -m modelFactory.fr_eodhd_euronext_sample_audit --resume-from artifacts/fr/research/eodhd_euronext_sample/audit-50-20261003 --output artifacts/fr/research/eodhd_euronext_sample/nouvelle-reprise --sleep 3 --retry-attempts 2
```

`state.json` contient l'état, le titre courant et sa tentative pendant la
collecte ; `progress.json` les titres terminés après chaque passage.
`report.json` n'est créé qu'au bilan final : `COMPLETE_SAMPLE_AUDIT` si tous
les titres ont été collectés, sinon `PARTIAL_COLLECTION_FAILURES`. La fin
technique du traitement n'est pas une garantie de couverture50/50.
Le rapport de reprise est directement relu par en-têtes (`header_checked=true`) ;
il n'exige pas un sous-dossier `header_checked` supplémentaire.

La tentative retry1 s'est arrêtée avant reprise réseau : une page HTML
optionnelle manquait pour un succès ancien. La réponse brute signée par hash
est présente ; sa relecture est désormais possible sans cette page optionnelle,
dont l'absence est explicitement enregistrée. Retry1 est conservé pour diagnostic.

Journaux de cette reprise : `log/batch/fr-euronext-audit-50-20261004-retry2`.

```powershell
Get-Content F:\projets\log\batch\fr-euronext-audit-50-20261004-retry2\stdout.log -Tail 15
Get-Content F:\projets\artifacts\fr\research\eodhd_euronext_sample\audit-50-20261004-retry2\state.json
Test-Path F:\projets\artifacts\fr\research\eodhd_euronext_sample\audit-50-20261004-retry2\report.json
```

Six tests ciblés passent, notamment parsing Last/Close/volume, milliers,
dénominateurs, tolérances, reprise bornée et refus d'une identité modifiée.
Ruff passe. Les résultats chiffrés de la reprise restent à lire après sa fin.

## Bilan final de la reprise — 4 octobre 2026

Rapport : `audit-50-20261004-retry2/report.json`, état
`COMPLETE_SAMPLE_AUDIT` : **50/50 collectés, 0 échec**, dont40actifs et10radiés.
Ce statut signifie fin de collecte/comparaison, pas admission canonique générale.

| Mesure | Numérateur / dénominateur | Taux |
| --- | --- | --- |
| Quatre OHLC concordants à0,0001EUR |20559/20718 journées appariées valides |99,23 % |
| Quatre OHLC concordants à10bps |20566/20718 |99,27 % |
| Clôture concordante à0,0001EUR |20570/20718 |99,29 % |
| Volume identique |20568/20718 comparaisons disponibles |99,28 % |
| OHLC stricts sur les10radiés |2050/2052 journées appariées valides |99,90 % |

22329 journées communes au total, dont1611sans quatre prix positifs/finis
appariables : elles ne sont pas mises dans le dénominateur des taux ci-dessus.
719 dates existent dans la référence Euronext sans correspondance EODHD ; il
faut examiner calendrier, bornes et statuts, pas les compter comme des prix
EODHD faux. Aucun jour EODHD seul à l'intérieur de l'étendue Euronext observée.
Les observations2026 sont un contrôle de qualité seulement, pas une sélection ML.

**Principal foyer : Hermès/RMS**,146 des159journées dont au moins unOHLC diverge
au seuil strict. Exemple4octobre2024 : ouvertureEODHD2127EUR contre
Euronext2118,281EUR. Les quatre prix ont alors un écart relatif quasi constant
d'environ41,16bps. Cette structure est **compatible avec une différence de
convention d'ajustement**, mais la cause n'est pas prouvée. Euronext est demandé
avec`adjusted=Y` ; ne pas déclarer EODHD erroné ni appliquer un ratio de correction
à toute la série sans pièces d'opérations sur titres et convention définie.

Conclusion : concordance élevée sur **cet échantillon et les journées valides
comparables**, pas certification de toutes les donnéesEODHD, de2018–2026 ou
de la négociabilité. Les lacunes/écarts restent explicitement conservés. Aucune
barre stockée n'a été corrigée. Étape utile restante : qualifier RMS et les13
autres journées divergentes, puis les journées non appariables et dates isolées.
