# US — Actualisation du régime après alimentation macro 2026

4 octobre 2026. Statut : terminé, lecture SQL seule. Cette actualisation
remplace la réserve « macro absente en 2026 » des audits antérieurs pour
les données aujourd'hui disponibles, sans effacer l'état constaté lors
des calculs initiaux.

## 1. Couverture et périmètre exact

VIX, VXN, VIX3M et MOVE sont désormais tous renseignés sur les 123 lignes
macro de janvier–juin 2026 : 20/19/22/21/20/21 par mois. Sur les **61 dates
du T1 étudié et 1 680 observations**, la couverture des quatre indices est
de 100 %. Les modes archivés comprennent 60 séances normales et une séance
en capital_preservation.

On réutilise exactement les candidats, les labels H20 et les features de
force relative/breadth de l'expérience précédente. Le recalcul économique
descriptif couvre **janvier–mars**, pas avril–juin : aucune sélection de ces
trois derniers mois n'est créée. Leur couverture macro est vérifiée seulement.

## 2. Deux contrôles indépendants de persistance

1. Relire mode/allow_new_entries actuels en base, sans les mettre à jour.
2. Recalculer séquentiellement les snapshots avec le véritable
   `service.market.regime_manager.build_snapshot`, configuration courante,
   equity=4 000 et état d'hystérésis propagé. Warmup du 3 novembre 2025 au
   31 décembre 2025, puis T1 2026. Chaque date macro exacte est contrôlée.

Le provider est `TableFirstMacroProvider(None, persist_fallback_hits=False)` :
pas de fallback réseau ni de persistance. Le sentiment est lu localement
via DbSentimentScoreProvider. Un garde SQL rejette toute instruction autre
que SELECT/SHOW/DESCRIBE/EXPLAIN. On n'appelle pas la fonction de
recalcul qui persiste les régimes en table.

Les deux contrôles donnent la même décision LONG : **interdiction le
30 mars 2026**, autorisation sur les 60 autres dates. Les 29 observations
de cette séance sont exclues. Les blocages sectoriels du snapshot n'excluent
aucun candidat supplémentaire dans ce test.

Le 27 mars, VIX élevé est détecté mais le mode reste normal ; le 30 mars,
le mode devient capital_preservation ; le 31 mars, il revient normal dans
ce rejeu. Un signal macro détecté ne signifie donc pas automatiquement
interdiction LONG : les règles de confirmation et de sortie s'appliquent.

## 3. Résultats sans changer la sélection

| Période du signal | Candidats avant/après | H20 brut avant | H20 brut après régime |
|---|---:|---:|---:|
| Janvier 2026 | 563 / 563 | +6,60 % | +6,60 % |
| Février 2026 | 521 / 521 | −0,03 % | −0,03 % |
| Mars 2026 | 596 / 567 | +18,27 % | +17,62 % |
| T1 complet | 1 680 / 1 651 | +8,68 % | +8,29 % |

Au T1, D10 passe de **36,13 % à 35,80 %**, D1 de **11,19 % à 11,33 %**.
Les observations écartées le 30 mars comptent 16 D10 et un D1 ; leur
rendement H20 moyen est +31,12 %. Les fenêtres de fin mars débordent en
avril. Le filtre supprime donc ici davantage une cohorte de rebond favorable
qu'une cohorte perdante, sans que cela invalide sa mission de protection.

À budget initial d'observations fixe (abstention=0), la contribution moyenne
des rendements retenus est +8,15 % contre +8,68 % initialement. Cette mesure
n'est pas un rendement de portefeuille, un rendement annualisé ni un PnL.

## 4. Les filtres secteur/breadth ne sont pas sauvés par cette mise à jour

| Politique T1 | Effectif | D10 | D1 | H20 moyen brut |
|---|---:|---:|---:|---:|
| BASE | 1 680 | 36,13 % | 11,19 % | +8,68 % |
| Régime recalculé | 1 651 | 35,80 % | 11,33 % | +8,29 % |
| RS + breadth | 417 | 25,90 % | 21,10 % | +0,65 % |
| Régime recalculé + RS + breadth | 416 | 25,96 % | 20,91 % | +0,70 % |

La conclusion précédente sur leur absence d'amélioration stable reste
inchangée. Aucun poids, seuil ou nombre de candidats n'a été réoptimisé.

## 5. Ce qu'on peut et ne peut pas conclure

- L'alimentation macro est effective ; l'ancienne réserve de couverture
  2026 est levée sur les dates testées.
- Le régime testé ne supprime pas le février presque neutre de cette
  sélection ; il réduit modestement la moyenne positive de mars.
- Ne pas en déduire qu'il faut désactiver le régime. Le contrôle protège
  les entrées et l'exposition, pas seulement la moyenne de rendement futur.
- Ce n'est pas un backtest complet : pas d'ouverture J+1, coûts, plafonds,
  capacité disponible, risque de positions ouvertes ou sorties.
- Régime calculé à J avec asof_inclusive ; pas de données macro futures.
  Les vintages économiques d'origine ne sont toutefois pas certifiés par
  un simple remplissage historique. Sentiment/secteurs restent soumis aux
  réserves PIT précédentes.
- Earnings lookup non injecté, aucun bouclier individuel earnings simulé.
  La configuration et le warmup sont enregistrés, pas une garantie de
  reproduction de chaque état d'un compte live historique.

## 6. Preuves

Script : `scripts/research/us_2026_regime_refresh.py`.
Sortie : `artifacts/research/us_atr_oracle_sentiment/regime-refresh-2026q1-20261004-v1/`.
`report.json`, `selection_refreshed.parquet`, `macro_read_snapshot.parquet`,
`snapshots.json` et `progress.json` COMPLETED. Hashes du fichier source de
sélection et de la configuration dans le rapport. Les anciens résultats
restent conservés pour comparer l'état avant/après alimentation.

Voir [résultats initiaux secteur/breadth](us_confirmation_secteur_breadth_resultats.md)
et [audit multi-annuel](us_2019_2026_audit_regimes_combinaison.md).
