# LLM factuel — dossier borné et faisabilité, 21 octobre 2026

## Conclusion

**Préparation technique et revue documentaire terminées. Pas de test LLM ni de
gain économique démontré.** Le travail consiste à préparer une extraction de
faits sourcés, pas à demander une nouvelle recommandation LONG/SHORT.

Les 24 dépôts déjà admis dans la cohorte TOP10 du premier trimestre 2024 ont été
relus sur leurs extraits pertinents. Ils ne représentent pas 24 annonces
trimestrielles comparables :

| Nature du dépôt | Nombre |
| --- | ---: |
| Publication de résultats, éventuellement non audités | 12 |
| Résultats préliminaires STAAR | 1 |
| Chiffres annuels préliminaires Chemours, avec retard et réserves comptables | 1 |
| Déclarations administratives de capital | 5 |
| Avis de réunion/calendrier de publication | 2 |
| Annexe PDF non extraite dans ce travail | 1 |
| Annexes non disponibles dans l'archive exploitable | 2 |

Il y a donc **14 dépôts contenant des résultats ou chiffres préliminaires**, et
non 14 occasions qualifiées ou rentables. La classification thématique s'appuie
sur **30 citations exactes**, vérifiées dans les textes de **21 dépôts lisibles**.
Une réception HTTP réussie ne signifie pas que toutes les annexes sont lisibles.

Cette revue est celle du même assistant, **pas une seconde revue humaine
indépendante**. Elle n'est ni un benchmark GPT/DeepSeek, ni une mesure de
précision d'extraction. Aucun coût d'API n'a été engagé.

## Ce que cette revue apporte de nouveau

### Bilibili : calendrier ≠ publication ≠ répétition

L'avis `0001193125-24-039227` annonce une future réunion et la date des résultats.
Le communiqué `0001193125-24-061286` contient les résultats du quatrième trimestre
et de l'année 2023. L'ancienne qualification avait réservé ce dernier comme
répétition parce qu'un document précédent mentionnait la même période.

**Ce motif, à lui seul, ne suffit pas à conclure à un doublon.** Le dossier actuel
classe correctement les deux natures de document. Il ne certifie pas pour autant
la toute première publication mondiale du communiqué. Les sorties antérieures
scellées restent inchangées ; cette correction interprétative est tracée ici.

### Chemours : document mixte, pas simple bruit administratif

`0001193125-24-051940` comporte des changements de direction, un retard de
publication, un examen des contrôles comptables **et des chiffres annuels
préliminaires**. Il faut conserver ces réserves avec les nombres : ce n'est pas
une annonce trimestrielle finale ordinaire. La présence de mots « résultats »
ou « chiffre d'affaires » ne suffit pas à qualifier une comparaison.

### Les métriques ne sont pas interchangeables

- ACIC et Lemonade : primes, chiffre d'affaires, résultat net et résultat
  opérationnel sont distincts ; plusieurs tableaux Lemonade sont des images.
- Hovnanian : résultat avant impôt ≠ résultat opérationnel.
- Bilibili : RMB et conversion de convenance en USD doivent rester séparés.
- Schrödinger et Zai Lab : segment logiciel ou produit particulier ≠ revenus
  consolidés. Une prévision annuelle ≠ prévision trimestrielle.
- STAAR : chiffres préliminaires observés ≠ prévisions de ventes futures.
- TAL : la date écrite du communiqué précède l'acceptation SEC. Ne pas inventer
  une heure ; les colonnes trimestrielles vont de 2022 à 2023, pas l'inverse.

Ces cas montrent l'utilité potentielle d'un extracteur factuel et de ses
contrôles. **Ils ne prouvent pas qu'un LLM saura les résoudre ni qu'ils prédisent
les cours.**

## Contrat d'extraction préparé

Un prompt de recherche séparé demande uniquement :

1. nature du fait : réalisé, préliminaire, guidance, calendrier, capital ou
   réserve de publication/comptabilité ;
2. métrique, valeur littérale, période fiscale, devise, échelle et base
   comptable ; `null` si la preuve manque ;
3. citation exacte et emplacement dans un extrait fourni ;
4. limites explicites, sans direction, confiance de trading ni prix futur.

La nouveauté reste `NOT_ESTABLISHED`. Un changement de guidance nécessite
**deux pièces datées comparables**, même période, métrique, unité et périmètre.
Le paquet courant n'en fournit pas une paire qualifiée par simple présence
du mot « outlook ». Une déclaration du dirigeant « au-dessus des attentes »
n'est pas une surprise mesurée contre un consensus historique indépendant.

Les requêtes prêtes à soumettre sont séparées des annotations de revue :
elles ne contiennent ni ces réponses attendues, ni réaction du prix, ni rendement
futur. Le texte source est une donnée non fiable, jamais une instruction.

Le validateur refuse les champs de direction, les citations absentes des extraits,
les mauvais offsets et les revendications de nouveauté non qualifiée. Il accepte
l'abstention. **Il contrôle la structure et l'ancrage documentaire, pas la vérité
sémantique d'une devise, d'une période ou d'un nombre choisi par un modèle.**

