namespace DependencyPropagation

inductive Term where
  | literal (value : Nat)
  | direct (position : Nat) (body : Term)
  | byContract (position operation : Nat)
  | sequence (left right : Term)
  deriving DecidableEq

inductive Step where
  | direct (position : Nat)
  | left (right : Term)
  | right (left : Term)

def plug : List Step → Term → Term
  | [], body => body
  | .direct position :: rest, body => .direct position (plug rest body)
  | .left right :: rest, body => .sequence (plug rest body) right
  | .right left :: rest, body => .sequence left (plug rest body)

theorem exactContextInjective (path : List Step) {a b : Term}
    (equal : plug path a = plug path b) : a = b := by
  induction path with
  | nil => exact equal
  | cons ctx remaining ih =>
    cases ctx with
    | direct position => exact ih (Term.direct.inj equal).2
    | left right => exact ih (Term.sequence.inj equal).1
    | right left => exact ih (Term.sequence.inj equal).2

theorem changePropagates (path : List Step) {a b : Term} (different : a ≠ b) :
    plug path a ≠ plug path b :=
  fun equal => different (exactContextInjective path equal)

def requiredBindings : Term → List Nat
  | .literal _ => []
  | .direct _ body => requiredBindings body
  | .byContract _ operation => [operation]
  | .sequence left right => requiredBindings left ++ requiredBindings right

def observe (binding : Nat → Nat) : Term → List Nat
  | .literal value => [value]
  | .direct position body => position :: observe binding body
  | .byContract position operation => [position, operation, binding operation]
  | .sequence left right => observe binding left ++ observe binding right

theorem bindingsOutsideRequiredSetAreIrrelevant (term : Term) (old new : Nat → Nat)
    (agree : ∀ operation, operation ∈ requiredBindings term → old operation = new operation) :
    observe old term = observe new term := by
  induction term with
  | literal value => rfl
  | direct position body ih =>
    have same := ih (fun operation member => agree operation member)
    simp [observe, same]
  | byContract position operation =>
    have same := agree operation (by simp [requiredBindings])
    simp [observe, same]
  | sequence left right ihLeft ihRight =>
    have sameLeft := ihLeft (fun operation member => agree operation (by
      simp [requiredBindings, member]))
    have sameRight := ihRight (fun operation member => agree operation (by
      simp [requiredBindings, member]))
    simp [observe, sameLeft, sameRight]

theorem unboundSubjectHasDistinctExecutions :
    observe (fun _ => 8) (.byContract 1 4) ≠ observe (fun _ => 9) (.byContract 1 4) := by
  decide

#print axioms exactContextInjective
#print axioms changePropagates
#print axioms bindingsOutsideRequiredSetAreIrrelevant
#print axioms unboundSubjectHasDistinctExecutions

end DependencyPropagation
