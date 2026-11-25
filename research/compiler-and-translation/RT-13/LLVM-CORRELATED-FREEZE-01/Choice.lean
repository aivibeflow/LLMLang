def admits (known seed first second : Bool) : Prop :=
  first = second ∧ (known = true → first = seed)

def choose (known seed witness : Bool) : Bool :=
  if known then seed else witness

theorem singleChoice (known seed witness : Bool) :
    admits known seed (choose known seed witness) (choose known seed witness) := by
  cases known <;> cases seed <;> cases witness <;> unfold admits choose <;> decide

theorem independentChoiceCanEscape :
    ¬ admits false false false true := by
  unfold admits
  decide

theorem invertedChoiceEscapes (known seed witness : Bool) :
    ¬ admits known seed (choose known seed witness) (!choose known seed witness) := by
  cases known <;> cases seed <;> cases witness <;> unfold admits choose <;> decide

theorem fixedChoiceRequiresSeed (seed first second : Bool) :
    admits true seed first second ↔ first = seed ∧ second = seed := by
  cases seed <;> cases first <;> cases second <;> unfold admits <;> decide

theorem unknownAllowsEitherCorrelatedPair (first second : Bool) :
    admits false false first second ↔ first = second := by
  cases first <;> cases second <;> unfold admits <;> decide

#print axioms singleChoice
#print axioms independentChoiceCanEscape
#print axioms invertedChoiceEscapes
#print axioms fixedChoiceRequiresSeed
#print axioms unknownAllowsEitherCorrelatedPair
