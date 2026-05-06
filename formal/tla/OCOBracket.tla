------------------------------ MODULE OCOBracket ------------------------------
(***************************************************************************)
(* Sprint S24.3 — Spécification TLA+ : machine d'état OCO bracket          *)
(*                                                                         *)
(* Modèle abstrait d'un bracket synthétique (entrée déjà fillée + 2        *)
(* enfants TP/SL). On vérifie 3 invariants forts :                         *)
(*                                                                         *)
(*  - MutualExclusion : au plus une jambe FILLED                           *)
(*  - SiblingCancelInitiated : si une jambe FILLED, l'autre est            *)
(*      CANCEL_PENDING / CANCELED / REJECTED                               *)
(*  - NoActiveAfterFinalize : après RUN_COMPLETED, aucune jambe NEW /     *)
(*      PARTIALLY_FILLED                                                   *)
(*                                                                         *)
(* Mirroir du test property `test_synthetic_bracket_properties.py`.       *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Qty  \* quantité initiale par jambe (Nat)

VARIABLES
  tp_status,
  sl_status,
  tp_filled,
  sl_filled,
  run_completed

vars == << tp_status, sl_status, tp_filled, sl_filled, run_completed >>

Status == { "NEW", "PARTIALLY_FILLED", "FILLED",
            "CANCEL_PENDING", "CANCELED", "REJECTED" }
Terminal == { "FILLED", "CANCELED", "REJECTED" }

TypeOK ==
  /\ tp_status \in Status
  /\ sl_status \in Status
  /\ tp_filled \in 0..Qty
  /\ sl_filled \in 0..Qty
  /\ run_completed \in BOOLEAN

Init ==
  /\ tp_status = "NEW"
  /\ sl_status = "NEW"
  /\ tp_filled = 0
  /\ sl_filled = 0
  /\ run_completed = FALSE

\* Fill complet de TP : marque SL en CANCEL_PENDING.
FillTP ==
  /\ ~run_completed
  /\ tp_status \notin Terminal
  /\ tp_status' = "FILLED"
  /\ tp_filled' = Qty
  /\ sl_status' = IF sl_status \in Terminal \/ sl_status = "CANCEL_PENDING"
                  THEN sl_status ELSE "CANCEL_PENDING"
  /\ UNCHANGED << sl_filled, run_completed >>

FillSL ==
  /\ ~run_completed
  /\ sl_status \notin Terminal
  /\ sl_status' = "FILLED"
  /\ sl_filled' = Qty
  /\ tp_status' = IF tp_status \in Terminal \/ tp_status = "CANCEL_PENDING"
                  THEN tp_status ELSE "CANCEL_PENDING"
  /\ UNCHANGED << tp_filled, run_completed >>

CancelAckTP ==
  /\ tp_status = "CANCEL_PENDING"
  /\ tp_status' = "CANCELED"
  /\ UNCHANGED << sl_status, tp_filled, sl_filled, run_completed >>

CancelAckSL ==
  /\ sl_status = "CANCEL_PENDING"
  /\ sl_status' = "CANCELED"
  /\ UNCHANGED << tp_status, tp_filled, sl_filled, run_completed >>

Finalize ==
  /\ ~run_completed
  /\ run_completed' = TRUE
  /\ tp_status' = IF tp_status \in Terminal \/ tp_status = "CANCEL_PENDING"
                  THEN tp_status ELSE "CANCEL_PENDING"
  /\ sl_status' = IF sl_status \in Terminal \/ sl_status = "CANCEL_PENDING"
                  THEN sl_status ELSE "CANCEL_PENDING"
  /\ UNCHANGED << tp_filled, sl_filled >>

Next == FillTP \/ FillSL \/ CancelAckTP \/ CancelAckSL \/ Finalize

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants                                                              *)
(***************************************************************************)
MutualExclusion ==
  ~ (tp_status = "FILLED" /\ sl_status = "FILLED")

SiblingCancelInitiated ==
  /\ (tp_status = "FILLED" =>
        sl_status \in { "CANCEL_PENDING", "CANCELED", "REJECTED" })
  /\ (sl_status = "FILLED" =>
        tp_status \in { "CANCEL_PENDING", "CANCELED", "REJECTED" })

NoActiveAfterFinalize ==
  run_completed =>
    /\ tp_status \notin { "NEW", "PARTIALLY_FILLED" }
    /\ sl_status \notin { "NEW", "PARTIALLY_FILLED" }

THEOREM Spec => []MutualExclusion
THEOREM Spec => []SiblingCancelInitiated
THEOREM Spec => []NoActiveAfterFinalize
================================================================================

