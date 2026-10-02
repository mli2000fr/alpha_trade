# Registre de marchés

Ce répertoire contient uniquement les contrats déclaratifs chargés par common.market_context.

## Contextes

- market_us.yaml : US_EQ, contexte historique actif ;
- market_cn.yaml : CN_A, préparé mais désactivé ;
- market_cn_bj.yaml : CN_BJ, préparé mais désactivé.
- market_fr.yaml : FR_EQ, préparé mais désactivé ; base physique `alpha_trade_fr`.

## Règles

- schema_version vaut 1 ;
- market_code, alias de base, pays, devise, timezone et calendrier doivent être cohérents ;
- enabled, live_enabled et short_execution_enabled sont de vrais booléens YAML ;
- un marché désactivé ne peut pas activer le live ;
- la vente à découvert requiert la capacité short_execution ;
- ne jamais activer CN avant les migrations, le routage de base, le calendrier et les contrôles prévus par les sprints suivants.
- ne jamais activer FR avant le schéma France, le calendrier XPAR et les contrôles PIT ; aucun broker France n'est configuré.

L’absence temporaire de market_code résout US_EQ avec un warning de migration. Un code inconnu ne bénéficie d’aucun fallback.
