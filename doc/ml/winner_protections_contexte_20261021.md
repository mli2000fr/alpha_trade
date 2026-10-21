# Protections contextuelles — audit de faisabilité intraday

## Question et périmètre figé

GO du 21 octobre 2026 : chercher si les avantages relatifs des protections
dépendent de situations observables avant l'entrée, **avant d'entraîner** un
sélecteur. Pas de modèle directionnel, de nouvelle optimisation de 144 profils,
de changement de configuration, de collecte fournisseur, d'appel LLM ou d'ordre.

Le contraste avec l'essai du 14 octobre est explicite : ici les protections
s'appuient sur les primitives communes du mécanisme actuel `winner_pyramiding`,
sur des bougies SIP cinq minutes, et l'horizon part de l'entrée. L'essai du
14 octobre utilisait des protections journalières sans expiration H20 ; la
grille intraday précédente expirait à J+H depuis Oracle, attente incluse.

**Ce premier étage mesure des rendements par unité de capital sur les mêmes
entrées ; ce n'est pas un nouveau backtest de portefeuille.** Il ne calcule pas
de rendement annuel réalisable, DD de compte, capital engagé ou levier : leur
calcul nécessiterait ensuite sizing, cash, risque et réinvestissements.

## Six profils, une seule dimension modifiée

| Profil | SL | Trailing | Horizon depuis l'entrée | TP |
| --- | ---: | ---: | ---: | ---: |
| REFERENCE | 7 % | 15 % | 20 séances | aucun |
| SL5 | 5 % | 15 % | 20 séances | aucun |
| TRAIL10 | 7 % | 10 % | 20 séances | aucun |
| TRAIL20 | 7 % | 20 % | 20 séances | aucun |
| HOLD15 | 7 % | 15 % | 15 séances | aucun |
| TP10 | 7 % | 15 % | 20 séances | 10 % |

Pas de renforcement. Fraction initiale 0,5, confirmation de deux clôtures et
attente maximale vingt séances inchangées ; la fraction de position ne multiplie
pas les rendements unitaires et ne constitue pas un sizing simulé. L'effet du
SL5 sur les quantités autorisées n'est pas assimilé à un effet de portefeuille.

Les sorties emploient `add_fill`, `due_open`, `resolve_bar_exit` et
`observe_completed_bar` du contrat partagé : arrondi au cent, SL prioritaire en
collision, gaps réels, TP plafonné à la limite, sommet connu des bougies
**précédentes** seulement. Après vingt séances entrée incluse : sortie à l'open
de la 21e. Intrabar : instant inconnu dans les cinq minutes ; horodatage à la
borne supérieure, pas de tick fictif.

Friction unitaire illustrative : 8 bps par jambe puis 25 bps en stress, sur les
notionnels d'entrée et de sortie respectifs. Aucun tarif historique bid/ask,
file d'attente ou fill broker certifié. Les frais ne modifient pas les quantités
dans cet étage **unitaire**.

## Population et sélection d'entrée

213 campagnes LONG de recherche CatBoost PATH H20, issues des scores TOP10
archivés 2025–2026, sans remplacement d'un titre exclu. Ce n'est pas tout le
TOP10 quotidien, ni le champion LightGBM de production. Le parent avait déjà
sélectionné des chemins futurs complets : biais de couverture/survivants hérité.

Les entrées sont recalculées avec le prédicat actuel `confirmed_breakout`, pas
reprises à l'identique depuis l'ancien simulateur. Il exige trois bougies
complétées de la même séance : une clôture au-dessous/au niveau du high de la
veille, puis deux au-dessus. Entrée hypothétique à l'open contigu suivant.
L'ancien signal pouvait utiliser la clôture de la veille comme première preuve ;
il n'est pas automatiquement équivalent au runtime courant.

Même première entrée pour les six profils, indépendamment des sorties futures.
Pas de risque de portefeuille/admission des positions déjà détenues dans cette
mesure unitaire. Une lacune rencontrée avant de qualifier le signal ne permet
pas de sélectionner discrètement un signal ultérieur.

Fenêtre commune de qualité et de maturité jusqu'à la clôture de la 21e séance
depuis l'entrée, même si un profil serait sorti avant. Les opportunités tardives,
les trous intraday, données invalides ou opérations sur titres connues dans la
fenêtre sont réservés **pour tous les profils**. Pas de validation asymétrique
des sorties précoces ; cela ajoute un biais de couverture explicitement publié.
L'absence d'événement dans la table d'opérations sur titres n'en certifie pas
l'exhaustivité.

## Facteurs déclarés avant lecture des nouveaux résultats

À la **veille** de la séance d'entrée, sans forward-fill de prix :

1. Régime prix SPY selon close/SMA50/SMA200 : BULL, CORRECTION, REBOUND ou SLIDE.
2. ATR20 du titre divisé par le close : inférieur à 5 %, ou au moins 5 %.
3. Momentum vingt séances du titre moins celui de SPY : positif ou négatif.
4. Volatilité des rendements sur vingt séances / soixante : expansion ou contraction.
5. Délai d'entrée depuis Oracle : au plus cinq séances, ou davantage.

