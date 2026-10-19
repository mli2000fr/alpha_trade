# TOP10 confirmé à J+2 — audit TP/SL fixes et ATR, entrée J+3

## Bilan

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** Oui, le TP/SL influence les
résultats ; non, changer uniquement ces protections ne suffit pas à qualifier
la règle de confirmation de direction. Les trois variantes ATR améliorent
certains LONG, mais chacune conserve au moins une année perdante. Les dix-neuf
configurations SHORT et les dix-neuf profils communs LONG/SHORT sont négatifs
dans chacune des trois années sur les occasions répétées.

Le meilleur réglage LONG **choisi uniquement sur 2024** est TP10/SL10. Il perd
encore en 2025 et son contrôle sans chevauchement est négatif en 2025/2026.
Un autre réglage, TP15/SL7, paraît très légèrement positif sur les trois moyennes
annuelles, mais ce constat est **rétrospectif après lecture de la grille**, pas
un choix validé : seulement +0,063 % en 2025 et +0,013 % en 2026, cette dernière
année devenant −0,783 % sans chevauchement. Pas de configuration robuste à
promouvoir au live ni d'« optimum » global démontré.

## Contrat, périmètre et sélection des paramètres

Deux demandes successives : auditer TP/SL, puis ajouter des protections ATR.
Les deux familles sont figées dans le même protocole avant le calcul des résultats.

- Même TOP10 Oracle amplitude H10 à J, mêmes modèles annuels de recherche.
- Même règle : quatre clôtures ajustées J−1<J<J+1<J+2 pour LONG,
  strictement décroissantes pour SHORT ; sinon abstention. Aucune nouvelle
  sélection du sens par modèle, aucun reclassement ou remplacement.
- Entrée open J+3 après confirmation, dix séances entrée comprise, expiration
  close J+12 si aucun seuil ; sans trailing.
- **16 profils fixes** : TP5/10/15/20 % × SL3/5/7/10 %. Référence TP10/SL5
  reproduite ligne par ligne sur les résultats du test précédent.
- **3 profils ATR** : stop à 1 / 1,5 / 2 × ATR20, TP à deux fois la distance
  de stop, bornes SL3–10 % et donc TP6–20 %.
- Frais supposés 8 bps par jambe, emprunt SHORT 0,3 %/an, stop gap à l'open,
  TP au prix limite, collision stop-first sauf ouverture départageant les seuils.
- Paramètres choisis **sur 2024 seulement**, pour LONG, SHORT et un profil commun
  aux deux sens : maximum de moyenne nette par occasion. Égalité départagée
  par stop fixe/minimum ATR le plus petit, puis TP fixe ou nom de profil.
  Le choix est enregistré avant le calcul des agrégats 2025/2026. Les paramètres
  négatifs « les moins mauvais » restent explicitement non exploitables.
- 2025/2026 : vérification figée sans changer le choix 2024. Les années ont déjà
  été examinées dans d'autres expériences : ce n'est **pas un holdout vierge**.
  Pas de choix fondé sur la moyenne des trois années ou le meilleur résultat2026.
- Pas de capital, sizing, levier, nombre de positions, locates, marge réelle
  ou drawdown de portefeuille simulé. Les résultats sont par occasion, pas
  des rendements annuels composés.

## Comment l'ATR est utilisé sans anticiper

ATR20 = moyenne simple des vingt true ranges, selon la définition utilisée par
`common/oracle_atr.py`, et non un lissage de Wilder. Les prix sont sur la base
ajustée de recherche déjà qualifiée. Les true ranges utilisent les high/low du
jour et la clôture précédente.

**Seulement les données jusqu'à la clôture J+2** : vingt TR nécessitent vingt
et une barres consécutives valides, soit J−18 à J+2. Historique source/identité/
ajustement stable, aucun remplissage ni rupture connue admis. Tous les profils,
y compris fixes, utilisent la même population qualifiée pour comparer équitablement
ATR et fixe. Les titres non qualifiés ne sont pas remplacés dans le TOP10.

À l'entrée J+3, avec le prix d'open/fill simulé connu, calcul :

```text
SL_pct = clip(k × ATR20_connu_à_J+2 / prix_entrée_J+3, 0.03, 0.10)
TP_pct = 2 × SL_pct
```

Ces niveaux sont ensuite **fixes pour la position**. Ce n'est ni un stop recalculé
chaque soir, ni un trailing stop, ni un modèle apprenant des protections dynamiques.
Les caps font partie de cette expérience ; aucune valeur de production n'est changée.

Dans le TOP10 observé, l'ATR est déjà élevé : le SL atteint son plafond10 %
dans 11,96 % des cas à 1×ATR, 57,32 % à 1,5×ATR et 90,19 % à 2×ATR
(ensemble des couples, avant filtre de confirmation). La dernière variante est
donc souvent simplement TP20/SL10, pas une personnalisation très fine.

## LONG : résultats principaux

Moyenne nette par occasion ; 232/255/221 LONG confirmés en 2024/2025/2026.
2026 limité aux **signaux jusqu'au 1er septembre**, comme les expériences sources.

| Protection | 2024 | 2025 | 2026 | Statut de lecture |
| --- | ---: | ---: | ---: | --- |
| TP10 / SL5 | +0,915 % | −0,756 % | −0,415 % | Référence initiale |
| TP10 / SL10 | +1,699 % | −0,764 % | +0,161 % | Choisi sur 2024 uniquement |
| TP15 / SL10 | +1,432 % | −0,014 % | +0,727 % | Comparaison descriptive, pas champion choisi |
| TP15 / SL7 | +0,840 % | +0,063 % | +0,013 % | Petit résultat apparent découvert rétrospectivement |
| ATR1×, TP2×distanceSL | +1,070 % | −0,320 % | +0,089 % | SL borné3–10 % |
| ATR1,5×, TP2×distanceSL | +0,524 % | −0,155 % | +0,441 % | SL borné3–10 % |
| ATR2×, TP2×distanceSL | +0,717 % | −0,198 % | +0,693 % | SL borné3–10 % |

