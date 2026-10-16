# Suite bornée : identités et préparation intraday — 16 octobre 2026

Le [diagnostic du corpus présélectionné est clôturé](news_financement_cloture_corpus_20261016.md)
après les quatre dernières lectures. Aucun rattrapage de prix supplémentaire
ni entraînement n'est déclenché par cette clôture.

Suite livrée : [seconde revue bornée de 30 textes nouveaux](news_financement_seconde_revue_20261016.md),
sans nouvelle collecte ni événement primaire entièrement qualifié du titre associé.

## Rattrapage autorisé, terminé et contrôlé — 16 octobre, 16h18 Paris

**Terminé COMPLETED à 16h18:39 Paris**, tâche Windows revenue Ready avec code
de sortie 0. Quinze tranches sur quinze réussies, zéro échec, vide ou rejet.
**4 776 barres réellement présentes en table**, vérifiées par SELECT sur
`run_id=intraday-8e54e4efc373af722a2c` : 15 titres, dates du 13 au 15 octobre,
`provider=alpaca`, `data_source=alpaca_sip`, `interval_code=5m`, marché US_EQ,
prix raw et zéro barre synthétique. Le compteur de persistence du collecteur
signifie lignes soumises ; la lecture SQL confirme ici la présence de 4 776
lignes rattachées au lot, sans prétendre auditer tous les historiques.

Contrôle de couverture après rattrapage, sans rendement : **10 fenêtres complètes**
sur les 30 couples initiaux, contre zéro auparavant ; 14 restent sans fenêtre
valide (notamment les autres symboles non sélectionnés), une garde sa réserve
de proximité d'ouverture, cinq restent non achevées **à la borne figée d'origine**.
Pas de décalage silencieux de cette borne vers l'heure courante.

Ces barres ont été reçues après l'ancien cutoff de news : cette couverture
technique actuelle n'est pas une preuve qu'elles étaient disponibles alors.
Le test reste bloqué faute d'événement primaire entièrement qualifié ; aucun
signal, rendement ni PnL n'est calculé. Rapport :
`artifacts/research/us_news_financing_feasibility/20261016-post-intraday-backfill-v1/report.json`.

Sur GO explicite utilisateur, le sous-univers de 15 titres a été matérialisé
dans `config/univers/research_news_issuer_20261016.txt`, sans modifier l'univers
tradable. Plan prévisualisé et verrouillé : **`intraday-8e54e4efc373af722a2c`**,
Alpaca **SIP**, compte `default`, 5 minutes, 13–15 octobre inclus, 15 tranches
maximum. Pas de `--refresh`, fallback ou collecte de séance courante.

Lancement via `AlphaTrade-NewsIssuerIntraday-Recovery-20261016`, tâche Windows
manuelle sans déclencheur, action masquée indépendante de cette conversation.
Les dates, sous-univers et identifiant attendus sont figés dans l'action.
Premier contrôle : 3 tranches terminées, 804 barres reçues/soumises, zéro rejet
ou échec ; ce n'est pas le bilan final ni le nombre garanti de nouveaux INSERT.

Suivi : `artifacts/intraday_backfill/intraday-8e54e4efc373af722a2c/progress.json`.
Rapport final : même dossier, `report.json`. Journal :
`log/batch/news-issuer-intraday-20261016.log`. L'écriture réelle autorisée
concerne `alpha_trade.stock_bars_intraday` et les fichiers/checkpoints du lot,
pas les prix quotidiens, news, modèles, tables FR/CN ou ordres.
Les sections « non exécuté » ci-dessous décrivent la préparation antérieure
et ne remplacent pas le suivi de ce lancement. Le 16 octobre reste différé.

## Résultat utile

**Les fenêtres manquent parce que les historiques intraday existants s'arrêtent
trop tôt**, pas parce que les requêtes de couverture auraient démontré une
panne Alpaca. Dans l'échantillon de 30 symboles, 29 ont leur dernière barre le
9 octobre ; EADSY n'a aucune barre locale. Les trois plans existants demandent
une fin au **10 octobre 2026**, un samedi. Les annonces des 14–16 octobre sont
donc en dehors du périmètre téléchargé. Ce contrôle ne démontre pas que le
fournisseur couvre EADSY, ni qu'il est incapable de le couvrir : aucun appel.

