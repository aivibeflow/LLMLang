structure Reply where
  status : Nat
  slot : Nat

inductive Outcome
  | value (word : Nat)
  | overflow (retained : Nat)
  | unknown (status slot : Nat)
  deriving DecidableEq

def decode (reply : Reply) : Outcome :=
  match reply.status with
  | 0 => .value reply.slot
  | 1 => .overflow reply.slot
  | status + 2 => .unknown (status + 2) reply.slot

def selected (word increment : Nat) (enabled : Bool) : Nat :=
  word + if enabled then increment else 0

def ProviderPremise (limit word increment prior : Nat) (enabled : Bool) (reply : Reply) : Prop :=
  (selected word increment enabled ≤ limit → reply.status = 0 ∧ reply.slot = selected word increment enabled) ∧
  (limit < selected word increment enabled → reply.status = 1 ∧ reply.slot = prior)

theorem checkedSuccess (limit word increment prior : Nat) (enabled : Bool) (reply : Reply)
    (observed : ProviderPremise limit word increment prior enabled reply)
    (fits : selected word increment enabled ≤ limit) :
    decode reply = .value (selected word increment enabled) := by
  obtain ⟨status, slot⟩ := observed.1 fits
  unfold decode
  rw [status, slot]

theorem checkedOverflow (limit word increment prior : Nat) (enabled : Bool) (reply : Reply)
    (observed : ProviderPremise limit word increment prior enabled reply)
    (overflow : limit < selected word increment enabled) :
    decode reply = .overflow prior := by
  obtain ⟨status, slot⟩ := observed.2 overflow
  unfold decode
  rw [status, slot]

theorem unknownPreservesRaw (raw slot : Nat) :
    decode ⟨raw + 2, slot⟩ = .unknown (raw + 2) slot := rfl

theorem abiShapeAloneAllowsWrongOverflow :
    decode ⟨1, 42⟩ ≠ .overflow 7 := by
  decide

#print axioms checkedSuccess
#print axioms checkedOverflow
#print axioms unknownPreservesRaw
#print axioms abiShapeAloneAllowsWrongOverflow
