# P0f — Entraînement Oracle sur univers quotidien PIT dynamique

## Décision expérimentale

P0f intègre le contrat P0b dans le vrai pipeline d'entraînement Oracle. Le but
est de mesurer si l'Oracle mutualisé conserve davantage d'amplitude OOF quand
ses labels et ses rangs de features sont calculés sur la population large
réellement admissible à chaque date.

Ce mode est **opt-in, Oracle-only et non servable**. Il ne remplace ni le mode
statique historique, ni un batch bundle. Une promotion vers la prédiction et le
backtest nécessitera d'abord que P0f passe les gates OOF, puis qu'un calcul
d'admission identique soit ajouté au serving.

## Contrat d'admission à la date J

La population candidate vient du fichier d'univers sélectionné dans l'IHM. Pour
chaque symbole et chaque date, l'admission exige :

- au moins 504 barres réelles observées jusqu'à J ;
- une barre réelle à J (`is_filled != 1`) ;
- clôture ajustée, ou clôture de secours, supérieure ou égale à 10 $ ;
- volume moyen trailing 20 séances supérieur ou égal à 100 000 actions ;
- dollar-volume moyen trailing 20 séances supérieur ou égal à 10 M$ ;
- part de barres remplies trailing 252 séances inférieure ou égale à 2 %.

Les contrôles de qualité du label restent séparés : barre réelle à J+20,
cohérence de source, absence de rupture d'identité connue et quarantaine des
sauts de prix inexpliqués. Une invalidité future ne retire pas rétroactivement
le titre de la population observable à J utilisée pour les rangs de features.

## Ordre causal des calculs

```text
fichier candidat large
        |
        v
barres connues jusqu'à J -> gates P0b à J -> univers admis U(J)
                                            |              |
                                            |              +-> rangs de features dans U(J)
                                            v
                                  rendement réel J -> J+20
                                            |
                                            v
                             déciles + cible D1 union D10 dans U(J)
                                            |
                                            v
                              Walk-Forward Oracle O0 strictement OOS
```

L'ordre est essentiel. Filtrer après le calcul des percentiles produirait des
features incompatibles avec les labels dynamiques. Utiliser uniquement les
labels futurs valides pour définir U(J) introduirait une fuite ; le code garde
donc deux contrats séparés : admission observable et exploitabilité du label.

## Protection mémoire

P0b représente environ 3,93 millions de lignes. Le chemin P0f :

- convertit les features flottantes en `float32` ;
- conserve seulement les bornes de dates des folds ;
- matérialise train/validation/test un fold à la fois ;
- évite de concaténer toutes les matrices de test uniquement pour les logs.

Le découpage temporel reste équivalent au splitter historique : fenêtre
expansive, purge H20, validation distincte pour l'early stopping, test OOS et
garde `oracle_available_date`.

## Lancement depuis l'IHM

Dans **Pipeline > entraînement ML** :

1. sélectionner `univers_filtred.txt` comme univers ;
2. cocher **Entraîner aussi le modèle Oracle Extreme** ;
3. choisir `oracle.json` dans **Features du modèle Oracle Extreme** ;
4. choisir **PIT dynamique quotidien — gates P0b (expérience P0f)** ;
5. vérifier que **Oracle Extreme ONLY** est coché et grisé ;
6. conserver H20, le Walk-Forward `504 / 126 / 126 / 126 / 12`, la période
   `2016-01-01` à `2025-12-31`, puis lancer.

Le fichier candidat large reste une reconstruction Grade B : titres connus
aujourd'hui, sans historique certifié de capitalisation, pays, type d'actif ni
couverture complète des titres radiés.

