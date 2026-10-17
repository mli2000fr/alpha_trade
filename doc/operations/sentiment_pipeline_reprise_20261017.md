# Étape 8 — Sentiment Pipeline : délais et reprise, 17 octobre 2026

## Évolution demandée : seuil de 95 % et bilan final des symboles KO

`sentiment_news_ingestion.min_success_ratio: 0.95` dans `config.yaml` autorise
désormais la suite si **au moins 95 %** des symboles demandés sont réussis.
Le numérateur est `succeeded_symbols + skipped_symbols` (checkpoints réussis
déjà à jour) ; le dénominateur est **tout l'univers demandé**, y compris les
titres en échec et ceux non exécutés. Une réponse fournisseur vide mais valide
est une collecte réussie, pas un échec. Les articles ne sont pas le dénominateur.

- 95/100 ou 19/20 : code 0, les sous-étapes FinBERT puis les étapes 9–12
  sélectionnées peuvent continuer, sous réserve de leurs propres contrôles.
- 94/100 : `INCOMPLETE`, code 1, chaîne bloquée.
- Auth/quota/TLS (erreur globale explicite) et SQL restent bloquants même
  au-dessus de 95 %. Aucun seuil ne contourne les contrôles d'accès ou de risque.
- Le coupe-circuit réseau ou les échecs consécutifs peuvent arrêter les appels ;
  les symboles non exécutés restent comptés. La décision finale porte sur la
  couverture atteinte, jamais sur les seuls titres tentés.

Une couverture partielle acceptée porte `status=COMPLETED` **pour l'orchestration**,
mais `collection_complete=false`, `coverage_status=PARTIAL_ACCEPTED` et les
compteurs/listes KO sont conservés. Le résumé porte un avertissement ; ce n'est
pas une déclaration de collecte exhaustive. La tolérance est appliquée au mode
résilient de l'étape 8 ; le CLI historique non résilient reste strict.

Le script PowerShell de l'étape 8 alloue un rapport unique par lancement via
`--summary-path`. Après la chaîne, même en cas d'échec, il relit ce rapport et
écrit un bilan lisible, par exemple :

```text
Étape 8 — bilan import news : 5 symbole(s) KO / 100 ; 0 non exécuté(s) ; couverture 95.00% ; PARTIAL_ACCEPTED
Symboles KO : ...
```

Ce nombre est celui de **l'import news**, pas un décompte inventé des erreurs
par symbole de FinBERT. En cas d'erreur SQL interrompant un lot, le journal
précise « KO connus » et que le compteur exact du lot est indisponible.
Le bilan final ne remet jamais à zéro le code d'une sous-étape échouée.

## Incident et diagnostic

Le run `20261017_071721_f2b84030` de 07h17 Paris s'est arrêté pendant l'import
EODHD `/news` sur `A.US` : cinq tentatives avec timeout de lecture de 15 secondes.
Le run précédent `20261017_014448_33995c90` avait échoué de même sur `AA.US`.
Le scoring FinBERT n'avait pas démarré lors du dernier incident. Le bandeau
« ETAPE 7 » est désormais aligné sur la carte **8** ; ce n'était pas la cause.

### Pourquoi un an dans le log ?

Sans date de début, `importe_news` utilisait `initial_backfill_days=365`.
Ce n'est **pas la preuve que tous les titres étaient interrogés sur un an** :
`--resume-checkpoints` était présent, puis la fenêtre était réduite par titre.
La lecture SQL du diagnostic a trouvé dans `eodhd_news` 12 760 checkpoints
`success`, 2 `failed` et un ancien `running`. Les watermarks conservés pour A
et AA étaient respectivement le 16 octobre 23:44:49 et le 10 octobre 00:21:37
(valeurs UTC du champ). Ces deux timeouts ne prouvent donc pas une requête annuelle.

Le collecteur quotidien utilise un namespace distinct, `eodhd_news_daily` :
ses checkpoints ne remplacent pas ceux de l'étape 8. Aucun rapprochement ni
réécriture SQL de ces sources n'a été effectué.

## Paramètres et comportement livré

Dans `config.yaml` :

```yaml
sentiment_news_ingestion:
  pipeline_lookback_days: 7
  request_timeout_seconds: 45
  max_attempts: 3
  max_consecutive_symbol_failures: 3
  min_success_ratio: 0.95
```

