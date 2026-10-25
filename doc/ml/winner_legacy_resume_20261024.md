# Reprise des anciennes séries Winner, règles d'origine conservées

L'utilisateur a demandé de reprendre les calculs stoppés, puis confirmé que les
anciens runs doivent garder leurs règles. Il ne s'agit donc **pas** d'appliquer
rétroactivement la liquidation DD15/DD25 ou la pause20 aux anciennes grilles.
Ces nouvelles règles restent dans leurs deux séries distinctes déjà lancées.

## Isolation

Deux modules moteur ont changé depuis l'arrêt : `backtesting/simulator.py` et
`backtesting/winner_intraday.py`. Le lanceur de reprise charge leurs copies
archivées **avant modification**, dont les empreintes avaient été vérifiées.
Les fichiers courants ne sont ni restaurés ni réédités ; les nouveaux runs
peuvent donc continuer avec leur moteur propre. Aucun import de moteur actuel
ne doit précéder l'installation du moteur figé dans le processus de reprise.

Pour ces deux noms de source seulement, la vérification des empreintes contrôle
le fichier effectivement chargé depuis l'archive. Tous les autres hashes des
sources, protocoles, snapshots et résultats restent strictement vérifiés.
Ce routage est consigné explicitement : aucune tolérance générale ni simple
désactivation du contrôle d'intégrité. Les sous-processus de recherche autorisés
héritent du même lanceur ; une cible de recherche inconnue est refusée.

Archive :
`artifacts/research/us_winner_monthly_selector/20261024-dd15-full-v2/predecessor`.
Reçu de reprise :
`artifacts/operations/winner-legacy-resume-20261024-v1/amendment.json`.
Ce reçu conserve les empreintes des rapports terminés, protocoles, moteurs et
les anciens états/logs avant redémarrage. Aucun rapport terminé n'est écrasé.
Une combinaison interrompue peut être recalculée ; les combinaisons finies sont
vérifiées puis ignorées, sans recommencer une année entière depuis zéro.

## Séries reprises

- grille TOP10 1x : 1567/3000 combinaisons conservées au départ ;
- grille TOP10 2x : 1039/3000 ;
- TOP50 2017 : 149/300 ; TOP20 déjà terminé300/300, non recalculé ;
- qualification/reprise des correctifs de centimes déjà validés ;
- ancienne sélection mensuelle : 2/10 comptes conservés, témoin de l'ancien
  protocole distinct des deux séries avec nouvelles ventes globales.

Les superviseurs de grilles ne prennent pas un millésime encore détenu par la
reprise du correctif de centimes : pas de double calcul concurrent de la même
année. Limitation opérationnelle : un worker par grille, un pour les centimes,
un TOP50 et un mensuel ancien, au plus cinq workers anciens simultanés.
Les autres années restent en file. Priorité système basse ; les deux nouvelles
séries déjà actives ne sont pas stoppées.

Les snapshots existants sont réutilisés. Pour2018/2026 encore non archivés,
la collecte intraday déjà terminée est lue en transaction SQL READ ONLY selon
le contrat d'origine ; pas de nouveau téléchargement, appel LLM, entraînement,
écriture SQL ou ordre. Les biais initiaux de couverture future, secteurs non
PIT et OHLC demeurent ; pas de nouvelle prétention de parité live.

Le lanceur est `scripts.research.us_winner_legacy_resume_20261024` :
`--phase probe` vérifie l'isolation dans un replay natif synthétique ;
`--phase prepare` scelle les inventaires ; `--target <module>` reprend le
superviseur concerné. Les anciens `progress.json` redeviennent la référence
de suivi, les nouveaux journaux de lancement restant dans le reçu de reprise.
