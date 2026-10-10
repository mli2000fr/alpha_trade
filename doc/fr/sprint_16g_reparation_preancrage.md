# Sprint 16-G — reconstruction partielle avant l'ancrage

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Vérification du 8 octobre 2026

Le dossier figé utilise 21 séances de features du 9 septembre au 7 octobre.
Treize séances précèdent son Full ESMA du 26 septembre. La nouvelle recherche
ne modifie ni ce dossier ni les batchs existants : elle reconstruit séparément
les références publiques, à partir des archives officielles ESMA.

**Constat réel :** le Full du 5 septembre existe (deux fragments actions),
mais l'index interrogé ne contient pas de Delta du **9 septembre**. Il est
interdit d'interpréter ce trou comme « aucun changement ». Cette voie ne
répare donc pas les treize séances. L'absence constatée concerne cet index
à la date de consultation, pas une preuve que le fichier n'a jamais existé.
Index et diagnostic conservés dans
`artifacts/fr/research/preanchor_replay_16g/index-blocked-sep05-20261008-v1/`.
Statut `BLOCKED_ARCHIVE_INDEX` : aucune archive téléchargée pour cette voie.

**Alternative disponible :** Full du **12 septembre**, deux fragments actions,
puis Delta de chaque date civile du 13 au 25 septembre : **44 archives** au total,
sans journée de publication ni fragment manquant dans l'index consulté.
Cette chaîne peut étayer les dix séances du 14 au 25 septembre, pas les
9, 10 et 11 septembre. La présence d'un index complet n'est pas encore une
validation des contenus : téléchargement, MD5, ZIP, lecture et rejeu nécessaires.

## Exécution séparée

Service : `service/fr/preanchor_replay_16g.py`.
Le service vise les **233 couples ISIN/MIC du dossier figé**, pas seulement
les trois sociétés du pilote. Les archives historiques déjà locales sont
réutilisées après vérification MD5 et ZIP. Les autres sont téléchargées dans
le seul répertoire de recherche. La lecture XML est en flux et filtre les
couples exacts. Les événements suivent le moteur de rejeu existant ; les
anomalies sont conservées et empêchent un succès complet.

Run lancé le 8 octobre à **21:44:24 Paris**, sans fenêtre Windows :
`artifacts/fr/research/preanchor_replay_16g/september-window-20261008-v3/`.
Logs : `log/batch/fr-preanchor-16g-20261008-v3/`.
La version v1 a échoué sur un mauvais appel du validateur Delta avec des Full,
corrigé et couvert par test. La v2 a correctement identifié la journée du
9 septembre manquante et n'a téléchargé aucune archive. Le run v3 utilise
l'alternative du 12 septembre. Ne pas confondre ces trois exécutions.

```powershell
Get-Content F:\projets\log\batch\fr-preanchor-16g-20261008-v3\stdout.log -Tail 10
Get-Content F:\projets\log\batch\fr-preanchor-16g-20261008-v3\stderr.log -Tail 15
Test-Path F:\projets\artifacts\fr\research\preanchor_replay_16g\september-window-20261008-v3\report.json
```

Chaque ligne du journal indique le fichier terminé et le nombre d'événements
cibles. La première ligne peut attendre la fin du téléchargement et de la
lecture du premier gros Full ; il ne s'agit pas de 44 entraînements.

Le rapport final distingue `covered_session_count` de `all_sessions_active`.
Un titre couvert sur 10/13 séances ne devient pas couvert sur toute la fenêtre.
`PREANCHOR_RESERVED` est donc attendu si les trois premières séances restent
non couvertes, même avec une reconstruction partielle utile.

L'index reçoit son horodatage réel de consultation ; chaque archive reçoit
l'heure de vérification. Ces preuves obtenues après 09:00 ne démontrent pas
leur réception par l'application avant la décision historique. Elles ne sont
jamais antidatées. Le champ nominal EUR FIRDS ne devient pas automatiquement
une devise de cotation qualifiée.

## Progrès parallèle du pilote actions/devises

