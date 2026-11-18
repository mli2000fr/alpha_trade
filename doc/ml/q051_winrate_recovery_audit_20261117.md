# Taux de réussite internes et reprise du compte — audit activation/sortie

17 novembre2026. Audit de cinq cohortes : pool Oracle TOP179, sélections B TOP10, sélections B+anti-SL TOP10, trades acceptés des comptes témoins B et B+anti-SL. Aucun nouveau replay, fit, SQL, fournisseur/LLM, ordre ou changement de production.

## Définition précise du taux gagnant

Oracle détecte une amplitude ; le taux mesuré ici est la rentabilité LONG de ses sélections avec SL5/open11 et frais8pb/côté, pas la précision de son amplitude. Pour les sélections, les labels qualifiés déjà archivés sont utilisés ; ils sont théoriques et ne sont pas tous des trades réellement finançables. Les trades effectivement acceptés sont une cohorte différente.
Tous les résultats attendent la maturité commune J+11 (ouverture11 de détention après entréeJ+1), y compris les stops précoces. Cela évite de faire baisser artificiellement le taux récent en comptant les perdants rapides avant les gagnants encore en cours. Les inconnus ne sont ni des pertes ni des gagnants. Certaines fins d’année manquent dans les archives de labels : des fenêtres, notamment janvier, restent non qualifiées.
Taux récent :20 séances de maturité. Référence :120 séances de maturité précédentes, sans recouvrement avec les20récentes. Couverture de labels≥80%, minimum40 labels récents/160 de référence pour les sélections ;20/80 pour les trades réellement acceptés. Fenêtre complète140séances, warmup exclu. Les observations peuvent partager un titre et des horizons chevauchants.

## Règle de taux figée, sans recherche de seuil

Activation : taux récent inférieur de5points à la référence, trois clôtures consécutives. La référence est figée lors de cette activation. Désactivation : taux récent revenu à référence figée moins2points, cinq clôtures consécutives. Une référence qui baisserait continuellement pendant la crise pourrait annoncer une fausse reprise ; elle reste donc fixe jusqu’à la sortie.
Les dates sont des signaux de clôtureJ pour application possibleJ+1. Préfixes reconstruits :15 égalités de taux et15 d’états, trois tests passent. Il s’agit d’un audit de conditions, pas d’un replay de portefeuille appliquant cette protection.

## Résultat sur la baisse ciblée

| Cohorte de sélections | Activation interne | Désactivation interne |
| --- | --- | --- |
| Oracle TOP179 | 6janvier2025 | 16mai2025 |
| Per-symbol B TOP10 | 24décembre2024 | 16mai2025 |
| Per-symbol B+anti-SL TOP10 | 20décembre2024 | 12juin2025 |

Ces alertes sont plus tardives que les premières pertes de novembre. La maturité H10 impose un délai ; elles pourraient réagir à la dégradation, pas l’anticiper totalement.
Après la désactivation B du16mai, le compte témoin SL10 sans protection gagne6,24% sur les20séances suivantes, mais recule temporairement jusqu’à4,64% sous son niveau de ce jour. Après la désactivation SL10 du12juin, ce témoin gagne7,28% à20séances. Une reprise finale positive n’exclut pas une baisse intermédiaire.

## Fiabilité descriptive sur toutes les années

Résultat mesuré : hausse du capital du témoin SL10 non protégé20séances après le signal OFF. Ce n’est pas un taux de trades gagnants ni le rendement causal d’un compte qui aurait effectivement repris à ces dates.

| Détecteur | Sorties | Témoin positif20 après | Contrôle sans fenêtres chevauchantes |
| --- | ---: | ---: | ---: |
| ORACLE179 | 12 | 8/12 (66.67%) | 8/12 |
| PER_B10 | 13 | 10/13 (76.92%) | 9/12 |
| PER_SL10 | 15 | 11/15 (73.33%) | 10/14 |
| TRADED_B | 6 | 4/6 (66.67%) | 4/6 |
| TRADED_SL10 | 7 | 3/7 (42.86%) | 3/7 |

