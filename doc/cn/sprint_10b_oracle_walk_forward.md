# Sprint 10-B — Oracle amplitude CN_A, évaluation Walk-Forward

## Question et portée

Le Sprint 10-B demande si les features **price-only** disponibles avant
l'ouverture de J distinguent mieux que la volatilité historique les titres
qui finiront dans D1 ou D10 à H5, H10, H15 ou H20. D1 et D10 constituent
ensemble la cible binaire d'**amplitude**, sans étiquette de direction dans
le modèle. Le global ranking signé et la direction conditionnelle restent
hors de cette campagne : un bon Oracle amplitude ne prouve pas D1 contre D10.

Cette campagne utilise exclusivement `CN_A`, les [panels du Sprint 9](./sprint_9_validation_2018_2025.md)
et les [labels audités du Sprint 10-A](./sprint_10a_validation_2018_2025.md).
Elle écrit des artefacts de recherche sous `artifacts/cn/oracle/sprint10b/` ;
elle ne modifie ni les tables de prédiction, ni le serving, ni le backtest.

## Protocole figé avant les tests

Le [fichier de pré-enregistrement](../../config/research_cn/sprint10b_oracle.yaml)
est la source exacte des paramètres. Il fixe :

- 2018–2025 en source, tests OOS semestriels de 2022H1 à 2025H2 ;
- H5/H10/H15/H20, soit 4 horizons × 2 modèles = **8 hypothèses** et
  **64 folds** évalués ;
- validation sur les 126 séances précédant le test et au moins 504 séances
  disponibles au train ;
- purge stricte : tout label de train doit être connu **avant la première
  décision de validation**, et tout label de validation **avant la première
  décision de test** ;
- échantillon d'entraînement plafonné à 600 000 lignes par fold, tiré par
  hachage déterministe des clés `(session_date, instrument_id)`, sans utiliser
  le label pour sélectionner les lignes ; validation et test non échantillonnés ;
- LightGBM et CatBoost peu profonds, hyperparamètres fixés, arrêt anticipé
  sur la validation seulement ; **aucune calibration sur le test** ;
- baseline `atr20_pct`, mesurée sur exactement les mêmes titres et dates
  labellisés que le modèle ;
- sélection TOP20 par date pour les métriques de précision et de mouvement
  absolu réalisé.

Les colonnes utilisées sont énumérées explicitement dans le YAML. Le secteur
historique n'est pas disponible en PIT : aucun champ secteur actuel n'est
injecté. Les sous-groupes sont board, année, semestre et régime de breadth
observé avant J. Le groupe secteur est **non mesurable** à ce stade.

## Mesures et gate

Chaque fold enregistre AUC, average precision, prévalence, précision TOP20,
lift, mouvement absolu moyen TOP20, effectifs D1/D10 sélectionnés,
couverture des labels et part ayant un indicateur d'éligibilité d'exécution.
Ces mesures portent sur les labels de prix valides ; il faut examiner la
couverture et ne pas extrapoler les métriques aux trajectoires censurées.

Le gate est fixé **avant** l'observation des 64 folds :

1. au moins 60 séances évaluables dans chacun des 8 semestres ;
2. au moins 95 % de labels valides parmi les trajectoires mûres pour
   chaque année de l'horizon considéré ;
3. précision TOP20 supérieure à la baseline dans au moins 6 semestres ;
4. amélioration globale d'au moins **2 points de pourcentage** ;
5. borne basse du bootstrap par blocs mensuels strictement positive, avec
   correction de Bonferroni sur les 8 hypothèses (alpha 0,05/8).

Un résultat positif est `GO_RESEARCH_ONLY`, jamais une activation automatique
du live. La métrique principale est la **précision TOP20 appariée** ; AUC,
average precision et les sous-groupes expliquent le résultat mais ne servent
pas à choisir a posteriori un autre seuil. Les données de test ne pilotent
ni features, ni hyperparamètres, ni early stopping.

## Exécution, reprise, lecture

Le [calcul par fold](../../modelFactory/cn_oracle_walk_forward.py), son
[agrégateur](../../modelFactory/cn_oracle_aggregate.py) et le
[lanceur reprenable](../../dataIntegrityEngine/cn_sprint10b_campaign.py)
forment une campagne distincte des traitements de production.

