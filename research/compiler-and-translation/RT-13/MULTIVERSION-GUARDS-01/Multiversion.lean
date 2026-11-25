inductive Lane where
  | zeroRight
  | smallNonnegative
  | baseline
  deriving DecidableEq

structure Route where
  lane : Lane
  available : Bool
  checked : Bool

inductive Dispatch where
  | unavailable
  | invoked (result : Option Int)
  deriving DecidableEq

def inInt32 (value : Int) : Prop :=
  -2147483648 ≤ value ∧ value ≤ 2147483647

instance (value : Int) : Decidable (inInt32 value) :=
  inferInstanceAs (Decidable (_ ≤ value ∧ value ≤ _))

def source (a b : Int) : Option Int :=
  if inInt32 (a + b) then some (a + b) else none

def inDomain (lane : Lane) (a b : Int) : Bool :=
  match lane with
  | .zeroRight => decide (b = 0 ∧ inInt32 a)
  | .smallNonnegative => decide (0 ≤ a ∧ a ≤ 127 ∧ 0 ≤ b ∧ b ≤ 127)
  | .baseline => true

def compute (lane : Lane) (a b : Int) : Option Int :=
  match lane with
  | .zeroRight => some a
  | .smallNonnegative => some (a + b)
  | .baseline => source a b

def eligible (route : Route) (a b : Int) : Bool :=
  route.available && route.checked && inDomain route.lane a b

def choose (routes : List Route) (a b : Int) : Dispatch :=
  match routes.find? (fun route => eligible route a b) with
  | some route => .invoked (compute route.lane a b)
  | none => .unavailable

theorem guarded_refinement (lane : Lane) (a b : Int) (allowed : inDomain lane a b = true) :
    compute lane a b = source a b := by
  cases lane with
  | zeroRight =>
    simp [inDomain] at allowed
    obtain ⟨rfl, bounds⟩ := allowed
    simp [compute, source, bounds]
  | smallNonnegative =>
    simp [inDomain] at allowed
    have bounds : inInt32 (a + b) := by unfold inInt32; omega
    simp [compute, source, bounds]
  | baseline => rfl

theorem choice_matches_reference (routes : List Route) (a b : Int)
    (coverage : ∃ route ∈ routes, eligible route a b = true) :
    choose routes a b = .invoked (source a b) := by
  unfold choose
  split
  next route found =>
    have check := List.find?_some found
    simp [eligible] at check
    exact congrArg Dispatch.invoked (guarded_refinement route.lane a b check.2)
  next missing =>
    obtain ⟨route, member, holds⟩ := coverage
    have nope := (List.find?_eq_none).1 missing route member
    simp [holds] at nope

theorem priority_invariant (first second : List Route) (a b : Int)
    (sameMembers : ∀ route, route ∈ first ↔ route ∈ second)
    (coverage : ∃ route ∈ first, eligible route a b = true) :
    choose first a b = choose second a b := by
  obtain ⟨route, member, allowed⟩ := coverage
  rw [choice_matches_reference first a b ⟨route, member, allowed⟩,
    choice_matches_reference second a b ⟨route, (sameMembers route).1 member, allowed⟩]

theorem unavailable_exactly_when_no_eligible (routes : List Route) (a b : Int) :
    choose routes a b = .unavailable ↔ ∀ route ∈ routes, eligible route a b = false := by
  unfold choose
  cases found : routes.find? (fun route => eligible route a b) with
  | none =>
    simp
    simpa using List.find?_eq_none.1 found
  | some route =>
    simp
    have allowed : eligible route a b = true :=
      List.find?_some (p := fun candidate => eligible candidate a b) found
    exact ⟨route, List.mem_of_find?_eq_some found, allowed⟩

#print axioms guarded_refinement
#print axioms choice_matches_reference
#print axioms priority_invariant
#print axioms unavailable_exactly_when_no_eligible
