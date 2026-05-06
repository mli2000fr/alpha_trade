------------------------ MODULE NoDoubleExec_proof ------------------------
(***************************************************************************)
(* Sprint S28.2 / A8 — Preuve TLAPS pour NoDoubleExec.tla                  *)
(*                                                                          *)
(* Statut : SKELETON. Les preuves ci-dessous sont triviales et exploitent  *)
(* uniquement la sémantique des sets (fills est de type Set ⇒ pas de       *)
(* doublons par construction). Une revue par un consultant TLA+ certifié   *)
(* est requise pour basculer le job CI ``tlaps`` en bloquant.              *)
(* Réf. : prompt/tod/32_plan.md §3 S28.2 et §6 risques.                    *)
(***************************************************************************)
EXTENDS NoDoubleExec, TLAPS, FiniteSetTheorems

(***************************************************************************)
(* Lemme 1 — TypeOK est invariant (élémentaire).                           *)
(***************************************************************************)
LEMMA TypeInvariant == Spec => []TypeOK
  <1>1. Init => TypeOK
    BY DEF Init, TypeOK
  <1>2. TypeOK /\ [Next]_vars => TypeOK'
    <2>1. SUFFICES ASSUME TypeOK,
                          NEW k \in Keys,
                          Submit(k)
                   PROVE TypeOK'
      BY DEF Next, TypeOK
    <2>2. fills' \subseteq Keys
      BY <2>1 DEF Submit, TypeOK
    <2>3. attempts' \in Seq(Keys)
      BY <2>1 DEF Submit, TypeOK
    <2> QED BY <2>2, <2>3 DEF TypeOK
  <1> QED BY <1>1, <1>2, PTL DEF Spec

(***************************************************************************)
(* Théorème principal — Singleton est trivial : ``fills`` est un set,      *)
(* donc Cardinality({k}) = 1 pour tout k.                                  *)
(***************************************************************************)
THEOREM SingletonProof == Spec => []Singleton
  <1>1. ASSUME NEW k PROVE Cardinality({k}) = 1
    BY FS_Singleton
  <1> QED BY <1>1, PTL DEF Singleton

(***************************************************************************)
(* Théorème NoDoubleExec — découle directement de fills ⊆ Keys.            *)
(***************************************************************************)
THEOREM NoDoubleExecProof == Spec => []NoDoubleExec
  <1>1. TypeOK => NoDoubleExec
    <2>1. SUFFICES ASSUME TypeOK PROVE Cardinality(fills) <= Cardinality(Keys)
      BY DEF NoDoubleExec
    <2>2. fills \subseteq Keys
      BY DEF TypeOK
    <2> QED BY <2>2, FS_Subset, FS_CardinalityType
  <1> QED BY <1>1, TypeInvariant, PTL DEF NoDoubleExec

================================================================================