Un garde-fou d'identité **de recherche** et une demande de rattrapage **non
exécutée** sont préparés. Aucun batch, univers actif, modèle ou table modifié.
Zéro API fournisseur/LLM, entraînement, rendement, backtest ou ordre.

## 1. Contrôle d'identité : réserver, jamais approuver automatiquement

Source : les mêmes 30 couples et leurs citations figés dans
`artifacts/research/us_news_event_qualification/20261016-complete-review-v1/bounded_review/`.
Référentiel : l'instantané `stock_metadata` déjà attaché à cette revue,
empreinte vérifiée. Il est actuel, non PIT ; date manquante non reconstruite.

Le script `scripts/research/us_news_issuer_readiness_20261016.py` extrait les
mentions **place:ticker** et produit seulement des réserves ou des demandes
de lecture. Une mention du titre peut désigner un concurrent ou un partenaire.
Un rapprochement lexical du nom ne prouve donc ni l'identité de l'émetteur
du financement, ni la nouveauté, ni l'instrument.

| Statut de diagnostic | Couples |
| --- | ---: |
| Mention explicite du ticker sur une place US, à relire | 7 |
| Simple indice lexical de nom, à relire | 18 |
| Collision explicite entre places | 2 : SUN et RGLD |
| Aucune ancre locale explicite, réservé | 3 |

- **SUN** : `TSXV:SUN` est Stardust Solar, pas `NYSE:SUN` Sunoco.
- **RGLD** : `CSE:RGLD` est Red Lake Gold, pas `NASDAQ:RGLD` Royal Gold.
- **BN** : mentions TSX et NYSE du même ticker ; pas de rejet automatique
  pour double cotation. La nature préférentielle de l'offre reste à traiter
  séparément des actions ordinaires.
- **CCJ/CCO** : Cameco est un indice de même société, mais une correspondance
  historique entre instruments reste à qualifier ; le nom seul n'est pas une preuve.
- **FBK/FBP** : les mots génériques tels que « financial » ne permettent pas
  de valider une identité d'entreprise.
- **FLEX** : un vrai `NASDAQ:FLEX` dans un article n'en fait pas l'émetteur
  de la dette de SentinelOne décrite dans un autre paragraphe.

**Zéro approbation automatique**, y compris sur les 25 couples à relire.
Ce test porte sur l'échantillon déjà lu, pas sur de nouvelles sociétés hors
échantillon. Ce n'est pas un modèle d'identification évalué par AUC/précision,
ni un filtre de production. Les associations news existantes ne sont ni
supprimées ni remappées ; une association contextuelle peut être légitime.

## 2. Diagnostic intraday en lecture seule

Requêtes indexables par symbole, intervalle 5m, tri date décroissante, limite 1,
schéma `alpha_trade`, session READ ONLY, timeout 15 s. Les champs de prix ne
sont pas nécessaires et ne sont pas lus. La dernière ligne observée n'est pas
un audit de continuité de toutes les barres du titre ou de tous les flux.

Les 29 dernières lignes retournées appartiennent au flux `alpaca_sip` et à la
séance du 9 octobre ; certaines se terminent après la clôture régulière.
Elles ne sont pas utilisées à tort pour compléter des fenêtres RTH du 14 octobre.

Plans locaux vérifiés :

| Plan | Début demandé | Fin demandée | Flux |
| --- | --- | --- | --- |
| `intraday-54e358aaf00a49fba091` | 2025-12-20 | 2026-10-10 | Alpaca SIP |
| `intraday-6286ab46f093feadb926` | 2025-01-01 | 2026-10-10 | Alpaca IEX |
| `intraday-fbc507f68cbaf2824fe7` | 2025-01-01 | 2026-10-10 | Alpaca SIP |

