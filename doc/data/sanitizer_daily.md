# Sanitizer daily et audits qualité

Retour : [références Data](README.md)

## Objectif

`DataSanitizer` transforme les séries brutes en daily alignées et auditées. Il accepte que quelques séances soient absentes mais refuse de fabriquer un long historique continu à partir d'un dernier close.

## Paramètres codés

SPY sert de référence. La reconstruction regarde 400 jours calendaires, avec 10 jours de padding pour SPY. Les anomalies utilisent une fenêtre 20, minimum 5, seuil 5 MAD et rendement absolu > 2 %. Plus de trois séances remplies consécutives déclenchent `DataQualityError`. Le commit par défaut intervient après 50 symboles effectivement traités.

## Pipeline par symbole

1. refléter les tables et garantir la présence de SPY 1D ;
2. charger la dernière synchro/audit et les barres de la fenêtre ;
3. valider colonnes, types, OHLC et ordre temporel ;
4. générer le calendrier de séances ;
5. left join des barres sur le calendrier ;
6. remplir uniquement les trous tolérés, marquer `is_filled` ;
7. recalculer `daily_return` avec le close précédent ;
8. mesurer chaque streak de fills et bloquer si > 3 ;
9. détecter les anomalies par médiane/MAD roulantes ;
10. upserter daily et audits ;
11. synchroniser l'état qualité vers les scores si de nouvelles barres ont été traitées.

Une ligne remplie reporte le prix antérieur selon le code et ne simule pas du volume réel. Les consumers doivent pouvoir distinguer `is_filled=true`.

## Détection robuste

Pour chaque rendement, le code calcule la médiane roulante, l'écart absolu à cette médiane puis la médiane roulante des écarts. `is_anomaly` est vrai si `abs_dev > 5 * MAD` et `abs(return) > 0.02`. La double condition évite qu'une MAD minuscule marque des mouvements triviaux.

Les anomalies restent dans la série avec un flag : les supprimer automatiquement créerait une décision implicite et pourrait effacer un vrai gap. L'investigation doit vérifier split, source, OHLC voisin et corporate action.

## Audits

`cleaning_audit_latest` garde le dernier état par symbole. `cleaning_audit_runs` conserve chaque exécution. Le payload inclut dernière synchro, trous, anomalies, statut et message. Un symbole sans nouvelles barres est skipped et ne remet pas les compteurs existants à zéro.

Le run continue après une erreur symbole et persiste un audit `failed`. Les échecs de qualité incrémentent aussi `degraded_symbols`. Une transaction externe est commitée périodiquement ; le dernier batch est commit en fin de run.

## Diagnostic

- `SPY 1D unavailable` : réparer la source benchmark avant les autres symboles ;
- streak > 3 : backfiller la série, ne pas augmenter le seuil sans analyse ;
- anomalies massives à une date : suspecter split/source mixte ;
- zéro ligne upsertée : vérifier dernière sync et date cible ;
- audits failed mais scores anciens : comportement attendu si aucune nouvelle barre ;
- daily et brut divergents : comparer `is_filled`, source et adjustment.

## Extension sûre

Toute nouvelle règle doit avoir : reason/status stable, compteur summary, test sur série vide/courte, test autour d'un week-end/jour férié, test de transaction et preuve qu'elle n'utilise aucune donnée future.

