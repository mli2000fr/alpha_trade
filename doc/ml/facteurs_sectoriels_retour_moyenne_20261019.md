# Facteurs sectoriels — comparaison de retour à la moyenne contre SPY

## Objet

GO pour tester en priorité la version sectorielle, à la suite de
[l'essai mono-facteur SPY](methodes_professionnelles_et_test_residuel_20261019.md).
Ni un nouveau modèle Oracle, ni un test PCA : un facteur ETF sectoriel par titre
remplace SPY dans le même modèle de retour à la moyenne.

Les années2024–2026 ont déjà été explorées. Ce test ne devient pas un nouveau
holdout vierge et ne certifie pas une méthode institutionnelle complète.

## Données effectivement disponibles et lecture seule

Les onze historiques sont déjà dans `alpha_trade.stock_bars_daily`.
Une extraction READ ONLY/REPEATABLE READ, terminée par ROLLBACK, a figé
**10 329 lignes : 939 séances par ETF**, du3 janvier2023 au30 septembre2026.
Pas de téléchargement fournisseur ni d'écriture SQL.

| Groupe sectoriel de recherche | ETF | Symboles raccordés |
|---|---|---:|
| Materials | XLB | 83 |
| Communication Services | XLC | 78 |
| Energy | XLE | 113 |
| Financials | XLF | 340 |
| Industrials | XLI | 285 |
| Information Technology | XLK | 158 |
| Consumer Staples | XLP | 46 |
| Real Estate | XLRE | 123 |
| Utilities | XLU | 63 |
| Health Care | XLV | 178 |
| Consumer Discretionary | XLY | 126 |

Les onze séries sont `eodhd_eod`, ajustement déclaré `split`, sans barre absente,
invalide ou synthétique sur ce calendrier. Aucun mouvement ajusté close/close
ou open/close précédent n'atteint le seuil d'alerte fixé à20 %. Ce contrôle ne
certifie pas indépendamment tous les ajustements et dividendes.

Les OHLC sont mis sur la même base avec `adj_close/close`. Aucun facteur de split
n'est inventé, aucun IEX ou Yahoo n'est utilisé comme secours. Le champ local
`instrument_id=ETF_SYMBOL:<ticker>` est explicitement une clé de recherche,
pas un identifiant canonique SQL obtenu ou fabriqué.

Sources de raccordement :

- [State Street — les onze ETF sectoriels](https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs),
  pour les correspondances groupe/ETF, pas pour télécharger les prix ;
- [MSCI — méthodologie GICS2024](https://www.msci.com/indexes/documents/methodology/0_MSCI_Global_Industry_Classification_Standard_GICS_Methodology_20240801.pdf),
  pour le rattachement des libellés Industrial Conglomerates et Transportation
  Infrastructure aux Industrials ;
- mapping courant déjà archivé le7 octobre2026, et fonction de regroupement
  existante `modelFactory.cross_sectional._map_to_gics_sector`, empreintes figées.

## Qualification des correspondances : **proxy courant, non PIT**

Le champ appelé `sector` dans l'archive correspond souvent à un libellé
d'industrie fournisseur, pas directement à l'un des onze secteurs GICS.
Le mapping est donc un **proxy de recherche**, non une certification GICS
historique titre par titre. Les changements anciens de classification et les
changements d'activité ne sont pas reconstruits.

Sur les1 790 symboles du fichier tradable figé :

- **1 593 raccordés** à un ETF ;
- **195 exclus** pour catégories ambiguës : Retail, Consumer Products,
  Communications, Building, Construction, Distributors, Packaging ;
- BAR exclu : Commodities Focused n'est pas un secteur actions raccordable ici ;
- PHYS exclu : classification absente dans l'archive.

Pas de correction individuelle de titre après observation des rendements. Les
deux regroupements industriels explicitement ajoutés restent dans ce script de
recherche seulement ; le mapping de production n'a pas été modifié.

Les secteurs américains de grandes capitalisations sont par ailleurs des
proxies imparfaits pour les petites capitalisations et les ADR étrangers.
Il n'est pas prétendu que tous les1593 raccordements sont des appartenances
historiques officiellement vérifiées.

## Comparaison figée

Deux bras, **sur les mêmes1593 titres** :

1. SPY, référence recalculée avec les mêmes données et fonctions que l'essai parent ;
2. ETF sectoriel assigné, sans choix de l'ETF donnant le meilleur backtest.

Même Oracle H10 TOP10 figé à J pour le sous-périmètre TOP10, mêmes prix actions,
mêmes dates de signaux2024–2026 jusqu'au1er septembre2026. Les titres exclus ne
sont jamais remplacés par les rangs11 et suivants.

Règles inchangées : OLS/OU sur60 rendements, bêta dans]0;3], temps de relaxation
<30 séances, entrée s<−1,25 LONG titre/SHORT facteur et s>1,25 SHORT titre/LONG
facteur au prochain open. Retour vers±0,5, modèle invalidé ou perte brute de
paire observée au close≤−5 % : sortie des deux jambes au prochain open.
Échéance au plus dix séances complètes, puis openJ+11 ; pas de TP ou trailing.
Le risque quotidien n'est **pas** un stop intraday garanti.

