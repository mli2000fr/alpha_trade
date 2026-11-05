# Formulaire Winner : défauts du test de référence

Depuis le 5 novembre 2026, les nouveaux formulaires Winner utilisent les
réglages suivants, demandés pour rapprocher la configuration du test H10 à
+130,57 %. Les autres réglages continuent à venir de la configuration chargée.

| Bloc | Champ | Défaut |
|---|---|---|
| Réglages Winner et limites du replay | Clôtures 5m de confirmation | 0 |
| Même bloc | Entrée journalière à l’ouverture J+1 | Cochée |
| Même bloc | Retard SIP accepté (secondes) | 0 |
| Dimensionnement et limites du portefeuille | Poids maximal par position (%) | 20 |
| Drawdown, pertes quotidiennes et volatilité | Liquider des positions au déclenchement du coupe-circuit | Décoché |
| Formulaire Winner | Appliquer le contrôle factoriel de production | Décoché |
| Drawdown, pertes quotidiennes et volatilité | Appliquer le contrôleur DD / perte quotidienne / B4 | Décoché |
| Formulaire Winner | Type de compte simulé | margin |
| Formulaire Winner | Exposition brute maximale | 2× si autorisé par la configuration de levier, sinon 1× |
| Dimensionnement et limites du portefeuille | Plafond d’exposition brute du risque (× capital) | 2,00 |

Les choix margin/2× ont leur propre initialisation unique pour les sessions déjà
ouvertes ; les modifications manuelles suivantes sont conservées. Ce défaut
sélectionne le levier demandé. Le plafond indépendant `risk.max_gross_exposure`
du formulaire est désormais également à 2,00 par défaut : la limite effective
reste la plus contraignante des réglages de levier et de risque. Aucun paramètre
de production n'est augmenté.
Le défaut 2× est une demande ultérieure de l'utilisateur ; l'ancien résultat
+130,57 % utilisait 1×.

### Autoriser réellement 2× dans un backtest Winner

Le champ **Plafond d’exposition brute du risque (× capital)** est modifiable
dans **Dimensionnement et limites du portefeuille**. Sa valeur initiale est
**2,00×** ; les anciennes sessions ouvertes passent une seule fois à ce défaut,
puis les modifications manuelles sont conservées. Pour autoriser
200 % du capital courant : régler ce champ sur **2,00**, sélectionner le type
de compte **margin** et **Exposition brute maximale = 2×**. L'écran affiche
le plafond combiné ; le risque, le compte et la configuration de levier
continuent à appliquer la limite la plus contraignante. Avec un compte cash
ou un levier autorisé à 1×, demander 2× au risque ne crée aucun emprunt.

Le champ est transmis dans `winner_risk_overrides.max_gross_exposure`, validé
entre 0 exclus et 2 inclus, appliqué à la copie de risque du run, puis borné
par le levier autorisé. Commande, protocole et rapport conservent ces choix.
Le rappel production réinitialise ce champ à la valeur chargée en configuration ;
le rappel du test de référence le remet à 2,00.
Ni `config.yaml`, ni les comptes de production, ni les anciens rapports ne sont
modifiés. Une capacité de 2× ne force pas son utilisation : dimensionnement,
titres déjà détenus et règles de répétition des entrées restent applicables.

La migration de l'écran retire une seule fois les anciennes valeurs mémorisées
de ces six champs, y compris pour une session déjà ouverte. Les modifications
manuelles suivantes sont conservées. **Reprendre les réglages de production**
recharge les valeurs de configuration et active le contrôleur ; **Reprendre les
réglages du test de référence** restaure les défauts ci-dessus. Ces boutons ne
modifient pas `config.yaml`.

## Effet du nouvel interrupteur

Décoché : pas de blocage des nouvelles entrées pour DD/perte quotidienne, pas de
réduction de l'allocation par B4, ni de liquidation associée au coupe-circuit.
La case de liquidation et les champs de seuil sont alors grisés. Le replay
continue à calculer le drawdown réalisé dans ses courbes et son rapport.

Le dimensionnement, les limites de positions/capital, la concentration, les
contrôles de données et les protections par position (SL/TP/trailing/horizon)
restent actifs selon leurs réglages. La cible de volatilité reste une option
distincte. Désactiver ce contrôleur ne désactive donc pas tout le module risque.

La désactivation utilise un contrôleur inactif **propre au backtest** ; elle
n'augmente pas artificiellement les seuils et ne modifie ni `CircuitBreaker`,
ni `CampaignRiskState`, ni les paramètres de production. Une liquidation globale
hard/cycle explicitement demandée dans le même replay est incompatible et
refusée, au lieu d'être ignorée.

Cocher réactive le contrôleur natif et sa politique configurée ; la liquidation
reste réglée par sa propre case. L'état actif/inactif et la liquidation effective
figurent dans `protocol.json` et `report.json`, sous `drawdown_controller`.

## Commande et compatibilité

