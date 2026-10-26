# Amendement technique avant tout calcul d'issue

26 octobre, avant analyse : l'export v1 n'a calculé aucun score/label/AUC.
Le producteur `service.forward_pit.options_delayed` collecte en `30Min`, pas
en `1Day`. Les 46 313 barres 1Day exportées sont des backfills reçus le11octobre,
et ne reconstituent pas les volumes prospectifs. Le v1 est conservé, non analysé.

V2 : remplacer uniquement ce périmètre technique par timeframe30Min, en gardant
la somme par côté/échéance et les contrôles de réception locale. Une seule grille
temporelle pour éviter le double comptage. Pas de reconstitution du flux signé.

Les prix SIP de l'univers sont presque tous limités au12–23octobre ; EODHD couvre
la fenêtre ancienne mais s'arrête au16octobre. EXPORTER les deux séparément :
EODHD primaire (source préférée actuelle de l'application et même prix de référence
que l'ancien diagnostic), SIP secondaire de sensibilité. Aucun parcours ne mélange
sources, aucun changement de YAML, aucun remplissage entre flux. Les mêmes trois
scores sont comparés sur les mêmes observations POUR CHAQUE flux ; une différence
de résultat entre flux de couverture différente n'est pas un effet causal du feed.

Les prix servent aussi au choix ATM de l'OI ; les candidats peuvent donc différer.
Maturité et contrôles de qualité inchangés ; zéro H20 mûr admissible sera publié
comme zéro, et non remplacé silencieusement par H5. Aucun poids modifié ni entraîné.
Cet amendement répond uniquement à la structure/couverture des sources vues avant
les résultats, sans sélection selon gains, pertes, AUC ou prix futurs.
