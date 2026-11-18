# B / B + anti-SL10 — audit des alertes de marché et de stratégie

17 novembre 2026. Audit terminé, sans nouveau replay, entraînement, SQL, fournisseur/LLM, ordre ou changement de production.

## Pourquoi le rendement et le DD se dégradent

La bascule SPY a été appliquée à toutes les séances de 2021 au 1er octobre2026, pas à une fenêtre choisie après observation. Pour MA50, elle reste active sur 371/1443 séances (25,71%), dont 66,93% des séances2022 et 30% de celles de2025. Pour MA20/100, les parts2022 sont62,15/80,48%.
En2022, B+anti-SL10 sans protection gagne48,60%, contre -5,49/-11,72/-14,96% pour les bascules20/50/100. La stratégie LONG sélectionnée peut gagner pendant que SPY est baissier ; un filtre de marché coupe alors aussi ses gagnants. En2023 et2026, les rebonds sont également moins capturés.
Les reçus natifs confirment le mécanisme : pour SL10/MA50 en2022, 60 des86 décisions de budget de volatilité actif aboutissent à zéro action (69,77%). Il s’agit des vérifications actives enregistrées, pas de69,77% de tous les signaux Oracle. Les contraintes de portefeuille changent aussi les autres achats et le chemin du capital.
Le DD maximal se déplace : SL10/MA50 descend de son sommet du16février2021 au9août2022 (-39,33%), alors que le témoin a son DD maximal du11novembre2024 au7avril2025 (-34,98%). Réduire une baisse donnée ne suffit pas à réduire le DD maximal de toute la stratégie. Aucun achat nouveau n’est garanti gagnant, aucune position détenue n’est liquidée par ce commutateur.

## Données et règles contrôlées avant l’entrée

Dix mesures individuelles et deux conjonctions figées, sans recherche de seuil : SPY/SMA50 et200 ; rendement SPY20 ; volatilité SPY20 au-dessus de sa médiane126 ; part de l’univers au-dessus de SMA50<40% ; part du TOP179 Oracle avec rendement passé20 positif<50% ; momentum médian Oracle20 inférieur au SPY ; profit factor des20 dernières clôtures connues<1 ; rendement passé20 du compte<-5% ; DD du compte sur63séances>10% ; SPY<SMA50 ET PF20<1 ; pool Oracle faible ET compte<-5% sur20.
Features arrêtées à la clôture du signal J et reliées aux vrais reçus d’entrée J+1. Aucune sortie future dans la santé du compte. Égalités de préfixes : trois pour les prix et six pour la santé des comptes ; quatre tests passent, dont ordre stable de clôtures simultanées. Les cas sans données restent inconnus. Les pools sont les179 candidats causaux initiaux, avant toute qualification future.
L’audit historique du25octobre2026 sur un ancien TOP20/H20 n’avait déjà validé aucun avertissement transversal. Le présent audit vérifie les règles sur les nouveaux comptes B/H10/TOP10 exacts ; il ne constitue pas une nouvelle source indépendante d’alpha.

## Alertes sur la fenêtre demandée

Fenêtre cible des entrées : 1ernovembre2024–30juin2025. Les dates suivantes sont les premières occurrences dans cette fenêtre, pas des seuils choisis après observation : PF20 du compte SL10 faible dès8novembre ; compte en baisse20<-5% dès5décembre ; univers breadth50<40% et SPY<SMA50 dès18décembre ; SPY<SMA200 seulement10mars2025. Ces premières occurrences peuvent être brèves, et ne garantissent pas une alerte continue.
Le pool Oracle faible apparaît dès le début de la fenêtre et le5décembre se combine avec la faiblesse du compte. Il se manifeste aussi pendant des périodes profitables : ce n’est pas un détecteur spécifique de la crise2024/25.

## Compromis pertes/gains — B + anti-SL10

Statistiques sur les trades effectivement acceptés, classés par date d’entrée, avec maturité H10 commune connue au1eroctobre2026. PnL net des frais par trade ; financement non artificiellement affecté aux lots. Ce ne sont pas les rendements d’un portefeuille après filtrage.

| Alerte | Trades signalés dans la fenêtre | Pertes ciblées dans la fenêtre | Gains aussi ciblés dans la fenêtre | Gains ciblés hors fenêtre |
| --- | ---: | ---: | ---: | ---: |
| SPY sous SMA50 | 44 | 27.05% | 23.18% | 29.25% |
| Univers : moins de40% au-dessus SMA50 | 43 | 29.74% | 23.91% | 22.48% |
| Oracle : moins de50% positifs sur20séances | 92 | 71.28% | 41.86% | 59.47% |
| PF20 du compte <1 | 122 | 81.58% | 69.70% | 43.24% |
| Compte : rendement20 <-5% | 65 | 46.46% | 29.77% | 13.40% |
| Oracle faible ET compte faible | 56 | 43.55% | 24.45% | 12.26% |

