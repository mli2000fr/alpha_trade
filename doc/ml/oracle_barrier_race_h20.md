# TOP10 Oracle × ATR — gain 20 % avant stop 7 %

## Protocole figé — 11 octobre 2026

Audit descriptif, sans entraînement ni calcul de portefeuille. Réutiliser les
prix du rapport d’excursions v2 après vérification des empreintes. Aucune lecture
ou écriture SQL supplémentaire, aucun modèle de production ni batch modifié.

Sélection : dix premiers en ordre de score Oracle dans Oracle TOP20 % ∩ ATR
TOP20 %, figée avant examen des résultats. Univers archivé nettoyé de 1 790 titres.
Observation des deux côtés indépendamment, **sans sélectionner le bon sens grâce
au futur**. LONG : objectif +20 %, stop −7 %. SHORT : objectif baisse 20 %, stop
hausse 7 %, exprimés en variation du prix depuis l’entrée.

Entrée à l’ouverture ajustée de J+1. Vingt séances observées, entrée comprise :
J+1 à J+20. Cette convention n’est pas une vente à l’ouverture J+21 après vingt
séances écoulées. Conversion OHLC par le facteur `adj_close / close` du snapshot.

Quatre résultats : objectif d’abord, stop d’abord, ambigu même séance, aucun seuil.
À chaque séance l’ouverture est connue avant le haut/bas : une ouverture au-delà
d’un seuil détermine le premier contact. Un gap stop peut dépasser 7 % de perte,
donc le stop n’est pas une garantie de perte plafonnée à 7 %.
Si l’ouverture reste entre les seuils et que haut/bas touchent les deux, l’ordre
est inconnu : conserver AMBIGUOUS, lecture conservatrice stop d’abord, borne
optimiste objectif d’abord. Aucune heure intraday inventée.

Retenir les chemins qualifiés par l’audit précédent, sans remplacement des
candidats réservés. Couverture indiquée par année. Conserver séparément une
sensibilité sans chemins comprenant `high/low >=1.5` : réserve exploratoire,
pas certification d’erreur de prix ni filtre appris pour trader.

Mesures : proportions des quatre résultats, borne conservatrice/optimiste,
objectif touché à un moment quelconque (même après un stop), gaps stop, séance
médiane de premier contact. Pour les chemins sans seuil, rendement terminal
signé du côté observé, uniquement descriptif, pas rendement de portefeuille.

Périodes : 2020–9 juillet 2024, puis 2025–3 septembre 2026. Second semestre 2024
absent. 2026 déjà étudié, pas un holdout vierge. Fenêtres chevauchantes et univers
historique non entièrement PIT. Aucun coût, spread, slippage, sizing, limite
de portefeuille, veto d’entrée gap, emprunt SHORT ou remplissage réel qualifié.

Une fréquence favorable ne suffit pas à autoriser un nouveau modèle ou à
conclure à une stratégie rentable : il faut ensuite une prédiction du côté et
un rejeu économique qualifié, après nouveau GO.

```powershell
python -u -m scripts.research.us_oracle_barrier_race --output artifacts/research/us_amplitude_rerank/barrier-race-h20-20261011-v1
```

Suivi `progress.json`, reprise par lots validés dans `done.json`. Résultats :
`report.json`, `annual.parquet`, `annual_range_sensitivity.parquet`,
`races.parquet`, `ambiguous.parquet`. Ne pas lancer deux instances sur le même dossier.

## Résultats — calcul terminé le 11 octobre 2026

46 lots terminés. 15 550 candidats titre/date, chacun observé en LONG et SHORT :
31 100 scénarios, dont 31 050 qualifiés (99,84 %). Vingt-cinq candidats sont
réservés, jamais remplacés. Les proportions ci-dessous sont par scénario
qualifié, pas par titre unique ni par portefeuille.

Lecture conservatrice : ambiguïtés affectées au stop. Aucun TP/SL exécuté
réellement, aucune performance économique calculée.

