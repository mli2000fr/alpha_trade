# Sprint 18-C — Pilote shadow prospectif Oracle CN

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Objet et frontière de sécurité

Le pilote relie l'export Oracle H20 prospectif du Sprint 15-D8 au moteur d'exécution **hypothétique** du Sprint 18-B. Il ne constitue ni une stratégie directionnelle validée, ni un backtest, ni une instruction de trading. Le routeur 18-A continue d'interdire tout ordre paper/live CN. Le module `service/market/cn_shadow_runner_18c.py` n'appelle aucun broker et n'écrit dans aucune table ; ses seules sorties sont des preuves JSON sous `artifacts/research/cn_shadow_18c/`.

```text
Export Oracle D8 publié avant 09:15 Shanghai
  → échantillon déterministe de 12 titres TOP20, indépendant des scores et rendements
  → intentions BUY diagnostiques figées avant le cutoff
  → préflight des règles/coûts datés de la séance CN
  → après clôture seulement : tentatives hypothétiques avec barre et limites observées
  → séance ultérieure seulement : marque de prix, séparée de la tentative
```

Les intentions BUY ont un budget *par titre* de 10 000 CNY par défaut. Ce n'est pas un cash commun, une allocation de portefeuille ou un signal LONG profitable. La sélection par SHA-256 (`seed|date|symbole`) vise une petite population reproductible sans trier sur le score Oracle, les labels ou les performances futures. Elle n'est pas représentative de tout le TOP20 et ne saurait établir une rentabilité.

## Sources et preuve PIT

La phase `plan` lit `artifacts/research/cn_oracle_prospective_15d8/<date>/report.json` et `oracle_top20.parquet`. Elle réutilise `verify_published` : statut prospectif, empreinte de l'export, publication antérieure au cutoff, disponibilité des scores, modèle entraîné avant la date, `oracle_oos=true`, TOP20 et cardinalité sont contrôlés. Elle associe les codes BaoStock aux `instrument_id` CN via `instrument_provider_symbols` et `instruments` en lecture seule, refuse mapping ambigu, devise ou MIC incohérent, puis passe chaque intention au pré-contrôle 18-B. Le fichier de plan est créé exclusivement et conserve la date/heure de création, le cutoff, la provenance Oracle, les identités et empreintes des intentions. `load_frozen_plan` revérifie l'export et la sélection avant toute tentative ; les preuves ne sont pas réécrites rétroactivement.

La phase `preflight` requiert **exactement une** règle `market_execution_rules` valide pour chaque couple MIC/board présent dans l'échantillon et **exactement un** profil `cn_execution_cost_profiles` `cn_a_research` valide pour la date. Zéro ou plusieurs lignes bloquent toute la cohorte (`BLOCKED_CONTRACT`), sans fill partiel. La phase `attempt` exige en plus les opt-in séparés `--allow-research-rules` et `--allow-research-proxy` si les données sont de recherche. Elle attend la clôture de `market_sessions`, puis lit les barres brutes canoniques, les limites et les facteurs non résolus disponibles à l'instant de l'observation. Les états de 18-B (`NOT_FILLED`, `UNVERIFIABLE`, `HYPOTHETICAL_FILL`, etc.) gardent leur sens strictement simulé ; le prix d'ouverture lu après clôture n'était pas un prix garanti à l'ouverture.

La phase `mark` n'accepte qu'une séance ultérieure clôturée et une preuve de tentative existante. Elle compare le close ultérieur aux fills hypothétiques. Elle ne prouve pas un ordre exécuté, ne calcule pas un PnL réalisé et ne remplace ni les coûts de sortie ni un replay de portefeuille. Les barres et limites manquantes produisent une observation non vérifiable, pas un rendement imputé.

## Contrat 2026 installé pour la recherche

La [migration CN 0009](../../database/sql/cn/migration_cn_0009_execution_contract_2026_shadow.sql) ajoute quatre lignes de règles pour XSHG/SH_MAIN, XSHG/STAR, XSHE/SZ_MAIN et XSHE/CHINEXT, valides **du 6 juillet au 31 décembre 2026**. La borne de début correspond à l'entrée en vigueur des révisions [SSE](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml) et [SZSE](https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html). L'achat se fait par pas de 100 actions pour les boards principaux et ChiNext, avec minimum 200 puis pas d'une action pour STAR ; tick A-share de 0,01 CNY, inventaire non revendable le jour de l'achat et short désactivé dans ce pilote. Les règles demeurent `research_only=true`. Leurs limites de prix générales restent **NULL** : les exceptions IPO, ST, suspensions et limites individuelles doivent être lues dans les données titre/séance. Les règles 2018–2025 restent inchangées ; aucun contrat janvier–juin 2026 n'a été inventé. [Mécanisme STAR SSE](https://english.sse.com.cn/start/trading/mechanism/), [règles SZSE 2026](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf).

