# Sprint 17-G — Décision bornée sur les capacités Trading212 Invest

## Conclusion au 9 octobre 2026

**Décision ultérieure de l'utilisateur :** option 2 retenue,
[clôture administrative avec réserves](sprint_17_cloture_avec_reserves.md).
Le raccordement d'ordres est suspendu ; aucune relance automatique de ce lot.

L'accès DEMO EUR et les lectures sont qualifiés. Les protections autonomes
requises par notre moteur ne le sont pas. **Trading212 reste candidat pour les
lectures et un éventuel test DEMO limité, pas un courtier FR opérationnel validé.**
Ce lot poursuit les recherches publiques et prépare une demande de confirmation.
Aucun ordre, message externe, batch, modèle ou base n'a été modifié.

## Sources et portée

1. [OpenAPI officiel](https://docs.trading212.com/_bundle/api.json?download=),
   consulté le 9 octobre : ordres simples stop/limite/stop-limit, annulation,
   soumissions non idempotentes ; aucun endpoint OCO explicitement identifié.
   Les garanties d'une réservation partagée et d'un remplacement atomique
   ne sont pas établies par ce contrat.
2. [Forum officiel — Bracket order placing](https://community.trading212.com/t/bracket-order-placing/50634),
   réponse de Bogi.H datée du **25 octobre 2024** : OCO réservé aux comptes CFD,
   sans projet alors annoncé pour Invest/ISA. Cette réponse ancienne renforce
   la réserve, mais ne certifie pas seule la situation API d'octobre 2026.
3. [Centre d'aide — Take Profit and Stop Loss](https://helpcentre.trading212.com/hc/en-us/articles/360007435978-Take-Profit-and-Stop-Loss-Orders)
   décrit les protections **CFD**. Ne pas importer ces fonctionnalités dans
   le contrat Invest ni basculer notre application vers les CFD.
4. [Forum officiel — API feedback](https://community.trading212.com/t/t212-api-feedback/90495),
   demande utilisateur du 17 février 2026 concernant notamment les brackets.
   Il s'agit d'une demande, pas d'une garantie technique du courtier.

Le forum et l'interface utilisateur ne remplacent pas un contrat API actuel.
L'absence d'endpoint identifié n'est pas une preuve qu'aucune évolution n'existe.
Une réponse officielle récente avec endpoints et garanties reste nécessaire.

## Questions précises pour le support

Le texte ci-dessous est prêt à copier. **Il n'a pas été envoyé.** Ne joindre
aucune clé API, aucun secret et aucun fichier privé de compte.

> Bonjour,
>
> Nous préparons une intégration de votre API publique pour un compte Invest
> DEMO en EUR, sur actions cotées à Paris. Nous ne travaillons pas sur les CFD.
> Pourriez-vous confirmer les capacités actuellement disponibles en DEMO et
> en réel, avec un lien vers les endpoints/documentation correspondants ?
>
> 1. L'API Invest permet-elle un bracket ou OCO natif associant un stop de vente
> et un take-profit limite sur une même position ? Quelle garantie existe
> contre la double exécution, notamment en cas de fills partiels ?
> 2. Deux sorties indépendantes peuvent-elles réserver les mêmes actions ?
> Si elles sont refusées ou partagent une réservation, quelles sont les règles
> exactes sur la quantité disponible et l'ordre de priorité ?
> 3. Le remplacement d'un stop est-il atomique via l'API ? Sinon, quel mécanisme
> permet de confirmer l'annulation et la quantité déjà remplie avant remplacement ?
> 4. Une vente limite ou stop bénéficie-t-elle d'une garantie reduce-only liée
> à la position ? Comment sont traitées deux sorties simultanées après fermeture ?
> 5. Après timeout de soumission, existe-t-il un identifiant client ou mécanisme
> de corrélation permettant de retrouver l'ordre sans le soumettre de nouveau ?
> 6. Quels champs permettent d'identifier chaque fill, les corrections ultérieures
> et le lieu réel d'exécution (MIC), distinct de la place de cotation ?
> 7. Les quantités réservées, statuts et frais du compte DEMO reproduisent-ils
> les mêmes règles que le compte Invest réel ? Quelles différences subsistent ?
>
> Nous ne souhaitons pas émuler un OCO local en supposant une atomicité non garantie.
> Merci de préciser explicitement les fonctionnalités non disponibles.

## Critères de décision

| Réponse | Suite |
| --- | --- |
| OCO/bracket natif, garanties et endpoints documentés | Concevoir un test DEMO borné, après GO explicite utilisateur |
| OCO absent, stop simple disponible | Ne pas prétendre à la parité actuelle ; choisir explicitement une autre politique de protection avant implémentation |
| Réponse vague, fonctionnalités UI/CFD uniquement | Maintenir le blocage d'exécution Invest |
| Contrat incompatible avec le moteur | Conserver les lectures et rechercher ultérieurement un courtier adapté, sans ouverture automatique de compte |

Même avec une réponse positive, restent à valider : exécutions partielles,
reprise après timeout, courses, frais/taxes, comptes/identités, MIC, disponibilité
des données et réserves shadow du Sprint 16. Une réponse support ne suffit pas
à déclarer un GO LIVE ou PAPER autonome.

## Borne de travail

Il n'est pas utile de multiplier les bancs synthétiques en prétendant débloquer
une capacité externe. Les lots 17-A à 17-F restent livrés ; le Sprint 17 global
reste **partiel, exécution bloquée par le contrat courtier et les réserves de données**.
La suite exige une réponse technique récente ou une décision explicite de changer
le contrat de protection. Aucun changement implicite stop seul/TP local/CFD.