## Équivalent CLI

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory --mode train --oracle-model-only --oracle-universe-mode pit_dynamic_bars --standalone-oracle-feature-profile oracle.json --symbol-source universe-file:univers_filtred.txt --training-start-date 2016-01-01 --training-end-date 2025-12-31 --forecast-horizon 20 --feature-set expert --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --artifacts-dir artifacts/models --max-workers 4 --log-level INFO --comment "P0f Oracle univers PIT dynamique large"
```

Les options génériques de modèle affichées par l'IHM peuvent rester présentes ;
l'Oracle O0 utilise son propre entraîneur LightGBM et le profil `oracle.json`.

## Gates de décision préfixés

La comparaison doit reprendre P0e sur les dates OOF communes : précision et
rappel TOP10/TOP20, lift et rétention d'amplitude, AUC, monotonie, semestres et
bootstrap mobile par blocs de 21 séances. Aucun seuil ne doit être choisi sur
2026H1.

P0f n'est promu que si les métriques TOP20 et l'amplitude gagnent de manière
stable, sans dégradation concentrée dans la majorité des semestres. Sinon, la
conclusion sera que l'élargissement rend la cible plus fidèle mais plus difficile
à prédire ; le modèle restera alors un résultat de recherche.

## Traçabilité produite

Le résultat Oracle et `feature_profile.json` enregistrent
`oracle_universe_mode`, les seuils et statistiques de couverture dynamiques.
Pour P0f, `serving_ready=false` est explicite afin d'interdire une utilisation
accidentelle en prédiction ou en bundle avant adaptation du serving.

## Incident technique initial

Le batch `model-factory-20260908230455-8f1ede` a échoué avant la construction
des labels et avant tout entraînement. L'admission dynamique avait correctement
trouvé 3 926 619 lignes et 2 493 symboles, mais le chargeur de prix reconstruisait
sa liste depuis le conteneur statique, vide dans ce mode. Le correctif dérive
désormais les symboles de l'univers quotidien admis et possède un test dédié.
Ce batch ne fournit aucune mesure P0f et doit être ignoré dans les comparaisons.

## Résultat du premier entraînement valide

Batch : `model-factory-20260908231513-4d6c17`.

Le run est techniquement complet :

- 3 926 619 lignes d'univers/labels écrites ;
- 3 926 579 labels valides et 40 invalides ;
- 2 403 symboles présents dans les prédictions OOS ;
- 12 champions Walk-Forward ;
- 2 427 186 prédictions OOS ;
- fenêtre OOS du 2018-07-05 au 2024-07-09.

Les 40 exclusions sont conformes au contrat qualité : 20 sorties futures
absentes et 20 sauts de prix extrêmes non ajustés.

### Qualité absolue P0f

| Mesure | P0f dynamique |
|---|---:|
| AUC | 0,7569 |
| précision TOP10 | 50,52 % |
| rappel TOP10 | 25,32 % |
| précision TOP20 | 44,04 % |
| rappel TOP20 | 44,08 % |
| lift amplitude TOP10 | 1,908 |
| lift amplitude TOP20 | 1,685 |
| rétention amplitude extrême TOP20 | 76,34 % |
| monotonie des déciles | 1,000 |

Le sommet du classement reste symétrique : 25,5 % de D1 et 25,1 % de D10
parmi les 10 % de probabilités les plus élevées. P0f améliore donc la détection
de l'amplitude ; il ne résout pas la direction D1/D10.

### Comparaison appariée avec l'ancien 400

Sur 1 512 dates OOS communes, au TOP20 :

| Delta P0f − ancien 400 | Moyenne | IC 95 % blocs de 21 séances |
|---|---:|---:|
| précision | +3,53 pt | [+2,81 ; +4,29] pt |
| rappel | +2,00 pt | [+1,22 ; +2,80] pt |
| lift amplitude | +0,074 | [+0,044 ; +0,105] |
| rétention amplitude extrême | +2,88 pt | [+0,29 ; +5,08] pt |

P0f gagne 13/13 semestres observés en AUC et précision TOP20, 11/13 en lift
d'amplitude TOP20 et 12/13 en rétention d'amplitude.

### Comparaison appariée avec le Balanced 400

Sur les mêmes 1 512 dates :

| Delta P0f − Balanced 400 | Moyenne | IC 95 % blocs de 21 séances |
|---|---:|---:|
| précision TOP20 | +4,69 pt | [+4,00 ; +5,30] pt |
| rappel TOP20 | +4,43 pt | [+3,69 ; +5,12] pt |
| lift amplitude TOP20 | +0,156 | [+0,129 ; +0,179] |
| rétention amplitude extrême | +4,49 pt | [+3,63 ; +5,33] pt |

### Verdict intermédiaire

P0f passe la comparaison OOF sur sa fenêtre disponible. C'est le premier
univers alternatif qui améliore simultanément la fidélité historique et la
détection d'amplitude du modèle Oracle. L'ancien 400 reste un témoin historique
et le Balanced 400 un univers de smoke tests ; aucun des deux n'est le candidat
principal pour un futur Oracle de production.

La promotion n'était toutefois pas encore prononcée à ce stade :
`wf-max-splits=12` arrêtait l'OOS en juillet 2024. Une confirmation identique
avec davantage de folds était requise afin de couvrir fin 2024 et 2025 sans
sélectionner un seuil ni toucher aux features.

## Confirmation temporelle à 14 folds

Batch : `model-factory-20260909051302-323684`.

Le plafond demandé était `wf-max-splits=15`, mais le contrat exige des fenêtres
complètes de 126 séances pour la validation et le test. Les données permettent
donc 14 folds effectifs, ce qui est le nombre attendu :

- 3 926 619 lignes d'univers/labels, dont 3 926 579 valides ;
- 14 champions Walk-Forward ;
- 2 908 295 prédictions OOS ;
- 2 475 symboles couverts ;
- 1 764 dates OOS, du 2018-07-05 au 2025-07-11.

Sur les 1 512 dates communes avec le batch 12-fold, toutes les métriques
appariées ont un delta strictement nul. Les anciennes prédictions sont donc
reproductibles ; les deux folds ajoutés prolongent réellement l'OOS sans
réécrire l'histoire.

### Qualité absolue confirmée

| Mesure | P0f 14 folds |
|---|---:|
| AUC | 0,7582 |
| précision TOP10 | 50,41 % |
| rappel TOP10 | 25,27 % |
| précision TOP20 | 44,08 % |
| rappel TOP20 | 44,12 % |
| lift amplitude TOP10 | 1,906 |
| lift amplitude TOP20 | 1,687 |
| rétention amplitude extrême TOP20 | 75,90 % |
| monotonie globale des déciles | 1,000 |

### Comparaison appariée confirmée avec l'ancien 400

Sur les 1 764 dates OOS communes, au TOP20 :

| Delta P0f − ancien 400 | Moyenne | IC 95 % blocs de 21 séances |
|---|---:|---:|
| précision | +4,08 pt | [+3,33 ; +4,74] pt |
| rappel | +2,74 pt | [+1,95 ; +3,45] pt |
| lift amplitude | +0,095 | [+0,063 ; +0,122] |
| rétention amplitude extrême | +3,23 pt | [+2,20 ; +4,24] pt |

Le gain se maintient sur la période ajoutée. En 2025H1, P0f atteint une AUC de
0,7598, une précision TOP20 de 44,16 % et un lift amplitude TOP20 de 1,712,
contre respectivement 0,6739, 36,44 % et 1,435 pour l'ancien 400. Les huit jours
de 2025H2 disponibles restent favorables, mais sont trop courts pour constituer
un semestre indépendant.

### Comparaison appariée confirmée avec le Balanced 400

Sur les mêmes 1 764 dates :

| Delta P0f − Balanced 400 | Moyenne | IC 95 % blocs de 21 séances |
|---|---:|---:|
| précision TOP20 | +5,13 pt | [+4,47 ; +5,73] pt |
| rappel TOP20 | +4,98 pt | [+4,23 ; +5,64] pt |
| lift amplitude TOP20 | +0,171 | [+0,147 ; +0,193] |
| rétention amplitude extrême | +4,80 pt | [+4,03 ; +5,53] pt |

### Verdict P0f

La confirmation temporelle est positive. P0f remplace les univers fixes de
400 comme contrat de recherche recommandé pour entraîner l'Oracle d'amplitude.
Ce verdict porte sur la détection des mouvements extrêmes, pas sur leur sens :
le TOP10 contient encore 25,5 % de D1 et 25,0 % de D10. La direction D1/D10
reste donc un problème séparé.

Le batch demeure `serving_ready=false`. Une promotion en production nécessite
encore l'adaptation explicite du serving à l'univers quotidien PIT et un test de
prédiction/backtest dédié ; elle ne doit pas être déduite du seul gain OOF.

Cette adaptation est ouverte exclusivement en shadow dans
[P0h — serving shadow dynamique](oracle_universe_p0h_shadow_serving.md).
