# US — Faisabilité des liens clients/fournisseurs parmi les TOP20 Oracle

Audit du 2 novembre 2026. **Terminé : faisabilité documentaire partielle ; pas
de test économique ni de promotion.** Quatre liens commerciaux explicites
concernent trois des vingt titres examinés. Leur intérêt directionnel reste
inconnu. Aucun appel LLM, téléchargement fournisseur, entraînement, prix futur,
calcul de rendement, ordre, écriture SQL ou changement de production ; coût 0 USD.

## Question et distinction avec les expériences antérieures

Un client important ou un fournisseur peut transmettre une information utile à
une autre entreprise. L'hypothèse consiste à enrichir le contexte du TOP20 avec
des **relations économiques explicitement documentées**. Le graphe P-MATH-1
de lead-lag statistique des cours était déjà NO_GO ; cette recherche examine
une autre source d'information, sans affirmer qu'elle donnera un meilleur résultat.

Le préprint [Cross-Stock Predictability via LLM-Augmented Semantic Networks](https://arxiv.org/html/2604.19476v2)
utilise des relations extraites de rapports annuels pour une stratégie de retour
à la moyenne. Il ne valide ni notre adaptation aux nouvelles des partenaires,
ni la direction du TOP20 Oracle, ni un horizon H5/H20. Une bonne nouvelle pour
un client n'est pas automatiquement une bonne nouvelle pour son fournisseur :
matérialité, nouveauté, attentes et calendrier restent à établir.

## Périmètre figé et méthode

- TOP20 **originaux**, avant filtre options, séance du **30 octobre 2026** ;
  modèle `model-factory-20261016180250-3b0515`.
- Instant limite de la sélection archivée : **1 novembre 2026, 09:26:02.535046 UTC**.
  Il s'agit de la préparation avant la séance suivante, pas d'une décision à la
  clôture du 30 octobre. Le document FMC, reçu le 31, n'était pas disponible
  localement pendant la séance du 30.
- Titres : CCOI, BAND, FUN, TXG, UCTT, DOCN, MXL, ICHR, COHR, QDEL, FORM,
  VICR, MRVL, PENG, SIMO, TSEM, FMC, SITM, ABR, FN.
- Lecture SQL seule dans `alpha_trade`, avec rejet des mutations et des prises
  de verrou. Sources existantes : `sec_filing_raw`, reçus `pit_collection_runs`,
  métadonnées de sociétés et cache local SEC. Les nouvelles des contreparties
  sont comptées via `news_raw` et `news_ticker_map`, sans nouvel appel fournisseur.
- Inventaire : 455 dépôts, dont 447 avec hash de contenu, pour la population
  courante et historique. Malgré la borne de recherche depuis 2023, le plus
  ancien dépôt effectivement trouvé date du **3 septembre 2026**.
- Copie locale bornée : au plus trois dépôts par titre courant, 60 documents
  et 15 Mo/document. **32 soumissions**, toutes vérifiées par hash, couvrent
  **14/20 sociétés (70 %)** ; 57 parties visibles, environ 2,21 millions de caractères.
  Les annexes XBRL techniques ne constituent pas des textes d'analyse.
- CCOI, COHR, FN, FUN, ICHR et TXG n'ont pas de corps copié dans ce périmètre.
  Cela ne prouve ni une absence de dépôt SEC, ni une absence de relations.

L'indicateur initial `selected_current_symbols=13` comptait les symboles SQL
stockés, parfois NULL. Le bon dénominateur est le propriétaire demandé et
vérifié par CIK : **14**, utilisé dans le bilan final. Aucun symbole SQL corrigé.

Les alias de noms servent à présélectionner des passages. « bandwidth »,
« packaging », « reliance », une cotation Nasdaq, un agent bancaire ou une
référence Nvidia ne suffisent pas à créer une relation client/fournisseur.

## Résultat documentaire

| Titre Oracle | Contrepartie | Relation prouvée dans le document | Limite |
|---|---|---|---|
| UCTT | Applied Materials — AMAT | Client : **22,3 %** du chiffre d'affaires du trimestre clos le 25 septembre 2026 | Poids passé, pas prévision de commandes |
| UCTT | Lam Research — LRCX | Client : **38,8 %** du même chiffre d'affaires ; les deux représentent **61,1 %** | LRCX absent du fichier tradable ; contexte externe autorisé, sans ajout à l'univers de trading |
| FMC | Corteva — CTVA | Accord de fourniture et licence, acompte initial de **200 M USD** | Produit différé au bilan ; ce montant n'est ni un bénéfice ni un revenu déjà reconnu |
| TSEM | Semtech — SMTC | Accord pluriannuel de capacité de fabrication SiGe ; partenariat de vingt ans | Pas de poids de revenus établi ; SMTC également hors fichier tradable |

**Couverture documentaire : 3/20 titres, soit 15 %, et quatre liens.** Ce
n'est ni quatre signaux de trading ni une estimation de précision. Les noms
des partenaires sont explicites ; leur correspondance aux tickers repose en
partie sur un cache SEC courant non versionné, insuffisant pour certifier une
identité historique à n'importe quelle date.

Deux partenariats supplémentaires restent séparés : BAND–Five9 et
FormFactor–Teradyne. Leur annonce ne démontre pas à elle seule une dépendance
client/fournisseur exploitable. Les liens financiers, anciennes acquisitions,
références de plateforme et simples mentions sont exclus du décompte.

### Cas important exclu : SITM–Avnet

Les **13,2 %** du trimestre clos le 30 juin figurent dans l'annexe des comptes
du **Timing Product Business de Renesas acquis par SiTime**, pas dans les
revenus consolidés de SiTime. Le texte de la transaction exclut expressément
les accords clients, fournisseurs et fonderies de la liste des actifs
transférés. La continuité d'un contrat avec Avnet n'est donc pas prouvée.
Ce passage est conservé avec le motif d'exclusion ; il ne compte pas comme
cinquième relation actuelle et ne permet aucune rétroprojection historique.

## Sources et disponibilité

| Dépôt SEC | Émetteur | Fin locale du run de collecte, UTC |
|---|---|---|
| `0001628280-26-067880`, 10-Q | UCTT | 29 octobre, 19:34:43.973498 |
| `0000037785-26-000171`, 10-Q | FMC | 31 octobre, 19:30:05.044000 |
| `0001178913-26-004752`, 6-K | TSEM | 14 octobre, 18:05:58.714867 |
| `0001451809-26-000068`, 8-K/A et annexe 99.1 | SITM, cas exclu | 13 septembre, 17:46:18.775211 |

L'éligibilité locale utilise le maximum entre observation, disponibilité et
fin du runner. Les runs sont `COMPLETED_WITH_WARNINGS` : les pièces sont
individuellement vérifiées par hash et identité, sans qualifier pour autant
toute la collecte comme parfaite. Le CIK du déposant est vérifié dans
l'en-tête ; les champs DEI du parent ou les tickers explicites du communiqué
relient le texte à l'émetteur. Les citations exactes, offsets, URL et hashes
sont conservés dans `closure/evidence.json`.

**Prudence sur les heures SEC :** le lecteur existant peut conserver
`ACCEPTANCE-DATETIME` sans fuseau dans `acceptance_datetime`. Cet audit
conserve cette horloge brute sans la déclarer UTC et ne l'utilise pas pour
antidater la disponibilité. Aucun changement du collecteur n'a été effectué.

## Nouvelles des contreparties et profondeur historique

Sur les sept jours précédant l'instant limite, les métadonnées existantes
contiennent **31 associations AMAT, 24 LRCX, 1 CTVA et 4 SMTC**. Les versions
et leurs associations ont des horodatages antérieurs au cutoff et au moins
300 caractères. Ce sont des comptes **par partenaire**, pas nécessairement
60 articles distincts. Ni l'attribution sémantique, ni la nouveauté, ni
l'intégralité hors paywall de ces articles n'ont été validées. Aucune
nouvelle n'a été transformée en signal directionnel. Avnet a trois
associations, inutilisées puisque son lien avec SITM est exclu.

Contrôle secondaire : 13 780 couples TOP20/jour, 237 titres, issus des modèles
annuels déjà archivés pour 2024–30 septembre 2026. Lecture des seules dates,
identités, rangs et scores ; **aucun résultat futur consulté**. Les quatre
relations retenues ont des reçus en octobre : **zéro couple historique
couvert par ces preuves disponibles à temps** — 0/5 040 en 2024, 0/5 000 en
2025, 0/3 740 en 2026. La liste des sociétés historiques ne constitue pas un
audit exhaustif de leurs propres rapports annuels ; seuls les TOP20 courants
ont eu une lecture des corps dans cette phase.

## Contrôle de la revue et écart de protocole

La borne initiale était vingt couples candidats et dix témoins. La correction
des alias a conduit à lire 22 couples distincts, puis deux contreparties
nommées dans des passages déjà lus : **24 couples**, dix témoins initiaux.
Cet écart est conservé explicitement ; plafond amendé à 25, revue arrêtée.
Aucun prix ni rendement n'a servi à sélectionner les passages. Les témoins
ne sont pas tous des négatifs certains : les mentions marketing « trusted by »
restent indéterminées. Il n'y a donc pas de calcul de précision/rappel du
repérage automatique. Revue par le même assistant, pas revue indépendante.

20 tests ciblés vérifient notamment les écritures SQL refusées, les alias
ambigus, les annexes XBRL, les preuves exactes, la finalisation des reçus et
l'exclusion du périmètre acquis. Les archives initiales, la seconde passe et
les échecs techniques d'inventaire sont conservés séparément.

## Conclusion bornée

**La donnée relationnelle existe, mais le corpus actuel est trop récent et
trop peu couvert pour tester honnêtement une amélioration directionnelle
historique.** La piste n'est pas invalidée économiquement ; son test est en
attente de preuves datées suffisantes. UCTT est un cas concret de forte
concentration clients à suivre, sans convertir cette concentration en LONG
ou SHORT. Pas de dépense GPT ni de nouveau modèle à ce stade.

Reprendre exigerait une décision distincte : compléter les relations sur un
périmètre figé, certifier les identités et dates, qualifier les nouvelles
des partenaires, puis comparer leur apport au contexte sectoriel sur des
dates non sélectionnées d'après les rendements. Aucun backtest de substitution
fondé sur des liens connus seulement après les décisions n'est prévu.

Artefacts : `artifacts/research/us_economic_links_feasibility/20261102-v4/closure/`.
Scripts : `us_economic_links_feasibility`, `us_economic_links_scan`,
`us_economic_links_news_coverage`, `us_economic_links_review` sous
`scripts/research`. La clôture est locale et refuse d'écraser son dossier.
