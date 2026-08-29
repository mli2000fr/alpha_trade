# Corporate actions — dividendes, splits et réconciliation

Retour : [corporate actions](../17_corporate_actions.md)

`provider.py` définit l'interface et implémentations Alpaca/EODHD. `engine.py` orchestre sync/apply ; `processors.py` applique ; `db_io.py` persiste ; `reconciliation.py` vérifie ; Yahoo sert de cross-check.

La sync normalise type, symbole, dates, ratio/montant et provider vers un événement unique. Le scope portfolio-only part des positions broker snapshot. L'application crée une row distincte liée à l'événement.

Dividende : calculer cash depuis quantité éligible et montant, écrire `portfolio_cash_ledger` une seule fois. Split : multiplier quantité et diviser cost basis selon ratio, conserver valeur notionnelle hors marché. Les prix étant split-adjusted, ne pas réajuster la série.

États pending/applied/failed permettent reprise. Avant replay, vérifier application et ledger. La réconciliation compare positions/cash et signale écarts. Un cross-check divergent n'écrase pas silencieusement le provider canonique.

