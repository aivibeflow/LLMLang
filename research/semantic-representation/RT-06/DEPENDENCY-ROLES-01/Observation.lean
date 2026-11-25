def observe (usesNote : Bool) (result note : Nat) : Nat × Option Nat :=
  (result, if usesNote then some note else none)

theorem unrelated_note_preserves (result old new : Nat) :
    observe false result old = observe false result new := rfl

theorem consumed_note_is_relevant (result old new : Nat) :
    observe true result old = observe true result new ↔ old = new := by
  constructor
  · intro same
    exact Option.some.inj (congrArg Prod.snd same)
  · intro same
    exact congrArg (observe true result) same

#print axioms unrelated_note_preserves
#print axioms consumed_note_is_relevant
