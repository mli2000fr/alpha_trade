------------------------ MODULE OCOBracket_proof ------------------------
(***************************************************************************)
(* Sprint S28.2 / A8 — Preuve TLAPS pour OCOBracket.tla                    *)
(*                                                                          *)
(* Statut : SKELETON. À renforcer par consultant TLA+ certifié.            *)
(* L'invariant cible est l'exclusivité OCO : si l'ordre TP est filled,     *)
(* l'ordre SL est forcément cancelled (et inversement).                    *)
(***************************************************************************)
EXTENDS OCOBracket, TLAPS

LEMMA OCOTypeInvariant == Spec => []TypeOK
  <1>1. Init => TypeOK
    BY DEF Init, TypeOK
  <1>2. TypeOK /\ [Next]_vars => TypeOK'
    BY DEF Next, TypeOK, FillTP, FillSL, CancelTP, CancelSL
  <1> QED BY <1>1, <1>2, PTL DEF Spec

THEOREM OCOExclusivityProof == Spec => []OCOExclusivity
  (* Squelette : la preuve effective requiert l'analyse du graphe         *)
  (* d'états (FillTP ⇒ SL_state = CANCELED) injecté dans la spec.         *)
  OMITTED

================================================================================