Une clé d'identité couvre fournisseur, modèle, options, prompt, émetteur,
empreintes et extraits. Elle prépare une réutilisation exacte sans confusion
entre deux tâches. **Aucun cache SQL ou nouveau flux de production n'est
implémenté/activé dans cette expérience.** Les anciennes réponses directionnelles
ne sont pas réétiquetées en extractions factuelles.

## Archives, couverture et disponibilité

Dossier neuf :
`artifacts/research/us_llm_factual_readiness/20261021-v1`.

- `protocol.json` : périmètre, limites et empreintes des entrées/code/tests.
- `prompt.json` : prompt factuel séparé.
- `*.packet.json` : textes dérivés normalisés, empreintes, reçus originaux,
  acceptation SEC et date réelle de récupération.
- `*.request.json` : seuls extraits et métadonnées nécessaires à l'extracteur.
- `topic-review.json` : revue annotée et citations, non envoyées comme réponses.
- `prior-table-references.json` : **cinq tableaux déjà rapprochés, vingt cellules**
  ASAN/BILL/HLF/TAL/W, re-rattachés à leurs citations et en-têtes. Ce n'est pas
  un nouvel échantillon indépendant ni une mesure de rappel sur tous les nombres.
- `source-receipts.json` : **32 fichiers sources** dont les empreintes ont été
  vérifiées. Plusieurs pièces peuvent appartenir au même dépôt.
- `report.json` : bilan et empreintes des **53 autres fichiers** du dossier.

Les textes dérivés normalisent les espaces ; les offsets se rapportent à ces
textes, **pas aux octets des originaux**. Les originaux et leurs empreintes
restent nécessaires à la traçabilité.

Par document : ouverture de 4 500 caractères, jusqu'à huit fenêtres de mots-clés,
puis contexte des citations et des cinq tableaux de référence. **19 dépôts sont
tronqués dans les requêtes** par rapport au texte lisible archivé. Le paquet
conserve le texte dérivé complet pour vérifier les extraits, mais ne prétend pas
qu'un fournisseur l'a lu. Les images, PDF non extraits, annexes manquantes et
passages omis restent des inconnues : on ne peut conclure à une absence de fait.

La cohorte est héritée du **CatBoost H20 de recherche**, sélection TOP10 exacte
au jour de réaction du premier trimestre 2024, pas des modèles annuels de
production. Aucune sélection par rendement ultérieur n'est ajoutée. Aucun prix
n'a été chargé pour ce nouveau dossier ; les anciens fichiers scellés sont
seulement contrôlés par empreinte. Pas de lecture de rendement futur.

L'acceptation SEC est un proxy public reconstructible ; la récupération locale
est datée de 2026. **Ni réception Alpha Trade en 2024, ni première publication
mondiale, ni correspondance historique ticker/émetteur n'ont été certifiées.**
Le zéro événement économiquement admissible signifie « preuve non qualifiée
dans ce dossier », pas « aucun fait accessible » ni « stratégie perdante ».

## Vérifications et reproduction

Exécution hors ligne, dossier neuf obligatoire :

```powershell
python -m scripts.research.us_llm_factual_readiness --output-dir artifacts/research/us_llm_factual_readiness/DATE-NOUVELLE-VERSION
```

Ne pas relancer sur `20261021-v1` : aucun remplacement n'est permis. L'outil ne
contient aucun appel fournisseur/LLM ou écriture SQL. Il réutilise les parseurs
locaux des études précédentes, sans appeler leurs fonctions de téléchargement.

Les contrôles portent notamment sur citations/offsets, fenêtres réellement
fournies, absence de direction et de label de revue dans la requête, séparation
index SEC/annexe, timezone explicite, identité de cache et refus d'écraser.
**24 tests ciblés passent, dont 16 nouveaux**, avec les contrôles des revues
antérieures. Contrôle de cohérence après exécution : 24 paquets,
53 empreintes de sorties, 32 reçus et les vingt valeurs des références vérifiés.

## Décision bornée et prochaine suite éventuelle

**Pas de comparaison économique “réaction seule” contre “faits + réaction” sur
ce corpus en l'état.** Les 14 documents de résultats sont hétérogènes, la première
publication et certaines identités ne sont pas qualifiées, et cinq tableaux
comparables ne constituent pas un effectif de confirmation.

Le livrable est prêt pour un **petit benchmark d'extraction**, distinct d'un test
de trading, si un nouveau GO avec budget autorise un appel fournisseur sur ce
paquet. Il faudrait alors noter exactitude, abstention, omissions et erreurs de
période/unité contre une revue corrigée — sans appeler cela un résultat financier.
Une comparaison économique ultérieure nécessiterait une cohorte plus grande et
qualifiée dès sa vraie disponibilité, des règles figées avant outcomes, puis le
même portefeuille/coûts/risque dans les deux bras.

Pas d'élargissement ou de collecte sans borne déclenché ici. Pas d'entraînement,
backtest, écriture SQL, modification de modèle/batch/configuration ou ordre.

Voir aussi les [réserves de qualification antérieures](qualification_consensus_annonces_sec_20261020.md)
et la [reconstitution des annonces SEC](reconstitution_annonces_financieres_sec_20261019.md).
