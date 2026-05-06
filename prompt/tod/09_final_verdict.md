# 09 — Verdict final

## 1. Note globale

| | |
|---|---|
| **Note globale Alpha Trade au 2026-05-06** | **6.4 / 10** |
| Niveau de confiance | **Élevé** |
| Verdict | **solide / quasi-pro partiel** |

## 2. Positionnement

| Référence | Position Alpha Trade |
|---|---|
| Application amateur sérieuse (4-5/10) | ✅ dépassé |
| Application indépendante avancée (6-7/10) | ✅ **positionnement actuel** |
| Application pro buy-side / prop / desk swing (8-9/10) | ⚠️ pas encore — gaps documentés |
| Application institutionnelle très mature (9.5+/10) | ❌ hors cible court terme |

## 3. Forces majeures (à préserver)

1. Architecture modulaire propre, séparation `service`/`core`/`database`/
   modules métier nette.
2. Pipeline complet et auditable de la donnée brute jusqu'à l'ordre broker
   réconcilié, avec lineage et idempotence.
3. Couverture de tests sérieuse sur les zones critiques (~190 fichiers).
4. Capital presets riches sur 6 tranches.
5. Multi-comptes Alpaca correctement modélisé.
6. EODHD bulk EOD comme provider primaire bien conçu (quota tracker, cache
   disque, circuit breaker, cross-check Stooq).

## 4. Faiblesses majeures (à corriger sous 4-6 semaines)

1. **3 anomalies P0** (incohérences doc/config sur provider OHLCV et CA) qui
   trompent l'opérateur — corrigeables en 1 sprint.
2. **Circuit breaker non branché par défaut** sur PnL réel — potentiellement
   inactif en production.
3. **Backtest non vérifié** sur l'inclusion ledger dividendes.
4. **Check env multi-comptes incomplet** dans `run_execution.py`.
5. **Petit compte** sous-investissable sans télémétrie sizing.
6. **Modules massifs** (`_execution_center.py`, `alpha_scanner.py`,
   `executor.py`) — dette technique à apurer.

## 5. Conditions de passage en swing trading réel discipliné

L'application **n'est pas prête** en l'état. Elle le devient à l'issue
**du Sprint S3 inclus** (cf. `08_sprint_plan.md`), soit ~4 semaines
d'effort développement, à condition que les tests P0/P1 associés soient
verts en CI.

À l'issue de S3, la note projetée est **7.4 / 10** : pleinement
exploitable pour swing US discipliné, sur petit ou grand compte.

## 6. Conditions pour revendiquer un niveau pro-grade

- Sprint S6 (refactor IHM) atteint → 8.0/10 (quasi pro-grade).
- Sprint S9 (parité backtest/live formalisée + alerting externe) atteint →
  8.5+/10 (pro-grade partiel revendiqué).
- Travaux additionnels (multi-broker, DR, mutation testing, formal
  verification) au-delà → 9.0+/10.

## 7. Recommandations pour la direction technique

1. **Geler les nouveautés fonctionnelles tant que les sprints S1 à S3 ne
   sont pas terminés.** Les contradictions doc/config actuelles sont un
   risque opérationnel concret.
2. **Bloquer le passage live** par un check formel en CI vérifiant les
   tests P0/P1 verts.
3. **Documenter publiquement la convention canonique** (`doc/`) une fois
   alignée — c'est le principal obstacle à la confiance d'un
   utilisateur/auditeur externe.
4. **Investir dans la parité backtest/live formalisée** (S9) : c'est le
   meilleur ratio confiance/coût pour passer pro-grade.

## 8. Conclusion

Alpha Trade est une plateforme **manifestement bien pensée et bien testée**,
construite par une équipe sérieuse. Sa qualité technique est **au-dessus du
niveau amateur sérieux** mais **en deçà du niveau buy-side professionnel**.
Les obstacles à franchir pour passer pro-grade sont **circonscrits,
identifiés, et tous adressables en 4-12 semaines** avec le plan de sprints
proposé.

Le verdict ferme : **solide / quasi-pro partiel**, **prêt swing trading
réel discipliné après Sprint S3 inclus**, **pro-grade revendiquable après
Sprint S9 inclus**.

