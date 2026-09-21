# Sprint 6 — Socle de données CN gratuit avec BaoStock

## 1. Décision et état

Le premier chemin opérationnel Chine d’Alpha-Trade repose désormais sur des sources gratuites :

```text
BaoStock
  → source primaire du socle de marché
  → aucune clé API
  → staging brut dans alpha_trade_cn

AKShare
  → enrichissement futur, facultatif et non bloquant
  → chaque endpoint devra être validé séparément

RQData
  → essai ou contrôle croisé futur
  → aucune dépendance du chemin gratuit

Tushare
  → connecteur conservé mais désactivé
  → aucune variable TUSHARE_TOKEN requise
```

Le 22 septembre 2026, le smoke réel BaoStock a passé le gate : 16 requêtes,
9 040 observations reçues et persistées, zéro échec. Le nombre comprend le référentiel
complet retourné par BaoStock et le sous-ensemble borné de cinq titres utilisé pour les séries.

Le staging reste isolé dans `alpha_trade_cn`. La publication vers des tables canoniques,
l’entraînement ML et le backtest CN restent volontairement désactivés pendant ce sprint.

## 2. Objectif fonctionnel

Le socle gratuit doit suffire à répondre à la première question de recherche :

> Peut-on détecter, sur les actions A chinoises, les titres qui réaliseront un mouvement
> absolu important à H5, H10, H15 ou H20 ?

Il ne cherche pas encore à répondre de manière fiable à :

> Le mouvement extrême sera-t-il D1 ou D10 ?

L’Oracle Extreme est un modèle d’amplitude. Il peut donc être entraîné avant la disponibilité
des données directionnelles payantes.

## 3. Périmètre réellement fourni

### 3.1 Référentiel

L’endpoint logique `stock_basic` collecte :

- le code BaoStock (`sh.600000`, `sz.000001`) ;
- le nom ;
- la date d’introduction ;
- la date de sortie lorsqu’elle existe ;
- le type d’instrument ;
- le statut courant.

Le connecteur conserve uniquement les symboles `sh.*` et `sz.*` pour les séries actions.
BaoStock ne couvre pas correctement la Bourse de Pékin dans le contrat actuellement validé.
`CN_BJ` reste donc hors du socle gratuit initial.

### 3.2 Calendrier

`trade_cal` collecte les dates et l’indicateur de séance ouverte. Le calendrier sert ensuite à :

- construire les horizons en séances plutôt qu’en jours civils ;
- empêcher les labels décalés pendant les jours fériés ;
- déterminer la disponibilité prudente des données ;
- aligner les splits Walk-Forward.

### 3.3 Barres quotidiennes

`daily` conserve dans le brut :

- open, high, low, close et previous close ;
- volume et montant échangé ;
- taux de rotation ;
- variation en pourcentage ;
- statut de négociation ;
- indicateur ST ;
- drapeau d’ajustement retourné par BaoStock.

Les prix demandés sont non ajustés (`adjustflag=3`). Les facteurs sont collectés séparément afin
de garder le choix entre prix bruts, prix ajustés et reconstruction historique reproductible.

### 3.4 Ajustements

`adj_factor` conserve les facteurs avant, arrière et le facteur publié par BaoStock dans le
payload brut. Le champ structuré `adjustment_factor` reçoit le facteur fournisseur principal.
La promotion canonique devra vérifier la convention par des cas de dividende et de split avant
de produire les prix ajustés destinés au ML.

### 3.5 Statuts ST et suspension

Les barres quotidiennes transportent `tradestatus` et `isST`. Le staging normalise :

| Valeur | Signification |
|---|---|
| `TRADE` | titre négociable selon BaoStock |
| `SUSPENDED` | absence de négociation signalée |
| `TRADE\|ST` | titre coté sous régime ST |
| `SUSPENDED\|ST` | titre ST suspendu |

Ces informations seront des contraintes d’éligibilité du backtest, et non de simples features.

### 3.6 Indices de référence

Le socle collecte actuellement :

- Shanghai Composite : `sh.000001` ;
- Shenzhen Component : `sz.399001` ;
- CSI 300 : `sh.000300` ;
- ChiNext : `sz.399006`.

Ils permettront de calculer force relative, beta, résidu marché, dispersion et régimes.

## 4. Architecture d’exécution

```text
batch_cn.yaml
    │
    ▼
dataIntegrityEngine.cn_provider_ingestion
    │
    ├── provider=baostock ──► service/baostock
    │                            ├── client
    │                            ├── symboles
    │                            ├── adaptateurs
    │                            └── reprise
    │
    └── provider=tushare ───► connecteur historique désactivé
                                 │
                                 ▼
                         alpha_trade_cn
                         ├── cn_ingestion_runs
                         ├── cn_raw_payloads
                         ├── cn_staging_rows
                         └── cn_staging_quality_metrics
```

La migration `0003_provider_neutral_staging` renomme les anciennes tables spécifiques :

