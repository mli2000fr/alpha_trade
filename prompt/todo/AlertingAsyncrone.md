# Système d'Alerte Asynchrone — Alerting & Notifications

> **Date** : 2026-06-22
> **Statut** : ⚠️ Infrastructure existante mais sous-exploitée — un seul événement déclencheur
> **Verdict** : L'architecture d'alerting est bien conçue (multi-canal, best-effort), mais **seul le circuit breaker l'utilise**. Tous les autres événements critiques sont silencieux.

---

## 1. La question posée

> *L'application dispose d'une interface Streamlit (pour une consultation humaine passive). Cependant, pour une application de production autonome, il manque cruellement un système d'alerte actif (comme des webhooks Slack, Discord ou des SMS via Telegram) pour vous notifier instantanément en cas d'anomalie critique.*

---

## 2. Ce qui existe — une architecture d'alerting bien conçue

### 2.1 ✅ Module d'alerting multi-canal

**Fichier** : `service/alerting.py`

Architecture propre avec protocole `Notifier` :

| Canal | Classe | Configuration | Statut |
|---|---|---|---|
| **Slack** | `SlackNotifier` | `ALPHA_TRADE_SLACK_WEBHOOK` (env var) | ✅ Implémenté |
| **Email SMTP** | `EmailNotifier` | `ALPHA_TRADE_SMTP_HOST/_TO/_FROM` (env var) | ✅ Implémenté |
| **Log (fallback)** | `LogNotifier` | Toujours disponible | ✅ Implémenté |
| **Telegram** | — | — | ❌ Non implémenté |
| **Discord** | — | — | ❌ Non implémenté |
| **SMS (Twilio)** | — | — | ❌ Non implémenté |

Détection automatique des canaux disponibles :

```python
def build_notifiers_from_env(env=None) -> tuple[Notifier, ...]:
    channels = []
    if webhook := os.getenv("ALPHA_TRADE_SLACK_WEBHOOK"):
        channels.append(SlackNotifier(webhook_url=webhook))
    if smtp_host and smtp_to and smtp_from:
        channels.append(EmailNotifier(...))
    if not channels:
        channels.append(LogNotifier())
    return tuple(channels)
```

Chaque notifier est **best-effort** : si Slack échoue, fallback sur le log. Aucun échec d'alerting ne bloque le trading.

### 2.2 ✅ Notification circuit breaker (le seul événement)

**Fichier** : `risk_management/circuit_breaker.py` → `_try_send_alert()`

```python
def _try_send_alert(event: str, payload: dict) -> None:
    # Email (historique)
    from ihm.services.email_notifier import send_notification
    send_notification(event=event, payload=payload)

    # Multi-canal (Slack / SMTP / log)
    if event == "circuit_breaker_fired":
        from service.alerting import send_system_alert
        send_system_alert(event="CIRCUIT_BREAKER_FIRED", payload=payload, severity="critical")
```

Déclenché par `notify_if_active()` — anti-doublon via signature hash.

### 2.3 ✅ Notifications de fin de workflow pipeline

**Fichier** : `ihm/services/notifications.py`

Envoie un email quand un workflow pipeline se termine (complété, échoué, timeout). Inclut le tail des logs pour diagnostic.

### 2.4 ✅ Interface Streamlit de supervision

**Fichier** : `ihm/pages/supervision_ops.py`

Dashboard passif montrant :
- État des services (watcher, pipeline, risk, exécution)
- Heartbeats (stale détecté)
- Derniers runs critiques
- Alertes synthétiques

⚠️ **Consultation passive uniquement** — il faut ouvrir l'IHM pour voir les problèmes.

---

## 3. Ce qui MANQUE — les événements non couverts

### 3.1 🔴 Aucune alerte sur les pannes API

Les appels à EODHD, Finnhub, Alpaca peuvent échouer silencieusement :

```python
# Nulle part dans le code :
send_system_alert("API_EODHD_DOWN", {"error": "Connection timeout"}, severity="critical")
send_system_alert("API_ALPACA_AUTH_FAILED", {"error": "401 Unauthorized"}, severity="critical")
```

**Impact** : si EODHD est down pendant 2h, les prix ne sont pas mis à jour, le scanner ne trouve pas de candidats, mais **personne n'est notifié**.

### 3.2 🔴 Aucune alerte sur le cash ledger

Le désalignement du cash ledger (J+1 settlement, cash vs positions) est une anomalie critique qui peut passer inaperçue :

