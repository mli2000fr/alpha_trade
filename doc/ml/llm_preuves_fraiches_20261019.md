# Contexte frais Oracle → LLM — 19 octobre 2026

## Livraison et périmètre

Les prochaines analyses de l'étape 10 utilisent le protocole
`oracle-fresh-evidence-trend-v7`, avec GPT **ou** DeepSeek, en mode
`local_data_only` **ou** `web_search`. Les deux prompts distincts sont conservés.
Ils demandent une tendance LONG/SHORT/ABSTAIN sur l'horizon de séances fourni,
pas une probabilité de profit ni l'atteinte d'un TP avant SL.

Le paquet est préparé par `service/llm_directional/fresh_evidence.py` : uniquement
lectures SQL des données déjà collectées, sans téléchargement de complément.
Il ne transmet pas les tables brutes. Il ajoute d'abord le calendrier et les
extraits SEC, puis un résumé prix/volume et les comptes SEC recevables. Consensus
et actualités archivées passent aussi un contrôle de fraîcheur plus strict.

Fournisseur, modèle configuré, univers, classement Oracle, protections, seuils de
confiance et règles risque/PAPER ne changent pas. Aucun entraînement ni gain
directionnel nouveau n'est démontré par cette livraison.

## Ce que signifie « à jour »

Le cutoff est l'heure UTC **réelle** de préparation du paquet, avant l'ouverture
de la séance suivante. Toutes les réceptions doivent le précéder. Publication,
période fiscale, séance de prix et réception sont distinguées ; une récupération
aujourd'hui ne transforme pas des comptes anciens en nouvelle annonce.

| Famille | Contrôle par défaut | Données transmises / limite |
|---|---|---|
| Consensus EODHD | Réception ≤ 72 h ; période fiscale entre J−120 et J+400 jours ; fourchettes cohérentes | Jusqu'à 4 périodes/horizons, 3 snapshots réellement collectés pour comparaison, dans la même limite de fraîcheur. Les références J−7/30/60/90 restent des champs fournisseur, pas des collectes inventées. |
| News archivées | Publication ≤ 7 jours et réception ≤ 72 h ; texte/mapping/reçus scellés compatibles | Jusqu'à 8 articles × 2 400 caractères ; troncature explicite. Pas de table courante mutable ni de score sentiment non relié à la version du texte. |
| Résultats à venir | Calendrier mis à jour depuis ≤ 72 h, 45 jours à venir | Jusqu'à 3 dates, estimations EPS/revenus et période ; heure d'annonce inconnue, date fournisseur non confirmée. Aucun résultat futur réalisé joint. |
| SEC | Dépôt et réception ≤ 14 jours ; référence ticker/CIK fraîche ≤ 7 jours et non ambiguë ; collectes terminées avant cutoff | Jusqu'à 3 extraits × 1 800 caractères ; 8-K/6-K/10-Q/10-K et amendements, EX-99 si disponible. URL SEC, CIK, accession et SHA-256 du contenu contrôlés. |
| Prix / volume | **Dernière séance US clôturée exacte**, barres non synthétiques et OHLC valides, reçues avant cutoff ; pas de repli J−1 | Résumé OHLCV, variations 1/5/10/20 séances, gap, variation intraday, volume relatif aux 20 séances précédentes. Historique contigu, même fournisseur/ajustement. IEX exclu. |
| Fondamentaux | Source SEC_EDGAR uniquement, récupération ≤ 45 jours, dépôt ≤ 120 jours, période fiscale ≤ 200 jours | Dernière période recevable : revenus, EPS, marges, croissance, endettement, liquidité et actions. NULL conservés. Échelles/TTM non certifiés signalés ; aucun repli Yahoo. |

Les limites sont dans `config.yaml → llm_directional_filter`, clés `evidence_*`.
Elles se modifient explicitement, pas automatiquement pour faire passer une
sélection. Pour les nouvelles preuves locales consensus/news, les limites les
plus restrictives s'appliquent aussi avec les réglages hérités
`consensus_max_age_days` / `max_source_age_days`.