Prix daily split-adjusted actuels : indicateurs causaux par calcul mais pas
vintages historiquement certifiés. Les prix raw SIP servent aux barrières et
fills ; les niveaux ajustés ne remplacent pas le high raw de déclenchement.

Les données macro existantes et secteurs actuels sont figés pour inventorier la
couverture, **pas utilisés comme facteurs de confirmation** : le PIT des vintages
macro et du secteur n'est pas établi. Pas de régime VIX inventé, ni de secteur
actuel présenté comme historique. Cette réserve borne la conclusion : l'audit
ne peut exclure une information macro/sectorielle correctement qualifiée future.

## Séparation temporelle et critères

Deux vues : toutes les observations, puis espacement par symbole, entrée la
plus ancienne conservée et blocage jusqu'à l'échéance **commune**, pas jusqu'à
la sortie favorable de tel profil. Cela réduit les chevauchements d'un même
titre ; les titres restent corrélés entre eux et les périodes marché communes.

- Développement : entrées 2025 dont le label commun était disponible avant 2026.
- Comparaison : entrées 2026 jusqu'au 30 septembre, déjà examinées dans les
  recherches antérieures : **pas de nouvel échantillon vierge**.
- Choisir le constant global sur 2025 uniquement ; pour chacun des cinq facteurs,
  choisir un profil par état sur 2025 uniquement. Égalité : ordre du tableau.
- État avec moins de douze observations 2025 : repli sur le constant 2025, pas
  sur le meilleur profil observé en 2026.
- Publier tous les états et facteurs, y compris rares et défavorables.

Pour justifier seulement un éventuel **protocole de petit modèle**, toutes les
conditions préfixées sont nécessaires : trente observations non chevauchantes
par année ; au moins douze par état et année pour la règle ; surplus théorique
du meilleur profil connu après coup ≥0,5 point unitaire chaque année ; au moins
deux profils effectivement sélectionnés en 2026 ; avantage de la règle ≥0,25
point contre le constant choisi sur 2025, positif aux frais 25 bps et dans les
deux semestres 2026 disponibles ; borne basse du bootstrap mensuel >0, avec au
moins six mois. Bootstrap descriptif de 2 000 tirages, graine 731 ; pas de
garantie d'indépendance ni de correction de multiplicité certifiée.

Un meilleur profil unique choisi partout n'est **pas** une personnalisation.
Un surplus rétrospectif n'est **pas** une capacité à prévoir le profil gagnant.
Si les données ou les confirmations manquent : arrêt explicite, pas un nouveau
modèle de plus, ni changement des seuils après lecture des pertes.

## Sources et exécution

Programme : `scripts/research/us_winner_context_headroom.py`, phases
`prepare`, `snapshot`, `analyze`. Préparation et protocole avant outcomes,
empreintes du code/tests/parent, transaction SQL `READ ONLY` et reçus locaux.
Pas d'appel de prédiction, de téléchargement externe ou d'écriture SQL.

Dossier de suivi :
`artifacts/research/us_winner_context_headroom/20261021-v1/progress.json`.
`protocol.json` fixe les hypothèses ; `snapshot.json` les fichiers lus ;
`reservations.parquet` tous les motifs ; `unit-results.parquet` tous les profils ;
`nonoverlap.parquet` le contrôle espacé ; `factor-state-summary.json` les états ;
`frozen-2025-policy.json` les choix fondés sur 2025 ; `context-checks.json` la
comparaison 2026. Le bilan terminal sera dans `report.json`.

## Résultats terminés — pas de facteur confirmé

