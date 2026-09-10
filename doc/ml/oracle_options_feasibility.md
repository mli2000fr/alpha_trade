# E6-B0 — Faisabilité des options après Oracle

## Résultat

E6-A a démontré une forte concentration OOF de l’amplitude dans le TOP20 Oracle.
E6-B0 vérifie si les données permettent de transformer ce constat en test
économique d’un straddle, sans inventer une prime ou un spread.

Le verdict est **GO pour un pilote REST borné à 2022–2025**, mais **pas encore GO
pour une campagne complète par flat files**.

## Preuves d’accès du 6 septembre 2026

| Source | Résultat | Usage possible |
|---|---|---|
| contrats historiques avec `as_of` seul | HTTP 200 | reconstruire call/put, strike et expiration PIT |
| agrégats journaliers d’un contrat expiré | HTTP 200 | prix/volume de transaction historique |
| trades d’un contrat expiré | HTTP 200 | historique depuis le 2 juin 2014 |
| quotes NBBO d’un contrat expiré | HTTP 200 | bid/ask exact depuis le 7 mars 2022 |
| catalogue flat files options day/minute | annoncé `entitled=true` | transport potentiel en masse |
| `/flatfiles/list` | HTTP 502, archive temporairement indisponible | inventaire impossible au moment du test |
| URL signée `/flatfiles/url` | HTTP 200 | URL délivrée |
| lecture de l’objet signé | HTTP 401 | téléchargement effectivement bloqué |

La documentation Eroya confirme les profondeurs trades/quotes, les routes
historiques et les archives options par séance. Elle indique aussi que la
livraison dépend des droits fournisseur/OPRA. Un droit annoncé dans le catalogue
ne vaut donc pas preuve de téléchargement réussi.

Le probe a aussi établi une subtilité d’API importante : `as_of=2024-07-01`
retourne correctement les contrats alors actifs et `expired=true` retourne les
contrats aujourd’hui expirés, mais combiner les deux filtres retourne zéro ligne.
La reconstruction PIT doit utiliser **`as_of` sans `expired=true`**.

## Pourquoi les snapshots existants ne suffisent pas

La collecte locale contient seulement 44 contrats pour 12 symboles. Le
collecteur avait volontairement demandé deux lignes et deux pages par symbole :
les réponses sont triées depuis les premiers strikes et ne forment pas une chaîne
ATM complète. Elles représentent l’état courant de septembre 2026, pas les états
historiques des dates Oracle.

Un snapshot peut valider le schéma (`bid`, `ask`, IV, Greeks, open interest),
mais ne doit jamais être joint rétroactivement à 2018–2025.

## Contrat PIT préfixé pour E6-B1

```text
Oracle TOP20 OOF connu à la clôture J
        │
        ▼
Open action J+1 et contrôle du gap
        │
        ▼
Expiration 35–55 jours, même strike call/put le plus proche
        │
        ▼
Entrée ≥ 09:35 ET : achat call ask + put ask
        │
        ├── valorisation H3
        ├── valorisation H5
        ├── valorisation H10
        └── valorisation H20
                 vente call bid + put bid avant 15:55 ET
```

- expiration au moins cinq jours calendaires après la sortie ;
- aucune interpolation si un côté du NBBO manque ;
- aucun `last_trade` utilisé comme substitut du prix exécutable ;
- spread payé deux fois implicitement par le chemin ask → bid ;
- commissions ajoutées séparément ;
- paire call/put strictement au même strike et à la même expiration ;
- fenêtres de split, contrat ajusté ou changement de ticker isolées ;
- comparaison quotidienne appariée TOP20, NEXT20 et REST80.

## Campagne proposée

### E6-B1 — pilote REST

Période autorisée par la profondeur NBBO : 7 mars 2022 au 11 juillet 2025.
Utiliser un calendrier de dates préfixé et tous les candidats de ces dates. Il
ne faut pas choisir a posteriori les jours dont les options sont rentables.

Le pilote doit d’abord mesurer : taux de contrat trouvé, taux de paire ATM,
taux de NBBO complet à l’entrée et à chaque sortie, spread médian, volume et
concentration par symbole. Aucun résultat de PnL n’est interprétable si la
couverture dépend fortement de la liquidité future.

### E6-B2 — écran large

À lancer seulement lorsque les flat files sont effectivement téléchargeables.
Les fichiers day/minute couvrent les transactions de tout le marché mais pas le
NBBO avant mars 2022. La période 2018–2022 peut documenter l’amplitude des primes
et le volume ; elle ne constitue pas une confirmation exacte ask → bid.

### E6-B3 — confirmation

Après le pilote, figer une seule politique de DTE/strike/liquidité et réserver
une période 2022+ intacte. Mesurer rendement net moyen et médian, drawdown,
semestres positifs, concentration et avantage contre NEXT20/REST80.

## Limites économiques

La réussite d’E6-A ne garantit pas la réussite d’un long straddle. L’Oracle peut
simplement reconnaître les titres auxquels le marché des options facture déjà
une volatilité implicite très élevée. E6-B doit donc répondre à :