Ils portent sur 1 790 symboles. Leur configuration de fin explique pourquoi
aucun ne demandait les séances des annonces ; elle ne prouve pas leur succès
sur chaque tranche historique. Aucun de ces runs n'a été repris ou modifié.

## 3. Rattrapage technique proposé, pas lancé

Demande figée :
`artifacts/research/us_news_financing_feasibility/20261016-issuer-readiness-v1/backfill_request.json`.

- **15 titres** dont le sujet/émetteur a déjà été rapproché dans la revue,
  sans collision explicite de place : AEP, BN, CBRL, CCJ, EMR, MSCI, NTR, PRMB,
  SNPS, SWKS, SYY, TSLA, TSM, UTHR et V.
- Ce sont des cas et témoins de **couverture**, pas 15 financements nouveaux,
  recommandations, LONG/SHORT ou événements qualifiés.
- **Alpaca SIP**, compte principal `default`, intervalle **5 minutes**,
  séances du **13 au 15 octobre 2026**, une tranche de sept jours maximum.
  Le 13 couvre la séance précédente des articles du 14 publiés avant ouverture.
- Prévision de 15 tranches symbole/période ; pas une garantie de 15 appels
  exacts, d'accès, de couverture ou de coût. Aucun fallback vers IEX/EODHD.
- L'univers ciblé serait `config/univers/research_news_issuer_20261016.txt`.
  **Fichier non créé à cette étape**, pas de modification du fichier tradable.
- Une prévisualisation de commande est conservée dans `report.json`, mais
  **elle n'est pas encore exécutable sans matérialiser cet univers**.
- **16 octobre différé** : le backfill existant refuse une fin à la date NY
  courante. Ce garde-fou n'est pas contourné. Pour cette journée, la commande
  actuelle ne deviendra recevable qu'après le passage au 17 octobre à New York,
  soit **le 17 octobre à 06h00 Paris**, pas simplement dès la clôture US.

La collecte nécessite un nouveau GO explicite. Le code existant pourrait
créer sa table si elle était absente et écrire les barres : ce n'est pas une
commande READ ONLY. Ici, seule la demande de recherche est enregistrée.

## 4. Ce que ce rattrapage ne résoudra pas

Télécharger les prix de publication autoriserait un diagnostic descriptif de
réaction, **pas un signal historiquement disponible à la publication**. Nos
réceptions de news et annotations restent datées réellement. Un test simulant
notre application doit partir du maximum des disponibilités requises, puis du
prochain instant d'exécution admissible ; il pourrait nécessiter des barres du
16 octobre ou après, absentes de ce premier lot fermé au 15.

L'identité de l'émetteur, la nouveauté et l'instrument restent des portes
distinctes. Même un téléchargement réussi ne ferait pas disparaître les
réserves sur les 30 couples de la revue. Aucun PnL ou nouvel entraînement ne
doit être lancé au seul motif que les barres deviennent présentes.

## 5. Preuves et tests

Rapport :
`artifacts/research/us_news_financing_feasibility/20261016-issuer-readiness-v1/report.json`.
Il lie les sources par empreinte et conserve diagnostics, dernières lignes
intraday et demande de rattrapage. Les anciennes bornes de publication ne sont
pas décalées silencieusement vers l'heure de ce nouveau contrôle.

**80 tests de recherche ciblés passent**, dont collisions SUN/RGLD, double
cotation BN, nom Cameco, faux ancrage générique, mention d'un ticker sans
identité d'émetteur, filtrage du lot technique et respect de la séance courante.
Tests sans API et sans écriture dans la base métier.

```powershell
python -u -m scripts.research.us_news_issuer_readiness_20261016 --pack artifacts/research/us_news_event_qualification/20261016-complete-review-v1/bounded_review --output artifacts/research/us_news_financing_feasibility/NOUVEAU-DOSSIER-IDENTITES
```

Suite du [bilan de validation et revue](news_financement_validation_revue_20261016.md).
