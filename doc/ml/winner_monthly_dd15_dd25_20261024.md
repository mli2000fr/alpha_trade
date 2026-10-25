# Winner — sélection mensuelle, DD15 partiel / DD25 total

## Variante additionnelle autorisée : stop20 et reprise après trois mois

Deux séries distinctes de dix comptes sont désormais demandées. La série
`hard25` conserve la règle décrite ci-dessous. La série `cooldown20` ajoute :

- liquidation totale au DD de cycle de **20 %**, avant le cap global25 ;
- trois **mois calendaires** de pause à partir de la date new-yorkaise de
  liquidation effective (fin de mois ramenée au dernier jour du mois cible) ;
- reprise à la première ouverture officielle à cette date ou après ;
- capital restant, aucun apport ; référence du cycle et épisode B4 réinitialisés ;
- **pic et DD globaux jamais effacés** : le cap global25 demeure définitif ;
- anciens plans annulés ; à la reprise, seul le signal de la dernière séance
  clôturée peut être réadmis, puis confirmation 5m et risque ordinaires.

Les seuils 15 %/20 % du cycle sont calculés depuis le pic de ce cycle.
Le seuil 25 % est toujours calculé depuis le pic de l'ensemble du compte.
Un gap franchissant20 et25 directement provoque l'arrêt global définitif,
pas une pause autorisant ensuite à contourner la limite. Frais et gaps réels
du replay restent comptabilisés, sans écrêter artificiellement les pertes.
Après un premier cycle4000→3200, le plancher global correspondant à25 %
reste3000 : la référence locale repart à3200 mais pas le bilan global.

Commande : même lanceur, `--variant hard25` ou `--variant cooldown20`.
Le second dossier est
`artifacts/research/us_winner_monthly_selector/20261024-dd15-cycle20-pause3m-global25-v2`.
Chaque série recalcule ses propres six shadows et choix mensuels ; aucune
courbe issue de l'autre règle de risque n'est mélangée aux choix30/50.
Les rapports incluent les liquidations de cycle, dates limites de pause,
reprises et pic global conservé ; les tests couvrent une reprise réelle
après trois mois, un jour férié US, le changement d'heure et les fins de mois.

## Décision figée le 24 octobre 2026

Le replay antérieur appliquait le sizing B4 mais pas la liquidation globale
configurée. Ses chiffres ne constituent donc pas une mesure de cette liquidation.
À la demande utilisateur, huit calculs ont été stoppés, superviseurs compris.
Les résultats déjà terminés sont préservés, pas mélangés aux nouvelles sorties.
Reçu : `artifacts/operations/winner-force-close-stop-20261024-v1/report.json`.

Le seuil total initialement envisagé à 20 % est **remplacé par 25 %** :

- À **15 % de DD**, liquidation partielle de **50 % du nombre de positions**,
  arrondi natif `max(1, int(n * 0.5 + 0.5))`, en commençant par les plus mauvais
  PnL latents en dollars. Positions entières, pas moitié de chaque ligne ni
  nécessairement moitié du capital. Un seul déclenchement par épisode B4,
  pas une division par deux répétée à chaque bougie. B4 conserve ses règles
  de reprise et son allocation réduite ; les protections individuelles restent.
- À **25 % de DD**, liquidation du solde, annulation des plans en attente,
  interdiction d'entrées/renforcements jusqu'à la fin du compte simulé.
  Pas de remise à zéro mensuelle, annuelle ou après quelques jours.
- Référence : plus haut historique observé de l'equity, positions ouvertes
  comprises. Fenêtre roulante de référence explicitement mise à zéro dans
  cette expérience, pour éviter qu'un ancien pic disparaisse du contrôle.

Cela n'arrête donc pas définitivement au premier franchissement de 15 %.
En revanche 25 % est une borne de déclenchement, **pas une perte maximale garantie**.
Gaps, frais et délai au prochain prix exécutable peuvent l'excéder.

## Exécution causale