- Étape 8 sans début explicite : **J−7/J**, fin UTC courante, puis reprise dans
  cette fenêtre selon les checkpoints de la même source. Ce périmètre récent
  ne certifie pas un rattrapage de l'historique antérieur.
- Un début explicitement choisi dans l'IHM reste prioritaire. Le CLI historique
  sans `--lookback-days` conserve son fallback 365 jours pour compatibilité.
- EODHD : **45 secondes par tentative, trois tentatives au maximum**, backoff
  conservé. Ce n'est pas un budget de durée totale du run.
- Une erreur fournisseur isolée est enregistrée par titre ; les suivants sont
  traités. Une réponse vide valide n'est pas assimilée à un timeout.
- Trois échecs consécutifs arrêtent les appels, compteur conservé entre lots ;
  la couverture est ensuite évaluée selon le seuil ci-dessus. Le circuit réseau
  peut interrompre plus tôt. Authentification 401/403,
  quota 429 et problème TLS bloquent globalement, sans contournement.
- Les erreurs SQL ou de programmation restent fatales et finalisent le rapport
  `FAILED` ; elles ne sont pas traitées comme de simples titres ignorés.

La commande générée contient `--continue-on-symbol-error`,
`--resume-checkpoints` si activé dans l'IHM, et `--lookback-days 7` sans début
explicite. La chaîne reste import → pertinence → FinBERT standard → contextuel
→ features. **Couverture sous le seuil ou erreur globale bloquante = code 1 :
les sous-étapes suivantes ne démarrent pas**. Une couverture partielle acceptée
sort à 0, conserve ses réserves et permet la suite.

## Reprise et compteurs

Seul un checkpoint réussi peut justifier de sauter un titre ou réduire sa
fenêtre. L'`updated_at` d'un checkpoint `failed`/`running` ne constitue pas une
preuve de réussite : ces titres sont rejoués dans la fenêtre demandée.

Le succès d'un titre, même avec réponse vide, enregistre sa fin uniquement après
pagination et persistance réussies. Les offsets EODHD dépendent de `from/to`
et du classement du flux : ils repartent à **zéro** en reprise, plutôt que
d'être utilisés avec une fenêtre modifiée. Les déduplications restent actives.
Une page récente d'une pagination incomplète ne remplace plus la borne du dernier
succès ; les pages anciennes peuvent encore manquer. Les pages déjà persistées
avant une erreur restent conservées et comptées. Une période historique plus
ancienne exige un rattrapage explicitement borné.

## Rapports et utilisation

`artifacts/news_import_runs/news-import-<id>/progress.json` et `report.json`
contiennent provider/source, fenêtre, titres demandés, sautés, tentés, réussis,
échoués, non exécutés et compteurs d'articles. Les unités sont explicites :
demandés/reçus = titres, persistés = lignes news comptées par le writer existant.
`INCOMPLETE` implique code 1. En cas d'erreur technique non isolable, les compteurs
du lot interrompu peuvent être partiels : le rapport le précise, sans succès inventé.
Écriture atomique avec reprises bornées des verrous Windows.

Le résumé `::alpha_trade_run_summary::` transmet les compteurs et détails aux
logs IHM, conservés dans `artifacts/ihm_pipeline_runs/sentiment_pipeline/<run_id>/`.

Lancer un **nouveau run de l'étape 8** pour utiliser le correctif. Si l'aperçu
conserve l'ancien bandeau ou n'affiche pas les nouveaux flags, recharger ou
redémarrer l'IHM avant lancement. Les anciens runs ne sont pas réécrits.

## Validation et limites

**280 tests ciblés réussis** : seuil inclusif 95 %, bilan final KO (deux chaînes
PowerShell locales factices, succès/échec), erreurs isolées, arrêt quota/auth/circuit,
compteurs partiels, checkpoint, offset zéro, fenêtre récente/historique explicite,
rapport incomplet, verrous Windows, commandes IHM, collecteur quotidien et workflow US.
Tests avec fournisseurs/bases simulés. Aucun import réel, scoring réel, appel LLM,
ordre, changement de tâche/horaire ni écriture SQL de maintenance lancé ; seules
des lectures de checkpoints ont été faites pour le diagnostic.

Le correctif ne garantit pas qu'EODHD répondra : une panne persistante sera
arrêtée et documentée. Si la couverture est insuffisante ou l'erreur globale
bloquante, le passage reste incomplet ; les manques ne sont jamais masqués.
