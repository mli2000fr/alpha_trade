# 51. Dépannage

## 1. « Ma page est vide »

| Cause | Solution |
|---|---|
| DB non connectée | Cliquez sur 🔧 dans la sidebar, ressaisissez les credentials. |
| Pipeline jamais lancé | Page Pipeline → lancez le workflow complet. |
| Step source en échec | Page Supervision Ops → identifiez le step rouge → relancez-le. |
| Filtres IHM trop stricts | En haut de la page, élargissez score min, secteurs, etc. |
| Date erronée | Vérifiez `trade_date` en haut de la page. |

## 2. « Base de données indisponible »

### Vérifications

```powershell
# Tester la connexion MySQL
mysql -u alpha -p alpha_trade
# si OK : tapez EXIT
```

### Causes courantes

| Cause | Solution |
|---|---|
| Service MySQL arrêté | Démarrer : `Get-Service MySQL80 \| Start-Service` |
| Mauvais credentials dans `.env` | Modifier `LOGIN_DB` / `PASSWORD_DB` |
| Base `alpha_trade` inexistante | `CREATE DATABASE alpha_trade CHARACTER SET utf8mb4;` |
| Migration alembic non passée | `alembic upgrade head` |
| Port 3306 bloqué (pare-feu) | Ouvrir le port 3306 |

## 3. Erreurs Alpaca

### « 401 Unauthorized »

Mauvais `ALPACA_API_KEY` / `_SECRET`. Régénérez-les sur
<https://alpaca.markets> → API Keys.

### « 403 Forbidden »

Vous tentez d'utiliser une clé paper sur l'URL live (ou inverse).
Vérifiez `ALPACA_BASE_URL` :
- Paper : `https://paper-api.alpaca.markets`
- Live  : `https://api.alpaca.markets`

### « Order rejected: insufficient settled cash »

Le compte cash n'a plus assez de cash settled pour couvrir l'achat.
Attendez le settlement `T+1` après une vente, réduisez la taille de l'ordre,
ou vérifiez le budget disponible dans la page Execution.

### « Order rejected: insufficient buying power »

Manque de cash. Vérifiez le buying power dans la page Execution.

## 4. Erreurs EODHD

### « 401 Invalid token »

Token absent ou faux. Vérifiez `EODHD_API_TOKEN` dans `.env`.

### « Quota exceeded »

Vous avez dépassé votre quota mensuel. Solution :
- attendre la fin du mois,
- ou passer à un abonnement supérieur,
- ou désactiver les steps qui consomment EODHD.

## 5. Watcher

### Le watcher est rouge

Relancez :
```powershell
cd F:\projets
.\.venv\Scripts\Activate.ps1
python execution_engine/protection_watcher.py
```

Laissez la fenêtre ouverte (le watcher tourne tant que la fenêtre vit).

### Le watcher tombe régulièrement

Logs : `log/protection_watcher.log`. Causes fréquentes :
- coupure réseau,
- API Alpaca down (vérifier <https://status.alpaca.markets>),
- Windows met l'ordi en veille → installer une garde anti-veille
  (cf. `common/windows_sleep_guard.py`).

## 6. Pipeline

### Step 2 (import bars) extrêmement lent

- Vérifiez votre débit Internet.
- Basculez sur EODHD (`market_data.bars_provider: eodhd` dans
  `config.yaml`).

### Step 9 (ML train) plante

- Mémoire insuffisante : réduisez `max_workers` (Settings → ML).
- GPU non détecté : passez `accelerator: cpu` dans Settings.
- Données insuffisantes : `rebuild-all` → augmentez la période historique.

### Pipeline bloqué « running » depuis > 4h

1. Page **🛟 Supervision Ops** → notez le PID.
2. Tuez le process Windows :
   ```powershell
   Stop-Process -Id <PID> -Force
   ```
3. Page Pipeline → bouton « Marquer comme failed » sur ce run.
4. Relancez juste le step bloqué.

## 7. Erreurs Python / pip

### `ModuleNotFoundError: No module named 'streamlit'`

Le venv n'est pas activé. Tapez :
```powershell
cd F:\projets
.\.venv\Scripts\Activate.ps1
```

### `Microsoft Visual C++ 14.0 is required`

Installez les **Build Tools for Visual Studio** :
<https://visualstudio.microsoft.com/visual-cpp-build-tools/>.

## 8. IHM Streamlit

### « Hello, please wait... » qui ne charge jamais

Rafraîchissez la page (F5). Si le problème persiste, redémarrez
l'application :
1. `Ctrl+C` dans la fenêtre PowerShell.
2. `python run.py`.

### Cache obsolète

Sidebar → menu hamburger (☰) → **Clear cache** → **Rerun**.

## 9. Logs — où chercher

| Module | Fichier |
|---|---|
| IHM | sortie console PowerShell |
| Pipeline runs | `artifacts/ihm_pipeline_runs/<run_id>/run.log` |
| Backtesting | `artifacts/ihm_backtesting_runs/<run_id>/run.log` |
| Watcher | `log/protection_watcher.log` |
| Pipeline backend | `log/pipeline.log` |

## 10. Aide ultime

Si rien ne marche :
1. Notez le **message d'erreur exact**.
2. Notez le **step concerné**.
3. Rassemblez les logs des 5 dernières minutes.
4. Consultez la documentation technique :
   - [doc/runbook_24_7.md](../backup/runbook_24_7.md)
   - [doc/runbook_provider_incident.md](../backup/runbook_provider_incident.md)
5. En dernier recours : ouvrez une issue sur le dépôt en joignant logs +
   contexte.