Exposition brute initiale d'une paire=1, bêta et quantités fixés à l'entrée.
Une exposition brute identique ne garantit pas une volatilité identique entre
les bras : leur bêta estimé et la part de capital allouée au titre diffèrent.
8bps par montant exécuté à chacune des deux jambes, stress20bps, emprunt
hypothétique0,3 % annuel sur jours calendaires. Les coûts de couverture ne
sont pas gratuits. Pas de marge réelle, locate ou cashflows de dividendes
indépendamment certifiés.

### Population comparable, signaux distincts

À J, le support passé exige les61 séances stables et valides du titre, de SPY
**et** de l'ETF sectoriel, et le filtre de liquidité du parent. Chaque bras
calcule ensuite son propre score, son propre bêta et son éventuel signal.
Le suivi quotidien utilise son facteur propre, pas les états futurs de l'autre bras.

Le contrôle de qualité futur exige, identiquement pour les deux bras, les prix
titre/SPY/secteur de J à J+11. Une inconnue n'est ni un rendement nul ni un
motif de remplacer le titre. Les épisodes sans chevauchement sont choisis
avant ce contrôle, avec blocage du symbole jusqu'à la fenêtre complète.

Les occasions déclenchées restent différentes : comparer les deux moyennes
n'est pas une expérience causale à titres/trades identiques. Le supplément
à poids égal par date n'utilise que les dates avec des entrées dans les deux
bras ; les dates manquantes ne sont pas remplies à zéro.

Les critères du parent restent figés : effectif≥100, intervalle95 % positif
par occasion et par date, coûts stressés et concentration dans les deux
années2025/2026. Pour annoncer une amélioration sectorielle, exiger en plus
un intervalle positif du supplément sectoriel−SPY dans les deux années.
Même un passage resterait limité à la recherche, compte tenu du non-PIT.

## Résultats

Replay terminé : **`NO_ROBUST_SECTOR_IMPROVEMENT`**. Les deux critères de
rentabilité absolue et d'amélioration contre SPY échouent sur les confirmations
2025 et2026. Aucun paramètre n'a été réajusté après lecture des résultats.

### Univers retenu : 1 593 symboles, épisodes sans chevauchement

Moyennes nettes par **exposition brute initiale de paire**, pas des rendements
annuels de capital. Les deux bras déclenchent des occasions différentes.

| Année | SPY : occasions | SPY : net moyen | Secteur : occasions | Secteur : net moyen |
|---|---:|---:|---:|---:|
| 2024 | 13 222 | −0,046 % | 13 477 | **−0,068 %** |
| 2025 | 13 082 | +0,001 % | 13 853 | **−0,126 %** |
| 2026* | 7 610 | −0,148 % | 8 869 | **−0,042 %** |

