------------------------------ MODULE IdempotenceCA ------------------------------
(***************************************************************************)
(* Phase C / S15 — Spécification TLA+ : idempotence des corporate actions  *)
(*                                                                         *)
(* Modèle abstrait : un ensemble d'événements CA, chacun caractérisé par   *)
(* un tuple (account_id, provider, symbol, ca_type, ex_date, amount).     *)
(* La fonction `Key(e)` calcule une clé déterministe ; on prouve que      *)
(* l'application répétée d'un même événement ne crée qu'une seule         *)
(* application en base.                                                    *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Events  \* ensemble fini d'événements CA candidats

VARIABLES applied  \* set de clés déjà appliquées (idempotency_key)

Init == applied = {}

Key(e) == e  \* abstraction : la clé EST l'événement (déterministe)

Apply(e) ==
  /\ Key(e) \notin applied
  /\ applied' = applied \cup {Key(e)}

Skip(e) ==
  /\ Key(e) \in applied
  /\ UNCHANGED applied

Next == \E e \in Events : Apply(e) \/ Skip(e)

Spec == Init /\ [][Next]_applied

(***************************************************************************)
(* Invariant clé : aucune application dupliquée.                           *)
(***************************************************************************)
NoDuplicate == Cardinality(applied) = Cardinality({Key(e) : e \in applied})

THEOREM Spec => []NoDuplicate
================================================================================

