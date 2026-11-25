theorem sequentialEquality {S O : Type} (observe : S → O) (base middle final : S)
    (first : observe base = observe middle) (second : observe middle = observe final) :
    observe base = observe final :=
  first.trans second

theorem uniformNonInterference {S O : Type} (observe : S → O) (first second : S → S)
    (firstStable : ∀ s, observe s = observe (first s))
    (secondStable : ∀ s, observe s = observe (second s)) (base : S) :
    observe base = observe (second (first base)) :=
  (firstStable base).trans (secondStable (first base))

def observeBoth (s : Bool × Bool) : Bool := s.1 && s.2
def editFirst (s : Bool × Bool) : Bool × Bool := (true, s.2)
def editSecond (s : Bool × Bool) : Bool × Bool := (s.1, true)

theorem disjointSeparateEditsInsufficient :
    observeBoth (false, false) = observeBoth (editFirst (false, false)) ∧
    observeBoth (false, false) = observeBoth (editSecond (false, false)) ∧
    observeBoth (false, false) ≠ observeBoth (editSecond (editFirst (false, false))) := by
  decide

#print axioms sequentialEquality
#print axioms uniformNonInterference
#print axioms disjointSeparateEditsInsufficient