Le contrôle voit les ouvertures connues et les clôtures de bougies achevées,
jamais leur futur high/low. Une clôture déclenche une demande, exécutée à
l'ouverture régulière suivante disponible, y compris la séance suivante.
À l'ouverture, stops et sorties MOO préexistants sont résolus avant la
liquidation : réconciliation des quantités, annulation confirmée des protections,
vente du seul solde. Frais normaux 8 pb par jambe et cash réellement débité/crédité.
Pas de vente rétroactive à la clôture ayant révélé le dépassement.
Une annulation non confirmée ou une quantité incohérente interrompt le replay.

Le DD du tableau historique reste calculé sur les clôtures de bougies 5m ;
`global_liquidation.max_observed_drawdown_pct` inclut aussi les ouvertures vues
par le contrôle. Ces deux mesures peuvent différer. Aucun plafonnement artificiel
du DD ou du prix n'est appliqué.

## Dix comptes relancés, pas les anciennes grilles

Nouveau dossier :
`artifacts/research/us_winner_monthly_selector/20261024-dd15-dd25-v2`.

Six comptes shadow depuis juillet 2019 jusqu'à fin 2024, avec les six profils
préexistants : SL5/H20 sans TP/trailing ; même profil avec trailing15 ;
SL5/H20/TP20 ; SL3/TR10/H10/TP7 ; SL5/TR15/H15 ; SL7/H20 sans TP/trailing.
Ils appliquent tous DD15/DD25, comme les quatre comptes évalués depuis 2020 :
`MONTHLY_30`, `MONTHLY_50`, `FIXED_REFERENCE`, `FIXED_TRAILING15`.

Choix mensuel fondé uniquement sur les 30/50 derniers rendements de clôture
déjà observables, positions ouvertes valorisées et frais inclus. Si un shadow
a atteint le hard stop, sa courbe reste en cash : conséquence du protocole,
pas relance ou financement artificiel pour améliorer son classement.

Chaque compte : 4 000 USD initiaux, TOP20 d'origine, position complète,
sans renforcement, vingt places, dix entrées par titre/180 jours, cap brut 1x.
Le profil d'une position financée reste figé ; un plan non tenté ne prolonge
pas son expiration lors du changement mensuel. Risque/corrélation/secteurs
et frais hérités sont conservés hors amendement explicite DD/force-close.

Les archives du prédécesseur sont réutilisées **sans lecture ni écriture SQL**,
sans téléchargement, LLM, entraînement ou ordre. Les empreintes antérieures
des deux sources moteur modifiées ont été sauvegardées et vérifiées avant édition.
Le nouveau protocole enregistre l'amendement et les nouvelles empreintes.
La configuration YAML de production n'est pas changée pour imposer le hard25.

## Validation et suivi

Lanceur : `python -u -m scripts.research.us_winner_monthly_drawdown_20261024 --variant hard25`.
Phases : `--phase prepare`, `--phase smoke --smoke-sessions 20`, `--phase run`.
Qualification technique : **180 tests passent** (reçu JUnit conservé dans chaque
dossier scellé). Les courts replays sur les archives ne comptent pas comme
des comptes terminés de l'expérience. Les anciens rapports restent séparés.
Le smoke borné n'est jamais compté comme un résultat complet de l'étude.
`progress.json` indique compte courant et séances ; les dix rapports sont écrits
dans `cases/<compte>/report.json`. Chaque compte terminé contient cash/frais,
trades, courbes 5m/jour, événements, profils et `breaker-5m.parquet`.
Les ventes globales ont le motif `GLOBAL_DRAWDOWN` et sont contrôlées séparément
des sorties scalaires SL/TP/trailing/horizon. Une liquidation finale en attente
ne peut pas être déclarée complète. `annual-summary.csv` et
`cumulative-summary.csv` sont produits après les dix comptes.

Limites : périodes déjà examinées, univers survivant, secteurs actuels non PIT,
sélection conditionnée par couverture future commune et corporate actions,
OHLC plutôt que bid/ask/fills historiques. **Pas de parité live complète ni
de nouvel avantage démontré avant les résultats.**