```text
tushare_raw_payloads  → cn_raw_payloads
tushare_staging_rows → cn_staging_rows
```

Elle conserve les données existantes et rend `provider` réellement discriminant.

## 5. Contrat PIT et lineage

Chaque appel stocke :

- le run et le batch ;
- le fournisseur ;
- l’endpoint logique ;
- la requête et son hash ;
- la réponse brute et son hash ;
- l’instant d’observation ;
- l’instant de disponibilité retenu ;
- les lignes normalisées ;
- une clé métier et le hash de chaque révision.

Deux exécutions identiques gardent chacune leur preuve brute, mais une ligne métier strictement
identique n’est pas dupliquée dans le staging. Une correction fournisseur produit une nouvelle
révision parce que son hash change.

Pour le backfill historique des prix, `available_at` représente l’instant de collecte et non la
preuve de l’heure de publication historique. Le futur dataset canonique appliquera une règle
prudente de disponibilité à la séance suivante pour éviter toute fuite intrajournalière.

## 6. Batchs disponibles

| Batch | Rôle | Activation |
|---|---|---|
| `cn_baostock_smoke` | cinq titres et période courte | manuel avec `--force` |
| `cn_master_calendar_sync` | référentiel et calendrier | désactivé jusqu’à décision d’exploitation |
| `cn_daily_market_data_sync` | J−10/J, facteurs et indices | désactivé jusqu’à décision d’exploitation |
| `cn_historical_backfill` | historique depuis 2010 | manuel et reprenable |
| `cn_staging_quality_daily` | qualité du staging | après première collecte significative |
| `cn_akshare_enrichment` | enrichissements futurs | bloqué par validation endpoint par endpoint |
| `cn_tushare_optional` | essai futur | désactivé, token facultatif |

Tous restent désactivés dans `batch_cn.yaml` afin qu’une installation des tâches ne déclenche pas
accidentellement un backfill lourd. Le lancement manuel reste possible.

## 7. Commandes opérateur

### Installation et migration

```powershell
F:\projets\.venv\Scripts\python.exe -m pip install -r requirements.txt
F:\projets\.venv\Scripts\python.exe -m service.tushare.bootstrap_database --upgrade --audit
```

Le nom historique du module de bootstrap est conservé pour compatibilité. Il audite désormais les
tables neutres et attend la révision `0003_provider_neutral_staging`.

### Smoke réel borné

```powershell
F:\projets\.venv\Scripts\python.exe -u scripts\smoke_baostock_cn.py
```

Rapport :

```text
artifacts/audits/market_integration/sprint_06/real_provider_smoke.json
```

### Audit du gate

```powershell
F:\projets\.venv\Scripts\python.exe -u scripts\audit_sprint6_cn.py
```

### Backfill historique

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_provider_ingestion `
  --job cn_historical_backfill --force
```

Le backfill peut durer. L’état de reprise est stocké dans :

```text
artifacts/cn/baostock/state/cn_historical_backfill.json
```

## 8. Limites connues

BaoStock ne remplace pas les familles directionnelles suivantes :

- historique PIT profond des révisions d’analystes ;
- Dragon and Tiger List détaillée et flux institutionnels attribués ;
- historique complet de verrouillage/rupture de limites et file d’ordres ;
- enchères et carnet d’ordres ;
- données robustes pour Beijing Stock Exchange.

AKShare ne doit pas être utilisé silencieusement comme source de secours. Ses endpoints peuvent
reposer sur des sites tiers et changer sans préavis. Chaque famille nécessitera :

1. un smoke depuis la France ;
2. la conservation du payload brut ;
3. une validation de profondeur historique ;
4. une règle `available_at` ;
5. un test de dérive du schéma ;
6. une décision explicite avant activation.

RQData n’est pas considéré comme gratuit en exploitation. Une éventuelle période d’essai servira
uniquement au contrôle croisé ; le pipeline ne doit pas cesser de fonctionner à son expiration.

## 9. Étapes ML après promotion canonique

La campagne Oracle sera menée séparément pour H5, H10, H15 et H20 :

```text
univers PIT éligible
→ features prix/volume/volatilité/gap/force relative
→ labels d’amplitude absolue
→ Walk-Forward strict
→ TOP20 prédit
→ mesure du rappel des extrêmes réels
→ stabilité par semestre, secteur et régime
```

Les premières features prévues sont :

- rendements et trajectoires J−5/J−10/J−20 ;
- ATR et volatilités multi-horizons ;
- gap overnight et position dans le range ;
- accélération volume/montant/turnover ;
- distance aux moyennes et aux extrêmes ;
- résidu face au CSI 300 ou à l’indice approprié ;
- dispersion et breadth du marché ;
- statut ST, suspension récente et ancienneté de cotation.

La direction D1/D10 restera une expérience séparée. Aucun résultat Oracle d’amplitude ne devra
être présenté comme une preuve de direction.
