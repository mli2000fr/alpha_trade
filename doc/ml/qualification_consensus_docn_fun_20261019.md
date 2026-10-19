# Consensus DOCN / FUN — qualification bornée du 19 octobre 2026

**Actualisation après réponse du support transmise par l'utilisateur** :
[bilan des précisions reçues](consensus_eodhd_precisions_support_20261019.md).
Unités complètes et USD DOCN/FUN confirmés ; ancrages fiscaux FUN et rôle de
`0q`/`+1q` expliqués. Base EPS par item et composition des contributeurs restent
inconnues. Les sections suivantes conservent la revue initiale datée, pas une
qualification rétroactive. Aucun ancien rapport scellé n'est modifié.

## Conclusion

**Revue terminée ; collecte fidèle vérifiée, qualification économique partielle.**
Les 112 lignes examinées correspondent aux réponses effectivement archivées.
Cela ne suffit pas encore à transformer leurs variations en signaux LONG/SHORT.
Lors de cette revue initiale, les définitions fournisseur étaient encore en
attente ; le support a depuis répondu via l'utilisateur. Son retour lève
plusieurs réserves documentaires, pas la base EPS inconnue par enregistrement.
Aucun abonnement supplémentaire ni réentraînement n'est justifié par ce retour seul.

Le GO était limité à **DOCN et FUN**. FMC reste réservé : ses changements de
consensus s'accompagnent d'importants changements du nombre de contributeurs.
Aucun rendement futur, entraînement, backtest économique, appel LLM, API de
données payante, ordre ou écriture SQL dans cette qualification. Les collectes,
configurations et modèles de production n'ont pas été modifiés.

## Contrôles des données déjà reçues

Dossier immuable :
`artifacts/research/us_consensus_identity_review/20261019-v1/`.
Rapport achevé le **19 octobre à 20:09:16 UTC / 22:09:16 Paris**.
Il se rattache au pilote
`artifacts/research/us_directional_information/20261019-v2/observed-revisions-v1/`.

- Deux émetteurs, huit observations réellement collectées du 11 au 18 octobre,
  sept enregistrements proches-période par émetteur et observation : **112 lignes**.
- **16 enveloppes brutes déjà présentes** relues en transaction READ ONLY,
  REPEATABLE READ, puis ROLLBACK. **112/112 items retrouvés**, empreintes et
  valeurs normalisées cohérentes, aucune enveloppe invalide sur ce périmètre.
- **66 observations de référentiel** examinées : 33 par symbole. Les six lignes
  Business Quant par symbole portant un CIK concordent avec le contexte SEC ;
  les 27 autres viennent du répertoire Nasdaq et ne renseignent pas ce CIK.
  Ce n'est pas une nouvelle certification globale des fournisseurs du master.
- DOCN : DigitalOcean Holdings, CIK **0001582961**.
- FUN : Six Flags Entertainment Corporation/NEW, CIK **0001999001** ; ne pas
  substituer l'ancien émetteur Cedar Fair à partir du seul ticker FUN.
- Les items `/calendar/trends` examinés ne contiennent pas de champ explicite
  certifiant la devise/unité et la convention comptable de l'EPS consensus.
  Ne pas les compléter implicitement depuis la devise de cotation.

Ces vérifications confirment la fidélité technique de la collecte, **pas la
justesse de chaque estimation d'analyste**, ni sa comparabilité comptable.

## État lors de la revue initiale, avant réponse du support

| Élément | DOCN | FUN |
|---|---|---|
| Identité émetteur, contexte master/SEC | Concordante | Concordante pour le nouvel émetteur |
| Fin de trimestre cible | 30 septembre 2026 confirmé dans le communiqué émetteur | Correspondance exacte avec le 30 septembre fournisseur non certifiée |
| Devise/échelle du consensus exact | Non qualifiée | Non qualifiée |
| EPS consensus GAAP/ajusté, dilué/basic | Non qualifié | Non qualifié |
| Sens des horizons simultanés pour une même date | À préciser | À préciser |
| Signal directionnel promouvable | Non | Non |

### DOCN : contexte fiscal clair, convention du consensus encore inconnue

