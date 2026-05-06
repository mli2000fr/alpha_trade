------------------------ MODULE IdempotenceCA_proof ------------------------
(***************************************************************************)
(* Sprint S28.2 / A8 — Preuve TLAPS pour IdempotenceCA.tla                 *)
(*                                                                          *)
(* Statut : SKELETON. À renforcer par consultant TLA+ certifié.            *)
(* L'invariant : appliquer 2 fois le même corporate action (même           *)
(* ``ca_id``) laisse l'état inchangé.                                      *)
(***************************************************************************)
EXTENDS IdempotenceCA, TLAPS

LEMMA CATypeInvariant == Spec => []TypeOK
  <1>1. Init => TypeOK
    BY DEF Init, TypeOK
  <1>2. TypeOK /\ [Next]_vars => TypeOK'
    BY DEF Next, TypeOK, ApplyCA
  <1> QED BY <1>1, <1>2, PTL DEF Spec

THEOREM IdempotenceProof == Spec => []Idempotence
  (* Squelette : Apply(ca, Apply(ca, s)) = Apply(ca, s) découle de la     *)
  (* garde ``ca_id \notin applied`` dans la transition ApplyCA.           *)
  OMITTED

================================================================================

