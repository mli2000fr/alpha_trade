# Réplication exacte du témoin +12,92 %, puis veto du bas du classement

GO du 23 octobre2026 : lancer en parallèle de l'essai Winner natif courant,
sans interrompre cet essai. **Seul changement économique : veto de candidats**.
Pas d'entraînement, SQL, fournisseur/LLM/courtier, écriture en base ni changement
de modèle, batch, YAML ou moteur de production.

## Référence inchangée

`artifacts/research/us_oracle_pyramiding/20261020-v1`, bras `HALF_CONTROL` :
SL5 %, trailing15 %, aucun TP, moitié entière de la quantité pleine, plafond
planifié2%equity par campagne, poids25%plein, huit positions, cash positif,
levier1x. Premier signal existant de deux clôtures5m, première tentative seule,
priorité date/rangOracle/symbole. Expiration à l'open de la dernière barre5m de
J+20 **depuis Oracle**, attente comprise ; pas vingt séances depuis le fill.

Compte4000USD continu2025→30septembre2026, capital et positions de fin2025
reportés, pas reset2026. Les mêmes213campagnes/72titres (119/94), prix et
calendrier sont repris. Pas B4, risque sectoriel/corrélation natif, quote/fill
historique ou OST cashflows ajoutés. Ancien simulateur, pas paritélive.
Coûts8bps/jambe ; sensibilité25bps avec **rejeu complet** des tailles/cash.

Gate impératif **avant chaque filtre** : rejouer les deux témoins8/25bps et
comparer exactement marques, lots, ordres et fills aux fichiers archivés.
Refuser si un tableau ou bilan annuel diffère : ne pas ajuster un paramètre
pour retrouver12,92 %. Référence8bps : +12,9191602862%en2025 et
+33,1928688236%en2026, capital final6016,010761468USD.

## Filtre unique figé

Ratio volatilité20/volatilité60 croissant, sens déjà figé avant ce GO. Calcul
backward-only depuis les prix auxiliaires archivés de l'audit précédent,
même générateur de features et contrôles historiques121barres/identité ;
aucun changement des cours/fills de l'ancien portefeuille.

Reconstituer le classement des **dix premiers Oracle d'origine** de chaque
date2025/2026 (`selected.parquet` parent), avant admission, qualité future et
premier signal intraday. Pas les nouveaux TOP10 annuels : ils diffèrent.
Trier ratio croissant, égalités départagées rangOracle puis symbole.
Les trois bras sont témoin, retirer les3derniers (garder7), retirer les5derniers
(garder5). Les conservés gardent leur priorité Oracle et leur premier signal
d'origine ; aucune réentrée, nouveau timing, remplacementTOP11, ajout gagnant
ou adaptation du budget. Le veto s'applique seulement avant l'entrée initiale,
jamais à une position détenue qui changerait de rang ensuite.

Si l'un des dix n'a pas de ratio J qualifié : **pas de filtre pour la date entière**,
dans les deux variantes. Pas d'imputation, de classement arbitraire d'un inconnu
comme perdant, ni d'exclusion d'un candidat qui modifierait le témoin. Motif et
fréquence de ce passthrough publiés. Une absence de prix futurs n'entre jamais
dans ce classement. Le témoin conserve exactement les213campagnes archivées.

Les features auxiliaires ne sont pas un nouvel univers de trading. Leur ratio
doit reproduire, sur les clés communes connues, celui de l'audit déjà réalisé.
Entrées et sources SHA256 vérifiées avant/après calcul ; aucun réétiquetage.

## Mesures, audits et limites

Publier les deux années par bras/coût : rendement net, capital final, DD5m,
gagnants/perdants, gains/pertes totaux et moyens, durées moyennes, capital brut
moyen, taux engagé, candidats retenus/exclus, frais, effet sur l'activité.
2026partiel ; ne pas comparer au compte2026reset4000 du nouvel essai natif.

Réutiliser l'auditeur scalaire d'origine : stops, chronologie, sizing, cash,
frais, capital partagé ; cohorte d'audit restreinte aux veto connus à J,
trajectoires et calendrier inchangés. Vérification séparée du filtre par date.
Même assistant ≠ revue humaine indépendante.

La règle de tri avait échoué à la validation2022/maxT ; 2025/2026 déjà observés,
pas un nouveau holdout indépendant. Couverture future/survivants de l'ancienne
cohorte conservée, pas certification de tout le TOP10 historique ou du live.
Différence de rendement = effet du veto dans ce simulateur et cette cohorte,
y compris les changements de capital/tailles, pas une preuve d'alpha général.
Pas de recherche de nouveaux seuils après lecture, ni promotion automatique.
