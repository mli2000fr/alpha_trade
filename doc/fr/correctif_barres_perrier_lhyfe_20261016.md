# Barres FR — correction Perrier et blocage fournisseur Lhyfe

## Bilan du 16 octobre 2026

### Décision ultérieure du même jour : exclusion opérationnelle de Lhyfe

À la demande de l'utilisateur, `batch_fr.yaml → fr_daily_bars_sync.excluded_symbols`
contient maintenant **`LHYFE.PA`**, le code encore présent dans S6C pour la société
dont le nouveau mnémonique est ALHYF. Le code `ALHYF.PA` n'était pas dans ce
référentiel : le retirer seul n'aurait pas supprimé l'appel à l'ancien code.

La liste effective du batch passe de **294 à 293 codes** sur la fenêtre courante,
avec ALPER conservé. L'exclusion s'applique à la collecte, aux sous-sélections
manuelles du collecteur, à la publication staging et à ses attentes de couverture.
Le résumé et le rapport staging conservent explicitement `excluded_symbols` :
une couverture de 100 % du périmètre réduit ne prouve pas que Lhyfe est couvert.

**Aucun effacement historique**, aucune modification du référentiel S6C figé,
aucun ancien run réécrit. Les autres batchs FR ne sont pas modifiés. Le blocage
fournisseur ci-dessous reste réel, mais ne fera plus échouer ce batch pour ce
seul titre au prochain passage. Aucune relance complète ni nouvelle publication
SQL n'a été effectuée pour l'exclusion. Validation : **77 tests ciblés réussis**.

Le bilan suivant décrit la réparation précédente, avant cette décision :

**Correction partielle effective, pas de déclaration de succès global du batch.**
Le dernier run `fr_daily_bars_sync` à 22h Paris a deux réponses vides,
`LHYFE.PA` et `PERR.PA`, sur le 9–16 octobre. Le staging des autres réponses
a abouti : 1 750 couples titre/séance sur 1 764 attendus (99,21 %).
Les alertes du 16 octobre pour ALBOU/MLCHE sont distinctes des deux échecs.

### Gérard Perrier : réparé

- ISIN `FR0000061459`, ancien code `PERR.PA`, nouveau code `ALPER.PA`.
- Transfert XPAR vers ALXP effectif le **7 septembre 2026** ; l'ESMA archivé
  dans le référentiel S6C comporte les épisodes des deux segments.
- [Référence émetteur diffusée par Euronext](https://live.euronext.com/fr/product/equities/FR0000061459-XPAR).
- Le catalogue Paris et `search/ALPER` EODHD identifient ALPER, France, EUR,
  Gérard Perrier Industrie. Le champ ISIN fournisseur est nul : il n'est pas
  inventé ; le lien repose sur la preuve de l'émetteur et l'ESMA.
- `eod/ALPER.PA` retourne les six séances 9, 12, 13, 14, 15, 16 octobre.

La configuration `batch_fr.yaml → fr_daily_bars_sync.provider_symbol_migrations`
porte le changement daté. Le collecteur et le publisher staging utilisent la
même résolution : ancien code jusqu'au 6 septembre inclus, nouveau à partir du
7 septembre. Si une fenêtre chevauche cette frontière, les requêtes sont
découpées et les attentes de couverture comptent les séances de chaque code,
sans doubler les attentes d'une même société à la transition.

Le fichier S6C figé et les anciennes archives sont inchangés. Les nouvelles
archives, observations, checkpoints et lignes SQL portent **ALPER.PA**, jamais
PERR.PA par commodité. La reprise exige le hash et la fenêtre réelle du payload.
Un changement d'ISIN, une autre place, une autre devise, une migration dupliquée
ou une vérification fournisseur future/non horodatée bloque la résolution.

Rattrapage réel : **6 barres ALPER ajoutées au staging**. Une vérification SQL
en lecture seule confirme six dates, qualité `VALID`, **une version par date**.
Ce statut est celui du contrôle technique OHLCV, pas une validation indépendante
du prix, une release canonique ou une autorisation tradable.

### Lhyfe : toujours bloqué par EODHD

- ISIN `FR0014009YQ1`, mnémonique officiel **ALHYF** depuis le 8 septembre.
- [Communiqué de l'émetteur](https://www.lhyfe.com/investors/financial-press-releases/?CLIENT=ACTUS-0-468&ID=ACTUS-0-100041).
- L'ancien `LHYFE.PA` retourne vide ; `eod/ALHYF.PA` retourne **HTTP 404**.
- Le catalogue Paris ne contient pas de remplaçant Lhyfe au moment du contrôle.
  La recherche par ISIN trouve seulement `F1B.F` (Allemagne).

**Ne pas remplacer par Francfort, par un ADR US ou par Alpaca SIP.** Ces flux
ne représentent pas la cotation EUR d'Euronext Growth Paris recherchée.
Avant la décision d'exclusion ci-dessus, Lhyfe restait dans les attentes de
collecte et dans les erreurs : le batch pouvait
donc encore être **FAILED**, mais l'ancien échec PERR n'a plus lieu d'être au
prochain passage. Les anciens runs FAILED ne sont pas réécrits.

Action fournisseur nécessaire : demander à EODHD le code/API couvrant
`FR0014009YQ1`, Euronext Growth Paris ALXP, EUR, mnémonique ALHYF, avec historique
depuis le 8 septembre 2026. Tant que ce code n'est pas accessible et vérifié,
ne pas ajouter de migration Lhyfe active ni annoncer que ses données sont réparées.

## Preuves et commande bornée

`artifacts/fr/research/daily_bars_repair/20261016-v1/` contient :

- `provider_checks.json` : recherches ISIN EODHD et réponse 404 ALHYF, avec
  horodatages réels, sans token ni URL signée ;
- `provider_identity_verification.json` : résultat `search/ALPER` confirmant
  le code Paris, le nom et la devise ; ISIN fournisseur nul conservé tel quel ;
- `report.json` : collecte ciblée ALPER et résultat de réparation partielle ;
- `staging_report.json` : publication FR de six lignes, couverture ciblée 100 %.

Les OHLCV bruts et observations sont archivés par le collecteur habituel dans
`artifacts/fr/operations/eodhd_daily`, avec SHA-256. Les nouvelles lignes sont
dans `alpha_trade_fr.fr_provider_bars_staging`, leurs sources dans
`fr_raw_payloads`, suivi dans `fr_staging_progress` et `fr_ingestion_runs`.
Ni SQL canonique, ni modèle, ni ordre, ni tâche Windows ou horaire modifiés.

Prévisualisation locale sans réseau ni SQL :

```powershell
python -m scripts.research.fr_daily_bars_repair_20261016 --output artifacts/fr/research/daily_bars_repair/NOUVEAU_DOSSIER
```

Ajouter `--write` réalise uniquement le contrôle fournisseur borné et le
rattrapage ALPER du 9–16 octobre en staging FR. Cette commande n'est pas un
backfill générique, ne réécrit aucun ancien run et exige un dossier de sortie neuf.
Il n'est pas utile de relancer tout le batch pour tenter de contourner le 404.

## Tests

69 tests ciblés collecte/staging/migration/runner/collecteurs réussis. La sélection élargie
avec collecteurs et horaires donne **81 réussites et 2 échecs hors correctif** :
`test_fr_cn_batch_schedules` attend encore 9 batchs FR actifs et n'inclut pas
`fr_consensus_snapshot` dans ses budgets, alors que ce batch a été activé
précédemment. Ni son activation ni les horaires n'ont été changés ici.
