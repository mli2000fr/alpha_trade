# Oracle parcours — séparabilité d'un filtre d'entrée TP20 avant SL10

## Objet et statut

GO utilisateur du 14 octobre 2026, après l'audit des pertes 2024–2026.
**Étude univariée, pas un entraînement ni un nouveau backtest.**
Lancement corrigé à **00:16 Paris**, PID lanceur **38888**, dossier
`artifacts/research/us_oracle_path_entry_separability/20261014-v2`.
27 tests ciblés passent (séparabilité et audit des pertes).
**Calcul terminé à 00:18 Paris**, sources recontrôlées, verdict
`NO_STABLE_UNIVARIATE_ENTRY_SEPARATION`. Aucune feature ni stratégie promue.

## Résultat et conclusion

Les 183 colonnes ont été examinées sur trois périmètres : **549 fiches de
features/TOP**, chacune sur six périodes. **Zéro piste** ne passe les gates
de découverte/validation, dans TOP10, TOP20 ou TOP50. Pas de filtre entraîné
ou de backtest supplémentaire à partir de ce résultat.

La meilleure AUC quotidienne orientée en découverte parmi les features de
prix non communes à une date est **0,5321 sur TOP10**, **0,5259 sur TOP20**,
**0,5375 sur TOP50**. Elles restent sous le minimum figé de 0,55. L'ajustement
des comparaisons multiples n'identifie pas non plus d'association convaincante
sur TOP10 : plus petite p maxT **0,817**.

Exemples TOP10, orientation déterminée en 2018–2021 seulement ; ces exemples
sont les premiers selon découverte, **pas une sélection selon les tests** :

| Feature | AUC découverte orientée | AUC validation 2022 orientée | p maxT |
| --- | ---: | ---: | ---: |
| vol_ratio_20_60_x_bull | 0,5321 | 0,4986 | 0,817 |
| momentum_20_zscore | 0,5284 | 0,5046 | 1,000 |
| momentum_10_zscore | 0,5282 | 0,4819 | 0,994 |
| vol_ratio_20_60 | 0,5278 | 0,4659 | 0,992 |

L'orientation favorable observée dans l'ancien historique disparaît ou s'inverse
en validation. Des AUC supérieures sur une seule année récente ne changent pas
ce verdict et n'ont pas servi à choisir une nouvelle règle.

### Couverture TOP10 et fréquence de TP20

| Période | Candidats originaux | Labels évaluables après contrôles/purge | TP20 avant SL10 |
| --- | ---: | ---: | ---: |
| Découverte 2018–2021 | 8 810 | 8 505 | 33,60 % |
| Validation 2022 | 2 510 | 2 287 | 28,03 % |
| Confirmation 2023 partielle | 1 280 | 1 280 | 40,08 % |
| 2024 | 2 520 | 2 520 | 23,45 % |
| 2025 | 2 500 | 2 500 | 35,20 % |
| 2026 partiel | 1 680 | 1 668 | 33,45 % |

**Ces fréquences ne sont pas les taux de trades gagnants du portefeuille** :
elles portent sur toutes les entrées théoriques des candidats, souvent répétées
sur un même titre, avant les limites de capital, positions, concentration,
régime et gaps d'entrée. Certaines expirations sans TP sont profitables.

Population figée TOP50 : **96 500 lignes sans doublon**, 1 930 dates, 612 titres
ayant figuré au moins une fois dans TOP50 de l'univers de 1 790. Historique :
**2 152 562 lignes observables scorées**, contre 2 146 823 anciennes lignes OOF
qualifiées. Les dix anciens OOF sont reproduits avec **écart maximal zéro**.

Les différences de couverture ancienne incluent la purge des labels tardifs,
les chemins non qualifiés et quelques ambiguïtés intrabar. En 2026 TOP10,
les douze exclusions sont des contrôles de qualité à J : aucune ambiguïté
future dans les 1 680 chemins originaux. Aucun candidat de remplacement.

### Contexte macro, distinct d'un filtre entre titres

Snapshot SELECT de **2 052 dates**, 2018-07-05…2026-09-02. Les huit champs
hors RVX sont renseignés sur ces dates ; **RVX entièrement absent**. Pas
d'imputation, valeur nulle conservée. Certains avertissements NumPy de séries
vides proviennent de ces colonnes absentes/constantes, pas d'un échec du run.

Exemple : corrélation de VIX avec la proportion quotidienne de TP20, TOP10 :
**+0,157** en découverte, **+0,210** en 2022, **−0,088** en 2023, **+0,325** en
2024, **+0,185** en 2025, **+0,335** en 2026. Ce constat temporel n'est ni une
capacité de choisir le bon titre le même jour, ni une preuve de rentabilité,
et les vintages de publication restent réservés. Le rendement 10 ans et les
features de tendance marché changent également d'association selon les périodes.
**Aucun veto macro ou seuil VIX n'est créé à partir de ces chiffres.**

