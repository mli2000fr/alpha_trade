# Conformité, fiscalité et corporate actions

## Pourquoi ces pages font partie du workflow

Une opération correcte techniquement peut être fausse économiquement si un
split, dividende ou autre corporate action n’est pas correctement rapproché. De
même, positions et lots alimentent les contrôles fiscaux et d’audit. Ces pages
ne sont donc pas un archivage passif.

## Corporate Actions

La page présente un résumé par statut/type, les événements et applications
récentes, ainsi que l’historique des résumés métier. Trois commandes sont
exposées :

- `sync` collecte/normalise les événements sur symboles et période ;
- `status` calcule ou affiche leur état sans appliquer la mutation métier ;
- `apply` applique les actions admissibles selon la commande et l’as-of.

Les contrôles incluent symboles, dates, taille de batch, cross-check et date
as-of. Avant `apply`, vérifier identité de l’événement, source, ratio/montant,
devise, ex-date, statut, applications existantes et résultats du cross-check.

L’idempotence attendue doit être contrôlée via les applications récentes : ne
pas relancer aveuglément une action parce qu’elle reste visible dans les
événements. Dividendes et splits n’ont pas les mêmes conséquences sur quantités,
prix, cash et séries ajustées.

## Compliance & Audit

La page regroupe plusieurs familles de contrôle et permet de relancer les jobs
associés. Un job produit un constat daté ; il ne corrige pas nécessairement
l’anomalie. Pour chaque exception, conserver règle, objet, période, sévérité,
preuve et statut de résolution.

Une relance après correction doit montrer la disparition de l’exception sans
masquer les observations historiques nécessaires à l’audit.

## Tax Compliance

La page expose les lots et ajustements wash sale. Le lot relie acquisition,
quantité, coût et réalisation. Un ajustement wash sale dépend d’une fenêtre et
d’achats de remplacement ; ne pas le reconstruire uniquement depuis une
position agrégée.

Les résultats sont un support technique et doivent être validés selon la
juridiction et le contexte fiscal applicables. Voir
[Fiscalité et wash sale](../operations/fiscalite_wash_sale.md).

## Sandbox health

Cette page suit la santé sur une fenêtre de trente jours et permet de relancer
des cross-checks Stooq ou des contrôles fournisseurs. Une divergence fournisseur
doit être qualifiée (calendrier, ajustement, devise, timestamp, symbole) avant de
remplacer une donnée.

## Comptes Alpaca

La page sépare l’état live du broker et l’historique canonique Alpha Trade. Le
payload brut aide au diagnostic, mais l’historique local reste l’objet d’audit
de l’application. La doctrine broker primaire/secondaire explique le rôle de
chaque compte/source. L’évolution du capital ne doit pas mélanger comptes ou
devises.

## Contrôle périodique recommandé

- quotidien : événements matériels, applications attendues, divergences broker ;
- après incident/replay : audit de conformité et sandbox health ;
- avant reporting fiscal : lots, réalisations et ajustements ;
- avant backtest long : convention d’ajustement et corporate actions historiques ;
- après changement de fournisseur : cross-check documenté.

Références : [Corporate actions](../17_corporate_actions.md),
[compliance](../operations/compliance_et_audit.md) et
[schéma métier](../database/schema_metier.md).