Le formulaire transmet `--no-drawdown-controller` par défaut, ou
`--drawdown-controller` lorsque la case est cochée. `BacktestRunOptions` et
`BacktestConfig` portent `winner_drawdown_controller_enabled`.

Les anciennes commandes sans ce paramètre conservent le contrôleur **activé**,
comme auparavant. Les anciens rapports/runs ne sont pas réécrits. Le chemin
SHORT reste isolé, conformément à la décision précédente.

## Limite de la comparaison au +130,57 %

Le nouveau mode journalier décrit ci-dessous aligne l'heure et la source de
prix de l'entrée initiale. Les autres différences de protocole et de couverture
demeurent : il ne remplace pas tout le replay par l'ancien moteur de recherche.
Mode journalier décoché, confirmation zéro retire l'attente du signal mais
l'ordre standard peut encore attendre son plafond de prix intraday.

Le résultat +130,57 % concernait les modèles de recherche annuels et la période
2024–19 octobre 2026, pas le nouveau modèle 2022. Aucun nouveau rendement ni
backtest économique n'est produit par cette évolution d'écran.

## Univers du modèle sélectionné automatiquement

Le champ **Univers Winner**, juste sous les dates, est **grisé et non modifiable**.
Il affiche le nombre de titres enregistré dans le contrat du batch choisi.
Changer de modèle sélectionne automatiquement son univers, avec ou sans
per-symbol. Les anciennes valeurs de fichier mémorisées dans le formulaire
sont ignorées ; le bouton de reprise de l'univers a été supprimé.

Le formulaire transmet `--symbol-source model-universe`. Le replay utilise
directement la liste figée dans le contrat, sans dépendre du contenu actuel
d'un fichier externe et sans en créer un nouveau. La source, le nombre,
les symboles et leur empreinte sont conservés dans `protocol.json.universe_resolution`.
Un univers de modèle absent, invalide ou dupliqué est refusé explicitement.

Les anciennes commandes `universe-file:...` restent utilisables hors IHM et
conservent leurs contrôles. Pour un univers différent dans le formulaire,
choisir un modèle entraîné sur cet univers. **Top N Oracle** change la taille
du classement, pas celle de l'univers d'entraînement. Aucun modèle, fichier,
N/X/Y, seuil LONG ou ancien run n'est modifié par ce choix automatique.

## Dates de signal nécessaires à une année de backtest

La période saisie décrit les séances d'exécution. Un achat à l'ouverture J+1
nécessite les scores de J : par exemple le premier achat de 2023, le 3 janvier,
utilise le signal du **30 décembre 2022**. Lancer ML Predict uniquement sur les
dates calendaires 2023 laisse donc cette première séance sans signal.
Il faut inclure la dernière séance précédant la première entrée demandée,
avec le même batch et des poids disponibles avant la date du signal. Le replay
valide la couverture et la traçabilité ; il ne saute pas silencieusement la
première séance et ne calcule pas de prédictions avec écriture SQL dans son
exécution isolée. Le message d'erreur précise désormais cette règle J→J+1.

## Seuil LONG per-symbol avant les achats

Lorsque **per-symbol** est coché, le formulaire propose **Score LONG minimum —
strictement supérieur**, par défaut **0,60**, sous les choix TOP N / TOP X / TOP Y.
Le pool Oracle est figé, puis les TOP X LONG sont classés, puis seuls les scores
**strictement supérieurs** au seuil sont retenus. À 0,60, un score 0,6000 est
exclu et 0,6001 passe. Aucun rang suivant n'est promu après ce filtre.
Le filtre ne déclenche pas la vente des positions déjà détenues et ne modifie
pas leurs protections ou renforcements. Il n'ajoute aucun SHORT automatique.

Commande : `--per-symbol-min-long-probability 0.6`. Le choix est enregistré dans
`protocol.json.per_symbol_selection.min_long_probability` et les paramètres du
rapport. `per-symbol-ranking.csv` conserve les scores, les rangs initiaux,
`long_selected_before_threshold`, `long_threshold_passed`, `long_score_threshold`
et le motif `LONG_SCORE_NOT_ABOVE_THRESHOLD`. `signals.csv` ne contient que
les candidats retenus après ce filtre, avant les refus du risque/détention.
Une séance sans candidat au-dessus du seuil ne produit aucune nouvelle entrée.

Le défaut 0,60 appartient à l'IHM ; les appels Python/CLI existants sans ce
nouveau paramètre restent sans seuil. Le pipeline et le trading réel ne sont
pas modifiés. Aucun modèle n'est réentraîné et aucun avantage économique de ce
seuil n'est supposé sans comparaison séparée.

## Entrée journalière à l'ouverture J+1

Dans **Réglages Winner et limites du replay**, la case **Entrée journalière à
l'ouverture J+1** est cochée par défaut. Le signal de J produit un seul essai
d'achat à l'ouverture de la prochaine séance officielle, week-ends et jours
fériés exclus. Le prix provient de `open_df`, issu des cours journaliers
canoniques avec la préférence de fournisseur du projet. Ni les clôtures 5m de
confirmation, ni un plafond limite intraday, ni le délai SIP ne déclenchent ou
ne retardent cet achat initial. Un refus n'est pas reporté dans la journée.

