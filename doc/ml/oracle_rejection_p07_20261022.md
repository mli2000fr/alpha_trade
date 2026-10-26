# P07 — rejet baissier et reprise : contrôle borné avant tout PnL

Préenregistré le22octobre2026. Canonique neuf :
`artifacts/research/us_oracle_rejection_p07/20261022-v1`.

## Phase autorisée

Vérifier d'abord **couverture et fréquence**, sans rendement, performance,
PnL, backtest économique ou lecture des chemins futursH20 pour sélectionner
les occasions. Si l'effectif manque, clôturer avec un statut insuffisant,
sans assouplir les critères ni lancer une grille. Aucun nouveau fournisseur,
SQL, LLM, entraînement, ordre ou paramètre de production modifié.

Source d'inspiration : FMZ797 «RSI Mean Reversion Breakout Strategy», commit
`7853bb2bf262c4567ac238d3552d97f0e50cb801`. Le code ne calcule pas de RSI.
L'adaptation actions daily/5m est la nôtre ; pas reprise de ses hypothèses
de fill ou de stop mobile avec le low courant.

## Configuration de rejet, connue à la clôture J

Dix séances NYSE régulières complètes terminées à OracleJ, agrégées depuis
les raw5m SIP non remplies : H=maxhigh, L=minlow, C=dernierclose5m régulier,
pas revendiqué comme prix officiel d'enchère. Aucun daily ajusté mélangé.

- `L_J < min(L des neuf séances précédentes)` : nouveau creux strict.
- `H_J−L_J > max(H−L des neuf précédentes)` : plus grande fourchette stricte.
- `(C_J−L_J)/(H_J−L_J) >= 0,75`, avec fourchetteJ positive.

Les trois conditions doivent être satisfaites. Un range nul est une absence
de motif connue, pas une absence de données. Un lookback incomplet reste
**inconnu**, jamais assimilé à un motif faux ou un titre perdant.

## Confirmation d'entrée, uniquement pour compter les signaux

Figer H_J et L_J. Pendant **J+1 et J+2 seulement**, première clôture régulière5m
strictement >H_J → achat hypothétique à l'open contigu suivant, même séance.
«Confirmation» signifie ici **une clôture5m**, conformément au protocole initial,
pas les deux clôtures Winner ni une sélection rétroactive du creux.

- Avant entrée, low5m <L_J : invalider la tentative avant toute reprise dans
  cette même bougie. Égalité à L_J n'invalide pas ; égalité à H_J ne confirme pas.
- Si le prochain open réel est <L_J, annuler avant fill, sans attendre de
  connaître son futur low/high. Un low futur sous L_J ne peut pas annuler
  rétroactivement une entrée valable à cet open.
- Première confirmation à la dernière bougie : pas de fill overnight ni de
  nouvelle tentative le lendemain. Absence de confirmation à J1 : continuer
  d'observer J2 seulement si aucune invalidation n'a eu lieu.
- Pas de fill de limite au niveau touché, pas de réentrée, miroir SHORT,
  volume/RSI/EMA, retest ou changement de trailing.

Témoin de fréquence : même cassure H_J, invalidation L_J et fenêtreJ1/J2,
**sans** le filtre de rejet. Le prix observé d'un signal n'est pas une preuve
d'exécution économique : sizing, capital, risque, spread/gap et frais restent
à qualifier dans une éventuelle phase ultérieure.

## Couverture et filtre de poursuite

213campagnes originales CatBoost PATH_H20 de recherche, pas tout le TOP10
quotidien ni LightGBM production. Elles sont déjà conditionnelles aux anciens
signaux/chemins/survivants. Même archive locale figée que les autres pilotes ;
aucune extension SQL ou collecte nouvelle. Séances qualifiées par le calendrier
NYSE réel, y compris fermetures anticipées. Les archives imposent déjà des
séances complètes ; ce gate de couverture reste une limite de sélection.

Comptes séparés : lookbacks qualifiés, motifs à J, scans d'entrée évaluables,
signaux après confirmation. Le scan s'arrête causalement après une entrée
ou invalidation connue à J1 : J2 manquant ensuite ne remet pas cette observation
en cause. Si J1 est absent, ne pas sauter vers J2. Les fenêtres encore futures
au30septembre2026 sont censurées. Aucun contrôle de cheminH20 ni de sa maturité
à ce stade : l'effectif est un **plafond avant qualification économique**.

Opérations connues du lookback réservées ; table héritée vide/incomplète,
pas preuve d'absence d'événement ni qualification exhaustive des identités.
2024 absente de l'archive figée, pas de nouvelle simulation.2025/2026 déjà
étudiées, pas de holdout neuf ; pas parité live complète.

Avant de passer à l'économie : dans **chacune** des années Oracle2025/2026,
au moins **30signaux non chevauchants,10titres et6mois de signaux**.
Espacement conservateur : première occasion évaluable par symbole puis blocage
jusqu'à OracleJ40open, comme les expériences précédentes. Cela inclut les
occasions sans motif, sans choisir après coup seulement les futurs signaux.
Pas de calcul de taux gagnant ou bootstrap de rendement pour franchir ce gate.

En cas d'échec : `INSUFFICIENT_P07_FREQUENCY_NO_BACKTEST`. Cela ne prouve pas
l'inefficacité universelle de P07 ; cela interdit seulement de prétendre la
valider sur cet effectif. Ne pas assouplir le quart supérieur, le lookback,
les comparaisons strictes, la fenêtre ou le minimum d'effectif après les chiffres.

Si le gate passe : qualifier les prix/chemins et figer une seconde phase
économique avant tout PnL : Winner et cassure sans filtre, mêmes4 000USD annuels,
1x/demi-cible/SL7/TR15/sansTP/sansadd/natifsB4DD15, vingt séances depuis l'entrée
puis open21, frais8/25bps. Le présent script **ne peut pas** lancer ce backtest.

## Audit et lancement

Calcul indépendant du motif et du premier signal, contrôle de toutes les
occasions, dates, absences, compteurs et espacement. Empreintes avant/après.
Même assistant, pas seconde revue humaine indépendante.

```powershell
python -u -m scripts.research.us_oracle_rejection_p07 --phase run
python -u -m scripts.research.us_oracle_rejection_p07_audit
```

Sources/tests/protocole empreintés avant les fréquences. Aucun écrasement de
dossier scellé ; correction technique éventuelle dans un dossier neuf.
