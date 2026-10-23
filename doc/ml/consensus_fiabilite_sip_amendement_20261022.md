# Amendement technique avant résultats : un seul flux de prix

Le premier calcul du dossier `us_consensus_reliability/20261022-v1` s'est arrêté
avant tout résultat, sur `Duplicate daily bars`. Les dates 12–16 octobre ont
deux sources distinctes en base : `eodhd_eod` et `alpaca_sip`. Ce ne sont pas
des doublons à supprimer en SQL.

Créer un dossier enfant immuable `sip-only-v2` : mêmes features, sélection,
cutoff du 22 octobre à20:15:54.864550UTC et snapshots. Seul changement : conserver
**Alpaca SIP exclusivement**, sans fallback EODHD, IEX ou mélange d'ajustements.
Les doublons au sein de ce seul flux restent bloquants. Aucun seuil, groupe,
date d'entrée ou horizon ne change après inspection d'un rendement.

Les prix bruts SIP ne deviennent pas un historique OST qualifié. Les prix en
base s'arrêtent au20octobre ; dates manquantes réservées, pas de téléchargement
ou réparation SQL dans cet audit. Le parent en échec est conservé, pas écrasé.

Vérification complémentaire des15items à intervalle incohérent, identifiés
**sans résultat de prix** : chercher ces items dans les enveloppes existantes,
sans élargissement fournisseur. Cela permet de distinguer mauvaise copie
locale et valeur déjà présente dans la réponse archivée. Ce contrôle ne
certifie ni la vérité économique des montants ni la population d'analystes.