### Décision

Cette piste **univariée** est clôturée : aucune preuve suffisante pour entraîner
un filtre d'entrée simple ou modifier TP20/SL10. Cela ne démontre pas que
toutes les interactions multivariées ou de nouvelles sources PIT seraient
inutiles ; elles n'ont pas été testées. Un éventuel nouveau protocole nécessite
un autre GO, sans transformer une association rétrospective en signal validé.

La tentative `20261014-v1` s'est arrêtée pendant la lecture des labels récents :
identifiants numériques archivés sous forme de chaînes nullable incompatibles
avec une opération booléenne NumPy du helper de labels. Les dix folds historiques
avaient été scorés et reproduits. Correction **dans l'adaptation locale de lecture**,
pas dans les prix, identités ou modèles. Identifiants non numériques => inconnus,
pas identités fabriquées. Les deux dossiers restent distincts. La v2 fige aussi
la classification des familles de features uniquement sur la découverte, sans
consulter la variabilité des périodes externes pour choisir les tests.

## Question étudiée

Parmi les premiers titres classés par l'Oracle d'amplitude, les informations
disponibles à la décision J permettent-elles de distinguer :

- **TP20 atteint avant SL10**, entrée à l'open J+1 ;
- **autres issues** : SL ou expiration sans TP dans les vingt séances ?

Ce n'est **pas** la classification D1/D10 du rendement terminal H20, ni une
prévision du PnL net. Une expiration sans TP peut avoir un rendement positif.
Une séparation sur ce label ne suffit donc pas à prouver un filtre profitable.

## Population et non-fuite

Univers figé de 1 790 titres du premier comparatif Oracle parcours. TOP **10 / 20 /
50 titres**, score LightGBM décroissant, symbole croissant en cas d'égalité.
TOP10 primaire ; TOP20/50 = robustesse, pas choix opportuniste du meilleur TOP.

### Historique

Les anciens fichiers OOF ne contiennent que les lignes dont le label d'amplitude
futur était qualifié. Ils **ne servent pas à définir les TOP historiques** de
cette étude : cela aurait filtré la population en fonction du futur.

Pour les dix folds 2018-07-05…2023-07-07, les **poids LightGBM existants**
scorent à nouveau toutes les features observables à J. Aucun fit ou recalibrage.
Dates maximales de disponibilité des labels d'entraînement et de validation
strictement antérieures à toute date scorée. Comparaison aux anciens scores
OOF sur leur sous-population comme test d'intégrité, tolérance 0,0000001.

Rangs XS reconstruits sur **tout l'univers observable de la journée**, jamais
sur un seul chunk, les seuls TOP ou les seuls labels futurs valides. TOP50 figé
avant les contrôles de qualité ; TOP10/20 en sont des sous-ensembles. Un candidat
exclu à l'entrée ou au diagnostic n'est pas remplacé par le suivant.

### Confirmation récente

Scores originaux de `oracle_path_confirmation/20261013-v1`, branche LightGBM,
dernier fold figé 2023-01-05. Ce ne sont pas les copies réentraînées pour le
comparatif LSTM. Prix récents : tape qualifiée du replay économique, avec ses
réparations déjà documentées ; parité parfaite features/prix des overlays non
certifiée, réserve conservée. 2026 borné aux décisions du **2 septembre**, comme
le replay économique. Pas d'intersection ATR ni de filtre sur les gains futurs.

### Labels

TP20/SL10 depuis l'entrée J+1 open, vingt séances, expiration à l'open J+21.
Disponibilité conservatrice du label à **J+22**, même s'il touche un seuil tôt.
Open observé avant HIGH/LOW ; double contact intrabar indéterminé = label
inconnu. Chemin complet, identités, source, ajustement, barres non remplies et
ruptures de prix contrôlés par le helper existant. Aucune résurrection d'un
trade stoppé, aucun remplacement du prix exécuté par un maximum futur.

## Features et qualification PIT

**173 features archivées du profil entraîné**, plus score Oracle de référence et
neuf champs macro : VIX, VIX9D, rendement 10 ans, VXN, VIX3M, MOVE, RVX,
variation 5 jours du rendement 10 ans, sentiment global. **183 colonnes examinées.**
Tout reste dans les sorties de recherche ; pas de features ajoutées au modèle.

Trois niveaux distingués :

1. Calculs prix/benchmark causalement bornés à J, mais sur des historiques
   fournisseurs ajustés actuels : pas attestation de leur vintage historique.
2. Features issues de sources dérivées/sélecteur : lineage réservé, non admissibles
   à une piste promue par les gates de cet audit.
3. Macro : lecture SELECT de `stock_macro_indicators_daily`, snapshot local sans
   écriture SQL et **sans forward-fill**. `created_at`/`updated_at` sont des dates
   de stockage, pas des dates de publication. Les valeurs historiques existent,
   mais leur disponibilité exacte avant la décision n'est pas certifiée. Ces
   associations restent descriptives ; aucune macro promue comme veto PIT.

