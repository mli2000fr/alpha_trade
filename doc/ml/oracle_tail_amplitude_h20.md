# Modèle global « grands mouvements » à deux parties — H20

## Protocole figé, 11 octobre 2026

Expérience distincte du ranker ordinal précédent : seuil absolu `|R H20| >= 20 %`
au lieu d’un classement relatif des rendements. Aucune recherche de seuil, aucun
modèle par symbole, aucune modification du serving ni écriture SQL.

1. Classifieur global : probabilité d’un mouvement absolu d’au moins 20 %.
2. Régression globale : amplitude absolue moyenne sur ces seuls événements.
3. Score : probabilité × amplitude conditionnelle (bornée logiquement à 20 %).

Ce score est une **contribution attendue des grands mouvements**, pas toute
l’amplitude attendue : la contribution des mouvements inférieurs à 20 % est
ignorée. Ni sens LONG/SHORT ni rendement de portefeuille n’en sont déduits.
Les probabilités brutes ne sont pas annoncées comme parfaitement calibrées.

Même pool quotidien Oracle TOP20 % ∩ ATR TOP20 %, sélectionné avant lecture des
labels. Même univers archivé nettoyé de 1 790 titres et mêmes 32 entrées numériques
que le test ordinal. Les caractéristiques propres aux titres (momentum, volatilité,
bêta, etc.) sont historiques ; pas d’identifiant symbole appris ni d’enrichissement
prospectif extrapolé dans le passé. Aucun sentiment ou consensus ajouté sans PIT.

LightGBM : 200 arbres pour chaque partie, profondeur 4, learning rate 0,03,
minimum 150 observations par feuille, seed 42, 4 threads, paramètres explicites
dans `protocol.json`. Classifieur sans pondération des classes ; régression
quadratique pour estimer une moyenne conditionnelle. Pas de tuning, calibration
sur les tests ni winsorisation du futur.

## Validation

Archives corrigées Oracle OOF : 2018–juillet 2024. Début des tests après 504
séances OOF, puis blocs de 126 séances. Apprentissage expansif ; seules les
cibles qualifiées dont la maturité précède strictement le test sont admissibles.
Minimum 480 séances matures et 1 000 événements extrêmes pour entraîner.

2025–3 septembre 2026 : les deux modèles restent figés sur l’historique antérieur,
sans apprentissage sur 2025/2026. Ces périodes et les résultats du ranker précédent
ont déjà été examinés : **pas de holdout vierge**. Second semestre 2024 absent.
Univers actuel nettoyé, pas une certification complète d’univers historique PIT.

Comparer les 10 et 20 premiers titres à l’ordre Oracle et à l’ordre ATR dans le
même pool. Pas de remplacement d’un candidat au rendement inconnu. Mesures
appariées sur les mêmes séances complètes pour les trois politiques ; compter
explicitement les couples date/N exclus.

Principales : proportion de `|R| >= 20 %` et amplitude moyenne absolue.
Secondaires : capture du label Oracle extrême, médiane, fréquence `|R| >= 50 %`.
AUC et Brier du classifieur sur tout le pool évaluable, non seulement le TOP10.
Bootstrap descriptif par blocs de 20 séances : retours H20 chevauchants.

Critère figé de suite : les deux mesures principales doivent s’améliorer contre
**les deux baselines**, dans chacune des années externes 2025 et 2026 et dans
une majorité des huit blocs historiques. Verdict séparé pour N=10 et N=20.
Même si ce critère passe : suivi de recherche seulement, pas activation live.
H20 est close J → close J+20 ; aucune simulation d’entrée, coût, SL ou TP.

## Exécution

```powershell
python -u -m scripts.research.us_oracle_tail_amplitude --threads 4 --output artifacts/research/us_amplitude_rerank/tail-two-stage-h20-20261011-v1
```

`progress.json` suit les sources puis les neuf blocs ; `done.json` permet la
reprise par bloc avec contrôle des empreintes. Ne jamais lancer deux instances
sur le même dossier. Rapport : `report.json`, `annual.parquet`, `blocks.parquet`.
Modèles et prédictions restent exclusivement dans les artefacts de recherche.

## Résultats terminés — 11 octobre 2026

Les neuf blocs ont terminé. Onze tests ciblés validés. Les neuf dates maximales
de maturité d’apprentissage précèdent strictement leur début de test ; le modèle
externe utilise 408 097 observations historiques, dont 81 193 mouvements >=20 %,
avec dernière maturité le 7 août 2024, avant le test externe du 2 janvier 2025.

TOP10, trois politiques comparées sur les mêmes séances complètes :

| Période | Séances | Fréquence >=20 % Oracle | Deux parties | Amplitude moyenne Oracle | Deux parties |
|---|---:|---:|---:|---:|---:|
| 2025 | 250 | 31,60 % | 30,88 % | 16,82 % | 16,32 % |
| 2026 jusqu’au 03/09 | 159 | 36,48 % | 34,40 % | 18,43 % | 17,56 % |

Ces fréquences portent sur **l’amplitude absolue**, pas sur le rendement LONG,
et ne sont pas la capture du label Oracle. Capture Oracle extrême secondaire :
54,28 % contre 52,44 % en 2025 ; 56,42 % contre 53,02 % en 2026.

TOP10 externe global (409 séances) contre ordre Oracle :

- fréquence >=20 % : −1,25 point ; intervalle descriptif [−2,71 ; +0,44] points ;
- amplitude moyenne : −0,64 point ; intervalle [−1,17 ; −0,14] points ;
- capture Oracle extrême : −2,44 points ;
- fréquence >=50 % : −0,39 point.

TOP20 externe (400 séances) : fréquence >=20 % −1,29 point et amplitude moyenne
−0,33 point contre Oracle. Le modèle dépasse ATR seul sur plusieurs mesures,
mais ne dépasse pas l’ordre Oracle, qui est la baseline à remplacer.

Historique juillet 2020–juillet 2024, 1 007 séances : TOP10 fréquence >=20 %
+0,67 point contre Oracle, mais amplitude moyenne −0,22 point. Les deux mesures
progressent contre les deux baselines dans six blocs sur huit (TOP20 : quatre
sur huit). L’agrégat reste influencé par les pertes d’amplitude du bloc 2020.
**L’avantage local historique ne se généralise pas sur 2025/2026.**

AUC du classifieur sur tout le pool externe évaluable : 0,594 ; Brier 0,159.
Cela indique une séparation partielle pour le seuil >=20 %, sans démontrer
une meilleure concentration TOP10, une calibration parfaite ou un gain économique.

31 couples date/N sont exclus par le contrôle de complétude commun aux trois
politiques. Les journées comparées peuvent donc différer légèrement de celles
du test ordinal antérieur : les chiffres Oracle 2026 ne doivent pas être comparés
entre rapports sans réappariement.

**Verdict figé : `NO_GO_STABLE_TAIL_RERANK` pour TOP10 et TOP20.**
Conserver l’ordre Oracle dans le pool Oracle × ATR. Ni champion, ni SQL, ni
batch modifié. Ne pas chercher maintenant un seuil ou une combinaison ajustée
sur ces échecs puis la présenter comme une confirmation indépendante.
