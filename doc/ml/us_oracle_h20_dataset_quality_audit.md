# US — Audit qualité du contrat Oracle H20 après exclusions

## Objet et statut

Audit lancé et **terminé le 7 octobre 2026**. Il ne s'agit ni d'un nouvel
entraînement, ni d'un test directionnel, ni d'un backtest économique.

Batch de référence : `model-factory-20261003082853-e98332`.
Univers courant : `config/univers/univers_filtred_tradable.txt`, **1 790 titres**.
Période de features examinée : **01/01/2016–31/12/2024**. Les données de chauffe
sont lues depuis le 27/12/2012. Ce passage ne certifie pas 2025–2026.

Il prolonge [l'audit des discontinuités de prix](us_oracle_remaining_discontinuities_audit.md),
qui ne vérifiait que trois calculs. Les exclusions sont KNTK, AMTB, DEC, TALO,
INDV, BASFY, PECO et FBRT ; les anciens modèles et labels n'ont pas été modifiés.

## Contrat réellement examiné

Le profil sauvegardé dans
`artifacts/models/oracle/champions/model-factory-20261003082853-e98332/feature_profile.json`
contient **173 features**, dont **44 rangs cross-sectionnels**, et un horizon 20.
Le programme vérifie l'ordre et les noms des features contre :

1. le profil sauvegardé ;
2. chaque entrée de `oracle_champions.json` ;
3. l'en-tête `feature_names` de chaque modèle LightGBM référencé.

Il refuse les divergences, les colonnes futures/interdites, un horizon différent
de H20 et un contrat d'univers différent de `static_bars`.
Ces contrôles prouvent la cohérence structurelle des artefacts, pas la qualité
prédictive des modèles ni l'absence exhaustive de fuite temporelle.

Options sauvegardées : EXPERT, short score et facteurs activés, rangs
cross-sectionnels activés. Sentiment, fondamentaux, options macro explicites,
score components et volume features optionnelles désactivés. Cela n'empêche pas
les features EXPERT de contenir déjà du volume, de la volatilité et du contexte
marché dérivé du benchmark SPY.

## Méthode de reconstruction des features

### Lots de symboles avec chauffe complète

Le calcul appelle `modelFactory.oracle.dataset.build_feature_matrix`, donc les
fonctions de calcul de l'application, avec les options du profil. Les titres
sont répartis en **72 lots d'au plus 25**, avec toute la profondeur historique.
Les règles de segmentation d'identité actuellement enregistrées restent actives.

Les rangs cross-sectionnels sont temporairement désactivés dans chaque lot :
les calculer sur 25 titres produirait un univers incorrect. Les features de base
et sources de rangs sont archivées en Parquet, puis réunies **sur l'ensemble
des titres pour chaque année**. La même formule `groupby(date).rank(pct=True)`
que le moteur Oracle est alors appliquée, avec le traitement canonique des ex aequo.

Les rangs obtenus correspondent au **nouvel univers réduit**, pas exactement
à celui des anciens entraînements. La reconstruction utilise le code et les
données disponibles aujourd'hui ; aucune ancienne photographie immuable de
l'ensemble du dataset n'est disponible pour une réplication bit-for-bit.

### Contrôles et statistiques

Pour chacune des 173 features, par année :

- nombre de lignes, valeurs finies, nulles et infinies ;
- nombre de zéros et de valeurs distinctes ;
- minimum, maximum et quantiles exacts 0,1 %, 1 %, 50 %, 99 %, 99,9 % ;
- trois plus grandes valeurs absolues avec titre, date et valeur ;
- liste des features constantes et de celles contenant des valeurs non finies.

Les quantiles sont exacts dans chaque année ; aucun quantile global approximatif
n'est présenté comme exact. Une valeur extrême, un zéro ou une feature constante
ne constitue pas à lui seul un bug. Les ratios à petit dénominateur, valeurs par
défaut et véritables événements doivent être distingués lors de l'interprétation.

Les clés `(date, symbol)` dupliquées bloquent la reconstruction. Chaque lot
compare aussi les dates de barres aux dates effectivement émises par le moteur :
nombre de lignes non émises, répartition par titre et titres sans aucune feature.

**Limite importante :** `compute_features` remplace ou impute certaines valeurs,
puis supprime des lignes non finies de ses features actives. L'audit mesure les
features **après** ce traitement. Il ne prétend pas compter toutes les valeurs
non finies intermédiaires avant nettoyage. Une barre non émise peut correspondre
à une chauffe normale, une segmentation ou une autre élimination ; le compteur
ne lui attribue pas automatiquement une cause.

## Audit distinct des labels H20 existants

Les labels sont lus depuis `global_oracle_labels` pour le batch et H20, par année.
Ils ne sont ni recalculés ni réinsérés en base. Les prix aux dates stockées de
départ et de sortie sont relus dans `stock_bars_daily` avec la même priorité
`COALESCE(adj_close, close)` que le constructeur de labels.

Deux périmètres sont affichés : **batch original complet** et **titres encore
présents dans l'univers courant**. Les rangs stockés sont contrôlés contre le
batch original : supprimer huit titres puis recalculer les rangs sur les seuls
restants ferait apparaître de fausses incohérences.

Contrôles :

- clés de labels dupliquées ;
- dates manquantes/incohérentes pour les labels déclarés valides ; disponibilité
  strictement après la sortie, elle-même strictement après la prédiction ;
- rendements non finis et divergence `future_return` / `future_return_raw` ;
- bornes des percentiles, cohérence des rangs avec les rendements du batch ;
- cohérence des déciles et de l'indicateur d'extrême avec le percentile ;
- prix d'extrémité manquants/non positifs ou sources différentes ;
- divergence entre rendement brut stocké et rendement relu aujourd'hui ;
- traversée d'une rupture d'identité connue du registre actuel ;
- couverture en labels et motifs de qualité réservés/invalides.

Les labels valides sans rang sont comptés à part : cela peut résulter d'un
univers quotidien trop petit et nécessite une lecture contextuelle.

Le contrôle utilise les **dates de sortie stockées**. Il ne certifie pas encore
indépendamment le décalage exact de 20 séances sur le calendrier originel, ni
toutes les ruptures inconnues à l'intérieur du chemin. Les sources d'extrémité
ne prouvent pas à elles seules la continuité de chaque barre intermédiaire.
Un rendement différent des prix actuels signale une divergence à examiner,
pas automatiquement une erreur de la valeur historique à l'époque.

## Sécurité, reprise et surveillance

Aucune écriture SQL : le moteur vise explicitement `alpha_trade` et chaque
transaction est déclarée en lecture seule. Aucun entraînement, calcul de PnL,
changement de modèle ou intervention sur les batchs existants.

Racine des résultats :
`artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-20261007-v1/`.

- `protocol.json` : options, colonnes, dates et empreintes de l'univers/profil,
  métadonnées et script de recherche.
- `features-NNN.parquet` et `features-NNN.json` : données par lot et marqueur
  validé avec hash, couverture et pertes de lignes.
- `year-YYYY.json` : distributions complètes et contrôles des labels de l'année.
- `progress.json` : phase, lots/années terminés et statut.
- `report.json` : bilan final, créé seulement après toutes les années.
- `error.json` : erreur lors d'une exécution, si présente ; vérifier sa date et
  la progression pour distinguer une ancienne tentative d'une reprise réussie.
- `stdout.log`, `stderr.log` : sortie du passage complet lancé en arrière-plan.

Le premier lot est terminé et les **28 tests ciblés passent**. Sur ce premier
lot : 53 098 barres dans la période et 52 098 lignes de features émises ; quatre
titres perdent chacun 250 premières observations. Cette observation est compatible
avec la chauffe mais ne constitue pas une conclusion globale.

Surveillance PowerShell :

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-20261007-v1\progress.json
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-20261007-v1\stderr.log -Tail 20 -Wait
Test-Path F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-dataset-audit-20261007-v1\report.json
```

Reprise, **uniquement une fois le processus précédent arrêté** :

```powershell
python -u -m scripts.research.us_oracle_h20_dataset_audit --batch-id model-factory-20261003082853-e98332 --output artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-20261007-v1
```

Ne pas démarrer deux instances sur la même racine. Les lots validés sont réutilisés
après vérification du hash ; un lot incomplet est recalculé. Une modification du
protocole nécessite une autre racine. La reprise n'est pas un snapshot SQL : des
données modifiées pendant le calcul peuvent mélanger des observations de moments
différents ; les divergences doivent donc être interprétées avec prudence.

## Décision après le rapport

1. Examiner les défauts structurels et divergences de labels, sans changer les
   prix arbitrairement pour obtenir de meilleurs résultats.
2. Identifier les défauts de couverture, les features inutilisées/constantes et
   les extrêmes économiquement plausibles ou non qualifiés.
3. Préciser les corrections nécessaires et les limites restantes avant tout GO
   pour réentraînement ou nouvelle construction des labels.
4. Ne comparer H5/H10/H15/H20 qu'ensuite, à univers et protocole fixés.

Aucun gain d'amplitude ou de direction D1/D10 n'est démontré par ce seul audit.

## Résultats finaux et interprétation

Statuts vérifiés : `progress.json = COMPLETED`,
`report.json = COMPLETED_READ_ONLY_AUDIT`. Les 72 lots et les neuf années ont
été traités ; aucune erreur finale dans le journal. Le complément de lecture
est archivé dans `interpretation.json` et produit par
`scripts/research/us_oracle_h20_audit_interpretation.py`.

### Couverture des features

| Mesure | Résultat |
|---|---:|
| Contrat vérifié | 173 features, 12 folds |
| Titres avec au moins une ligne émise | 1 790 sur 1 790 |
| Barres dans la période 2016–2024 | 3 860 349 |
| Lignes de features émises | 3 787 770 |
| Barres sans ligne émise | 72 579, soit 1,88 % |
| Features non finies après nettoyage | Aucune dans les neuf rapports annuels |

263 titres perdent chacun exactement 250 observations dans la période ; les
autres pertes par titre sont inférieures à 250. C'est compatible avec la chauffe
des fenêtres longues et les dates de début d'historique. Cela ne remplace pas
une attribution ligne par ligne des causes de suppression : ne pas présenter
les 72 579 lignes comme 72 579 erreurs de prix.

### Labels H20 : cohérence des contrôles réalisés

3 874 908 labels du batch original sont examinés, dont 3 873 149 déclarés valides.
Les 1 759 invalides se répartissent en 1 679 `missing_exit_bar` et 80
`extreme_unadjusted_price_jump`. Ils ne sont pas des labels valides silencieusement
utilisés par cet audit.

**Zéro violation** des contrôles implémentés sur les labels valides, aussi bien
sur le batch original que sur le sous-ensemble encore présent dans l'univers :
dates, valeurs finies, rangs/déciles/extrêmes, prix d'extrémité, sources,
rendement contre les prix actuels et ruptures connues. Aucun label valide sans
rang n'est relevé. Les limites de calendrier et de continuité inconnue décrites
plus haut restent applicables : ce résultat n'est pas une certification exhaustive.

### Défaut confirmé — facteurs CAPM alimentés par des rendements SPY absents

Sur les neuf années, `beta_252 = 1`, `alpha_252 = 0` et `r_squared_252 = 0`
pour toutes les lignes émises. Ce ne sont pas des expositions estimées : ce sont
les valeurs par défaut du module factoriel.

Chaîne vérifiée dans le code et par lecture SQL :

1. `load_benchmark_bars` fournit les barres SPY et leur colonne persistée
   `daily_return`.
2. Les **3 023 valeurs** de cette colonne sont NULL dans la fenêtre lue.
3. `modelFactory/factor_features.py::compute_factor_features` consomme cette
   colonne, puis remplace les valeurs manquantes par zéro. Il ne dérive pas ici
   les rendements depuis les prix ajustés.
4. La variance benchmark devient nulle ; la régression conserve les valeurs par
   défaut. `momentum_252_vs_market` soustrait aussi une somme de rendements
   benchmark nulle : le nom « vs market » ne correspond plus au calcul attendu.

Contrôle **hors production**, SPY contre lui-même :

| Variante | beta | alpha | R² | momentum252 vs marché |
|---|---:|---:|---:|---:|
| Rendements SPY persistés actuels | 1 | 0 | 0 | 0,217481 |
| Rendements SPY dérivés des prix, en mémoire seulement | 1 | 0 | 1 | 0 |

Ces chiffres sont ceux de la dernière ligne du contrôle ; ils ne constituent
ni une correction SQL ni un nouveau résultat ML. Les autres features marché
EXPERT calculent déjà certaines variations depuis les prix et ne sont pas
automatiquement touchées par ce même défaut.

**Action recommandée avant réentraînement :** dériver/valider les rendements du
benchmark sur la même base ajustée que les rendements titre, gérer explicitement
la couverture, puis tester beta/alpha/R² et la comparaison relative. Ne pas
simplement supprimer trois colonnes et laisser `momentum_252_vs_market` faux.
La correction applicative nécessite un GO distinct ; elle n'a pas été appliquée.

### Fragilité numérique — divisions par un dénominateur quasi nul

Les features restent finies, mais leur échelle peut devenir démesurée :

| Feature | Extrême observé | Lignes avec valeur absolue > 1 million | Explication mesurée |
|---|---:|---:|---|
| `rsi_14_div_volatility_20` | environ 10 milliards | 870 | Les 870 ont une volatilité ≤ 1e−8 |
| `log_return_div_intraday_range` | environ −74,05 millions | 50 058 | Les 50 058 ont un range ≤ 1e−8 |

Le seuil d'un million sert **uniquement au diagnostic d'échelle**, pas à une
sélection de trading ou à une optimisation de performance. Les formules EXPERT
divisent par un dénominateur plafonné à un minimum de 1e−8 ; un contrôle limité
à `isfinite` ne détecte donc pas le problème.

Exemples de barres locales relues :

- FLUT, 11/01/2016 : O=H=L=C=130,90272485, volume nul.
- BWLP, 04/02/2020 : O=H=L=C=8,99, volume nul.
- EVVTY, 05/06/2019 : O=H=L=C=7,9160064, volume 212.

111 510 lignes émises ont un range nul ; aucun range négatif n'est observé dans
ce contrôle. Une barre sans range peut être une observation OTC/stale ou une
journée réellement sans variation intraday ; ces chiffres ne suffisent pas à
qualifier 111 510 erreurs de prix.

**Action recommandée :** définir un contrat pour les ratios non interprétables
(dénominateur insuffisant, donnée manquante ou barre peu informative), avec
neutralisation/imputation explicite et indicateur de qualité si approprié.
Ne pas choisir un plafond sur les pertes de backtest et ne pas retirer tous les
titres concernés pour masquer une fragilité de formule. Aucun plafonnement ni
changement de features n'a été appliqué.

### Couverture limitée du short score et colonnes constantes

`selector_short_score` vaut zéro sur **3 759 323 lignes, soit 99,249 %** du dataset.
Le code utilise aussi zéro comme valeur par défaut lorsqu'un contexte manque :
ce taux n'est donc pas une mesure directe de la proportion de vrais scores
neutres. Ne pas attribuer un gain potentiel à cette option sans qualifier sa
couverture et la disponibilité PIT de ses sources.

`is_filled` reste constant à zéro dans ce dataset. `regime_bull_market` est
constant sur 2017, 2021 et 2024 ; une caractéristique de marché peut légitimement
être constante sur une période. Ce constat seul n'est pas un bug de régime.

### Conclusion et prochaine étape

Les anciennes valeurs astronomiques de rendement ne sont plus les seules
réserves : l'audit complet révèle **un défaut factoriel confirmé** et des
**ratios numériquement dégénérés**. Continuer uniquement à retirer des titres
n'est pas la bonne réponse à ces deux problèmes de calcul.

Avant de réentraîner : corriger/valider le calcul factoriel, définir le traitement
des ratios quasi nuls, puis relancer ce contrôle dans une nouvelle racine et
comparer les distributions et pertes de lignes. Conserver les anciens artefacts
comme état « avant ». Les labels ne nécessitent pas de réécriture sur la seule
base des contrôles réalisés ici.

Les modèles existants n'ont pas été réparés rétroactivement. Aucun effet causal
sur leurs performances, ni amélioration D1/D10, n'est démontré par ce constat.

## Suite autorisée — corrections numériques

Après GO utilisateur, les calculs factoriels et six ratios EXPERT ont été
corrigés, avec 224 tests ciblés passants. Le rapport ci-dessus reste l'état
**avant correction**. Un nouvel audit comparatif est lancé dans une racine
`oracle-h20-dataset-audit-corrected-20261007-v2` distincte.
Voir [contrat corrigé, compatibilité des anciens modèles et surveillance](oracle_numeric_feature_corrections.md).
La commande de reprise de l'ancien rapport est historique : avec les sources
corrigées, utiliser la nouvelle racine, pas réutiliser les anciens caches.
