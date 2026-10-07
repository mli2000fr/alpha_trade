# Sprint 12-A — Contrat d'exécution daté CN_A

## État et périmètre

Le socle d'exécution du marché CN_A est **installé dans `alpha_trade_cn`
pour la recherche historique 2018–2025**. L'audit réel a confirmé quatre
règles de board, deux profils de coûts et `markets.live_enabled = false`.
Il n'existe volontairement **aucune règle CN pour 2026** dans ce premier
jeu : la résolution doit échouer plutôt que réutiliser 2025 par défaut.
La base US `alpha_trade` et le simulateur US n'ont pas été modifiés.

Ce sprint livre le *contrat* qui prépare le Sprint 12-B, non le moteur de
backtest. Une décision `ORDER_CANDIDATE` signifie seulement qu'un ordre
respecte les contraintes de lot, budget et inventaire T+1 ; une décision
`PROXY_ELIGIBLE` signifie seulement que les données quotidiennes ne
révèlent pas de blocage évident. **Aucune des deux ne prouve un fill** :
les barres journalières et limites dérivées ne contiennent pas le carnet
ni la priorité dans la file d'ordres.

## Schéma et installation

La [migration CN 0008](../../database/sql/cn/migration_cn_0008_execution_contract.sql)
crée dans la **base CN seulement** :

| Table | Rôle |
| --- | --- |
| `market_execution_rules` | Règle par marché, MIC, board et fenêtre de validité ; lots, tick, T+1 et champ de provenance |
| `cn_execution_cost_profiles` | Frais par clé de profil et fenêtre de validité, décomposés par côté et explicitement typés `RESEARCH_PROXY` ou `VERIFIED_BROKER` |

Le nom/schéma de `market_execution_rules` reprend le contrat transversal
déjà présent dans `database/sql/market/`. La table n'avait pas été
créée dans `alpha_trade_cn`. La migration 0008 est une migration SQL
**propre à la base CN** : elle ne fait pas partie de la chaîne Alembic
US, qui pointe sur `alpha_trade`. La lancer via Alembic US serait une
erreur de base.

L'[installateur-auditeur](../../dataIntegrityEngine/cn_sprint12a_migrate.py)
vérifie `SELECT DATABASE() = 'alpha_trade_cn'` avant d'appliquer le SQL.
Il est idempotent : les tables existantes sont conservées, les clés
déjà présentes ne sont pas écrasées, puis les valeurs attendues sont
auditées. Si une ancienne ligne diverge, l'audit échoue au lieu de la
masquer. L'installation et l'audit ont été exécutés avec succès :

```powershell
F:\projets\.venv\Scripts\python.exe -m dataIntegrityEngine.cn_sprint12a_migrate --apply
F:\projets\.venv\Scripts\python.exe -m dataIntegrityEngine.cn_sprint12a_migrate
```

Le premier appel peut être rejoué sans créer de nouvelles règles. Le
second n'écrit rien. Les quatre scopes seedés sont `XSHG/SH_MAIN`,
`XSHE/SZ_MAIN`, `XSHE/CHINEXT` depuis le 01/01/2018 et
`XSHG/STAR` depuis le 22/07/2019, tous expirant le 31/12/2025.
Leurs lignes déclarent T+1, achat de 100 actions par pas sur les trois
premiers boards et minimum de 200 actions avec incrément d'une action
sur STAR. Une vente résiduelle inférieure au minimum n'est recevable
qu'en liquidation de toute la position restante, et seulement si ces
actions sont déjà vendables.

Ces lignes sont marquées `research_only` dans `metadata_json`. La
fonction de résolution les **refuse par défaut** et exige
`allow_research_rules=True`. Une future règle officielle vérifiée doit
apporter `source_type=OFFICIAL_VERIFIED` et un `source_ref` daté.
L'absence de règle, plusieurs règles actives, un MIC/board inconnu ou
un marché US provoquent une erreur explicite.

## Coûts : seulement des hypothèses de recherche

Les deux profils seedés reproduisent l'analyse du Sprint 11-B :

| Profil | Période | Commission proxy | Minimum par côté | Autres composants |
| --- | --- | --- | --- | --- |
| `cn_a_research` | 2018–2025 | 10 bps achat et vente | 5 CNY | zéro dans ce proxy |
| `cn_a_research_stress` | 2018–2025 | 25 bps achat et vente | 5 CNY | zéro dans ce proxy |

