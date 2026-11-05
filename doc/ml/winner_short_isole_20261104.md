# Winner SHORT — prototype isolé du 4 novembre 2026

## Décision

L'utilisateur demande des simulations de ventes à découvert avec la sélection
per-symbol configurable. Après développement et validation des composants
isolés, il confirme : **« Garder le SHORT isolé pour l'instant »**.

Le raccordement au replay existant n'est donc pas appliqué. La case SHORT peut
être paramétrée, mais son lancement dans le formulaire Winner reste désactivé,
et le CLI refuse ce mode explicitement. Aucun ordre, entraînement, appel
fournisseur, écriture SQL ou backtest économique réel n'a été lancé ici.

La revue automatique d'approbation a refusé les modifications des fonctions
partagées avec le live, puis le changement du moteur et du coordinateur du
replay existant. Motifs : risque de modifier les protections de production,
puis les résultats LONG et la comptabilité avec capital partagé. Les patches
refusés n'ont pas été appliqués. L'exécution réelle est inchangée.

## Composants conservés, sans branchement dans l'IHM

- `backtesting/winner_short.py` : plan SHORT local, cassure du plus bas de la
  séance précédente suivie de N clôtures cinq minutes, entrée sans confirmation
  si N=0, SL au-dessus du prix d'entrée, TP en dessous, trailing sur le creux,
  un renforcement gagnant au maximum, horizon officiel depuis le premier fill.
  Réapprobation utilisant `RiskCheckerImpl`, les limites directionnelles,
  le coupe-circuit, les corrélations signées et les facteurs signés.
- `backtesting/winner_short_broker.py` : sous-classe isolée du broker simulé,
  valeur négative de la dette en titres, cash et capacité partagés, rachats
  totaux/partiels, frais, coût d'emprunt simulé, dividendes dus par le SHORT,
  priorité au stop lors d'une collision stop/TP, absence de remplissage
  rétroactif. Les méthodes LONG délèguent au broker existant ; les tests
  vérifient leur égalité exacte sur des événements déterministes.
- `backtesting/winner_short_ports.py` : staging et coordination mixtes locaux,
  ordre de sélection conservé, fermeture SHORT pour liquidation globale,
  compteurs natifs de concentration. Ces ports restent **non raccordés**.

La simulation isolée requiert un compte de type margin et l'activation SHORT
dans sa configuration de risque locale. Aucun drapeau de production n'est
modifié. Les tests n'utilisent que des données synthétiques, sans réseau ni SQL.

## Validation et limites

Les tests dédiés couvrent **18 cas**, dont : comptabilité SHORT et rachat
partiel, frais/dividendes, absence de capacité créée par les produits de vente,
capital mixte 1×/2×, ordre de priorité LONG/SHORT, comparaison exacte du
coordinateur LONG, confirmation à la baisse, N=0, sortie à l'horizon, SL/TP,
trailing, renforcement gagnant et délai SIP de 930 secondes. La suite ciblée
avec les régressions du replay, du runtime et du risque compte **74 tests
réussis** avant raccordement. Cela ne valide pas une performance historique.
La validation finale incluant aussi le classement per-symbol, l'IHM, les
commandes de backtest et le bundle directionnel termine à **172 tests réussis**
(neuf avertissements). Rapport technique :
`artifacts/test_tmp/short-final-qualification.xml`.

L'emprunt historique n'est pas démontré : disponibilité des titres, recalls et
locates resteraient des **hypothèses explicites**, avec un taux de frais visible
et archivé. Le taux est fourni à la classe isolée, jamais présenté comme un coût
historique observé. Le prototype facture une séance à l'entrée puis une fois
par séance de détention, sur le notionnel marqué, avec base 252. Le financement
des LONG doit rester distinct du coût d'emprunt des titres SHORT ; le solde
`financing_balance()` ne laisse pas les produits SHORT financer gratuitement
les achats LONG.

Les prix OHLC ne certifient pas un carnet ou une quote SIP historique. Le proxy
IOC SHORT borne séparément le prix minimum de vente et le prix maximum couvert
par le budget de risque ; un saut au-delà de cette réservation annule ce proxy.
Ce choix prudent peut écarter des occasions et n'est pas une reproduction du
courtier. Un stop SHORT ne plafonne pas la perte en cas de gap.

## Reprise future — travail encore requis

1. Raccorder explicitement les ports au replay, conserver le chemin LONG
   existant et valider les simulations complètes dans la même campagne.
2. Ajouter les contextes SHORT de concentration, de prix, de risque et les
   niveaux du plus bas précédent ; conserver les vetoes et la traçabilité.
3. Brancher la fermeture SHORT au coupe-circuit global et la facturation du
   financement/emprunt dans la boucle quotidienne, sans double déduction.
4. Exposer et archiver les hypothèses et le taux d'emprunt dans le formulaire,
   le CLI et le rapport ; ne pas certifier des locates historiques inexistants.
5. Vérifier les parcours de bout en bout, en particulier les limites de slots,
   les données manquantes, les comptes cash refusés et les fermetures à
   l'ouverture suivant l'horizon. Retirer ensuite le blocage IHM/CLI seulement
   lorsque le raccordement est qualifié.

Aucune de ces étapes restantes n'est considérée comme réalisée par les seuls
tests des composants isolés. Aucun accès SHORT réel n'est demandé ou activé.