Le signal Oracle faible seul distingue mieux les pertes de cette fenêtre que SPY, mais il toucherait59,47% des gains effectivement réalisés hors fenêtre. Les trades ainsi signalés hors fenêtre totalisent +10903,20$ sur ce compte. Ce chiffre mesure des opportunités du témoin, pas le capital qu’un replay filtré perdrait exactement.
La conjonction Oracle faible ET compte faible est plus ciblée : elle touche43,55% de la masse des pertes de la fenêtre et24,45% de ses gains ; hors fenêtre,9,90% des pertes et12,26% des gains. Ses trades signalés hors fenêtre restent rentables (+2714,18$ cumulés). Leur rendement net moyen est supérieur de1,18point à celui des autres trades hors fenêtre ; un veto automatique n’est donc pas validé.
Les signes annuels s’inversent. Par exemple, Oracle faible signalé−autre sur SL10 : +1,57point2022, -2,59en2023, +1,14en2024, -1,64en2025, +1,15en2026. La faiblesse peut précéder la continuation de la baisse OU un rebond profitable. Les tableaux annuels détaillés sont conservés, sans choisir le sens du filtre après coup.

## Macro et périmètre

VIX/VIX9D/VIX3M/VXN/MOVE/taux10ans sont présents dans une archive locale pour163 dates de la fenêtre. Ces lignes ont été créées en juillet2026 ; la disponibilité et le vintage exacts pour une décision2024/25 ne sont pas qualifiés ici. Elles ne sont pas présentées comme des snapshots disponibles à l’époque et ne participent pas aux règles principales. Voir macro-inventory.json. Les prix SPY/univers sont également des historiques rétrospectifs révisés, pas une certification PIT.
IWM, QQQ, RSP et les ETF de crédit ne sont pas dans la matrice figée commune à ces comptes. Aucune série nouvelle n’a été téléchargée ou inventée. Les news, options et consensus d’aujourd’hui ne sont pas rétroprojetés en2024.

## Conclusion

**Aucun indicateur audité ne valide simultanément une bonne détection de la fenêtre2024/25 et un faible coût hors de cette fenêtre.** Les mesures du pool Oracle et de la santé réelle du compte sont plus pertinentes à examiner que SPY seul, mais les observations ne justifient pas encore une règle de trading.
Un éventuel prochain replay pourrait évaluer une réduction partielle des nouvelles entrées sur la conjonction pool faible/compte faible, plutôt qu’un arrêt complet ou un budget covariance20% très contraignant. Ce serait une hypothèse supplémentaire à tester, sans promesse d’amélioration et sans seuil choisi pour épouser la période défavorable. Aucun replay de ce type n’a été lancé.

Les fichiers warning-diagnostics.csv et warning-calendar.csv séparent fenêtre cible, reste, années et données inconnues. budget-impact-by-year.csv, switch-episodes.csv et switch-max-dd-dates.csv expliquent les six simulations existantes. Ne pas soustraire des PnL de trades pour annoncer un rendement ou DD alternatif : la réallocation et le chemin du capital nécessitent un replay complet.
Limites : période choisie après observation, douze règles examinées, années déjà vues, dépendances titres/dates, univers/secteurs contemporains, intraday incomplet avec repli OHLC, échantillon de trades acceptés conditionné par le capital du témoin. Aucun holdout ou avantage causal indépendant établi.

Archives : `artifacts\research\us_q051_b_market_warning_audit\20261117-v2`.


## Audit complémentaire des sorties de protection

La sortie n'avait pas été validée séparément : règle figée de cinq clôtures SPY au-dessus de101% de MA20/50/100. Audit a posteriori uniquement, pas de nouveaux seuils ni de replay. Les résultats20 séances suivants utilisent les clôtures SPY et les capitaux des témoins B/SL10 sans protection, pas le profit causal d'une reprise du compte protégé. Échantillons faibles et dates corrélées entre moyennes.

| Moyenne | Désactivations | SPY positif20séances après | Témoin B positif20 après | Témoin SL10 positif20 après | Retour en protection sous20séances |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20 | 16 | 9/16 | 10/16 | 9/16 | 4 |
| 50 | 11 | 7/11 | 6/11 | 7/11 | 2 |
| 100 | 6 | 4/6 | 5/6 | 5/6 | 1 |

Référence descriptive : sur toutes les 1423 dates communes mûres2021–2026, SPY est positif20séances plus tard dans 65.99% des cas. Les occurrences ne sont pas indépendantes ; ce n'est pas un test statistique apparié.

Exemple de fausse reprise : OFF MA50 au signal20février2025, puis SPY -7,35% sur20séances, B -13,07% et SL10 -8,66% sur leurs comptes témoins. Réactivation8séances plus tard le4mars. Reprises postérieures : OFF MA20 le30avril (+6,40% SPY20), MA50 le13mai (+2,47%), MA100 le16mai (+1,43%). Ces exemples sont constatés après coup, sans détecteur permettant de les distinguer à l'avance. Aucun signe de sortie fiable confirmé.