```powershell
# Un fold de contrôle
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.cn_oracle_walk_forward --horizon 5 --test-semester 2022H1 --model lightgbm

# Campagne complète ; les folds déjà vérifiés sont sautés
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint10b_campaign

# Ne rendre un verdict qu'avec les 64 résultats
F:\projets\.venv\Scripts\python.exe -m modelFactory.cn_oracle_aggregate --require-complete
```

Chaque fold conserve le modèle de recherche, ses prédictions OOS Parquet,
les métadonnées de purge et les SHA de provenance. Le lanceur vérifie les
empreintes avant un `SKIP`, et refuse d'écraser un artefact existant.
Le rapport consolidé est `artifacts/cn/oracle/sprint10b/sprint10b_oracle_summary.json`.
Un rapport `INCOMPLETE` n'autorise aucune conclusion sur l'horizon gagnant.

## Limites de lecture

Le TOP20 est évalué parmi les lignes ayant une cible observable et un score
baseline ATR disponible. Certaines lignes futures ne pourront pas être
labellisées (suspension, facteur non vérifié, fin 2025) : les métriques sont
conditionnelles à cette population. Le classement de prix n'est pas une
simulation d'ordres : T+1, limite verrouillée, quantité négociable, frais et
impact seront traités plus tard. Un éventuel gain d'amplitude ne doit pas
être décrit comme une capacité à choisir LONG ou SHORT.

## Résultat de la campagne figée

Les **64/64 folds** sont produits (62 nouveaux, 2 pilotes repris après
vérification des SHA). L'agrégation stricte retourne
`COMPLETE_RESEARCH_ONLY`, `missing=0`. Le [rapport consolidé](../../artifacts/cn/oracle/sprint10b/sprint10b_oracle_summary.json)
contient les 8×8 métriques et les bornes bootstrap. Chaque combinaison est
positive sur les **8 semestres sur 8** et franchit le gate pré-enregistré.

| Horizon | Modèle | AUC | Précision TOP20 | Baseline ATR | Gain | Borne basse corrigée |
|---|---|---:|---:|---:|---:|---:|
| H5 | LightGBM | 0,713 | 41,14 % | 35,40 % | +5,74 pp | +4,90 pp |
| H5 | CatBoost | 0,709 | 40,75 % | 35,40 % | +5,35 pp | +4,48 pp |
| H10 | LightGBM | 0,700 | 39,85 % | 34,78 % | +5,07 pp | +4,34 pp |
| H10 | CatBoost | 0,696 | 39,46 % | 34,78 % | +4,68 pp | +3,86 pp |
| H15 | LightGBM | 0,689 | 38,81 % | 34,28 % | +4,53 pp | +3,82 pp |
| H15 | CatBoost | 0,688 | 38,60 % | 34,28 % | +4,32 pp | +3,55 pp |
| H20 | LightGBM | 0,682 | 38,00 % | 33,71 % | +4,29 pp | +3,55 pp |
| H20 | CatBoost | 0,680 | 37,76 % | 33,71 % | +4,05 pp | +3,26 pp |

« Borne basse » désigne la borne inférieure de l'intervalle bootstrap par
mois, avec alpha 0,05/8. Il s'agit d'une preuve **relative à la baseline ATR
sur la population labellisée**, pas d'une preuve de gain économique ni d'une
certification statistique absolue dans tous les régimes futurs. Le semestre
2023H1 est le moins favorable, mais il reste positif pour les huit
combinaisons ; aucune combinaison ne dépend d'un seul semestre gagnant.

Le diagnostic de composition interdit de traduire ce GO en ordre LONG : pour
H5 LightGBM, les TOP20 sélectionnés comprennent 233 165 D1 et 155 834 D10.
Pour H20 LightGBM, 223 083 D1 et 127 963 D10. L'Oracle trouve davantage
d'extrêmes, **avec une prédominance des baisses extrêmes** dans ses choix.
Même la plus forte précision observée, H5 LightGBM, laisse environ 59 % des
TOP20 hors D1/D10, et ne fournit aucun sens exploitable à elle seule.

Le meilleur gain *observé* est H5 LightGBM, mais choisir maintenant cet
horizon pour le live à partir de ces tests serait une sélection sur OOS.
Une confirmation indépendante et un audit d'exécutabilité sont requis avant
toute promotion. Le Sprint 10-B est donc **GO recherche amplitude**, et
**NO-GO serving/backtest économique automatique**.