> Le mouvement réalisé après le signal Oracle excède-t-il la prime et le spread
> déjà exigés par les vendeurs d’options ?

Sans prix exécutable historique, la réponse reste inconnue.

## Résultat E6-B1 — straddle 45 DTE

Artefact : `oracle-options-pilot-20260906130521-0802c8`. Le calendrier comprend
une date fixée au milieu de chaque semestre, soit huit dates, 588 événements
TOP20 et 152 symboles entre mai 2022 et juillet 2025.

### Couverture

- paire call/put au même strike trouvée : 534/588 (`90,82 %`) ;
- paire avec NBBO d’entrée synchronisé : 397/588 (`67,52 %`) ;
- sortie exploitable : 268 à H3, 270 à H5, 276 à H10 et 243 à H20 ;
- seulement 111 observations possèdent les quatre horizons complets ;
- les pertes de couverture proviennent de l’absence de contrat, d’une jambe sans
  NBBO ou de quotes non synchronisées, jamais d’une interpolation.

### Résultats ask → bid, commissions incluses

| Horizon | Observations | Moyenne | Médiane | Trades positifs | Dates moyennes positives |
|---:|---:|---:|---:|---:|---:|
| H3 | 268 | -16,77 % | -13,97 % | 13,06 % | 1/8 |
| H5 | 270 | -15,02 % | -15,15 % | 15,93 % | 1/8 |
| H10 | 276 | -22,47 % | -21,95 % | 10,14 % | 0/8 |
| H20 | 243 | -29,68 % | -33,22 % | 11,93 % | 0/8 |

Le résultat n’est pas causé par quelques mauvais contrats manifestes. Avec une
distance au strike limitée à 3 % et une prime totale limitée à 30 % du
sous-jacent, H20 reste à `-27,0 %` en moyenne et `-30,4 %` en médiane sur 191
observations.

Le score Oracle ne classe pas le rendement du straddle : Spearman proche de zéro
à tous les horizons (`-0,05` à H3/H5, `-0,005` à H10, `+0,056` à H20). En
revanche, l’amplitude **réalisée a posteriori** est bien corrélée au rendement de
l’option. Même son quartile supérieur reste toutefois perdant en moyenne à H20
(`-21,4 %`). Ce dernier classement est diagnostique et non tradable, puisqu’il
utilise le futur.

### Verdict

Le long straddle ATM d’environ 45 DTE acheté au ask après chaque signal TOP20 est
**rejeté dans cette formulation**. Le marché facture une prime d’entrée médiane
de `19,04 %` du sous-jacent ; l’amplitude détectée par Oracle ne suffit pas à
compenser la prime, le spread et la décroissance temporelle.

Ce pilote ne valide ni une vente de straddle — dont le tail-risk serait majeur —
ni un déploiement. Avec seulement huit dates, il constitue un rejet préliminaire
fort de la formulation 45 DTE, pas une estimation définitive de stratégie.

La seule variante encore justifiée sans optimisation opportuniste est un contrat
DTE préfixé par horizon : environ 14 DTE pour H3, 21 pour H5, 28 pour H10 et 45
pour H20. Elle répond à une différence structurelle de durée, et non à un seuil
choisi sur les pertes observées. Le pilote conserve désormais bid et ask à
l’entrée et à la sortie afin d’attribuer séparément spread et variation de valeur.

## E6-B2 — DTE adapté à l’horizon

La campagne conserve exactement le calendrier E6-B1 et sépare quatre contrats :

| Sortie | DTE minimum | DTE cible | DTE maximum |
|---:|---:|---:|---:|
| H3 | 10 | 14 | 21 |
| H5 | 14 | 21 | 28 |
| H10 | 21 | 28 | 35 |
| H20 | 35 | 45 | 55 |

Chaque horizon possède son propre run afin que le strike, l’expiration et la
prime soient reconstruits indépendamment à J+1. Les dates, symboles, horaires,
commission et règle ask→bid restent identiques à B1. Les nouveaux artefacts
conservent également le bid d’entrée, le midpoint, le spread combiné et les asks
de sortie.

Exemple H3 :

```powershell
python -u -m modelFactory.oracle_options_pilot --events-path artifacts/models/shared_directional/oracle-amplitude-audit-20260906094826-0802c8/event_metrics.parquet --output artifacts/models/shared_directional/oracle-options-dte-h3 --start-date 2022-03-07 --end-date 2025-07-11 --dates-per-semester 1 --horizons 3 --min-dte 10 --target-dte 14 --max-dte 21 --minimum-exit-buffer-days 5
```

Les gates sont préfixés avant résultats : couverture NBBO ≥ 40 %, rendement net
moyen et médian positifs, au moins cinq dates moyennes positives sur huit, puis
robustesse ATM/liquidité et absence de concentration. Une amélioration restant
négative signifie « moins mauvais », pas une validation.

### Résultat E6-B2 — DTE adapté à l’horizon

