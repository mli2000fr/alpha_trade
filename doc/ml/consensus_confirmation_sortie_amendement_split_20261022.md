# Amendement technique de base de prix, avant tout résultat

Le dossier de préparation v1 fixe12confirmations sur9titres et deux dates.
Aucun prix nouveau ni rendement n'y a été calculé. L'inventaire de la source
parent montre que les11 548barres SIP existantes sont **split-adjusted**, pas
raw. Ne pas les rebaptiser raw ni appeler un autre fournisseur.

Le dossier v2 conserve strictement les features,fréquences,cutoffs,TP10/SL5,
horizons et sorties ; validation sur **SIP split-adjusted uniquement** avec
identité constante. Ce sont des prix rétrospectivement ajustés : réserves
OST/dividendes/identité persistantes,pas une parité d'exécution réelle.
Pas de fallback raw/EODHD/IEX et pas de transformation de prix à la volée.
Le validateur est adapté en mémoire par un module de recherche séparé,
sans changer les sources/protocoles v1 scellés ni les données de production.