*Signaux jusqu'au1er septembre2026, prix de suivi jusqu'au30 septembre.*

La version sectorielle réduit la perte moyenne2026, mais dégrade2024–2025.
En2025, le supplément par date commune vaut−0,104 point, IC95
**[−0,178 ; −0,028] point**. En2026, il vaut+0,089 point, IC95
**[−0,056 ; +0,212] point** : pas d'amélioration transversale démontrée.

Les gagnants nets sectoriels représentent52,16/51,99/53,73 % des épisodes
en2024/2025/2026, mais les profits moyens ne compensent pas les pertes et les
frais. Avec20bps par montant exécuté, moyennes sectorielles
**−0,308/−0,367/−0,282 %**. Ce ne sont pas des taux garantis du courtier.

### Sous-périmètre TOP10 Oracle amplitude H10

| Année | SPY : occasions | SPY : net moyen | Secteur : occasions | Secteur : net moyen | Secteur : gagnantes |
|---|---:|---:|---:|---:|---:|
| 2024 | 130 | +0,655 % | 129 | **+0,222 %** | 51,94 % |
| 2025 | 76 | +0,865 % | 99 | **+0,784 %** | 57,58 % |
| 2026* | 40 | −0,105 % | 87 | **+0,333 %** | 50,57 % |

**Point encourageant, mais exploratoire :** la version sectorielle est positive
en moyenne dans les trois années, et2026 passe de négatif à positif par rapport
au témoin SPY. Elle reste moins bonne en moyenne en2024 et2025 et les intervalles
sur sa propre moyenne incluent zéro dans chacune des trois années :

- 2024 : **[−0,518 ; +0,890] %** ;
- 2025 : **[−0,324 ; +2,485] %** ;
- 2026 : **[−0,600 ; +1,377] %**.

Les vingt meilleurs gagnants portent62,56/69,41/71,67 % des contributions
positives ; les critères d'effectif et de concentration ne sont pas satisfaits
sur les deux confirmations. Sous stress20bps, net moyen TOP10 secteur
**−0,020/+0,542/+0,091 %** : la positivité2024 n'est pas robuste aux coûts.

Comparaison à poids égal sur les seules dates communes aux bras :

| Année | Dates communes | Secteur−SPY | IC95 du supplément |
|---|---:|---:|---|
| 2024 | 63 | −0,641 point | [−1,439 ; +0,150] point |
| 2025 | 42 | +0,120 point | [−0,752 ; +1,102] point |
| 2026 | 23 | +1,215 point | [−0,643 ; +3,430] points |

Cette ventilation n'est pas une comparaison à positions identiques : les titres,
sens, bêtas et sorties peuvent différer, même un jour commun. Le supplément2026
ne permet pas à lui seul de choisir le secteur après coup comme gagnant certain.

### LONG et SHORT, sans sélectionner le meilleur après résultat

TOP10 secteur, toujours après frais hypothétiques :

| Sens du titre | 2024 | 2025 | 2026* |
|---|---|---|---|
| LONG / SHORT ETF | +0,610 % —94 occasions | +1,292 % —57 | +0,261 % —54 |
| SHORT / LONG ETF | −0,819 % —35 occasions | +0,095 % —42 | +0,451 % —33 |

Les résultats LONG2025/2026 restent incertains et2024 SHORT est négatif.
Cela ne démontre ni un prédicteur D1/D10, ni un filtre LONG/SHORT robuste à
mettre derrière l'Oracle en production.

Le contrôle même paire conservée dix séances vaut+0,829/+0,841/−0,122 % sur
TOP10 secteur : la sortie quotidienne aide2026 mais coupe des profits2024.
Il n'est pas remplacé a posteriori par une combinaison des meilleures politiques
de chaque année.

### Couverture des signaux, inconnues conservées

369 313 candidats au total sur les deux bras/périmètres, dont **368 937 qualifiés**.
376 inconnus ne sont ni remplacés ni comptés comme perdants/gagnants :