| Année | LONG objectif avant stop | LONG stop d’abord | LONG aucun seuil | SHORT objectif avant stop | SHORT stop d’abord | SHORT aucun seuil |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 29,15 % | 68,43 % | 2,41 % | 21,32 % | 73,50 % | 5,18 % |
| 2021 | 25,32 % | 68,49 % | 6,19 % | 17,66 % | 74,13 % | 8,21 % |
| 2022 | 24,53 % | 73,99 % | 1,48 % | 26,29 % | 71,48 % | 2,23 % |
| 2023 | 29,80 % | 59,28 % | 10,92 % | 11,72 % | 76,52 % | 11,76 % |
| 2024 jusqu’au 09/07 | 20,23 % | 64,00 % | 15,77 % | 10,08 % | 61,54 % | 28,38 % |
| 2025 | 28,52 % | 61,52 % | 9,96 % | 16,32 % | 73,24 % | 10,44 % |
| 2026 jusqu’au 03/09 | 25,39 % | 71,02 % | 3,59 % | 18,50 % | 74,67 % | 6,83 % |

Trente scénarios sur l’ensemble historique sont ambigus. En 2025–2026,
les bornes optimistes ne changent que très peu les fréquences : LONG 2025
28,56 % au lieu de 28,52 %, LONG 2026 25,45 % au lieu de 25,39 %.
L’absence d’ordre intraday n’explique donc pas l’essentiel des stops.

### Atteindre le gain après un stop ne compte pas comme une réussite

En LONG 2025, 39,32 % touchent +20 % à un moment pendant les vingt séances,
mais seulement 28,52 % avant le stop. En 2026 : 41,86 % contre 25,39 %.
Le grand mouvement peut donc arriver **après** la sortie stop ; le précédent
audit d’excursions ne suffisait pas à mesurer une opportunité compatible avec
un stop 7 %. Les seuils du présent test sont ancrés à l’ouverture J+1, et non
à la clôture J : ne pas comparer directement aux 62–70 % de l’audit précédent.

### Sensibilité aux plages intraday larges

Sans les chemins signalés `high/low >=1.5` :

- LONG 2025 : 28,13 % objectif d’abord, 61,82 % stop conservateur ;
- LONG 2026 : 25,20 % objectif d’abord, 71,18 % stop conservateur ;
- SHORT 2025 : 16,42 % objectif d’abord, 73,04 % stop conservateur ;
- SHORT 2026 : 18,61 % objectif d’abord, 74,50 % stop conservateur.

La conclusion qualitative ne dépend pas de ces plages exceptionnelles.
Cette sensibilité reste exploratoire et ne certifie pas les prix.

### Gaps et durée

Scénarios LONG avec premier stop franchi par gap : 7,40 % en 2025 et 6,95 %
en 2026 ; SHORT : 10,20 % et 9,88 %. Les ouvertures observées peuvent être
bien au-delà du stop nominal. Certains cas particulièrement larges restent
à qualifier indépendamment avant tout PnL, y compris ceux qui passent le
contrôle interne de cohérence OHLC.

En LONG, objectif atteint d’abord à la médiane au 9e jour en 2025 et au 6e
en 2026 ; stop conservateur au 4e et au 3e jour. Les stops arrivent souvent
avant que le grand mouvement favorable ne se matérialise.

**Conclusion : l’amplitude seule ne suffit pas à choisir le côté ni à assurer
une trajectoire compatible avec SL 7 %.** La fréquence de stops élevée ne
prouve pas à elle seule une stratégie perdante : gains/pertes ont des tailles
différentes, chemins sans seuil et gaps comptent, et les coûts manquent.
Ne pas annoncer un rendement à partir de ces pourcentages.

Une éventuelle suite, après nouveau GO, serait un modèle de probabilité
« objectif avant stop » sur les deux côtés, avec maturité/purge et tests
chronologiques identiques. Son avantage contre Oracle seul reste à démontrer ;
ne pas chercher un nouveau SL/TP adapté rétrospectivement aux pertes.
