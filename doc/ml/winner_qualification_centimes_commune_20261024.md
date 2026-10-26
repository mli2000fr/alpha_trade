# Qualification commune des écarts d'un centime — 24 octobre 2026

GO utilisateur : étendre la qualification du correctif aux autres cas.
Compagnon versionné `scripts.research.us_winner_cent_qualification_20261024`.
Sources économiques, prix, modèles, profils, audit scalaire et tolérances des
quatre runs restent inchangés. Aucun entraînement, API, SQL ni ordre.

## Mécanisme et gates

Le correctif déjà qualifié CNK/2020 conserve exactement le prix moyen broker
du premier fill IOC intégral, sans multiplication/division inutile susceptible
de décaler l'arrondi SL/TP. Fills partiels hors qualification, refus explicite.
L'adaptateur de recherche du 23 octobre reste immuable ; aucune correction live
ou réécriture des sources scellées n'est annoncée.

Chaque nouveau cas doit d'abord reproduire l'ancien échec dans un dossier isolé.
On exige une différence exactement d'un centime, un horaire/motif de sortie
identique, et la correspondance explicite du niveau SL/TP calculé depuis le
prix reconstitué face au prix moyen broker d'origine. Pas de diagnostic deviné.
Les erreurs de timing, trailing, données ou risque restent bloquantes.
Puis le profil défaillant est rejoué avec correction, audit strict natif complet.

Les rapports antérieurs et leurs fichiers sont inventoriés par SHA256. Tous les
achats sont contrôlés, positions ouvertes comprises. Un cas terminé dont le
niveau initial pourrait changer est rejoué séparément : il faut retrouver les
mêmes transactions, positions, courbe d'equity et résultats avant de le conserver.
Sinon le périmètre est bloqué ; aucun résultat antérieur n'est écrasé.
EXPI/2022 `SL3_TROFF_H5_TP10` est un tel cas à vérifier, pas une perte supposée.

Le profil corrigé validé, auparavant sans rapport terminé, est copié dans son
dossier initial avec rapport scellé en dernier ; les traces d'échec et fichiers
non scellés précédents sont conservés. Il n'est pas recalculé inutilement une
deuxième fois. Les autres comptes manquants reprennent avec le même adaptateur.

## Pilotage et coexistence

Dossier `artifacts/research/us_winner_cent_qualification/20261024-v1`.
Deux sous-processus supplémentaires au maximum, threads numériques limités
à un et priorité Windows inférieure. Les qualifications connues passent avant
les reprises longues. Aucun processus existant n'est interrompu ; l'ancienne
reprise 2020 x1 reste active. La charge partagée peut ralentir tous les calculs.

Les verrous annuels d'origine empêchent les doublons ; TOP20/TOP50 conservent
également leur verrou de racine. Le compagnon observe les nouveaux échecs
de prix d'un centime dans les quatre grilles et leur applique les mêmes gates.
Un échec réel de qualification n'est jamais relancé en boucle.

Par cas : `request.json`, `preserved.json`, `diagnosis/diagnosis.json`,
`validation/`, éventuel `prior-validation/`, `qualified.json`, `resolution.json`
ou `blocked.json`. Le reçu de résolution n'existe qu'après 300 comptes annuels
validés et recontrôle des archives conservées. Suivi global `progress.json` ;
suivi annuel toujours dans les `year-<année>.json` d'origine.

## Finalisation globale

Les superviseurs historiques peuvent conserver une erreur déjà reprise dans
leur liste d'incidents. Le compagnon ne l'efface pas pendant leur exécution.
Lorsque tous les comptes sont réellement présents, il attend leur verrou de
racine, vérifie tous les rapports/fichiers puis produit les agrégats d'origine.
Le statut antérieur est archivé séparément. Pour x2, attendre le bilan x1 afin
de produire les 3 000 comparaisons appariées. Aucun succès global sur une grille
partielle. Une couverture, statistique ou erreur autre que le mécanisme qualifié
reste une réserve, pas un échec à contourner.

Les biais de sélection par couverture future, univers survivant, secteurs non
PIT, prix OHLC et autres limites du protocole original restent intégralement
applicables. Ce correctif numérique ne démontre aucun gain de stratégie.