- secteur : 15 en2025,205 en2026 ;
- SPY : un en2024,deux en2025,153 en2026 ;
- toutes les occasions TOP10 déclenchées sont qualifiées dans les deux bras.

Les motifs sont des prix actions absents/invalides et les réserves de base de
prix héritées, pas des lacunes des ETF. Toutes les occasions, motifs, adhésions
et sorties sont archivés. Chaque bras conserve son adhésion indépendante
antérieure à l'inspection de la qualité future.

### Vérifications

**143 tests passent**, dont28 nouveaux : mapping, exclusions ambiguës,
sources interdites ou inconnues, historique non rempli, alertes d'ajustement,
support causal et dates absentes jamais assimilées à un rendement nul.
Ce groupe ciblé ne prétend pas satisfaire le seuil de couverture de tout le projet.

La référence SPY reproduit à l'identique les résultats du parent sur les symboles
retenus : **352 196 lignes, écart maximal net=0**, mêmes dates de sortie et
mêmes adhésions sans chevauchement. Le certificat et les empreintes des deux
fichiers sont dans `spy-parent-parity.json`. Ce contrôle empêche d'attribuer au
secteur une différence issue d'une modification du moteur de référence.

L'audit final est **terminé : `PASS_EXPLORATORY_SECTOR_PROXY_ONLY`**.
Il vérifie les **737 874 lignes de sorties**, les **369 313 candidats**,
**6 372 estimations OLS/OU scalaires** et **100 contrôles par préfixe historique**,
ainsi que les coûts des deux jambes, les dates, les exclusions et les empreintes.
Les séries SPY des 1 593 titres sont également reproduites. Le certificat est
conservé dans `final-audit.json` ; il confirme les calculs, **pas la rentabilité**.
Cette seconde implémentation par le même assistant ne constitue pas une revue
humaine indépendante. Les réserves non PIT et de qualification économique restent
entières.

## Décision

Les facteurs ETF sectoriels sont **disponibles, raccordés et effectivement
testés**. Ils apportent un résultat TOP10 plus intéressant en2026 que SPY seul,
mais sans confirmation statistique et avec des classifications non PIT.

**Conserver comme piste de recherche, sans promotion de cette règle.** Ni les
trois moyennes TOP10 positives ni le seul millésime2026 ne justifient une
intégration live, un rendement annuel annoncé ou une nouvelle optimisation de
TP/SL après résultats. Les réserves de cashflows, emprunt, risque spécifique et
capital du parent restent applicables.

**PCA non testée dans ce run.** Elle demeure une approche distincte, calculable
avec des fenêtres historiques uniquement, à qualifier dans son propre protocole.

Suite sur GO distinct : [PCA de trois facteurs ETF, même date](pca_etf_retour_moyenne_20261019.md).
Ce nouveau test ne modifie ni les résultats ni les empreintes du présent run.

## Artefacts et reproduction

Dossier : `artifacts/research/us_sector_residual_reversion/20261019-v1/`.
Protocole, mapping complet avec motifs, ETF bruts, contrôles qualité, support
commun, scores, candidats y compris non qualifiés, sorties, bilans et empreintes
sont conservés. Aucun modèle, batch, univers de production ou ordre modifié.

```powershell
python -m scripts.research.us_sector_residual_reversion --phase prepare --output <nouveau-dossier>
python -m scripts.research.us_sector_residual_reversion --phase snapshot --output <même-dossier>
python -m scripts.research.us_sector_residual_reversion --phase build --output <même-dossier>
python -m scripts.research.us_sector_residual_reversion --phase summarize --output <même-dossier>
python -m scripts.research.us_sector_residual_reversion_audit --output <même-dossier>
```

Seule la phase snapshot lit la base existante, sans écriture. Les autres calculs
sont offline. Les résultats sont **par exposition brute d'occasion**, pas des
rendements annuels de portefeuille ni une parité d'exécution broker.
