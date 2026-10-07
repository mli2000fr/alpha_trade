# E22 — Trajectoire pré-signal J−5 à J pour Oracle Extreme

## Statut

**TERMINÉ / NO-GO H20.** E22 est un harness de recherche
isolé. Il ne modifie ni les modèles Oracle servis, ni les prédictions SQL, ni
les batchs existants.

## Hypothèse

L'Oracle O0 reçoit une ligne par date et symbole. Cette ligne contient déjà des
résumés historiques — momentum, volatilité, RSI, accélération et rangs
cross-sectionnels — mais pas l'ordre brut des séances récentes. Deux chemins
ayant le même rendement cumulé peuvent porter une information d'amplitude
future différente.

E22 teste si la forme causale de J−5 à J améliore la probabilité de détecter
les futurs TOP10 ou BOTTOM10, sans chercher leur direction.

## Variantes gelées

1. 'O0_BASELINE' : les 168 features du profil Oracle canonique.
2. 'O0_LAGS_5' : O0 plus J−1 à J−5 pour sept variables courtes.
3. 'O0_PATH_SHAPE_6' : O0 plus 14 descripteurs compacts de J−5 à J.

Les descripteurs couvrent rendement, volatilité réalisée, fraction de jours
positifs, alternance des signes, série signée la plus longue, concentration du
mouvement, drawdown, run-up, expansion de range, gaps, volume et
corrélation rendement-volume.

Une absence de séance pour un symbole invalide les lags concernés. Les
week-ends ne créent pas de trou : la continuité est mesurée sur l'index global
des séances présentes, pas en jours calendaires.

## Protocole

Les trois variantes partagent strictement dataset, labels, univers, folds,
validation d'early stopping, horizon et période. Le test de chaque fold reste
OOS. E22 conserve les prédictions OOS en Parquet et écrit un 'report.json';
aucun modèle produit n'est servable.

Les 12 fenêtres sont les **12 folds valides les plus récents**, et non les 12
premiers. Cette règle garantit que l'audit couvre la fin de la période demandée
et permet d'observer la dérive récente. Elle a été verrouillée après le smoke
technique, qui a révélé que le comportement par défaut du splitter partagé
s'arrêtait à mi-2024 malgré des données disponibles jusqu'à fin 2025.

Métriques : AUC, average precision, précision/rappel aux TOP10 et TOP20
prédits, résultats par semestre et taux de folds gagnants.

Une variante ne passe que si elle respecte simultanément :

- delta average precision >= +0,005 ;
- delta AUC >= +0,005 ;
- delta précision TOP20 >= +0,01 ;
- AUC meilleure sur au moins 60 % des folds communs ;
- aucun semestre sous −0,02 de précision TOP20 face à O0.

Ces seuils sont fixés avant exécution. Un succès sur H20 devra encore être
confirmé sur un batch/horizon distinct avant toute évolution du serving.

## Commande initiale H20

    python -u -m modelFactory.oracle_trajectory_e22 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --log-level INFO

Pour un smoke technique seulement, ajouter '--max-symbols 50'. Ce smoke ne
peut jamais statuer sur l'hypothèse.

## Smoke technique du 15 septembre 2026

Le smoke sur 50 symboles a construit 12 folds et 91 155 lignes sans toucher la
base ni le serving. Les trois variantes ont terminé. Les lags bruts échouent les
gates. La forme compacte améliore l'AUC de +0,0227 et l'average precision de
+0,0240, mais seulement +0,0022 sur la précision TOP20 ; elle échoue aussi la
stabilité par fold et la sécurité semestrielle. Ces chiffres ne constituent pas
un résultat scientifique : les 50 symboles sont uniquement un échantillon de
smoke, et les folds initiaux ne couvraient que juillet 2018 à juillet 2024.

Artefact :
'artifacts/research/oracle_trajectory/e22-h20-smoke50-20260915-v1'.

Le protocole final sélectionne maintenant les 12 folds les plus récents. Le
second smoke sur 20 symboles confirme une couverture du 8 juillet 2019 au
11 juillet 2025, dernière fenêtre OOS matérialisable avec les données réellement
disponibles. Ses métriques TOP20 sont volontairement non interprétables : après
filtrage des historiques incomplets, plusieurs dates passent sous le minimum
transversal de 20 titres. Le run complet n'a pas cette limitation.

Artefact de validation du protocole :
'artifacts/research/oracle_trajectory/e22-h20-smoke20-latest-20260915-v2'.

## Résultat complet H20 — 15 septembre 2026

Artefact :
'artifacts/research/oracle_trajectory/e22-h20-20260915190508'.

Le run complet porte sur 2 493 symboles, 2 557 086 prédictions OOS, 1 512
dates et 12 folds récents, du 8 juillet 2019 au 11 juillet 2025. Les trois
variantes utilisent exactement les mêmes observations OOS. Aucun artefact de
serving et aucune donnée SQL n'ont été modifiés.

| Variante | Features | AUC | Average precision | Précision TOP10 | Précision TOP20 |
|---|---:|---:|---:|---:|---:|
| O0 baseline | 168 | 0,759104 | 0,419723 | 0,506055 | 0,441879 |
| O0 + lags J−1 à J−5 | 203 | 0,759623 | 0,420532 | 0,506036 | 0,442104 |
| O0 + forme J−5 à J | 182 | 0,759167 | 0,419742 | 0,506101 | 0,441852 |

### Lags ordonnés

Les deltas face à O0 sont +0,000519 d'AUC, +0,000809 d'average precision et
+0,000225 de précision TOP20, soit seulement +0,0225 point de pourcentage.
Sept folds sur douze gagnent en AUC (58,3 %), sous le gate de 60 %. Le dernier
semestre complet, 2025H1, perd 0,226 point de précision TOP20. Seul le gate de
sécurité semestrielle passe ; les quatre gates de performance et stabilité
échouent.

### Forme compacte de trajectoire

Les deltas sont +0,000063 d'AUC, +0,000019 d'average precision et −0,000027 de
précision TOP20. Six folds sur douze gagnent. Cette variante est statistiquement
et économiquement indiscernable de la baseline ; seul le gate de sécurité
semestrielle passe.

### Décision

**NO-GO pour H20.** La trajectoire J−5 à J n'apporte pas d'information
incrémentale exploitable au TOP20 Oracle. Le petit signal vu sur 50 symboles
était un effet d'échantillon et disparaît sur l'univers complet. Les résumés
temporels déjà présents dans les 168 features O0 capturent vraisemblablement
l'essentiel de cette information ; ajouter 35 lags augmente la dimension de
20,8 % pour un gain TOP20 négligeable.

Conséquences : aucun changement du profil `oracle.json`, aucun réentraînement
de production, aucune nouvelle prédiction et aucun backtest économique. E22
est fermée pour H20. Une réplication sur horizon court constituerait une
nouvelle expérience pré-enregistrée, et non une continuation optimisée d'E22.
