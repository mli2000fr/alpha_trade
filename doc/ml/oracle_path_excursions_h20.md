# Excursions pendant H20 masquées par le rendement final

## Audit figé, 11 octobre 2026

Avant de proposer un troisième modèle de tri, mesurer si le parcours contient
une information différente du rendement final utilisé par les deux essais
précédents. **Pas d’entraînement, pas de backtest économique, aucune écriture SQL.**

Pool : mêmes archives corrigées Oracle TOP20 % ∩ ATR TOP20 %, sélection par les
observables sans utiliser le futur. Historique à partir du 1er janvier 2020
jusqu’au 9 juillet 2024, puis 2 janvier 2025–3 septembre 2026 ; second semestre
2024 absent. Univers archivé nettoyé de 1 790 titres, pas univers historique PIT
certifié. 2026 déjà examiné, pas de holdout inédit.

## Conventions

Référence : clôture ajustée J. Parcours : les vingt séances NYSE **J+1 à J+20**,
sans inclure J, sans sauter ni remplir une barre absente. Ce n’est pas une entrée
à l’ouverture J+1 ni vingt séances après l’entrée.

Calculer séparément :

- excursion haussière maximale sur les hauts quotidiens ;
- excursion baissière maximale sur les bas quotidiens ;
- amplitude maximale entre les deux sens ;
- maximum des mouvements absolus visibles aux seules clôtures ;
- rendement terminal signé et absolu à J+20 ;
- différence amplitude maximale moins amplitude terminale ;
- seuils absolus ±20 % et ±50 %, séance du premier contact, contacts dans les
  deux sens et premier contact simultané ambigu avec OHLC quotidiens.

Un mouvement est « masqué » si le parcours atteint le seuil mais le rendement
absolu final reste en dessous. Distinguer un pic intraday d’une excursion encore
visible à une clôture. Un contact de seuil ne prouve ni exécution, ni liquidité,
ni capacité à capturer ce rendement. Ne pas interpréter le plus haut futur comme
un prix de vente disponible au modèle.

## Prix et réserves

Lecture de `alpha_trade.stock_bars_daily` sous transactions SQL READ ONLY, cache
local par lots de 25 symboles. Les hauts/bas sont remis sur la base du label en
appliquant `adj_close / close` à chaque barre. Ce traitement n’est pas une
certification indépendante de toutes les opérations sur titres.

Qualification du chemin entier : OHLC positifs, finis et cohérents, volume
positif, barre réelle non remplie, source et convention d’ajustement stables,
identifiant instrument stable et renseigné, aucune discontinuité d’identité
connue. Les sauts quotidiens ajustés >=20x ou <=1/20x sont réservés ; les sauts
>=50 % sont signalés pour revue, pas déclarés automatiquement erronés.

Le rendement recomposé doit correspondre au label archivé et sa disponibilité
doit suivre la sortie J+20. Sinon conserver la ligne en réserve avec les motifs,
sans remplacer le candidat. Les taux sont calculés sur les chemins qualifiés,
avec couverture explicite pour rendre visible le biais des exclusions.

## Rapport

Année et source séparées, pour tout le pool, les dix premiers en ordre Oracle
et les dix premiers en ordre ATR. Fréquences du seuil atteint, terminal au-dessus
du seuil, excursions masquées et part masquée parmi les chemins ayant atteint
le seuil. Les agrégats sont des observations titre/date chevauchantes, pas des
trades indépendants ni du PnL. Les exemples futurs sont rétrospectifs uniquement.

```powershell
python -u -m scripts.research.us_oracle_path_excursions --output artifacts/research/us_amplitude_rerank/path-excursions-h20-20261011-v1
```

`progress.json` suit les lots ; chaque `chunk-NNN/done.json` permet une reprise
avec vérification des caches. Ne pas lancer deux instances dans le même dossier.
Résultats : `report.json`, `annual.parquet`, `paths.parquet`,
`hidden_examples.parquet`, `large_jump_review.parquet`. Pas de nouveau modèle
automatiquement autorisé à la fin : interpréter d’abord taille, couverture et
stabilité de l’effet, puis définir une hypothèse distincte si nécessaire.

## Correctif technique et sensibilité (avant interprétation)

Le premier rapport v1 n’est **pas interprétable** : certains booléens Python/numpy
mixtes ont été agrégés comme une réduction logique au lieu d’une moyenne. Les
chemins et prix archivés restent exploitables. Le rapport v2 convertit explicitement
les indicateurs en nombres avant agrégation, avec test de non-régression.

Recalcul v2 à partir du snapshot de prix v1 vérifié par empreintes, sans nouvelle
lecture SQL. Les candidats, dates, univers et registre d’identités doivent être
identiques. Les chemins sont recalculés, pas simplement copiés.

Une sensibilité exploratoire exclut les chemins comprenant un jour `high/low >=1.5`.
Cette plage quotidienne >=50 % est une réserve de revue, **pas une preuve d’erreur**.
Elle est ajoutée après constat de quelques pics très larges, et ne sera pas
présentée comme un filtre prédictif pré-enregistré. Résultats séparés dans
`annual_range_sensitivity.parquet` et `intraday_range_review.parquet`.