Statut **`NO_GO_CONTEXT_NOT_CONFIRMED`**. Lecture locale figée de **523 941 barres**
pour 72 titres, couvrant les fenêtres demandées sur 6 737 couples titre/séance
(certaines séances n'ont aucune ligne). Les 213 campagnes ont toutes été traitées.

- **204** ont une entrée et une fenêtre commune qualifiées : 113 en 2025, 91 en 2026.
- Cinq réserves de couverture H20 : KURA, CODI, GPRE, LASR et UCTT.
- Quatre fenêtres encore immatures à la borne du 30 septembre : PENG, MXL,
  TSEM et MRVL. Ne pas les récupérer rétroactivement grâce à des prix d'octobre.
- Après espacement par symbole : **95 en 2025 et 74 en 2026**, soit 169.
- Le choix fondé sur 2025 n'utilise que **84** de ces 95 : les onze autres
  labels communs n'étaient pas disponibles avant le début de 2026.
- Parmi les 74 observations 2026, 63 sont au premier semestre et 11 au second
  semestre partiel. La seconde moitié constitue donc une confirmation faible.

### Les protections ne donnent pas toutes le même résultat

Rendement **unitaire moyen net par entrée** sur le contrôle espacé, frais 8 bps
par jambe. **Ce ne sont pas des rendements annuels de portefeuille** :

| Profil | Entrées 2025 | Entrées 2026 jusqu'au 30 septembre |
| --- | ---: | ---: |
| REFERENCE — SL7 / TR15 / H20 / sans TP | **+4,60 %** | +3,11 % |
| SL5 | +3,03 % | +2,30 % |
| TRAIL10 | +1,95 % | +2,04 % |
| TRAIL20 | +4,30 % | +2,93 % |
| HOLD15 | +3,70 % | **+3,91 %** |
| TP10 | +0,66 % | +2,20 % |

Le meilleur constant observé est REFERENCE en 2025 et HOLD15 en 2026. Le
sélecteur parfait, connaissant chaque parcours futur, aurait un surplus moyen
de **3,46 / 5,95 points unitaires** contre le meilleur constant de l'année.
L'espace théorique de personnalisation est donc matériel. Mais **52,63 % /
44,59 %** des observations espacées perdent avec **tous les six profils** :
personnaliser les sorties ne transforme pas nécessairement une mauvaise entrée
en bonne entrée.

### Choisir un profil à partir des facteurs de 2025 ne se confirme pas

Le constant sélectionné sur les 84 labels 2025 disponibles est REFERENCE.
Chaque règle ci-dessous est choisie uniquement sur ces labels, puis évaluée
sur les 74 observations 2026, sans modification de seuil ni ajout de profil :

| Facteur de choix | Écart moyen en 2026 contre REFERENCE | Décision |
| --- | ---: | --- |
| Régime prix SPY | −0,35 point | Pas d'amélioration, certains états trop rares |
| ATR relatif au prix | 0,00 | Choisit toujours REFERENCE, pas de personnalisation |
| Momentum relatif titre/SPY | −0,48 point | Pas d'amélioration |
| Expansion/contraction de volatilité | −0,58 point | Pas d'amélioration |
| Délai d'entrée après Oracle | 0,00 | Choisit toujours REFERENCE |

Le stress de frais 25 bps conserve les trois écarts négatifs : −0,35 / −0,48 /
−0,58 point. Leurs intervalles bootstrap mensuels traversent zéro ; les bornes
basses sont négatives. Aucun des cinq facteurs ne passe le critère annoncé.

Exemple de non-stabilité : sur le développement disponible, le momentum
relatif négatif choisit SL5, le positif REFERENCE. Sur 2026, les meilleurs
profils **observés après coup** sont respectivement HOLD15 et TRAIL20. Les
constater maintenant ne permet pas de les choisir causalement dans le test.

Le régime a bien changé de relation avec les profils, mais il ne suffit pas
à sélectionner la bonne combinaison avec la règle testée. Les états SLIDE
(trois cas 2026) et REBOUND (deux cas 2025, aucun en 2026 qualifié) ne supportent
pas une conclusion robuste. Ne pas bâtir un arbre fin à partir de ces nombres.

### Contrôles effectués

**84 tests ciblés passent**, dont 21 propres à l'audit et à sa reconstruction,
avec les tests du contrat partagé et du backtest intraday. Rapport :
`artifacts/tmp/winner-context-final-20261021.xml`.

Un calcul scalaire séparé, sans utiliser les fonctions de sorties communes,
reproduit **2 448 chemins profil/frais** (204 × 6 × 2), leurs motifs et dates de
sortie. Erreur maximale de rendement : **5,69 × 10⁻¹⁴ point**. Les 204 déclenchements
d'entrée, maturités, absence de chevauchement des 169 observations et choix
fondés seulement sur les 84 labels 2025 sont vérifiés.
`completion-audit.json` est `PASS_SCALAR_EXITS_AND_TEMPORAL_CHOICES`.
Même assistant, pas revue humaine indépendante.

Les 437 lignes macro et 72 lignes de secteur actuel sont archivées pour
traçabilité, **pas testées comme prédicteurs PIT**. Le bilan ne porte donc pas
sur toutes les interactions possibles régime/macro/secteur, ni sur un modèle
multivarié qui n'a pas été entraîné.

## Décision et borne de ce GO

Il existe quelque chose à gagner **si l'on savait choisir avec le recul**,
mais pas de moyen confirmé ici de choisir avant l'entrée. **Aucun modèle
supplémentaire entraîné, ni profil dynamique promu.** Aucune relance de la
grille pour adapter les seuils à ces pertes.

L'audit demandé est clos sur ce résultat, et non laissé indéfiniment en cours.
Un autre GO pourrait étudier une information différente réellement qualifiée,
ou un benchmark multivarié explicitement exploratoire ; il ne faudrait pas
présenter les mêmes 84/74 observations déjà vues comme un nouveau holdout.
Une comparaison de portefeuille nécessiterait toujours le raccordement du
sélecteur au sizing, cash, frais, risque et chemins de réinvestissement.