Les quatre runs sont terminés sur le même échantillon que B1 : `588` événements,
`152` symboles et `8` dates réparties de 2022H1 à 2025H2. Les rendements sont
calculés selon le contrat conservateur préfixé : achat du call et du put au ask,
liquidation au bid et commission de `0,65 USD` par contrat et par côté.

| Horizon | DTE cible | Observations | Couverture | Rendement net moyen | Médiane nette | Trades positifs | Dates moyennes positives |
|---:|---:|---:|---:|---:|---:|---:|---:|
| H3 | 14 | 257 | 43,71 % | -15,76 % | -17,49 % | 19,46 % | 1/8 |
| H5 | 21 | 249 | 42,35 % | -14,39 % | -19,31 % | 22,09 % | 2/8 |
| H10 | 28 | 136 | 23,13 % | -22,33 % | -25,21 % | 11,76 % | 0/8 |
| H20 | 45 | 243 | 41,33 % | -29,68 % | -33,22 % | 11,93 % | 0/8 |

La couverture franchit le seuil de 40 % à H3, H5 et H20, mais H10 échoue avec
seulement 23,13 %. Aucun horizon ne franchit les deux gates de rentabilité : les
moyennes et les médianes sont toutes négatives. Le gate de stabilité temporelle
échoue lui aussi largement : le meilleur cas, H5, ne compte que deux dates
moyennes positives sur huit, contre cinq exigées.

#### Comparaison au témoin E6-B1 à 45 DTE

| Horizon | Variation de la moyenne nette | Variation de la médiane nette | Variation de couverture | Lecture |
|---:|---:|---:|---:|---|
| H3 | +1,02 point | -3,52 points | -1,87 point | moyenne légèrement moins mauvaise, médiane dégradée |
| H5 | +0,63 point | -4,16 points | -3,57 points | moyenne légèrement moins mauvaise, médiane dégradée |
| H10 | +0,14 point | -3,26 points | -23,81 points | quasi aucun gain économique et forte perte de couverture |
| H20 | 0,00 point | 0,00 point | 0,00 point | même configuration 45 DTE, donc témoin identique |

Les contrats plus courts réduisent la prime médiane rapportée au sous-jacent :
`11,05 %` à H3, `12,30 %` à H5 et `15,56 %` à H10, contre `18,65 %` à H20.
Cette réduction ne suffit pas. Le spread combiné médian reste proche de 20 à
23 %, et le rendement calculé depuis le midpoint jusqu’au bid demeure négatif
à chaque horizon (`-4,50 %`, `-2,74 %`, `-12,88 %`, `-21,17 %`). La conclusion
ne dépend donc pas uniquement de la convention d’achat au ask : la valeur du
straddle après entrée ne compense pas suffisamment sa prime et son coût de
liquidation.

### Verdict E6-B2

**E6-B2 est `NO_GO`.** Adapter mécaniquement le DTE à H3/H5/H10/H20 ne rend pas
le long straddle ATM exploitable sur les événements Oracle TOP20. Les petits
gains de moyenne à H3/H5/H10 sont des résultats « moins mauvais » et non une
validation : les médianes se détériorent et les gates temporels échouent.

La confirmation E6-B3, préconditionnée au succès de B2, n’est donc pas
justifiée. Ce verdict ferme la formulation *long straddle ATM systématique* ; il
ne rejette pas une étude distincte d’information optionnelle directionnelle
(skew, risk reversal ou flux put/call), ni une stratégie dont le payoff et le
risque seraient différents.

Artefacts canoniques :

- [H3 — 14 DTE](../../artifacts/models/shared_directional/oracle-options-dte-20260906-h3-0802c8/report.json) ;
- [H5 — 21 DTE](../../artifacts/models/shared_directional/oracle-options-dte-20260906-h5-0802c8/report.json) ;
- [H10 — 28 DTE](../../artifacts/models/shared_directional/oracle-options-dte-20260906-h10-0802c8/report.json) ;
- [H20 — 45 DTE](../../artifacts/models/shared_directional/oracle-options-dte-20260906-h20-0802c8/report.json).

Limite de traçabilité : le champ `experiment` interne des quatre rapports garde
le nom générique `E6_B1_oracle_options_rest_pilot_v1`. L’identification E6-B2
repose donc sur le répertoire et sur les paramètres DTE présents dans chaque
rapport. Cela n’altère pas les calculs, mais ce libellé devra être distingué si
le pilote est réutilisé.

## Implémentation

- `modelFactory/oracle_options_feasibility.py` : audit reproductible des snapshots
  et décision à partir des preuves d’accès ;
- `tests/test_oracle_options_feasibility.py` : paires call/put, accès REST,
  blocage flat files et contrat ask → bid ;
- artefact : `artifacts/models/shared_directional/oracle-options-feasibility-*/report.json`.

Références fournisseur : [documentation API Eroya](https://docs.eroya.co/llms.txt)
et [couverture de données Eroya](https://eroya.co/data).
