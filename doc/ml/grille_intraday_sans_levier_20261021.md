# Même grille intraday sans levier — comparaison ×1 / ×2

## Demande et lancement du21octobre2026

144 politiques LONG et144SHORT, sur2025 et2026 jusqu'au30septembre :
**576 simulations annuelles**, dans un nouveau dossier :
`artifacts/research/us_intraday_protection_grid/20261021-1x-v1`.
La référence ×2 `20261021-v1` et ses sources scellées restent inchangées.

**107tests passent**, dont neuf nouveaux contrôles ×1 ; les quatre pilotes
LONG/SHORT2025/2026 et leurs audits passent. **Grille terminée :576/576cas,
aucunéchec, en19min36s. Audits/hashes et toutes les admissions×1 validés.**
Profil illustratif LONGSL7/trailing15/H20/sansTP :+33,15%en2025 et+31,67%en2026,
DD30,68/20,88%, capitalfinal5325,83/5266,82USD, capitalmoyenengagé
2992,38/2784,57USD. AucunSHORTpositif ; pas de promotionlive.
Suite séparée : [protections de portefeuille de production](grille_intraday_risque_production_20261021.md).

## Comparaison contrôlée

Seuls le budget global et le plafond d'exposition brute aux **nouvelles entrées**
passent de200%à100% de l'equity. Le levier est explicitement désactivé dans
la configuration de simulation. Capital initial **4000USD indépendant par année**.

**La cible individuelle ne change pas** : cible complète bornée à50%equity et
4%de risque SL planifié, puis demi-position entière, au plus environ25%equity.
Le capital restant peut réduire/refuser une entrée. Il ne s'agit ni de diviser
les tailles automatiquement par deux, ni de diviser les rendements ×2 par deux.
Quantités, refus, cash, portefeuille et performances sont entièrement rejoués.

Les achats LONG ne peuvent emprunter du cash. Le financement conventionnel
6,5%ACT/360 est conservé, mais ne s'applique qu'à un débit réel. **SHORT implique
toujours un emprunt de titres**, même sans levier : disponibilité supposée et
coût0,3%annual252 inchangés. Les proceeds SHORT ne créent pas un budget gratuit.
La dérive du ratio brut/equity d'une position SHORT existante n'est pas
automatiquement rééquilibrée : stops/maintenance restent identiques. Le plafond
×1 porte sur chaque nouvelle entrée frais inclus, pas une garantie de ratio
toujours inférieur à1 à toute marque future. Ce n'est pas un compte cash SHORT.

Restent identiques :

- Grille SL3/5/7%, trailingOFF/10/15/20%, J+H5/10/15/20, TPOFF/10/20%.
- Copies de prix, calendrier, candidats et contexte à **empreintes identiques**
  au run ×2 :213campagnes qualifiées,119/94 sur2025/26,72titres.
- Même Oracle PATH_H20 CatBoost OOS de recherche/TOP10, confirmation5m,
  premier essai, prochain open contigu, admission parent20séances.
- Attente incluse dans J+H, échéance open dernière barre5m J+H, protections,
  priorités stop/TP, gaps et trailing sans information de barre future.
- Frais8bps/jambe, emprunt, minimum equitySHORT, huit positions, trackers
  natifs, maintenance hypothétique et positions annuelles encore ouvertes MTM.
- Biais de survivants et sélection sur couverture future, cohorte incomplète,
  absence de preuves exhaustives quotes/borrow/cashflows d'opérations sur titres.
  **Toujours pas de parité historique intégrale PAPER/live.**

Une sous-classe de recherche est sélectionnée uniquement dans les processus
du nouveau calcul ; aucun fichier de moteur/ancienne expérience n'est modifié.
Pas de SQL, fournisseur, LLM, entraînement, ordre ou configuration de production.

## Fichiers et reprise

- `progress.json` : terminés/échecs/total et estimation restante.
- `annual-summary.partial.csv`, puis `annual-summary.csv` : mêmes mesures que
  ×2, notamment capital final/rendement, DDmax, gagnants/perdants, gains/pertes
  moyens USD/%, détentions en séances et jours calendaires, capital moyen/max
  réellement engagé et ratio brut/equity, débit cash, levier observé, intérêts.
- `comparison-1x-vs-2x.csv` : comparaison **politique par politique**, avec les
  mêmes paramètres, et différences des mesures. Rendements/DD en points de
  pourcentage ; ne pas comparer seulement les meilleurs profils a posteriori.
- `cases/<identifiant>/` : trades, marques5m, décisions, maintenance, audit,
  marqueur terminé scellé. Les nouvelles entrées conservent leur preuve ×1.
- `final-review.json` : uniquement après576cas terminés et audits/hashes/preuves
  de toutes les admissions ×1 vérifiés. Même assistant, pas humain indépendant.

Le capital engagé moyen inclut les barres sans position et est pondéré par
temps de séance régulière5m. Les intérêts incluent les week-ends ACT/360. Les
gagnants/perdants ne comprennent que les trades clos ; l'equity finale inclut
les positions ouvertes valorisées. Le financement est présenté séparément,
sans affectation arbitraire à chaque trade. Les autres définitions sont celles
du [protocole ×2](grille_intraday_long_short_20261021.md).

```powershell
python -u -m scripts.research.us_intraday_protection_grid_1x --output artifacts/research/us_intraday_protection_grid/20261021-1x-v1 --workers 2
Get-Content artifacts/research/us_intraday_protection_grid/20261021-1x-v1/progress.json
```

Reprise : utiliser ce **nouveau module**, pas le module ×2 en changeant simplement
son dossier. Les entrées/sources sont vérifiées, seuls les cas terminés intacts
sont ignorés. Les années ont déjà été examinées : cette comparaison reste
exploratoire, sans sélection automatique de champion ni GO live.