```powershell
python -u -m scripts.research.us_oracle_path_excursions --bars-cache artifacts/research/us_amplitude_rerank/path-excursions-h20-20261011-v1 --output artifacts/research/us_amplitude_rerank/path-excursions-h20-20261011-v2
```

## Résultats v2 — terminé

46 lots terminés, 426 299 observations titre/date dans le pool, 425 260 chemins
qualifiés (**99,76 %**), 1 039 réservés. Vingt-et-un tests ciblés validés, dont
le test des booléens mixtes. Aucun entraînement ni écriture SQL.

Résultats des dix premiers en ordre Oracle **dans le pool Oracle × ATR** :

| Année | Observations qualifiées | Final `|R| >=20 %` | Seuil ±20 % atteint pendant H20 | Masqué au final | Masqué mais visible à une clôture |
|---|---:|---:|---:|---:|---:|
| 2020 | 2 528 | 52,49 % | 79,98 % | 27,49 % | 18,28 % |
| 2021 | 2 520 | 37,70 % | 68,45 % | 30,75 % | 19,64 % |
| 2022 | 2 507 | 40,65 % | 82,25 % | 41,60 % | 30,51 % |
| 2023 | 2 500 | 30,76 % | 56,32 % | 25,56 % | 16,16 % |
| 2024 jusqu’au 09/07 | 1 300 | 15,38 % | 35,38 % | 20,00 % | 11,92 % |
| 2025 | 2 500 | 31,68 % | 62,32 % | 30,64 % | 19,56 % |
| 2026 jusqu’au 03/09 | 1 670 | 36,71 % | 69,94 % | 33,23 % | 22,28 % |

Les dénominateurs sont des **observations titre/date qualifiées**, pas des titres
uniques ni uniquement des journées entièrement complètes. Les observations
2026 couvrent 169 séances de signal, avec 20 chemins TOP10 réservés. Ces taux
ne sont pas directement appariés aux rapports des modèles antérieurs. Une
tolérance numérique 1e-12 inclut les contacts exactement à 20 %, ce qui explique
aussi certains petits écarts avec les comparaisons antérieures sans tolérance.
Les trois colonnes seuil final/parcours/masqué respectent l’identité arithmétique
`parcours − final = masqué` après correction.

En 2025, **49,17 % des chemins TOP10 qui ont atteint ±20 %** terminent ensuite
sous ce seuil absolu ; en 2026, 47,52 %. Le phénomène n’est donc pas limité à
quelques pics intraday : une part importante reste visible à une clôture.

Pour ±50 %, TOP10 Oracle : 8,12 % atteignent le seuil en 2025 contre 3,76 % qui
y restent au final ; 8,62 % contre 5,03 % en 2026. Aucun sens de mouvement n’est
encore prédit, et aucune de ces amplitudes n’est un PnL réalisable garanti.

### Robustesse aux plages intraday très larges

2 247 chemins qualifiés du pool sont signalés par `high/low >=1.5` sur au moins
un jour ; 1 220 par un saut ajusté de clôture >=50 %. Les ensembles se chevauchent.
Des exemples spectaculaires (notamment REPX 2020 et CAR 2026) restent à vérifier
indépendamment avant de les valoriser ou d’en faire des cibles d’apprentissage.
Le contrôle interne OHLC ne certifie pas la réalité de tous les extrêmes.

Sensibilité TOP10 sans plage quotidienne >=50 % :

| Année | Observations conservées | Final >=20 % | Parcours >=20 % | Masqué |
|---|---:|---:|---:|---:|
| 2025 | 2 478 | 31,72 % | 62,03 % | 30,31 % |
| 2026 | 1 655 | 36,19 % | 69,67 % | 33,47 % |

La conclusion qualitative persiste. En 2020 cette sensibilité retire davantage
de chemins (plages larges pendant la crise), ce qui ne prouve pas qu’ils étaient
erronés : conserver séparément mesure complète et sensibilité exploratoire.

### Réserves et interprétation

Principaux motifs : 777 chemins OHLC/volume/fill incomplets ou invalides,
391 labels archivés non qualifiés et écarts de rendement, 262 disponibilités
absentes/incompatibles, 221 sources/identités/ajustements inconnus ou changeants,
16 ruptures de prix >=20x. Les motifs se chevauchent ; ne pas additionner.

Seulement 15 chemins qualifiés du pool ont un premier contact ±20 % simultané
dans les deux sens sur le même jour ; 4 158 touchent les deux sens au cours de
H20. Le sens et les sorties restent donc un problème distinct.

Parmi les chemins TOP10 Oracle ayant atteint ±20 %, le premier contact survient
à la médiane au **8e jour**, avec quartiles 5 et 13. C’est une statistique
conditionnelle rétrospective, pas une recommandation d’entrer au jour 8.

**Conclusion : l’hypothèse de cible parcours est matériellement justifiée**, car
le rendement final masque des excursions fréquentes sur toutes les années.
Cela ne démontre pas qu’un modèle peut les anticiper. Une suite possible,
après nouveau GO, serait une cible robuste aux seules clôtures (probabilité
de dépasser ±20 % pendant H20), comparée hors échantillon au même ordre Oracle.
Qualifier davantage les pics OHLC avant de privilégier une cible intraday.
Ne pas lancer automatiquement un troisième modèle ni un replay économique.
