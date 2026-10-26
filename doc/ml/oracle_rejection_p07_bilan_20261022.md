# P07 — rejet baissier : zéro motif qualifié, aucun backtest

22octobre2026. **TERMINÉ / INSUFFICIENT_P07_FREQUENCY_NO_BACKTEST.**
Contrôle de couverture/fréquence uniquement ; **aucun rendement ou PnL calculé**.
Dossier canonique : `artifacts/research/us_oracle_rejection_p07/20261022-v1`.
[Protocole préenregistré](oracle_rejection_p07_20261022.md).

## Conclusion

**Décision utilisateur : piste mise de côté dans sa forme actuelle**, sans
changement des seuils ni intégration en production. Une éventuelle reprise
demanderait un échantillon nettement plus large, correctement qualifié, un
protocole figé et un nouveau GO ; pas de relance automatique.

Parmi les **112occasions/38titres** ayant un lookback10séances complet, **aucune
ne présente le motif P07** : nouveau creux strict, plus grande amplitude
stricte et clôture dans le quart supérieur de la même séance. Le seuil de
poursuite n'est pas atteint ; **aucun backtest économique n'a été lancé**.

Ce n'est pas une preuve de pertes ou d'inefficacité universelle : il n'y a
aucun signal à évaluer sur ce périmètre conditionnel. Ne pas abaisser le seuil
de clôture, raccourcir le lookback ou élargir la fenêtre après ces chiffres.
Les101autres occasions restent **inconnues**, pas de faux motifs ou de pertes.

## Critères figés

Source d'inspiration : [FMZ797, RSI Mean Reversion Breakout](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/RSI%E5%9D%87%E5%80%BC%E5%9B%9E%E5%BD%92%E7%AA%81%E7%A0%B4%E7%AD%96%E7%95%A5-RSI-Mean-Reversion-Breakout-Strategy.md).
Malgré le titre, pas de RSI dans ce code ; adaptation actions daily/5m propre.

Sur dix séances régulières raw achevées jusqu'à OracleJ :

1. `low_J < min(low des neuf séances précédentes)`.
2. `high_J−low_J > max(range des neuf précédentes)`.
3. `(close_J−low_J)/(high_J−low_J) >= 0,75`, rangeJ positif.

Une égalité de creux/range ne satisfait pas les comparaisons strictes. Le
close est le dernier close5m régulier, pas une certification de l'enchère
officielle. Une séance plate est un non-motif connu, pas un manque de données.

Entrée hypothétique seulement après une première clôture5m >hautJ pendant
J1/J2, open contigu suivant dans la même séance. Low sous le creuxJ avant
entrée : annulation prioritaire, y compris dans la bougie de confirmation.
Gap du prochain open sous ce creux : annulation avant fill. Ne jamais utiliser
le futur low de la bougie d'entrée pour annuler rétroactivement son open.
Première confirmation à la dernière bougie : pas de fill overnight ni de réessai.
Pas de retest, RSI, volume, SHORT ou nouveau trailing ajouté.

## Couverture et fréquence

Archives locales scellées, SIP raw régulières non remplies, calendrier NYSE
réel.213campagnes CatBoost PATH_H20 de recherche héritées, déjà conditionnelles
à d'anciens signaux/chemins futurs/survivants : **pas tout le TOP10 quotidien
ni le LightGBM de production**. Pas de nouveau téléchargement ou lecture SQL.

| Année Oracle | Occasions initiales | Lookback10 complet | Motif P07 | Signaux P07 | Signaux non chevauchants |
| --- | ---: | ---: | ---: | ---: | ---: |
|2025|119|58|0|0|0|
|2026|94|54|0|0|0|
|Total|213|112|0|0|0|

101lookbacks manquent. La clôtureJ et les observations J1/J2 sont évaluables
sur les112cas restants ; pas de manque supplémentaire dans les scans nécessaires.
Les comptes de motifs utilisent les prix connus à J, pas des résultats futurs.

Chaque condition prise séparément est présente, mais jamais les trois ensemble :

| Année | Nouveau creux | Plus grande amplitude | Clôture quart supérieur | Creux + amplitude |
| --- | ---: | ---: | ---: | ---: |
|2025|8|11|11|5|
|2026|12|7|14|1|