Le [communiqué officiel du 4 août](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Second-Quarter-2026-Financial-Results/default.aspx)
vise explicitement le trimestre finissant au 30 septembre 2026. Sa guidance
distingue revenus en millions de dollars et EPS dilué non-GAAP. C'est une
**prévision de la société**, pas la définition de la moyenne des analystes
exposée par EODHD. Aucune exhaustivité des communications ultérieures n'est
affirmée par cette seule pièce.

### FUN : ne pas assimiler automatiquement trimestre fiscal et date calendaire

Le [communiqué officiel déposé à la SEC](https://www.sec.gov/Archives/edgar/data/1999001/000199900126000094/sixflags-exh991xq22026.htm)
indique un deuxième trimestre clos le **28 juin 2026**, alors que les items
fournisseur correspondants portent le **30 juin**. Cela peut être une convention
d'ancrage ; ce n'est pas, à lui seul, une preuve d'erreur de données.
La correspondance de la cible fournisseur du 30 septembre avec la fin fiscale
exacte du troisième trimestre doit donc être explicitée. **Aucune fin fiscale
n'a été inventée en extrapolant treize semaines.**

Le [communiqué émetteur diffusé le 7 octobre](https://www.businesswire.com/news/home/20261007925585/en/Six-Flags-to-Announce-2026-Third-Quarter-Results-on-November-5-Earnings-Call-Starts-at-8-AM-EST)
annonce la publication des résultats le 5 novembre avant ouverture, mais ne
résout pas la convention de date du fournisseur. Il a été consulté via la
recherche Web ; sa capture HTTP locale unique a expiré sans réception du corps.
Il **ne figure donc pas parmi les quatre documents localement archivés** et
n'est pas utilisé pour lever la réserve de période.

### La définition du réalisé ne certifie pas celle du consensus

Le [glossaire EODHD](https://eodhd.com/financial-academy/financial-faq/fundamentals-glossary-common-stock)
qualifie `epsActual` de non-GAAP, mais décrit `earningsEstimateAvg` comme une
moyenne d'estimations. Il ne certifie pas la convention comptable de ce dernier
champ pour ces deux sociétés. Une définition du réalisé ou une guidance
non-GAAP n'est donc pas une preuve suffisante pour qualifier l'EPS consensus.

La [documentation Calendar/Trends](https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits)
décrit les fins de période, horizons et estimations ; la comparaison de deux
horizons reçus simultanément appelle encore une précision sur leur référence.
Les réponses observées sont conservées telles quelles, sans fusion `0q/+1q`.

## Changements réellement reçus, sans interprétation de trading

Pour la cible fournisseur **2026-09-30**, entre les observations du 11 et du
18 octobre :

| Titre / horizon brut | EPS moyen | Revenus moyens, unité fournisseur brute | Analystes EPS / revenus |
|---|---:|---:|---:|
| DOCN `0q` | 0,3180 → 0,3186 | 306 657 240 → 306 723 910 | 17 / 15, inchangés |
| DOCN `+1q` | 0,2842 → 0,2842 | 299 713 730 → 299 713 730 | 16 / 13, inchangés |
| FUN `0q` | 2,0934 → 2,0811 | 1 170 267 190 → 1 168 235 510 | 5 / 13, inchangés |
| FUN `+1q` | 2,1470 → 2,1470 | 1 225 022 610 → 1 225 022 610 | 6 / 13, inchangés |

DOCN `0q` : variations relatives **+0,189 % EPS / +0,022 % revenus**.
FUN `0q` : **−0,588 % / −0,174 %**. Ce sont des variations d'agrégats reçus,
pas des probabilités, performances ou changements de guidance prouvés.

La coexistence de valeurs différentes à date fiscale identique n'est pas
automatiquement un bug : elle peut refléter des horizons ou références
différents. Sans leur sens exact, ne pas choisir après coup la version
produisant le signal souhaité. Un nombre d'analystes constant ne garantit
pas que ce soient les mêmes analystes.

## Disponibilité : pas de qualification rétroactive

Le cutoff d'entrée initial était le **19 octobre à 13:30 UTC / 15:30 Paris**.
Cette revue s'achève après : même une future clarification complète ne doit
pas être présentée comme une validation opérationnelle déjà acquise à cette
ouverture. Les dates de publication déclarées et les dates de réception des
pages sont conservées séparément.

Les cinq URL prévues ont fait l'objet d'au plus une tentative HTTP chacune,
TLS vérifié, sans contournement : **quatre réponses 200 archivées avec empreintes**,
une expiration technique Business Wire conservée comme échec. Les quatre
captures sont actuelles, **pas des réceptions historiques reconstituées**.
Le cache SEC companyfacts est également un contexte local, pas une preuve que
sa version actuelle existait à chaque ancienne date de décision.

## Questions préparées à l'origine — réponse désormais reçue

[Message anglais prêt à copier](message_support_eodhd_consensus_docn_fun_20261019.md)
et [extrait de huit items sélectionnés, sans secrets](extrait_support_eodhd_consensus_docn_fun_20261019.json)
préparés après le GO suivant. L'utilisateur a indiqué avoir envoyé le message,
puis a transmis la réponse conservée dans le bilan actualisé ci-dessus.
Aucun envoi par l'assistant. L'extrait n'est pas une réponse API complète.

Pas besoin de demander encore quel forfait donne un historique PIT : le
support a déjà répondu que ce produit n'en archive pas. Demander la définition
de ce qui est effectivement collecté prospectivement :

1. Pour `/calendar/trends`, `earningsEstimateAvg` et `epsTrendCurrent` sont-ils
   GAAP ou ajustés, dilués ou basic, pour **DOCN.US et FUN.US**, cible déclarée
   2026-09-30, observations des 11 et 18 octobre 2026 ? Comment la convention
   et ses changements sont-ils identifiés ?
2. Quelle est la devise de publication et l'échelle de `revenueEstimateAvg`
   pour ces enregistrements ? Où trouver une métadonnée explicite, puisque
   les items reçus n'en contiennent pas ? Même question pour l'unité EPS.
3. Pour FUN, quelle est la règle de correspondance entre dates calendaires
   normalisées et fins fiscales réelles ? Le 30 juin correspond-il au
   28 juin 2026 ? À quelle période fiscale exacte correspond le 30 septembre ?
   Confirmer le périmètre post-fusion Six Flags, CIK 0001999001.
4. Pourquoi, le 18 octobre, pour une même date 2026-09-30, DOCN a-t-il
   `0q=0.3186` et `+1q=0.2842`, et FUN `0q=2.0811` et `+1q=2.1470` ?
   À quelle date de référence chaque horizon se rattache-t-il ? Comment
   sélectionner sans ambiguïté la prévision courante plutôt qu'une ancienne
   prévision conservée pour le même trimestre ?
5. Des contributeurs peuvent-ils entrer/sortir tout en gardant le même nombre
   d'analystes ? Les compteurs de révisions permettent-ils de distinguer ces
   changements de composition des révisions des mêmes analystes ?

Ne joindre au besoin qu'un extrait des items concernés, jamais le token API,
les secrets ou les enveloppes complètes d'autres sociétés.

## Suite bornée et critères d'arrêt

**Cette revue publique est close**, sans élargir indéfiniment la recherche.
Le contexte émetteur gratuit ne suffit pas à certifier une convention interne
du fournisseur. En l'absence de réponse précise, conserver ces cas en recherche,
sans les promouvoir et sans conclure que les révisions n'ont aucun intérêt.

La collecte prospective continue selon sa configuration existante ; aucune
nouvelle activation ici. Après clarification, figer une nouvelle date de
qualification pour les décisions ultérieures. La maturité H10 de la cohorte
du 19 serait le 30 octobre après clôture, mais **huit dates de collecte ne
permettent pas une confirmation indépendante**. Le protocole initial demande
au moins 50 dates d'entrée et 100 épisodes TOP10 sans chevauchement.

## Reproduction et tests

Script : `scripts/research/us_consensus_two_issuer_qualification.py`, phases
`prepare`, `proofs`, `public`, `report`, argument `--output` vers un dossier
neuf. Ne pas relancer les phases déjà achevées dans le dossier scellé.
Constats manuels identifiés par empreinte dans
`scripts/research/us_consensus_docn_fun_findings_20261019.json`.
Revue par le même assistant, **pas une seconde revue humaine indépendante**.

**125 tests ciblés passent**, dont 12 nouveaux : une preuve sur le mauvais
champ EPS ne qualifie pas le consensus, pas de qualification antidatée,
composantes manquantes et absence d'enveloppe bloquantes. Ce nombre porte
sur les six fichiers de tests collecteur/LLM-evidence/consensus/pilote/
diagnostic/revue, pas sur l'ensemble du projet.