Pas de nouveau corpus consensus/news : il n'est pas dans ce profil figé. Les
features activées peuvent néanmoins contenir des composantes de volume malgré
l'option spécialisée `include_volume_features=false` ; inventaire réel dans le
profil et le CSV, pas déduction fondée sur un seul boolean.

## Protocole statistique figé

| Période | Rôle | Usage des labels |
| --- | --- | --- |
| 2018–2021, OOF à partir du 5 juillet 2018 | Découverte | Disponibles avant 2022 |
| 2022 | Validation | Disponibles avant 2023 |
| 2023, OOF jusqu'au 7 juillet | Confirmation ancienne | Aucun changement d'orientation/feature |
| 2024 | Confirmation exploratoire | Idem, cohorte mature |
| 2025 | Confirmation exploratoire | Idem |
| 2026 jusqu'au 2 septembre | Confirmation partielle | Disponibles au plus tard le 9 octobre |

2024–2026 ont déjà été observés : **pas des holdouts vierges**. Les rangs,
features et familles sont déterminés avant les exclusions de labels ; les
couvertures exclues/inconnues restent comptabilisées dans les rapports.

### Mesures

- Couverture, cardinalité, moyennes/médianes par classe, différence standardisée ;
- AUC brute agrégée, avec réserve temporelle ;
- **AUC conditionnelle par journée**, puis moyenne à poids égal des dates ;
- au moins deux TP et deux autres issues avec feature finie pour l'AUC du jour ;
- taux de dates discriminantes et nombre de dates évaluables ;
- orientation « valeur haute/basse favorable » figée sur découverte uniquement.

Une variable commune à tous les titres le même jour ne distingue pas les
candidats de cette journée. Elle est examinée séparément comme **contexte
temporel** : corrélation Spearman de sa valeur journalière avec la proportion
de TP ce jour-là, couverture par période. Les constantes ne deviennent pas des
« signaux directionnels » grâce aux différences entre années.

### Gates de sélection d'une piste, avant périodes externes

- Feature de calcul prix causal, pas source à lineage réservé ni score Oracle
  existant présenté comme nouvelle feature ;
- couverture ≥90 % en découverte et validation ;
- AUC quotidienne moyenne orientée ≥**0,55** en découverte, ≥**0,53** en 2022 ;
- au moins 100 dates évaluables en découverte, 30 en validation ;
- test conjoint max-|t|, sign-flips de blocs de **63 séances**, **999** tirages,
  seed **20261014**, p ajustée maxT ≤**0,05** ;
- au moins huit blocs, vingt dates évaluables par bloc.

Les mêmes signes aléatoires s'appliquent simultanément aux features, pour
tenir compte des comparaisons multiples et de leur redondance. Les blocs
réduisent la fausse indépendance de chemins H20 recouvrants ; cette approximation
ne constitue pas une preuve exacte d'indépendance ou d'alpha exploitable.

Confirmation figée d'une piste sélectionnée : AUC orientée ≥**0,52**, couverture
≥90 %, au moins 30 dates dans **chacune** des quatre périodes externes. Aucun
choix d'orientation, poids ou seuil à partir des pertes 2024–2026. TOP20/50 ne
remplacent pas un échec du périmètre primaire TOP10.

Verdict possible : association monotone à confirmer, **pas alpha**, ou absence
de séparation univariée stable. Un NO_GO univarié ne prouve pas l'absence de
toute interaction multivariée ; aucun modèle de ce type n'est entraîné ici.

## Suivi et sorties

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_entry_separability\20261014-v2\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_path_entry_separability\20261014-v2\stderr.log -Tail 20 -Wait
```

- `protocol.json` : sources et code figés, gates et dix folds ;
- `oof-check-*.json` : reproduction des scores originaux, population élargie ;
- caches locaux par phase avec empreintes ;
- `candidate-population.parquet` : sélection avant labels, features J, labels
  et qualité/horodatage ;
- `macro-snapshot.parquet` : observations stockées, sans dates publiées inventées ;
- `coverage.csv` : inconnus, exclusions, ambiguïtés et prevalence TP ;
- `feature-statistics.csv` : toutes les features, TOP et périodes ;
- `report.json` / `report.md` : pistes figées, stabilité et contexte temporel ;
- `progress.json` : état du calcul.

Sources recontrôlées à la fin, verrou exclusif, caches vérifiés avant reprise.
Code : `scripts/research/us_oracle_path_entry_separability.py`.
Tests : `tests/test_us_oracle_path_entry_separability.py`.

**Aucun modèle, batch, paramètre live, protection, prédiction SQL ou compte
courtier modifié. Une éventuelle expérience suivante nécessite un nouveau GO.**