Les six cas réunissant les deux premières conditions :

| Titre | OracleJ | Position de clôture dans le range |
| --- | --- | ---: |
|ASAN|2025-03-11|54,36 %|
|FUTU|2025-04-04|39,17 %|
|BLMN|2025-05-07|6,83 %|
|CLF|2025-05-23|1,54 %|
|TROX|2025-09-24|33,96 %|
|MU|2026-02-04|31,71 %|

Ce diagnostic explique le zéro ; **ce n'est pas un test de seuils alternatifs**.
Aucun rendement de ces titres n'a été examiné pour retenir une autre condition.

Le témoin sans motif P07, mais avec la même cassureH_J/invalidationL_J/J1J2,
produit43signaux de cassure :20en2025 et23en2026. Ce ne sont pas des trades
gagnants démontrés. Les69autres scans se terminent par59invalidations du creux
et10absences de cassure. La nouvelle information P07 manque dès la clôture J :
la confirmation ultérieure ne peut pas créer rétrospectivement ce motif.

## Seuil de poursuite et arrêt

Il fallait, **chaque année**,30signaux non chevauchants sur10titres et6mois de
signaux. L'espacement conservateur OracleJ40 de toutes les occasions évaluables,
y compris sans motif, laisse37occasions en2025 et36en2026, mais toujours zéro
signalP07. Aucun taux gagnant, rendement, DD ou avantage directionnel n'est estimé.

Aucun chemin futurH20 ni sa maturité n'a servi de nouveau filtre à ce stade ;
les fréquences auraient été un plafond avant la qualification économique.
Le scan peut s'arrêter après une décision causale connue à J1, sans exiger J2
si elle n'est plus nécessaire. Cela ne supprime pas les biais de couverture
des archives et de sélection de la cohorte initiale.

La suite économique conditionnelle n'est donc **pas autorisée par le gate** :
pas de grille, de comparaison du PnL ou d'entraînement lancé. Une éventuelle
reprise demanderait une couverture plus large avec signaux Oracle OOS qualifiés,
un protocole figé et un nouveau GO ; pas de changement silencieux des seuils.

## Audit, limites et clôture

**272tests passés**, dont30P07. Audit séparé du motif et du premier signal :
213dossiers vérifiés,112features qualifiées confirmées, zéro signalP07,
contrôle des compteurs, inconnus et espacement. Statut technique :
`PASS_P07_FEATURE_ENTRY_FREQUENCY_NO_PNL_REVIEW`. Même assistant,
**pas revue humaine indépendante**. Empreintes sources/données/rapport contrôlées.

Zéro nouveau calcul de performance, backtest économique, SQL, appel fournisseur/
LLM, entraînement, ordre, modèle, batch ou configuration de production modifié.
Téléchargements en cours non touchés. Les scripts interdisent la transition
automatique vers un moteur économique.

Limites : faible couverture, cohorte survivante/conditionnelle de recherche,
années2025/2026 déjà examinées, pas de2024dans l'archive retenue, PIT/identités/
opérations sur titres non entièrement qualifiés. La table d'événements héritée
est vide/incomplète, pas preuve d'absence d'événement. Pas de parité live complète.

**Les sept hypothèses FMZ retenues sont désormais traitées à leur étape prévue** :
cinq non confirmées par leur comparaison, P04 à effectif trop faible, P07
arrêtée dès la fréquence. Cela ne signifie pas sept backtests économiques
ni sept preuves d'inefficacité universelle. Aucune stratégie promue.
Le catalogue des nouvelles pistes FMZ est clôturé, registre actualisé.

## Pièces

Dans le dossier canonique : `protocol.json`, `report.json`, `final-audit.json`,
`frequency-summary.csv`, `coverage-and-signals.parquet`, `nonoverlap.parquet`,
`P07-entry-signals.parquet` (vide) et `session-quality.parquet`.
Pas d'`annual-summary.csv` ni de sous-dossiers de backtest.

SHA256 rapport : `18c89d7fe7c1a41fe5174a35e199cbae926cfb401f607b357d7dfab9a17eb334`.
