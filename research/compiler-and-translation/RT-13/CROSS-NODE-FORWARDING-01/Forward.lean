structure Observation where
  refused : Bool
  slot : Nat
  events : List Nat
  deriving DecidableEq

def finish (beforeLoad loaded amount : Nat) (prefixEvents : List Nat) : Observation :=
  if loaded < amount then ⟨true, beforeLoad, prefixEvents⟩
  else ⟨false, loaded - amount, prefixEvents ++ [loaded - amount]⟩

def original (produced amount : Nat) (callback : Nat → Nat × List Nat) : Observation :=
  let (slot, events) := callback produced
  finish slot slot amount events

def forwarded (produced amount : Nat) (callback : Nat → Nat × List Nat) : Observation :=
  let (slot, events) := callback produced
  finish slot produced amount events

theorem exact_slot_guard_suffices (produced amount : Nat) (callback : Nat → Nat × List Nat)
    (preservesSlot : (callback produced).1 = produced) :
    forwarded produced amount callback = original produced amount callback := by
  cases outcome : callback produced with
  | mk slot events =>
    simp [outcome] at preservesSlot
    simp [forwarded, original, outcome, preservesSlot]

theorem rejects_after_retaining_callback (produced amount : Nat) (callback : Nat → Nat × List Nat)
    (insufficient : (callback produced).1 < amount) :
    original produced amount callback = ⟨true, (callback produced).1, (callback produced).2⟩ := by
  cases outcome : callback produced with
  | mk slot events =>
    simp [outcome] at insufficient
    simp [original, outcome, finish, insufficient]

#print axioms exact_slot_guard_suffices
#print axioms rejects_after_retaining_callback