```python
# Aucune alerte de type :
send_system_alert("CASH_LEDGER_MISALIGNMENT", {
    "settled_cash": 5000.0,
    "unsettled_cash": 12000.0,
    "market_value": 8000.0,
    "expected_equity": 25000.0,
    "reported_equity": 22000.0,
    "delta": -3000.0,
}, severity="critical")
```

### 3.3 🔴 Aucune alerte sur les heartbeats stale

Le watcher de protections peut s'arrêter (crash, redémarrage Windows) :

```python
# Aucune alerte de type :
send_system_alert("WATCHER_STALE_HEARTBEAT", {
    "service": "execution_protection_watch",
    "last_heartbeat": "2026-06-22T08:00:00",
    "age_seconds": 1200,
    "threshold_seconds": 600,
}, severity="critical")
```

### 3.4 🟡 Aucune alerte précoce (early warning)

Le circuit breaker alerte quand il est **déjà déclenché** (drawdown > 15%). Il n'y a pas d'alerte préventive :

```python
# Aucune alerte de type :
if drawdown > 0.10 and drawdown < 0.15:
    send_system_alert("DRAWDOWN_APPROACHING", {
        "drawdown_pct": 12.5,
        "threshold_pct": 15.0,
    }, severity="warning")
```

### 3.5 🟡 Pas d'intégration Telegram/Discord

Telegram est le canal idéal pour le trading algorithmique :
- Gratuit, instantané
- Fonctionne sur mobile sans configuration email
- Supporte les messages formatés (Markdown, code blocks)
- API Bot simple (HTTP POST)

### 3.6 🟡 Pas d'alerting sur les jobs schedulés

Si Task Scheduler Windows ou NSSM ne lance pas un job, aucune notification.

---

## 4. Couverture des événements critiques

| Événement | Détecté ? | Alerté ? | Canal |
|---|---|---|---|
| Circuit breaker (drawdown > 15%) | ✅ | ✅ | Email + Slack + Log |
| Circuit breaker (perte quotidienne > 5%) | ✅ | ✅ | Email + Slack + Log |
| Perte quotidienne approchant le seuil (> 4%) | ✅ | ❌ | — |
| API EODHD down | ⚠️ Exception loggée | ❌ | — |
| API Alpaca auth failed | ⚠️ Exception loggée | ❌ | — |
| API Finnhub down | ⚠️ Exception loggée | ❌ | — |
| Cash ledger désaligné | ❌ | ❌ | — |
| Watcher heartbeat stale | ✅ (IHM) | ❌ | — |
| Pipeline step failed | ✅ (IHM) | ✅ (fin de workflow) | Email |
| Slippage > seuil (TCA) | ✅ (log) | ❌ | — |
| Kill switch activé | ✅ | ❌ | — |
| Corporate action détectée | ✅ (log) | ❌ | — |
| ML model drift | ⚠️ (drift policy) | ❌ | — |
| Stale quotes (> N heures) | ❌ | ❌ | — |
| Univers de trading vide | ✅ (log) | ❌ | — |

**Taux de couverture : 2/15 événements critiques sont alertés (13%)**

---

## 5. Plan d'action

### Priorité 1 (immédiat) : Ajouter Telegram + élargir les déclencheurs

**Fichier à créer** : `service/alerting.py` — ajouter `TelegramNotifier`

```python
@dataclass
class TelegramNotifier:
    """Envoie un message via Telegram Bot API."""
    bot_token: str
    chat_id: str
    timeout_seconds: float = 5.0
    fallback: Notifier | None = None

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
        text = f"{emoji} *{subject}*\n```\n{body}\n```"
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=self.timeout_seconds)
            if resp.status_code >= 300:
                raise RuntimeError(f"Telegram HTTP {resp.status_code}")
        except Exception as exc:
            LOGGER.warning("[alerting] Telegram send failed: %s", exc)
            if self.fallback:
                self.fallback.send(subject, body, severity=severity)
```

**Configuration** : `ALPHA_TRADE_TELEGRAM_BOT_TOKEN` + `ALPHA_TRADE_TELEGRAM_CHAT_ID` (env vars).

### Priorité 2 (immédiat) : Brancher `send_system_alert()` sur les événements critiques

Ajouter des appels à `send_system_alert()` dans :