- [Airbus, transactions du 11 au 18 septembre](https://www.airbus.com/en/newsroom/press-releases/2026-09-airbus-reports-share-buyback-transactions-11-18-september-2026) et [du 21 au 25 septembre](https://www.airbus.com/en/newsroom/press-releases/2026-09-airbus-reports-share-buyback-transactions-21-25-september-2026) : l'ISIN et des transactions exprimées en EUR apparaissent dans des tableaux agrégés XPAR/XETA. Corroboration ponctuelle, pas preuve d'un intervalle complet propre à XPAR ni split/dividende.
- [L'Oréal, AG du 24 avril](https://www.loreal-finance.com/fr/communique-de-presse/assemblee-generale-mixte-du-24-avril-2026) : dividende ordinaire 7,20 EUR, détachement le 29 avril. Cet événement est hors fenêtre septembre–octobre ; il ne prouve pas l'absence d'un autre événement dans la fenêtre.
- [Sanofi, dividende](https://www.sanofi.com/en/investors/sanofi-share-and-adrs/dividend) : détachement de l'action le 5 mai 2026, dividende 4,12 EUR ; les dates ADR sont distinctes. Même limite de couverture.

Ces pages HTML ont été consultées après la décision. Notes documentaires
uniquement : aucun archivage massif de sites investisseurs, aucun endpoint
Euronext de cours/Excel, aucune réactivation de source suspendue. Aucun
ajustement automatique des prix à partir de ces notes.

## Résultat final vérifié — 8 octobre 2026

Le run v3 est **terminé à 21:53:09 Paris**, statut `PREANCHOR_RESERVED`.
Ce statut traduit une réserve résiduelle, pas un plantage du calcul.

| Contrôle | Résultat |
|---|---:|
| Archives relues | 44 / 44 : 2 Full, 42 Delta |
| Archives réutilisées / nouvellement téléchargées | 42 / 2 |
| Journées ou fragments manquants sur la chaîne 12 → 25 septembre | 0 |
| Anomalies de rejeu | 0 |
| Événements Delta concernant les 233 couples candidats | 0 |
| Candidats avec dix séances pré-ancrage couvertes | 233 / 233 |
| Candidats avec les treize séances pré-ancrage couvertes | 0 / 233 |

Les dix séances reconstruites sont les **14–18 et 21–25 septembre**.
Les trois restantes sont les **9, 10 et 11 septembre**, pour les 233 candidats.
Le `reference_covered_count=0` mesure la couverture complète des treize séances ;
il ne signifie pas que les dix séances reconstruites sont inutilisables.

Après notification de fin, les SHA256 et MD5 des **44 fichiers** ont été
revérifiés, soit 471 346 750 octets lus, sans divergence. L'empreinte du dossier
source et la population exacte ISIN/MIC/symbole concordent. Les rapports figés
antérieurs n'ont pas été modifiés. Aucun modèle exécuté ni donnée SQL écrite.

## Suite après lecture du rapport

Mesurer les séances effectivement reconstruites, examiner chaque anomalie,
puis conserver explicitement les trois dates non prouvées. Une future fenêtre
entièrement postérieure au Full du 12 peut éviter ce trou de référence ; elle
exige néanmoins ses propres bars, actions, devises et preuves disponibles
avant la nouvelle décision. Ce n'est pas une permission de déplacer
rétroactivement la fenêtre du test figé.

Il reste interdit d'activer le serving ou les ordres sur la seule reconstruction.
Les contrôles de devise et d'opérations sur titres du
[pilote](sprint_16g_pilote_devises_actions.md) restent ouverts.

## Vérifications logicielles

Suite préparée : [nouvelle fenêtre prospective du 14 septembre au 12 octobre](sprint_16g_nouvelle_fenetre_prospective.md), décision minimale le 13 octobre.

**162 tests ciblés Sprint 16 passent**, dont dix nouveaux tests de rejeu :
couverture partielle, version future, absence de référence, radiation,
annulation, date de première cotation, séparation Full/Delta, journée manquante,
fragment Full dupliqué et absence de libération implicite. Commande :
`python -m pytest tests/test_fr_*16*.py --no-cov -q`.
Le test porte sur les garde-fous logiciels ; la validation des archives est
rapportée séparément ci-dessus. Le code et le rapport restent confinés à la recherche.
