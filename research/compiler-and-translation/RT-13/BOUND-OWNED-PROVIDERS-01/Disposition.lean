inductive Disposition where
  | ok | retained | consumed | indeterminate
  deriving DecidableEq

inductive Policy where
  | scripted | consumeRetained

inductive Obligation where
  | absent | usable (token : Nat) | reconcile
  deriving DecidableEq

def actual (policy : Policy) (request : Disposition) : Disposition :=
  match policy, request with
  | .consumeRetained, .retained => .consumed
  | _, request => request

def reply (policy : Policy) (request : Disposition) (token : Nat) : Disposition × Nat :=
  let disposition := actual policy request
  (disposition, if disposition = .retained then token else 0)

def obligation (disposition : Disposition) (token : Nat) : Obligation :=
  match disposition with
  | .retained => .usable token
  | .indeterminate => .reconcile
  | .ok | .consumed => .absent

def decode (result : Disposition × Nat) (token : Nat) : Option Obligation :=
  if result.1 = .retained then
    if result.2 = token ∧ token ≠ 0 then some (.usable token) else none
  else if result.2 = 0 then some (obligation result.1 token) else none

theorem decode_preserves_obligation (policy : Policy) (request : Disposition)
    (token : Nat) (live : token ≠ 0) :
    decode (reply policy request token) token =
      some (obligation (actual policy request) token) := by
  cases policy <;> cases request <;> simp [decode, reply, obligation, actual, live]

theorem distinct_bindings_change_retained_request (token : Nat) (live : token ≠ 0) :
    decode (reply .scripted .retained token) token = some (.usable token) ∧
    decode (reply .consumeRetained .retained token) token = some .absent := by
  simp [decode, reply, obligation, actual, live]

#print axioms decode_preserves_obligation
#print axioms distinct_bindings_change_retained_request
