Nouvelle expérience research-only : persistent_top10_dip_reclaim

Objectif

Tester si attendre une confirmation de reprise du prix après un DIP améliore encore la qualité du signal LONG.

Hypothèse :

GlobalRank reste TOP10% plusieurs jours
+
le prix baisse suffisamment pour former un DIP
+
ensuite le prix récupère une partie ou la totalité du DIP
=>
probabilité plus élevée d'être un vrai bon TOP futur

Aucun changement modèle / risk / PROD.

Baseline DIP déjà validée en diagnostic

Utiliser :

N = 4
X = 2%

Détection du DIP à la date J :

global_rank_20 >= 0.90
pendant J, J-1, J-2, J-3

ET

close[J] / close[J-4] - 1 <= -0.02

Définir :

start_price = close[J-4]
dip_price   = close[J]
dip_size    = start_price - dip_price
Variante P1 — DIP direct

Contrôle :

DIP détecté à J
-> signal LONG à J
-> entrée selon contrat PROD à J+1
Variante P2 — 50% RECLAIM

Après détection du DIP à J, ne pas entrer immédiatement.

Attendre une date future T > J telle que :

reclaim_level_50 =
dip_price + 0.50 * (start_price - dip_price)

et :

close[T] >= reclaim_level_50

Ajouter comme condition que le titre reste encore :

global_rank_20 >= 0.90

à la date T.

Signal calculé au close T.
Entrée au prochain open T+1 selon le contrat PROD.

Variante P3 — 100% RECLAIM

Même logique, mais attendre :

close[T] >= start_price

donc récupération complète du niveau précédant le DIP.

Exiger également :

global_rank_20[T] >= 0.90

Signal au close T, entrée T+1.

Horizon maximum d'attente

Ne pas attendre indéfiniment.

Pour le premier test, utiliser un seul plafond pré-spécifié :

max_wait = 10 séances

Si aucun reclaim n'a lieu dans les 10 séances suivant J :

signal_expired = true
aucune entrée

Ne pas faire de sweep sur 5/7/10/15/20 jours dans cette première expérience.

Important — éviter le look-ahead

Toute décision à T utilise uniquement les données disponibles jusqu'au close T.

Aucun usage de future_return, oracle_decile ou prix futurs dans la décision.

Diagnostics à produire

Comparer :

P0 = TOP10 GlobalRank simple
P1 = DIP N4/X2 direct
P2 = DIP + 50% reclaim
P3 = DIP + 100% reclaim

Pour chaque variante :

n_signals
signals_per_month
reclaim_rate
expired_rate
median_wait_days
mean_wait_days

Puis, à partir de la vraie date d'entrée :

D1 ... D10
BAD5
GOOD5
D10%
D1%
GOOD5-BAD5
mean forward return
median forward return
P(return > 0)
PF
MFE
MAE
Mesurer le coût du retard

Très important :

return_consumed_before_entry

= mouvement réalisé entre le prix du DIP et le prix au moment du reclaim.

Puis :

remaining_forward_return
remaining_MFE
remaining_MAE

Le but est de vérifier si le reclaim améliore la qualité sans consommer trop du rebond.

Diagnostic central

Comparer :

P(D10 | DIP direct)
P(D10 | DIP + 50% reclaim)
P(D10 | DIP + 100% reclaim)

et :

P(D1 | ...)
BAD5
GOOD5

Hypothèse attendue :

reclaim plus strict
-> D1/BAD5 ↓
-> D10/GOOD5 ↑

mais potentiellement :

fréquence ↓
rendement restant ↓
Critère GO

Un reclaim est intéressant seulement s'il améliore simultanément :

BAD5 ↓
GOOD5 ↑
D1 ↓
D10 maintenu ou ↑
PF ↑ ou stable

avec :

fréquence encore exploitable
rendement restant après entrée encore significatif

Ne pas retenir une variante seulement parce qu'elle a un meilleur win-rate si elle supprime presque toutes les entrées.

Pas de tuning supplémentaire

Pour cette expérience, tester uniquement :

DIP = N4 / X2%
RECLAIM = 50% et 100%
max_wait = 10 séances

Ne pas ajouter d'autres seuils tant que ce test n'est pas terminé.