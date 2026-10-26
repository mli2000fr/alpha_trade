# TOP20 2017 : ajouter uniquement un TP à 20 %

GO du 24 octobre 2026 après observation des pics des positions sorties à H20.
Hypothèse rétrospective, période déjà observée : pas de validation indépendante.

Reprendre exactement les deux variantes de `us_winner_top20_capacity_2017` :
couverture stricte Jsignal..Jsignal+40 et couverture de détention à l'entrée
Jentrée..Jentrée+20. Ajouter uniquement `take_profit_pct: 0.20`. Comparer
chacune à son résultat sans TP archivé ; ne pas réutiliser une simple moyenne
de pics comme rendement simulé. Le TP peut libérer du capital et modifier les
entrées suivantes, donc le portefeuille entier est rejoué.

Paramètres inchangés : TOP20 dans l'ordre Oracle, 02/06–31/12/2017, LONG,
4 000 USD, position initiale complète, sans renforcement, SL 5 %, aucun
trailing, vingt séances puis vente à l'ouverture de la 21e, vingt places,
dix entrées par titre sur 180 jours, trois pertes/90 jours d'exclusion.
Confirmation par deux clôtures 5m, attente vingt séances, risque B4/DD15,
budget/secteur/corrélation et plafond brut 1x identiques. Frais 8 bps/jambe,
réserve 25 bps de sizing, financement, année non liquidée mais valorisée.

Exécution du TP par le moteur natif : niveau arrondi au centime ; gap haussier
plafonné au TP plutôt que gain d'ouverture favorable inventé ; collision SL/TP
dans une même bougie résolue SL d'abord. L'ordre de sortie à l'échéance déjà
préparé pour l'ouverture conserve la priorité prévue par le protocole natif.
Audit scalaire inchangé sur les achats/sorties, cash/frais/positions et DD.

Même données, cohortes et qualification future de couverture : cette dernière
reste un biais déclaré. Le TP ne permet pas de raccourcir après coup la
qualification de données en fonction des trades gagnants. Les données des
positions détenues restent obligatoires ; aucun prix inventé, relâchement
d'audit ou substitution de bougie manquante. Secteurs actuels non PIT,
univers survivant et hypothèses OHLC : aucune parité live complète.

Sources et entrées scellées, ancien test et grilles inchangés. Script wrapper
séparé avec paramètres process-locaux restaurés. Aucun SQL, fournisseur,
entraînement, appel LLM, ordre ou changement de configuration de production.
Un worker supplémentaire à priorité basse, deux bras séquentiels, pas de grille.

Suivi : `artifacts/research/us_winner_top20_tp20_2017/20261024-v1/progress.json`.
Résultats : `comparison.csv`, `paired-deltas.csv`, `report.json`, plus rapports,
trades et courbes par bras. Les nouvelles statistiques incluent rendement,
capital final/moyen, DD, taux et montants gagnants/perdants et détention.
