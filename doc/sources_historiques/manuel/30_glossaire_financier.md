# 30. Glossaire financier

> Définitions volontairement simples, en français, illustrées.
> Triées par ordre alphabétique.

## A

**Action (stock / equity)** — Titre représentant une fraction du capital
d'une entreprise. Acheter 1 action AAPL = devenir copropriétaire (très
minoritaire) d'Apple.

**Alpaca** — Broker américain en ligne, gratuit, avec une API permettant à
l'application d'envoyer automatiquement des ordres. Compte « paper »
gratuit pour tester.

**Alpha** — Performance d'une stratégie **au-delà** du marché. Si SPY
(indice S&P 500) fait +10 % et votre stratégie +13 %, votre alpha est
+3 %.

**ATR (Average True Range)** — Indicateur de **volatilité** : moyenne sur
N jours de l'amplitude (high − low) ajustée des gaps. Sert à dimensionner
les stops.

**AUC** — Métrique d'un modèle ML (entre 0.5 et 1.0). 0.5 = aléatoire,
0.7 = bon, 0.9 = excellent.

## B

**Backtest** — Simuler une stratégie sur l'historique pour mesurer ses
performances passées.

**Bar / OHLCV** — Pour une période donnée (jour, heure…) : Open
(ouverture), High (haut), Low (bas), Close (clôture), Volume.

**Beta** — Mesure de sensibilité au marché. Beta = 1 → bouge comme le
marché. Beta = 1.5 → bouge 1.5× plus.

**bps (basis points)** — 1 bp = 0.01 %. 25 bps = 0.25 %.

**Broker** — Intermédiaire qui exécute vos ordres en bourse (ex. Alpaca,
IBKR, Bourse Direct).

## C

**CAGR (Compound Annual Growth Rate)** — Taux de croissance annualisé
composé. Si vous passez de 1 000 € à 1 600 € en 4 ans : CAGR = +12.5 %/an.

**Candidate** — Une action retenue par le Selector comme « digne d'intérêt
pour les prochains jours ».

**Cash account** — Compte broker sans levier. Pas de marge.
Le capital y est réutilisable selon les règles de settlement du broker.

**Champion / challenger** — En ML, le modèle actuel en production
(champion) vs les modèles concurrents (challengers).

**Commission** — Frais facturés par le broker à chaque ordre. Ex. Alpaca
US : 0 USD. IBKR Tiered : ~1 USD.

**Conviction score** — Score combiné (technique + ML + sentiment) calculé
par le module Risk.

**Corporate action** — Événement modifiant les titres d'une entreprise :
dividende, split, spin-off, fusion.

**Corrélation** — Mesure (entre -1 et +1) de la similitude des
mouvements. 2 actions à 0.95 montent et descendent presque ensemble.

## D

**Day trade** — Acheter et revendre **le même jour**.

**Dividende** — Versement de l'entreprise à l'actionnaire (ex. 0.50 $/an
par action AAPL).

**Drawdown** — Perte temporaire depuis un sommet. Si votre capital monte
à 2 500 € puis redescend à 2 100 €, votre drawdown est de 16 %.

**Drawdown maximum (Max DD)** — Pire drawdown observé sur la période.
Indicateur clé de la « douleur » d'une stratégie.

## E

**Equity** — Valeur totale du compte (cash + valeur des positions).

**EODHD** — End Of Day Historical Data, fournisseur de données
historiques + fundamentals (abonnement payant).

**ETF** — Fonds indiciel coté en bourse (ex. SPY = ETF S&P 500).

**Ex-date** — Date à partir de laquelle l'action se traite « ex-dividende »
(sans le droit au dividende à venir).

## F

**Facteur (factor)** — Caractéristique mesurable d'une action : momentum,
value, qualité, taille, volatilité…

**Fill** — Exécution réelle d'un ordre par le broker.

**FinBERT** — Modèle d'IA de type BERT spécialisé sur le langage
financier. Sert à scorer le sentiment des news (positif / neutre /
négatif).

**Final score** — Score de 0 à 100 attribué par le Selector à chaque
candidat (basé sur les facteurs).

**Fingerprint** — Hash SHA256 court permettant d'identifier de manière
unique une configuration (preset, modèle…).

**Fractional shares** — Possibilité d'acheter une fraction d'action
(ex. 0.3 action GOOGL). Supporté par Alpaca, pas par tous les brokers.

## K