| Fichier | Événement | Severity |
|---|---|---|
| `dataIntegrityEngine/sync_latest_quotes.py` | API EODHD/Finnhub down | `critical` |
| `service/alpaca/clientAlpaca.py` | Auth failed / API down | `critical` |
| `execution_engine/executor.py` | Kill switch activé | `critical` |
| `execution_engine/executor.py` | Slippage > seuil | `warning` |
| `risk_management/circuit_breaker.py` | Drawdown approche le seuil (≥ 80% du seuil) | `warning` |
| `ihm/services/ops_supervision.py` | Heartbeat stale > N secondes | `critical` |
| `selector/` | Univers de trading vide | `warning` |
| `modelFactory/drift_policy.py` | Model drift détecté | `warning` |

### Priorité 3 (court terme) : Alerting cash ledger

**Fichier** : `execution_engine/` ou `risk_management/`

Ajouter une vérification quotidienne de cohérence :

```python
def check_cash_ledger_consistency(
    settled_cash: float,
    unsettled_cash: float,
    market_value: float,
    reported_equity: float,
    tolerance_pct: float = 0.01,  # 1%
) -> None:
    computed_equity = settled_cash + unsettled_cash + market_value
    delta_pct = abs(computed_equity - reported_equity) / reported_equity
    if delta_pct > tolerance_pct:
        send_system_alert("CASH_LEDGER_MISALIGNMENT", {
            "computed_equity": computed_equity,
            "reported_equity": reported_equity,
            "delta_pct": round(delta_pct * 100, 2),
        }, severity="critical")
```

### Priorité 4 (moyen terme) : Dashboard Grafana + alertes

Compléter les tâches S5.4 et S5.5 (actuellement NOT_STARTED) :
- Métriques Prometheus exposées par l'app
- Dashboard Grafana avec graphiques de santé
- Alertes Grafana pour les métriques (ex: `api_error_rate > 5%`)

### Priorité 5 (long terme) : Discord webhook

Ajouter `DiscordNotifier` sur le même modèle que `SlackNotifier` (structure de webhook similaire).

---

## 6. Comparaison : IHM passive vs Alerting actif

| Capacité | IHM Streamlit | Alerting (actuel) | Alerting (cible) |
|---|---|---|---|
| Voir l'état du système | ✅ Dashboard | ❌ | ✅ Push |
| Détecter un circuit breaker | ✅ (si connecté) | ✅ Email+Slack | ✅ +Telegram |
| Savoir si EODHD est down | ❌ | ❌ | ✅ Push immédiat |
| Être réveillé la nuit | ❌ | ❌ | ✅ Telegram mobile |
| Recevoir une alerte sans ouvrir l'app | ❌ | ⚠️ Email seulement | ✅ Multi-canal |
| Anti-doublon (pas de spam) | — | ✅ Signature hash | ✅ Idem |
| Historique des alertes | ✅ Logs IHM | ❌ | ✅ Journal alerting |

---

## 7. Synthèse

| Point | Statut |
|---|---|
| Architecture Notifier (multi-canal) | ✅ Bien conçue |
| Slack webhook | ✅ Implémenté |
| Email SMTP | ✅ Implémenté |
| Log fallback | ✅ Implémenté |
| Notification circuit breaker | ✅ Seul événement alerté |
| Notification fin de workflow | ✅ Implémenté |
| **Telegram** | ❌ **Absent — priorité 1** |
| **Discord** | ❌ Absent |
| **Alertes API down** | ❌ **Absent — priorité 2** |
| **Alertes cash ledger** | ❌ **Absent — priorité 3** |
| **Alertes précoces (early warning)** | ❌ Absent |
| **Alertes heartbeat stale** | ❌ Absent |
| **Grafana + Prometheus** | ❌ NOT_STARTED (S5.4, S5.5) |

### Verdict

L'infrastructure d'alerting est **bien architecturée** mais **dramatiquement sous-utilisée**. Le module `service/alerting.py` est prêt à l'emploi avec Slack, Email et Log — mais **une seule ligne de code** l'appelle (`circuit_breaker.py` L59).

Le problème n'est pas l'absence de capacité technique, c'est l'absence d'**intégration** dans les points de défaillance du système. Il faut brancher `send_system_alert()` partout où une anomalie critique peut survenir, et ajouter Telegram pour les notifications mobiles instantanées.

**Effort estimé** : 2-3 jours pour P1+P2 (Telegram + brancher les 8 événements critiques).
