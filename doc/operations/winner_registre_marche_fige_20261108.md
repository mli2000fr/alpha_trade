# Winner : registre des marchés figé pendant le replay

## Incident

Le replay continu 2021–2026 v4 a terminé 1 035 séances (dernière séance achevée :
14 février 2025), puis échoué pendant le suivi d'EGO avec « Le registre de
marchés est vide ». Aucun bilan financier final n'a été publié.

Les quatre fichiers `config/markets/market_*.yaml` sont présents, valides et
datés du 7 octobre. Le runtime Winner reconstruit un calendrier dans le contrôle
d'échéance ; cela résout le contexte marché et reparcourt les fichiers. Une
lecture vide du répertoire provoque l'erreur, même si un registre valide avait
déjà permis de démarrer la simulation. La cause système précise de cette
lecture vide n'est pas établie ; aucun fichier n'a été reconstitué arbitrairement.

## Correctif

`backtesting/frozen_market_registry.py` charge et valide le registre une fois,
vérifie US_EQ/us_primary et le marché activé, puis le conserve pendant un appel
au moteur Winner. Un `ContextVar` dans `common/config_loader.py` fournit ce
registre aux helpers du même replay. La portée se termine même en cas d'erreur ;
les autres threads et les chargements explicites d'un autre répertoire ne sont
pas redirigés. Hors replay, le chargement habituel reste en vigueur.

La simulation ne recharge donc pas ces fichiers à chaque contrôle d'échéance.
Les calendriers officiels, les stops, les horizons et les règles de risque sont
inchangés. Le rapport archive les contextes et leurs empreintes. Un registre
invalide au départ reste refusé.

67 tests passent : contexte marchés, Winner natif, protections daily et mapping
annuel. Le test ciblé rend le registre inaccessible après son premier chargement,
vérifie la sortie à échéance et compare exactement trades et capital au témoin.

## Reprise

Programme : `scripts/research/us_winner_continuous_registry_recovery_20261108.py`.
Version active : `artifacts/research/us_winner_continuous_annual_models/20261108-v6`.
Journal : `artifacts/research/us_winner_continuous_annual_models/registry-recovery-v6.log`.

Prix, secteurs, opérations sur titres et signaux sont repris bit pour bit de v4,
dont le correctif des 125 lignes de prix à volume nul. Aucune requête SQL,
collecte fournisseur, inférence ou ordre. Un manifeste des marchés est ajouté
aux entrées scellées. Les sources de code modifiées sont documentées.

Le lancement vérifie d'abord le témoin 2025 déjà calculé (18 indicateurs
financiers), puis enchaîne automatiquement le portefeuille continu 2021–2026.
Ce portefeuille repart du début : v4 ne contenait pas de checkpoint complet du
cash, des positions et de B4 permettant une reprise exacte à la séance suivante.
Les tentatives précédentes restent intactes ; v5 est une préparation interrompue
sur un refus Windows de créer un lien de fichier. v6 utilise une copie si les
liens ne sont pas autorisés.

Validation du témoin terminée : PASS sur les 18 indicateurs, capital final
4 275,953666526648 USD, rendement +6,898841663166189 %, DD−10,856029369198783 %,
59 trades dont27 gagnants. Le correctif ne change pas ce résultat.
État final : replay continu v6 terminé le08/11/2026 à15h15 Europe/Paris,
capital final6 186,50 USD,+54,66 %, DD−29,65 %,1 254 trades, taux gagnant38,68 %.
Les deux anciens points de panne (EGO et TPB) ont été franchis. Le statut des
données reste `INCOMPLETE_COVERAGE` avec repli OHLC journalier documenté.