Ils ne sont **pas** une grille de courtage, de stamp duty ou de frais de
place. Leur décomposition en commission est une convention de proxy, pas
une attribution juridique du coût. Le [service de
résolution](../../service/market/cn_execution_contract.py) exige
`allow_research_proxy=True` pour les lire. Pour un backtest exécutable
plus tard, il faudra des coûts `VERIFIED_BROKER` datés, avec source,
commission/minimum, frais de transfert, taxe vendeur et slippage
justifiés ; le service calcule déjà ces composantes séparément, mais
aucune valeur réelle n'a été inventée.

## Limites, suspensions et preuve de fill

Le pourcentage `daily_price_limit_pct` des quatre règles de board est
**NULL intentionnellement**. Il serait incorrect d'appliquer un simple
10 % ou 20 % à toutes les dates : IPO, traitement spécial, board et
modifications réglementaires créent des exceptions. La table existante
`cn_daily_price_limits` fournit une ligne par instrument/date avec
`policy_code`, `locked_up`, `locked_down` et provenance ; plusieurs
de ces bornes sont **dérivées** et leur contradiction avec l'OHLC n'est
détectable qu'après la clôture. Le contrôle de séance ne les transforme
donc jamais en prédicteurs pré-entrée.

Le service refuse une barre absente, une suspension et les conflits de
statut. Il classe `UNVERIFIABLE` une limite ou un état de verrouillage
inconnu, une politique non reconnue ou une borne dérivée contredite par
l'observation. Même lorsque les données passent ces contrôles, le
résultat est `PROXY_ELIGIBLE`, **pas** `FILLED`. Le Sprint 12-B devra
définir scénarios de non-fill, report/annulation et inventaire ouvert
en fin de période, puis tenir les positions bloquées dans les comptes.

Les références officielles soutiennent la nécessité de règles par place
et période : [règles de négociation SZSE
2023](https://www.szse.cn/English/rules/siteRule/P020240911598586572526.pdf),
[mécanisme SSE](https://english.sse.com.cn/start/trading/mechanism/) et
[règles spéciales
ChiNext](https://www.szse.cn/English/rules/siteRule/P020200811392728112984.pdf).
La [révision SSE effective en juillet
2026](https://english.sse.com.cn/news/publications/newsletter/c/10819283/files/d5ad54ae74ca4cc9a54b1f98c1af50c8.html)
illustre pourquoi aucune règle 2025 n'est prolongée implicitement
en 2026. Ces sources ne remplacent pas un contrôle de l'instrument
et des conditions du courtier à la date de l'ordre.

## API et scénarios testés

Le module `service.market.cn_execution_contract` expose :

- `resolve_rule` : exactement une règle MIC/board/date, recherche sous opt-in ;
- `resolve_cost_profile` : exactement un profil/date, proxy sous opt-in ;
- `prepare_buy` : arrondi au lot et vérification **frais inclus** dans le budget ;
- `prepare_sell` : inventaire par lots/date, revente des achats du jour
  interdite, traitement conservateur du reliquat impair ;
- `estimate_cost` : commission/minimum, transfert, taxe vendeur et slippage
  en CNY, sans ambiguïté `*_usd` ;
- `assess_fill_proxy` : qualité de séance uniquement, jamais preuve de fill.

Les tests couvrent date absente (2026), marché US refusé, chevauchement
de règles, opt-in des proxies, minimum de commission, budget insuffisant
après frais, T+1, reliquat impair, suspension et politique de limite
inconnue. Ils ne prétendent pas valider des fills historiques.

## Suite réalisée au Sprint 12-B

Le contrat n'est pas branché au simulateur US. Le [replay CN
12-B](./sprint_12b_replay_portefeuille_cn.md) consomme ces règles, suit
cash et inventaire dans le temps, gère plusieurs positions et sorties
reportées, puis publie un journal détaillé d'ordres/non-fills/coûts.
Il marque les corporate actions non classifiées et les delistings sans
recouvrement vérifié comme non résolus. Aucun résultat des Sprints
11-A/11-B n'est pour autant converti en rendement net OOS de portefeuille :
le gate économique du Sprint 13 reste ouvert.