Les candidats sont traités dans leur classement, avec le capital partagé,
les frais, le dimensionnement sur le SL Winner, les plafonds de risque et le
levier autorisé. Les titres déjà détenus ne sont pas rachetés. Les contrôles
factoriels et le contrôleur DD restent applicables s'ils sont activés. Une
demi-position reste une demi-position ; le renforcement, s'il est activé,
conserve ses confirmations et son délai de disponibilité.

**Correctif du raccordement, 5 novembre 2026 : aucune lacune intraday future
ne peut exclure une entrée journalière.** L'horizon commence au fill effectif.
La journée J n'a pas besoin de bougies intraday pour préparer l'achat J+1.
En mode journalier, le filtre rétrospectif des lacunes et le rattrapage
fournisseur sont désactivés, même si une ancienne commande les demande.

Les protections utilisent une séance 5m complète, valide et cohérente avec la
base journalière (écart d'ouverture au plus 1 %). Sinon, **toute la séance du
titre est traitée sur les OHLC daily**, sans interpolation ni conversion de
split inventée. Cela traite aussi une absence totale de bougies 5m. Un cours
journalier d'ouverture valide reste nécessaire pour l'achat ; capital,
dimensionnement et contrôles de risque restent applicables.

- Gap : exécution sur l'ouverture daily ; le SL ne garantit pas son prix.
- SL/TP durant la séance : plus bas/plus haut daily ; collision inconnue,
  SL prioritaire. Le résultat n'est enregistré et le cash réutilisable qu'à la
  clôture, borne de temps explicite, sans inventer l'heure du franchissement.
- Trailing : ancien stop testé d'abord ; plus haut daily utilisé seulement à
  la clôture pour un nouveau stop effectif à l'ouverture suivante.
- Renforcement : aucune confirmation 5m inventée sur une séance daily ; il
  peut reprendre sur une séance intraday qualifiée ultérieure.
- Horizon : vente sur l'ouverture daily de la séance prévue, même sans 5m.
- DD/B4, si activé : contrôles sur les valorisations effectivement connues.
  Une liquidation concernant un titre sans prix intraday exécutable attend
  l'ouverture officielle suivante ; elle ne vend pas à un ancien cours.
- Si daily **et** intraday sont inutilisables pour protéger une position déjà
  détenue, arrêt explicite du run ; aucune position ni perte n'est effacée.

Les séances utilisées sont dans `daily-protection-fallback.csv`, les logs et
`report.json.protection_resolution`. `entry_excluded=false` signifie que ce
repli n'a pas filtré le signal, pas que tous les autres contrôles ont accepté
un achat. Le statut peut rester « couverture incomplète » car l'exécution
intraday n'est pas connue. Les anciens runs ne sont pas recalculés.
Cela reste une simulation OHLC, sans carnet ni slippage spécifique à l'enchère.

Le formulaire transmet `--daily-entry`; décocher transmet `--no-daily-entry`.
Le champ `winner_daily_entry_enabled` est propre au backtest. Les appels et
commandes antérieurs sans option gardent leur mode intraday. `protocol.json`
et `report.json` mémorisent `initial_entry`, et les fills portent
`execution_proxy=DAILY_SESSION_OPEN`. Le bouton de réglages de production
désactive ce mode ; celui du test de référence le réactive. Aucun paramètre de
production, ordre réel ou ancien run n'est modifié.

## Capital engagé moyen dans les détails du run

Le résumé détaillé affiche **Capital engagé moyen** en dollars et **Engagement
moyen / capital du compte** en pourcentage. L'engagement est l'exposition brute
valorisée : montants absolus des positions LONG et SHORT additionnés. Les
observations sans position sont incluses. Le pourcentage est la moyenne des
ratios exposition/equity observés, pas le montant moyen divisé par le capital
initial. Il peut dépasser 100 % avec levier.

Les anciens rapports Winner portent déjà `average_gross_capital` et
`average_gross_equity_ratio` : l'écran les utilise sans relancer le backtest.
Les nouveaux rapports les reprennent aussi dans `summary`, avec une base de
mesure `REGULAR_5M_MARKS`. Pour les backtests classiques, le montant provient
des `daily_leverage_snapshot.current_gross_notional`, sur les observations
quotidiennes avant entrées (`DAILY_BEFORE_ENTRIES`). Une donnée absente apparaît
comme « — » ; elle n'est pas estimée depuis les trades ou le capital initial.

Avec repli daily, la base devient `MIXED_5M_AND_DAILY_KNOWN_MARKS` : le prix
d'ouverture connu est conservé pendant la séance, puis remplacé par la clôture
disponible. Ces relevés ne prétendent pas reproduire l'equity intraday inconnue.
Le DD sur ce périmètre est celui des prix observables, pas le pire creux
intraday possible. `equity-5m.csv` indique `daily_fallback_positions`.
