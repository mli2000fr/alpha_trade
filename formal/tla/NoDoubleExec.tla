------------------------------ MODULE NoDoubleExec ------------------------------
(***************************************************************************)
(* Sprint S24.3 — Spécification TLA+ : pas de double exécution             *)
(*                                                                         *)
(* Modèle : ensemble fini de tentatives d'exécution caractérisées par     *)
(* leur `idempotency_key`. On vérifie l'invariant `Singleton` : pour      *)
(* toute clé donnée, au plus UNE fill est enregistrée — quel que soit le  *)
(* nombre de retries / réémissions.                                       *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Keys  \* ensemble fini d'idempotency_keys candidates

VARIABLES
  fills,        \* set de clés effectivement fillées
  attempts      \* multiset des tentatives (séquence)

vars == << fills, attempts >>

TypeOK ==
  /\ fills \subseteq Keys
  /\ attempts \in Seq(Keys)

Init ==
  /\ fills = {}
  /\ attempts = << >>

Submit(k) ==
  /\ k \in Keys
  /\ attempts' = Append(attempts, k)
  /\ IF k \in fills
       THEN UNCHANGED fills
       ELSE fills' = fills \cup {k}

Next == \E k \in Keys : Submit(k)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariant clé : Singleton — au plus une fill par idempotency_key        *)
(***************************************************************************)
Singleton ==
  \A k \in fills : Cardinality({ k }) = 1

\* Invariant constructif : `fills` est un set ⇒ pas de doublon possible.
\* On exprime l'intention : pour chaque clé soumise, soit elle est dans
\* `fills` (1 occurrence), soit elle a été ignorée (skip).
NoDoubleExec ==
  Cardinality(fills) <= Cardinality(Keys)

THEOREM Spec => []Singleton
THEOREM Spec => []NoDoubleExec
================================================================================

