namespace DeadStoreBoundary

inductive ReadRoute
  | absent | aliasTarget | otherCell
  deriving DecidableEq

structure Observation where
  finalTarget : Nat
  finalOther : Nat
  intermediate : Option Nat
  writes : List Nat
  deriving DecidableEq

def load (route : ReadRoute) (target other : Nat) : Option Nat :=
  match route with
  | .absent => none
  | .aliasTarget => some target
  | .otherCell => some other

def original (visible : Bool) (route : ReadRoute) (first last other : Nat) : Observation :=
  ⟨last, other, load route first other, if visible then [first, last] else []⟩

def rewritten (visible : Bool) (route : ReadRoute) (initial last other : Nat) : Observation :=
  ⟨last, other, load route initial other, if visible then [last] else []⟩

theorem exactEliminationCriterion (visible : Bool) (route : ReadRoute)
    (initial first last other : Nat) :
    original visible route first last other = rewritten visible route initial last other ↔
      visible = false ∧ (route ≠ .aliasTarget ∨ first = initial) := by
  cases visible <;> cases route <;> simp [original, rewritten, load]

theorem finalCellsAgree (visible : Bool) (route : ReadRoute) (initial first last other : Nat) :
    (original visible route first last other).finalTarget =
      (rewritten visible route initial last other).finalTarget ∧
    (original visible route first last other).finalOther =
      (rewritten visible route initial last other).finalOther := ⟨rfl, rfl⟩

#print axioms exactEliminationCriterion
#print axioms finalCellsAgree

end DeadStoreBoundary