**Kelly criterion** — Formule mathématique optimisant la taille de
position selon win rate et payoff. Très agressive — souvent appliquée à
1/4 (« quarter Kelly »).

**Kill switch** — Bouton d'urgence qui annule **tous** les ordres ouverts.

## L

**Leverage / margin** — Trading à crédit. Permet de prendre plus de
position que le capital, mais multiplie les pertes. **Inadapté débutant.**

**Live trading** — Mode argent réel.

**Long** — Position acheteuse (vous gagnez si le cours monte).

## M

**Margin call** — Appel de marge : le broker exige que vous remettiez du
cash sinon vos positions sont liquidées.

**Market cap** — Capitalisation boursière = prix × nb d'actions. Petit
< 2 Md$, moyen 2-10 Md$, grand > 10 Md$, méga > 200 Md$.

**Momentum** — Tendance d'un cours à continuer dans la même direction. La
stratégie de l'app est principalement momentum.

## O

**OCO (One Cancels Other)** — Couple d'ordres dont l'exécution de l'un
annule l'autre (ex. take-profit + stop-loss).

**Ordre limite** — Ordre conditionnel : « acheter à max X $ ».

**Ordre marché** — Ordre exécuté immédiatement au meilleur prix
disponible.

**Overfitting** — Modèle ML trop ajusté à l'historique : excellent en
backtest, médiocre en live.

## P

**Paper trading** — Trading simulé avec faux argent chez le broker.
**Étape obligatoire** avant le live.

**Payoff ratio** — Gain moyen / perte moyenne. Cible > 1.5.


**P&L (Profit & Loss)** — Gain ou perte.

**Position** — Quantité d'actions détenues sur un symbole.

**Preset (capital preset)** — Bouquet de paramètres calibrés pour une
tranche de capital (ex. `capital_0_2000`).

**Probability long** — Probabilité (0-1) calculée par le ML que le cours
atteigne le seuil de hausse cible dans l'horizon.

## R

**R-multiple** — Unité = montant risqué initial. Trade à +3R = gain 3× le
risque.

**Réconciliation** — Vérification que les positions DB locale ↔ broker
correspondent.

**RSI (Relative Strength Index)** — Oscillateur 0-100. > 70 = sur-acheté,
< 30 = sur-vendu.

**Rebalancing** — Ajuster les positions vers un portefeuille cible.

## S

**Sandbox** — Environnement de test isolé.

**Selector** — Module qui sélectionne les top 15-50 candidats par
momentum.

**Sentiment** — Score (-1 à +1) calculé sur les news par FinBERT.

**Sharpe ratio** — Performance / volatilité. > 1 bien, > 2 excellent.

**Sortino ratio** — Variante de Sharpe ne pénalisant que la volatilité
**baissière**. > 1.5 = bon.

**Slippage** — Différence entre prix attendu et prix d'exécution réel.
Plus l'ordre est gros, plus il est élevé.

**Split** — Division d'une action (ex. split 2-for-1 : 100 actions à
200 $ → 200 actions à 100 $).

**Spread** — Différence ask − bid. Plus c'est large, plus c'est cher de
trader.

**SPY** — ETF S&P 500, benchmark de référence.

**Stop-loss** — Ordre auto de vente si le cours touche un seuil bas.

**Swing trade** — Trader sur quelques jours à quelques semaines (par
opposition au day trading et au long-terme buy & hold).

## T

**Take-profit (TP)** — Ordre auto de vente à un seuil haut pour empocher
le gain.

**Ticker / symbole** — Code court d'une action (AAPL, MSFT, NVDA…).

**Trailing stop** — Stop qui « monte » avec le cours.

## V

**VCP (Volatility Contraction Pattern)** — Pattern technique de Mark
Minervini : contraction de volatilité avant cassure haussière.

**Volatilité** — Amplitude des variations de prix.

**Volume** — Nombre d'actions échangées sur une période.

## W

**Walk-forward** — Méthode de backtest rigoureuse en fenêtres glissantes
train → val → test. Défense contre l'overfitting.

**Watcher** — Processus 24/7 qui supervise les ordres protecteurs chez le
broker.

**Win rate** — % de trades gagnants. Une stratégie peut être profitable
même à 35 % si le payoff est élevé.

---

> Pour les termes techniques de l'application (run_id, fingerprint…),
> voir [31_glossaire_application.md](31_glossaire_application.md).