Pour comparaison descriptive, le témoin SL10 est positif20séances plus tard dans56,99% des1423dates mûres de toute la période. Les sorties per-symbol B donnent10/13positives (76,92%), mais l’intervalle Wilson approximatif95% s’étend de49,74% à91,82%, avant même de corriger les dépendances temporelles. Échantillon insuffisant, années déjà vues, plusieurs indicateurs examinés : pas de fiabilité prédictive établie.
Les faux signaux existent : sortie B le16juin2022 suivie de-6,23% du témoin SL10 sur20séances, creux intermédiaire-8,94%. Sortie SL10 le20août2026 suivie de-4,83%. Les bons cas ne suffisent pas à garantir le déclencheur.

## Activation : un avantage encore faible

Le régime dégradé issu du taux per-symbol B signale, sur les trades SL10 évaluables de toutes les années, un rendement net unitaire inférieur de0,82point à celui des autres trades. Hors de la fenêtre novembre2024–juin2025, cet écart reste seulement-0,52point. Mais il concernerait47,58% des gains effectivement réalisés hors fenêtre : ce n’est pas une justification d’arrêt complet. Le taux des seuls trades du compte a encore moins de support et peut rester longtemps en protection.

## Reprise du compte supérieure à5% sur20séances

Condition testée : cinq clôtures consécutives avec rendement20>+5%, après les activations SPY50 existantes. Un compte protégé peut rester presque à plat ; attendre son propre +5% est tardif et peut se bloquer si aucune position n’est détenue. Un compte témoin virtuel indépendant continue la stratégie et évite ce cercle. En backtest, les comptes B/SL10 sans protection déjà calculés remplissent ce rôle ; ce sont des simulations, aucun ordre supplémentaire.
En2025, le témoin B confirme+5% le8mai, et le témoin SL10 le19mai. Le compte protégé SL10/MA50 ne le confirme que le12juin. Le signal19mai du témoin SL10 est suivi de+5,54% sur20séances dans ce même compte témoin.
Après dédoublonnage des reprises communes à plusieurs activations SPY, la condition+5% du témoin SL10 donne7reprises positives à20séances sur10dates distinctes (70%). Le critère tiré du compte réellement protégé donne5/8. Cohortes petites, activations SPY préexistantes, pas un test indépendant ou directement comparable aux dates OFF des taux.
Revenir au taux observé juste avant une protection déjà déclenchée tard peut être trop facile : après ON SPY du4mars2025, le taux B antérieur n’était que20,2%; son retour à ce faible niveau donnerait31mars, avant une nouvelle chute. La référence120 antérieure figée est plus exigeante. Aucun seuil n’a été optimisé pour éviter cet exemple.

## Conclusion

**Les taux de réussite per-symbol mûrs et la reprise d’un compte témoin virtuel sont des candidats plus encourageants pour la sortie que le seul seuil SPY. Ils ne sont pas encore validés comme fiables.** Pour l’activation, le signal du taux apparaît après une partie de la baisse et touche encore beaucoup de gains hors période. L’effet économique sur rendement/DD exige un replay dédié, non réalisé ici.
Ne pas confondre AUC des modèles, taux LONG profitable de sélections, taux gagnant des trades réellement acceptés, et fréquence de reprise positive du capital. La réussite d’amplitude Oracle n’est pas une réussite directionnelle.

Archives : `artifacts\research\us_q051_winrate_recovery_audit\20261117-v1`. Voir cohort-coverage.csv, recovery-summary.csv, activation-trade-diagnostics.csv, on-off-future-shadow-diagnostics.csv, account-return20-plus5-recovery.csv et les timelines.
Limites héritées : rétrospectif, univers contemporain, labels journaliers qualifiés parfois manquants, intraday partiel avec repliOHLC, aucun holdout nouveau ni parité live.
