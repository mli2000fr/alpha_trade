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

## Implémentation

- `modelFactory/oracle_options_feasibility.py` : audit reproductible des snapshots
  et décision à partir des preuves d’accès ;
- `tests/test_oracle_options_feasibility.py` : paires call/put, accès REST,
  blocage flat files et contrat ask → bid ;
- artefact : `artifacts/models/shared_directional/oracle-options-feasibility-*/report.json`.

Références fournisseur : [documentation API Eroya](https://docs.eroya.co/llms.txt)
et [couverture de données Eroya](https://eroya.co/data).