Les comparaisons de consensus sont marquées `HISTORICAL_COMPARISON` et ne
comptent pas comme autant de preuves directionnelles actuelles indépendantes.
Les périodes ou fourchettes incohérentes sont écartées. Les tableaux provisoires
ne sont jamais rebaptisés « qualifiés » parce que leur réception est récente.

### SEC : extrait utile et provenance

Le contenu SEC peut être une soumission SGML complète, pas seulement une page
HTML. Le lecteur retire l'en-tête technique, sélectionne un communiqué EX-99
intégré lorsqu'il existe, sinon le texte du formulaire principal. Pour un
communiqué, l'introduction est conservée : une mention tardive d'« outlook » ou
le safe harbor ne doit pas masquer l'annonce et ses chiffres principaux.
Scripts, styles et faits inline XBRL cachés ne sont pas utilisés comme texte.

L'archive conserve accession, URL, hash du **document intégral reçu**, type du
document extrait (`excerpt_document_type`), conteneur et troncature. Il ne s'agit
pas de prétendre avoir téléchargé un fichier séparé lorsqu'on lit un EX-99
embarqué dans une soumission déjà archivée. La disponibilité inclut par prudence
la fin du run de collecte. Une date de dépôt reste une date seule ; le champ
d'acceptation historique naïf est conservé brut, sans heure UTC inventée.

Un extrait valide permet de discuter des faits et des risques, **pas** de
conclure automatiquement LONG/SHORT. Le prompt distingue résultats/guidance,
émission exécutée, enregistrement shelf, revente et dette ; il interdit de
confondre émetteur, partenaire, investisseur et déclarant d'un 13F.

### Prix et opérations sur titres

Sources admises : `alpaca_sip`, `eodhd`, `eodhd_eod`. Pas de calcul mélangeant
sources ou ajustements. Une rupture de séance/provenance raccourcit l'historique ;
un split connu dans la fenêtre supprime les variations historiques et le volume
relatif. L'absence de split connu n'est **pas** une preuve d'exhaustivité des
opérations sur titres. Les statuts et réserves restent dans le résumé.

## Contexte n'est pas autorisation d'entrée

- Calendrier, prix/volume et fondamentaux : **contexte**, jamais une preuve
  directionnelle suffisante à eux seuls.
- Consensus non qualifié (unités/période/statut) et news dont seul le mapping
  fournisseur est connu : contexte provisoire, pas de promotion automatique.
- SEC : identité ticker/CIK, provenance et intégrité vérifiées dans le paquet.
  Le LLM doit encore citer un extrait exact et argumenter la direction.
- En local, la réponse doit citer le nombre minimal de preuves **admissibles**.
  En Web, les règles de sources Web traçables/récentes restent requises.

Il est donc normal qu'un contexte plus complet conduise à ABSTAIN. On n'a pas
levé les réserves SQL de consensus/news ni inventé de qualification humaine.
Aucune écriture de statut dans les tables sources. Options, ownership/13F,
macro et borrow ne sont pas ajoutés en vrac dans ce paquet.

## Sources Web et fraîcheur

DeepSeek Search/Fetch v7 applique la fenêtre la plus stricte entre
`max_source_age_days` et `evidence_news_max_age_days` (7 jours par défaut).
Les résultats périmés, futurs, non datés ou à date ambiguë sont exclus **avant**
Fetch et avant l'analyse DeepSeek. Les reçus bruts et motifs d'exclusion restent
archivés, pas effacés. Aucun relais GPT.

Pour GPT Web, la recherche est un outil intégré côté fournisseur : l'application
ne contrôle pas chaque page vue **avant** son exposition au modèle. Le prompt
impose la fraîcheur et le validateur applique après réponse la même fenêtre de
7 jours, les URL traçables et les dates recevables. Ne pas présenter ce mécanisme
comme un filtre préalable de toutes les pages consultées côté OpenAI.

Les dates seules sont évaluées comme des intervalles, sans heure inventée ;
les ambiguïtés ne valent pas preuve fraîche. Les URL inventées restent exclues.
La structure JSON requise, selon les
[sorties structurées OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs),
ne certifie pas les faits : les contrôles locaux demeurent indispensables.

## Péremption du paquet, archive et exploitation

