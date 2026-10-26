# DD15/min70 : pause vingt séances contre trois mois et absence de pause

26octobre2026. Un nouveau compte, même TOP20,4000USD,minimum70USD,FULL,cap1x,
SL5/sansTP/TR/open21, vingt séances de détention,2020–24 continu. Mêmes frais,
admission, risque B4, liquidation100% au DD15 de cycle, reset au vrai solde sans
apport, pas de plafond DD25. Seule l'unité/durée de pause change.

## Convention explicite

Le jour de liquidation est exclu du compte de séances complètes. Les VINGT
séances officielles NYSE suivantes sont entièrement sans exposition ni entrée.
Reprise à l'ouverture de la21e séance après liquidation. Un jour férié ou un
week-end ne compte pas ; une séance abrégée compte pour une séance officielle.
Les heures d'ouverture NY et les changements d'heure sont respectés.
Pas de définition approximative en20jours calendaires,4semaines ou1mois.

Exemples de contrôle : liquidation24mai2024→pause28mai–25juin→reprise26juin ;
liquidation27novembre2024→29novembre–27décembre→reprise30décembre ; la séance
abrégée29novembre compte, Thanksgiving et Noël non.

## Implémentation isolée et audit

Nouveau contrôleur de recherche hérite des ventes causales et du reset existants,
change seulement la date de reprise. Configuration et état effectifs :0mois,
20séances. Un pont de constructeur utilise temporairement le contrat3mois
pour réutiliser ses validations, sans conserver ni appliquer ce délai. Aucun
champ ni code de production ajouté/modifié, anciennes sources scellées intactes.

Sources/moteurs/prix identiques au test3mois. Son contrôle borné de parité sur
20séances sans liquidation est réutilisé, pas une certification sur toute l'histoire.
Audit indépendant des20sessions officielles et de chaque reprise, en plus du
cash/frais/quantités/sorties scalaires/annulations/pauses plates/reset B4 déjà
contrôlés. Tests natifs de liquidation puis reprise avec signal frais ; tests
de corruption des dates, du capital, des quantités et de la référence de risque.

Références scellées réutilisées : sans pause13641,66USD/+241,04%/DD−36,25% ;
trois mois14559,54USD/+263,99%/DD−39,12%. Aucun témoin recalculé. Le bilan
compare les trois variantes globalement et par année, inclut positions ouvertes,
frais, DD historique, temps investi/cash et liquidations/reprises. Le DD15 est
un seuil de déclenchement non garanti en gaps, pas un plafond global des pertes.

Commande : `python -u -m scripts.research.us_winner_cycle15_pause20_min70_20261026`.
Sorties : `artifacts/research/us_winner_cycle15_pause20_min70/20261026-v1`.
Suivi `progress.json`, bilan `report.json`, comparaison `comparison.json` et
`annual-comparison.csv`. Archives locales uniquement, zéro SQL/API/LLM/
entraînement/ordre/changement de configuration production. Historique déjà vu,
biais OOF/survivants/secteurs actuels/coverage future hérités : exploratoire.
