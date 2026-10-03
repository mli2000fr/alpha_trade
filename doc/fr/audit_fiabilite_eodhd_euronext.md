# Fiabilité EODHD France — comparaison élargie avec Euronext

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