Avant **chaque appel**, le cutoff et les limites sont revérifiés. Un paquet
préparé depuis plus de 30 minutes est bloqué (`evidence_context_max_age_minutes`),
sans rafraîchissement implicite au milieu de l'analyse. Relancer une **nouvelle**
analyse si nécessaire. Prix J absent/invalide : arrêt avant tout appel LLM.
Famille facultative absente/périmée : statut explicite, pas de contenu de repli.
Erreur SQL réelle : ne pas l'assimiler à une absence normale de données.

Les tables existantes suffisent :

- `llm_directional_runs.input_json` : paquet exact, dates, statuts, exclusions,
  limites et empreinte ; `config_json` : réglages figés ;
- `llm_directional_assessments.request_json/response_json` : requête/réponse exactes,
  reçus Search/Fetch lorsqu'utilisés ;
- `assessment_json` : citations, qualifications, décision/confiance subjective,
  `consensus_analysis` et nouvelle `context_analysis`.

Les logs détaillent le cutoff et les statuts par famille ; le rapport LLM expose
ces statuts et la politique de fraîcheur. Pas de nouvelle table/migration.
Les archives v4/v5/v6 gardent leurs prompts, requêtes et règles historiques.
Les étapes 11/12 revalident l'archive du run exact, sans aller substituer les
données devenues courantes. Les protections et contrôles de nouvelles entrées
restent séparés. Les anciens résultats ne sont pas enrichis rétroactivement.

## Vérification en base, sans appel LLM

Outil reproductible, dossier neuf obligatoire :

```powershell
python -m scripts.research.us_llm_fresh_context_preview --output artifacts/research/us_llm_fresh_context/NOUVEAU_DOSSIER
```

Il réutilise **la sélection Oracle archivée du dernier run terminé**, pas un
nouveau classement Oracle, et prépare le contexte avec un cutoff courant.
Chaque requête est gardée en lecture seule par un garde SELECT/SHOW/DESCRIBE.
Un fichier par titre et `report.json` sont produits localement ; aucun
`Repository.create`, appel GPT/DeepSeek/fournisseur, ordre ou entraînement.
Cet aperçu courant n'est **pas** une reconstitution historique PIT.

Rapport de référence :
`artifacts/research/us_llm_fresh_context/20261019-v4/report.json`.
Sélection archivée du 16 octobre : CCOI, ICHR, BAND, FUN, UCTT, FMC, MXL, COHR,
TXG, DOCN (`llm-fa604bed142d41a7be61012432c1fc6e`).

- 10 contextes préparés, 0 blocage ; calendrier et résumé prix disponibles pour
  les dix, quatre périodes de consensus récentes chacune, toujours provisoires.
- 48 extraits de news au total, répartis sur neuf titres ; mapping d'identité
  non qualifié, donc pas d'autorisation directionnelle automatique.
- Un dépôt SEC récent qualifiable : FMC, 8-K du 15 octobre, communiqué EX-99.1
  extrait de la soumission archivée. Aucun avis LONG/SHORT généré ici.
- Aucun fondamental SEC ne passe tous les critères pour ces dix titres ; statut
  explicite, pas de valeurs anciennes/Yahoo substituées.
- Les versions d'aperçu antérieures restent conservées pour la traçabilité des
  corrections d'extraction ; v4 fait référence.

Ces observations ne garantissent pas que tous les titres passeront les gates
du filtre local. Une future étape 10 crée un nouveau run et ses propres dates.

Tests : fraîcheur/publication/réception, erreurs, calendrier sans résultats
futurs, CIK ambigu, intégrité/extraction SEC, prix J/SIP/splits, quatre parcours
GPT/DeepSeek × local/Web avec transports simulés, refus des pages périmées,
archive v7 revalidable sans tables sources et compatibilité v4/v5/v6.

**Bilan de vérification : 802 tests passent**, dont 53 contrôles v7 dédiés,
avec clés API et accès SQL neutralisés pour la suite hors ligne. L'aperçu de
production a exécuté 182 requêtes de lecture et aucune écriture SQL. Aucun
test payant de génération n'a été lancé ; la qualité réelle des futures
décisions LONG/SHORT reste à évaluer séparément.
