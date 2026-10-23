# P03 — premier retest confirmé : protocole figé

Préenregistré le22octobre2026 avant calcul des nouveaux résultats. Dossier neuf :
`artifacts/research/us_oracle_retest_p03/20261022-v1`.

## Question et intervention

Attendre un premier retest d'un niveau préalablement cassé améliore-t-il le
timing d'entrée Winner ? Aucun nouveau modèle ni avantage directionnel supposé.
Sources d'inspiration FMZ au commit `7853bb2bf262c4567ac238d3552d97f0e50cb801` :
documents8 et253, zones engulfing/3EMA ; le premier peut entrer immédiatement
sans retest. **L'adaptation testée est la nôtre**, sans EMA ni chandelle ajoutée.

## Définition complète, LONG seulement

Pour chacune des213campagnes de recherche archivées, chercher le premier
franchissement Winner dans les vingt séances après Oracle : haut raw de la
séance précédente, clôture à/au-dessous puis deux clôtures5m strictement
au-dessus, achat témoin à l'open contigu suivant. Ce premier niveau est figé.
Pas de nouveau breakout, autre jour, deuxième retest, remplacement TOP11 ou
réessai après refus du risque. Les entrées autres que ce premier Winner sont
uniquement les deux variantes de timing ci-dessous.

Tolérance = **1× le dernier ATR20 Wilder des bougies5m de la séance précédente**,
séance complète régulière, SMA20 initial, premier TR=high−low, reset à chaque
séance. ATR arrondi scalaire à huit décimales, bornes niveau±tolérance également.
Ce n'est **pas** l'ATR daily ajusté employé séparément par le sizing historique.
Ainsi, le niveau et sa tolérance sont sur les mêmes prix raw et connus avant
la décision. Pas de volatilité de la séance en cours ou de futur creux.

P03 commence après la bougie de confirmation du premier Winner. Pendant au
plus12nouvelles bougies complètes (une heure), dans la **même séance** :

1. Le premier low5m ≤ niveau+tolérance constitue le retest.
2. Toute bougie complète dont low < niveau−tolérance invalide la tentative,
   même si elle termine au-dessus. Invalidation prioritaire sur reprise
   ambiguë dans la même bougie ; aucune séquence high/low intrabar inventée.
3. Après la bougie de retest, exiger deux clôtures consécutives >niveau,
   sur deux bougies strictement ultérieures. La bougie touchée ne compte pas.
   Une clôture ≤niveau remet le compteur à zéro, sans changer le premier retest.
4. Acheter à l'open contigu suivant, encore dans la même séance. Un retest ou
   une confirmation à la dernière bougie sans open suivant n'est pas exécuté.

Pas d'ordre limite réputé exécuté par simple contact du low. L'open suivant
est un prix d'exécution, pas un filtre choisi avec le futur. Les écarts entre
signal et fill gardent le garde-fou natif3 % commun aux bras ; aucun filtre
supplémentaire sur l'open ni stop élargi pour rendre le signal admissible.

## Témoin de simple attente

DELAY_CONTROL attend **six bougies complètes**, trente minutes à partir de
l'open d'entrée Winner, puis entre au prochain open : même séance exigée.
Tous les lows de ces six bougies doivent rester ≥borne basse et les deux
dernières clôtures >niveau. Pas de condition de retest. Ce délai est fixé
avant calcul, jamais ajusté au futur délai réel P03 de chaque occasion.
L'invalidation après l'entrée du témoin ne doit pas annuler rétroactivement
son signal. Même règle pour P03 une fois confirmé.

## Comparaison économique et couverture

Quatre bras ×2025/2026 ×8/25bps parjambe = **seize portefeuilles** :

- WINNER : ancre200campagnes/69titres déjà auditée P01, quatre cas à reproduire
  à l'octet près (trades, marks, décisions, maintenance, événements B4).
- COMMON_WINNER, DELAY_CONTROL et P03 : occasions communes recalculées depuis
  les213campagnes originales. Leurs réserves peuvent différer de P01, car les
  scans P01 pouvaient chercher un autre breakout beaucoup plus tard.

Toutes les occasions sans signal restent dans les unités avec zéro rendement,
pas éliminées comme « mauvais trades ». Manque dans le scan jusqu'au premier
Winner, ATR insuffisant ou chemin futur incomplet/immature pour une entrée émise
réservent l'occasion identiquement pour les trois bras communs. Pas de sélection
du chemin uniquement jusqu'au futur stop. Les signaux sont tous le même jour
que leur Winner initial : horizon calculé depuis chaque entrée réelle.

Archives existantes scellées, raw SIP régulières non remplies, calendrier NYSE
avec fermetures anticipées ; aucun SQL ou téléchargement. Actions connues
réservées, mais table héritée vide/incomplète : pas certification des identités
ni de l'absence d'opération sur titres. Pas de mélange daily ajusté/raw pour
la tolérance. Le sizing conserve les mêmes archives ATR/ADV daily qu'avant.

Capital annuel4 000USD, plafond admission1×, demi-cible, quantités entières,
SL7/TR15/sansTP/sansrenforcement et B4DD15 natifs inchangés. Vingt séances de
détention, entrée incluse, vente à l'open21. Gaps au prix exécutable, risque
et protections existantes prioritaires. Les cash/sizing/B4 peuvent diverger
avec le timing : mêmes formules, pas quantités artificiellement égales.

## Critères de confirmation et réserves

Pas de grille ni d'optimisation du délai, ATR, tolérance ou confirmations.
Résultats nets/DD/exposition, fréquences, occasions perdues, concentration et
prix/délais d'entrée sont publiés, avec appariement unitaire par occasion.
Sensibilité sans chevauchement par symbole, blocage conservateur jusqu'à
OracleJ40 ; bootstrap des mois Oracle,2 000tirages,graine731.

Pour poursuivre : au moins30signaux P03 sans chevauchement et10titres par an,
rendement portefeuille supérieur **aux deux contrôles** dans les deux années
aux deux frais, DD non aggravé à8bps, surplus unitaire positif à25bps et borne
basse95 % mensuelle >0 contre chacun, sur au moins6mois. Sinon non-confirmation
ou échantillon insuffisant, jamais assouplissement postérieur des critères.

2025 et2026au30septembre déjà explorées, pas holdout neuf ;2024 non simulée,
absente de l'archive intraday retenue. Cohorte conditionnelle de recherche
CatBoost PATH_H20, pas tout le TOP10 quotidien ni le LightGBM de production.
Couverture future/survivance, PIT, secteur, NBBO/queue/fills/latence non résolus :
**recherche exploratoire, pas parité live complète**. B4DD15 ne garantit pas
un DD maximal de15 %.

Sélecteur/arithmetic d'audit distinct, contrôles cash/sorties/B4 et quatre
ancres exactes, empreintes sources/données avant/après. Même assistant,
pas revue humaine indépendante. Aucun modèle, batch ou configuration de
production, SQL, LLM/fournisseur, entraînement ou ordre modifié.

```powershell
python -u -m scripts.research.us_oracle_retest_p03 --phase run
python -u -m scripts.research.us_oracle_retest_p03_audit
```

Ne pas réutiliser le dossier scellé ; correction technique éventuelle dans un
dossier neuf sans retoucher les seuils selon les résultats.
