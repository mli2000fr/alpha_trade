# Winner : exclure les trois ou cinq derniers du TOP10 estimé

GO utilisateur du 22 octobre : comparaison économique exploratoire 2025 et
2026 jusqu'au 30 septembre. Aucun entraînement, téléchargement fournisseur,
écriture SQL, ordre ni changement de production. SQL existant READ ONLY autorisé
pour figer les bougies SIP et métadonnées nécessaires ; pas de second backfill.

## Hypothèse gelée avant performance

Le seul classement testé est celui déjà identifié dans l'audit : ratio de
volatilité20/volatilité60 **croissant**, connu au close du signal Oracle J.
Faible ratio en tête, fort ratio en bas, égalité par rang Oracle puis symbole.
Ce ne sont pas les trois/cinq futurs perdants connus par anticipation.

Trois bras LONG : Winner seul ; exclure rangs estimés8–10 (garder7) ; exclure
rangs estimés6–10 (garder5). Les candidats conservés gardent **leur priorité
Oracle d'origine**, pas la nouvelle priorité du score auxiliaire. Aucun TOP11,
remplacement des manquants ou achat forcé ; Winner attend sa propre confirmation.
Une campagne ne se ferme pas parce que son symbole sort ensuite du classement.

Classement calculé sur les dix candidats **avant qualité future**, à partir de
`observable-top10.parquet` scellé par l'audit du parcours ; jamais ses labels.
Les données J inconnues sont bloquées dans tous les bras, pas imputées ; elles
viennent en dernier pour le classement mais ne deviennent pas des preuves de perte.
Oracle parcours CatBoost annuel2025 `102eca`, 2026 `bc35a7`. Le dernier signal
de l'année précédente peut alimenter le premier jour de l'année testée.

La règle échouait au gate de validation2022/maxT. Les résultats2025–2026 étaient
déjà vus au stade descriptif. Ce nouveau GO autorise un **test économique après
observation**, pas une confirmation indépendante ou un signal déjà validé.

## Moteur et configuration

Utiliser le vrai coordinateur local `winner_intraday`, ses campagnes, risque
réapprouvé à l'entrée, B4, concentration, corrélation, capital partagé, coûts,
frais de financement et protections ; aucune connexion au courtier.

Configuration Winner `config.yaml` figée à la préparation, enabled forcé à true
**en mémoire seulement** : demi-position, sans renforcement, deux clôtures5m
de confirmation, SL7 %, trailing15 %, aucun TP, attente maximale20séances,
vingt séances depuis le fill initial puis vente open21. Pas l'ancienne expiration
à J+20 depuis Oracle. Si le YAML diffère de ces valeurs, refuser plutôt que
modifier silencieusement le contrat.

Capital4000USD redémarré par année/bras ; profil `capital_2001_5000`, equity
explicitement4000 (ne pas reprendre l'equity100000 du YAML). Levier autorisé
selon YAML jusqu'à2x, **limite d'exposition du risque courante conservée** :
ne pas forcer2x si le risque limite1x. Pas de réinvestissement fictif de la taille
des titres exclus dans les autres ; le capital libéré reste soumis aux règles.
Financement6,5% annuel/252 sur cash débiteur ; frais canoniques du moteur.

Deux composants actuellement non qualifiés par ce replay : modèle factoriel et
filtre de corrélation factorielle. Ils sont explicitement désactivés dans les
trois bras de recherche, sans modifier le YAML ; Pearson et autres gardes restent.
Ce n'est donc pas la parité complète du portefeuille live. Secteurs actuels
non PIT explicitement assumés, pas de secteurs historiques inventés.

## Données et couverture commune

Ne pas mélanger les 213anciennes campagnes et leurs classements Oracle différents.
Nouveau snapshot ciblé des vrais TOP10 : SIP5m régulier/raw/nonrempli avec
horodatage de fin et hash fournisseur. Index symbole/timestamp ; pas de nouveau
comptage global de toute la table pendant les backfills utilisateur.

Pour chaque signal initial, vérifier la fenêtre maximale d'attente+détention,
signal inclus, jusqu'à J+40 ou fin d'année si antérieure : sessions officielles
complètes, chaque OHLCV positif/cohérent, provenance et durée5m. Réserver aussi
toute campagne dont cette fenêtre comporte une opération sur titres de
l'inventaire archivé : ce replay ne qualifie pas son lifecycle. Aucun événement
manquant n'est réputé impossible, inventaire non certifié exhaustif.

Cette exigence est un **conditionnement sur la couverture future**, pas un filtre
live : même cohorte pour les trois bras, motifs/quotients sur tous les candidats
initiaux. Pas de remplacement des titres exclus. Le tri reste figé avant ces
exclusions. Les trois comptes doivent garder leurs positions ouvertes marquées
à la fin de chaque année, pas de vente artificielle de clôture.

Daily/benchmark : cache split existant de l'audit, jamais assimilé à des raw pour
les niveaux de cassure : le runtime utilise le plus haut de la session raw5m
précédente. Historique et métadonnées actuels/vintages révisés ne sont pas des
reçus d'application PIT historiques certifiés. Univers amont survivant1790.

Si une position détenue manque d'une bougie, arrêter ce compte en échec ; pas
d'invention de prix ni de frais gratuits. Si la couverture initiale ne permet
aucune comparaison utile, rapporter le blocage, sans relancer une collecte.

## Bilan prévu et limites

Capital final, rendement après coûts, DD5m, trades gagnants/perdants, gains/pertes
totaux et moyens, durées moyennes, positions MTM, frais, financement, capital
brut moyen/max, proportion de capital engagée, nombre de signaux exclus/acceptés
et motifs risque/couverture. Comparaisons appariées avec Winner seul par année.
Pas de grille supplémentaire, optimisation de seuil, changement de signe ou
choix d'une version sur la seule année favorable. Une hausse du rendement peut
venir d'une exposition différente ; aucun alpha causal garanti sans contrôle
supplémentaire. Deux années déjà inspectées ne suffisent pas pour promouvoir.

Scripts/tests/manifeste scellés avant calcul, audits de sélection et de cash/
coûts/exits. Même assistant ne signifie pas revue humaine indépendante.
