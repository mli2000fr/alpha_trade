# E19-A2 — Contrat PIT fondamental

## 1. Statut

E19-A2 corrige le contrat applicatif identifié par E19-A. Le code, la migration
Alembic `0074` et le SQL manuel sont prêts et testés.

La base observée conserve toutefois `0068_analyst_snapshot_collection` dans
`alembic_version`, alors que des changements 0069–0073 sont déjà présents
physiquement. Pour éviter de rejouer aveuglément ces migrations, 0074 n’est pas
appliquée automatiquement. Après exécution du SQL autonome, les lignes SEC
historiques doivent être rafraîchies pour renseigner leur lineage.

```text
loader PIT corrigé                         OUI
migration et SQL de référence              OUI
schéma 0074 appliqué à la base observée     NON
lineage des anciennes lignes SEC renseigné NON
E19-B autorisé                              NON, jusqu'au gate DATA_READY
```

## 2. Contrat des dates

Les dates ont désormais des rôles non ambigus :

| Champ | Sens |
|---|---|
| `trade_date` | date de l’événement fournisseur ; date `filed` pour SEC |
| `fiscal_period_end` | clôture de la période comptable représentée |
| `fetched_at` | instant réel de collecte par Alpha-Trade |
| `available_date` | première date civile autorisée pour une feature ML |

Règles :

```text
SEC_EDGAR : available_date >= filed_date + 1 jour civil
autre source : available_date >= date(fetched_at) + 1 jour civil
```

Le merge avec les barres ne conserve que les séances de marché. Un dépôt du
vendredi devient donc visible le lundi ; un dépôt du lundi devient visible le
mardi. Un snapshot EODHD téléchargé en 2026 mais portant une période fiscale de
2020 ne peut plus être utilisé en 2020.

La règle est conservatrice parce que la table ne conserve pas l’heure SEC
d’acceptation permettant de prouver que le dépôt précédait la décision au close.

## 3. Sélection des fournisseurs

Une collision à la même date de disponibilité est résolue sur une ligne
cohérente complète, sans mélanger des colonnes provenant de définitions
différentes :

```text
SEC_EDGAR > EODHD > Yahoo Finance > Finnhub > FMP > source inconnue
```

La priorité sert uniquement à départager une même date effective. Une nouvelle
observation réellement disponible remplace naturellement l’ancienne lors du
forward-fill.

## 4. Bord gauche de la fenêtre

Le loader ne commence plus à `start_date`. Il charge l’historique antérieur,
reconstruit les dates de disponibilité puis conserve :

- la dernière observation disponible avant `start_date` pour chaque symbole ;
- toutes les observations disponibles entre `start_date` et `end_date`.

La première journée d’un fold ou d’un backtest ne perd donc plus artificiellement
le dernier 10-Q/10-K connu.

## 5. Valeurs manquantes

Les anciens remplacements sémantiques sont supprimés : PE `-1`, current ratio
`1`, bêta `1`, ROE `0`, etc. Pour chaque feature fondamentale `fund_x`, la
matrice expose maintenant :

```text
fund_x          valeur réelle, ou 0 uniquement comme représentation numérique
fund_x_missing  1 si absente, 0 si observée
```

Le couple distingue un vrai zéro économique d’une absence. Les masques font
partie de la liste de features et doivent être appris dans les nouveaux modèles.
Tout modèle historique entraîné avec `include_fundamentals` doit donc être
réentraîné avant comparaison ou serving avec ce contrat.

## 6. Lineage SEC

La table reçoit :

- `fiscal_period_end` ;
- `form` (`10-Q`, `10-K`, amendement) ;
- `accession_number` ;
- `dividend_per_share`, séparé de `dividend_yield`.

Le mapper XBRL transporte ces valeurs jusqu’à l’upsert. Le gate E19 exige que
95 % au moins des lignes SEC utilisées aient une lineage complète. Ajouter les
colonnes ne suffit donc pas : les lignes historiques doivent être recollectées.

## 7. Corrections sémantiques

| Élément | Avant | Après |
|---|---|---|
| dette/equity | passif total / capitaux propres | dette financière / capitaux propres |
| EBITDA | résultat opérationnel accepté en fallback | tag EBITDA uniquement |
| dividende | dividend/share temporairement stocké comme yield | colonne `dividend_per_share` dédiée |

`fund_estimate_revision` reste une croissance entre estimation suivante et
estimation courante, pas une révision temporelle. Comme les champs d’estimation
ont 0 % de couverture SEC historique, cette feature et les quatre champs forward
restent exclus de la future expérience E19-B.

## 8. Déploiement du schéma

Deux représentations équivalentes sont livrées :

- `alembic/versions/0074_fundamental_pit_contract.py` pour une chaîne Alembic
  réconciliée ;
- `database/sql/ml/alter_stock_fundamentals_pit_contract.sql` pour l’application
  manuelle actuelle.

Ne pas exécuter les deux. Sur la base observée, utiliser le SQL manuel est le
chemin le moins risqué tant que `alembic_version` n’a pas été réconciliée.

Après le SQL :

1. relancer la collecte SEC sur l’univers E19 ;
2. vérifier le taux de lineage ;
3. rejouer `modelFactory.fundamental_pit_availability_audit` ;
4. n’ouvrir E19-B que si le verdict devient `DATA_READY`.

## 9. Tests de non-régression

Les tests couvrent notamment :

- invisibilité SEC le jour du dépôt et visibilité à la séance suivante ;
- interdiction de rétro-projeter un snapshot non-SEC avant sa collecte ;
- priorité fournisseur déterministe ;
- chargement du prédécesseur ;
- distinction zéro réel / donnée absente ;
- lineage SEC ;
- dette financière, EBITDA et unité du dividende.