Le nouveau profil `cn_a_research` 2026 est **`RESEARCH_PROXY`**, jamais `VERIFIED_BROKER` : 10 bps de commission par côté avec minimum 5 CNY, 0,1 bp de frais de transfert par côté, 5 bps de taxe côté vente et 2 bps de slippage par côté. La commission et le slippage sont des **hypothèses** de recherche, non le tarif d'un compte. Les frais de place intégrés à la commission ne sont pas ajoutés une seconde fois. Les composantes publiques sont rapprochées du [guide SSE](https://one.sse.com.cn/onething/gptz/) et du [barème SZSE 2026](https://investor.szse.cn/marketServices/deal/payFees/index.html). Ce profil n'est pas suffisant pour un backtest net vérifié ou pour le live.

L'[installateur-auditeur](../../dataIntegrityEngine/cn_sprint18c_contract_2026.py) refuse toute autre base que `alpha_trade_cn`, contrôle `markets.live_enabled=false`, applique les insertions dans une transaction et vérifie valeurs, périodes, provenance, unicité et type proxy. Une deuxième application a été testée sans doublons. Elle n'active aucun routage broker.

## État réel au 1er octobre 2026

Le plan pour la séance du **8 octobre 2026** a été figé à partir de l'export D8 prépublié : **12 titres** sélectionnés et `QUEUED`, sous `artifacts/research/cn_shadow_18c/plans/2026-10-08.json`. La date du 8 octobre suit les congés du 1er au 7 octobre selon le calendrier CN configuré. Après installation et audit de la migration 0009 dans `alpha_trade_cn`, le préflight réel renvoie **`READY_FOR_RESEARCH_ATTEMPT`**, sans raison bloquante. `markets.live_enabled` reste `false`. **Aucune tentative, marque ou transaction n'a été produite** ; seules les cinq lignes de contrat 2026 ont été ajoutées en base CN. Les règles 2018–2025 du Sprint 12-A ne sont pas prolongées tacitement.

Le blocage contractuel est levé **pour la recherche uniquement**. La phase tentative attendra les observations canoniques post-clôture du 8 octobre et une reprise manuelle selon le [TODO 18-C](./TODO_sprint_18c_post_cloture_2026_10_08.md). Il n'y a **pas de batch planifié**.

La phase supplémentaire `observation-preflight` inspecte en lecture seule les 12 barres et leurs statuts **seulement après la clôture canonique** ; elle affiche manques et anomalies par intention, sans écrire de tentative et avec `authorizes_attempt=false`. Au 01/10, elle retourne normalement `WAITING_FOR_SESSION` pour le 08/10. Les contrats seuls restent `READY_FOR_RESEARCH_ATTEMPT` ; ce statut n'atteste pas encore les observations de marché.

## Commandes de recherche, sans activation automatique

Depuis `F:\projets` :

```powershell
python -m service.market.cn_shadow_runner_18c --phase preflight --decision-date 2026-10-08
```

Le plan de cette date existe déjà ; relancer `--phase plan` doit refuser l'écrasement. Si et seulement si le contrat 2026 a été qualifié et les barres du 8 octobre sont disponibles **après clôture**, le protocole permet la tentative de recherche :

```powershell
python -m service.market.cn_shadow_runner_18c --phase attempt --decision-date 2026-10-08 --allow-research-rules --allow-research-proxy
```

Pour une séance ultérieure déjà clôturée, la marque est distincte :

```powershell
python -m service.market.cn_shadow_runner_18c --phase mark --decision-date 2026-10-08 --mark-session 2026-10-09
```

Ces commandes n'installent aucun service, ne soumettent aucun ordre et ne changent aucune donnée de marché. Ne pas interpréter un éventuel `HYPOTHETICAL_FILL` comme une performance de la direction Oracle : l'Oracle prédit l'amplitude, pas LONG.

## Tests et limites connues

`tests/test_cn_shadow_runner_18c.py` vérifie le plan pré-cutoff, le refus d'écraser, l'empreinte et la sélection figées, le blocage par contrat manquant, les opt-in recherche, l'interdiction avant clôture, une tentative hypothétique et une marque ultérieure sur fixture synthétique. Les suites 18-B, 18-A et 12-A/B restent couvertes séparément.

`tests/test_cn_sprint18c_contract_2026.py` vérifie aussi les quatre boards, les périodes bornées, les opt-in, la décomposition des coûts, le refus d'une règle divergente et l'absence de commutateur live dans la migration.

Ce pilote ne donne pas d'estimation de slippage d'ouverture, de capacité réelle, de liquidité au premier cours, de short, de frais de sortie ou de rendement portefeuille. Les observations post-clôture servent à **auditer une hypothèse d'exécution**, jamais à reconstruire un signal pré-ouverture. Une décision de déploiement demanderait des preuves économiques et opérationnelles additionnelles indépendantes du pilote.