Le taux gagnant du TP10/SL10 devient **57,33/49,02/52,04 %**, contre
43,10/32,16/32,13 % en TP10/SL5, sans résoudre la rentabilité en 2025. Augmenter
le taux gagnant ne suffit pas : les pertes deviennent aussi plus grandes et
les gaps ne sont pas plafonnés au stop. Pire perte LONG du TP10/SL10 :
−14,22/−36,68/−19,10 % selon l'année, sur les prix d'archive.

### Contrôle sans chevauchement

Même espacement par symbole/sens que précédemment : prochaine entrée seulement
après la fin de la fenêtre de dix séances, même si le TP arrive plus tôt.
128/143/108 épisodes LONG. Pas un portefeuille réellement dédupliqué entre sens.

| Protection LONG | 2024 | 2025 | 2026 |
| --- | ---: | ---: | ---: |
| TP10/SL5 | +0,700 % | −0,405 % | −0,732 % |
| TP10/SL10, choix 2024 | +1,518 % | −0,390 % | −0,627 % |
| TP15/SL7, rétrospectif | +1,018 % | +0,370 % | −0,783 % |
| ATR1× | +1,176 % | +0,337 % | −0,444 % |
| ATR1,5× | +0,797 % | +0,412 % | −0,453 % |
| ATR2× | +0,879 % | +0,376 % | −0,104 % |

Les trois ATR et le TP15/SL7 ne restent donc pas positifs transversalement avec
ce contrôle. Les intervalles descriptifs appariés par blocs du supplément des
ATR et du TP15/SL7 face à TP10/SL5 comprennent zéro pour chaque année LONG.
Une moyenne légèrement positive après recherche sur19 profils ne suffit pas
à établir un avantage prédictif, surtout sur ces périodes déjà vues.

## SHORT et combinaison des sens

Les 338/304/188 SHORT confirmés restent négatifs pour **tous les dix-neuf profils**.
La meilleure moyenne2024, TP5/SL5, est déjà négative ; il ne s'agit donc pas
d'un candidat « gagnant » à autoriser. Les ATR avec stops plus larges aggravent
fortement le bras SHORT2026.

| Protection SHORT | 2024 | 2025 | 2026 |
| --- | ---: | ---: | ---: |
| TP10/SL5, référence | −1,296 % | −1,301 % | −2,034 % |
| TP5/SL5, moins mauvais en2024 | −0,458 % | −1,230 % | −1,090 % |
| ATR1× | −2,020 % | −1,545 % | −4,088 % |
| ATR1,5× | −2,464 % | −1,789 % | −4,786 % |
| ATR2× | −2,421 % | −1,888 % | −4,856 % |

Profil commun choisi2024 : TP5/SL7, combiné
**−0,146/−0,882/−1,044 %**. Ses taux gagnants58,77/54,56/52,08 % n'en font pas
une stratégie rentable : TP plus petit que SL et pertes/coûts comptent aussi.

Contrôle protections distinctes choisies sur2024, LONG TP10/SL10 et SHORT TP5/SL5,
sans désactiver une branche après observation des années test : combiné
**+0,420/−1,017/−0,414 %**, sans chevauchement **+0,632/−0,697/−0,432 %**.
Ce mélange ne fournit pas non plus une solution transversale.

## Contrôles, artefacts et décision

Même sélection d'origine : **6 690 couples**, 669 séances, 161 symboles distincts ;
tous ont l'historique ATR valide, donc aucune exclusion nouvelle de cohorte.
Les 570/559/409 occasions confirmées sont inchangées entre les19 protections.
13 380 issues de référence reproduites exactement ; **254 220 sorties**
(19 × 6 690 × 2 sens) vérifiées par un calcul scalaire séparé. Les ATR sont
recalculés en scalaire, les caps et ratios contrôlés, de même que les mêmes
clés, les coûts, les choix2024 et les métriques de chaque profil.

**133 tests passent**, dont quinze propres à la grille/ATR : disponibilité J+2,
sources/historique, bornes, parité exacte du moteur à barrières variables avec
le contrat fixe sur seize couples dans les deux sens, sélection indépendante
des métriques2025/2026. Audit `PASS_EXPLORATORY_ONLY`.

Réserves héritées : prix ajustés/OST partiellement qualifiés, univers survivant,
historique déjà exploré, PIT complet des features/fills non certifié. Les
protections ne transforment pas ces réserves en preuves d'exécution réelle.

Dossier : `artifacts/research/us_top10_confirmation_protection_grid/20261019-v1/` :
`protocol.json`, `cohort.parquet`, `parts/`, `selected-on-2024.json`,
`grid-comparison.csv` (tous les19 profils et les sept bras),
`frozen-validation.csv`, `report.json`, `atr-distance-audit.json`,
`final-audit.json`, `progress.json`.

Scripts `us_top10_confirmation_protection_grid` et son `_audit` sous
`scripts/research/`. Aucun entraînement, SQL, appel fournisseur/LLM, ordre,
configuration, modèle ou batch de production modifié. Pas de nouveau balayage
automatique ni de changement live. **Ne pas retenir un réglage de production
sur cette seule grille ; le TP/SL n'a pas réparé la confirmation de direction.**
