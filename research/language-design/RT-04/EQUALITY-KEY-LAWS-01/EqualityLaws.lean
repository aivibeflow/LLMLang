def EquivalenceLaws {α : Type} (r : α → α → Prop) : Prop :=
  (∀ x, r x x) ∧ (∀ {x y}, r x y → r y x) ∧
    (∀ {x y z}, r x y → r y z → r x z)

def KeyEquality {α : Type} (key : α → Nat) (x y : α) : Prop :=
  key x = key y

theorem keyEqualityLaws {α : Type} (key : α → Nat) :
    EquivalenceLaws (KeyEquality key) :=
  ⟨fun _ => rfl, fun h => h.symm, fun h₁ h₂ => h₁.trans h₂⟩

theorem compatibleProjectedHash {α : Type} (key : α → Nat) (hashCode : Nat → Nat)
    {x y : α} (h : KeyEquality key x y) :
    hashCode (key x) = hashCode (key y) :=
  congrArg hashCode h

def Near (x y : Nat) : Prop :=
  x ≤ y + 1 ∧ y ≤ x + 1

theorem nearReflexive (x : Nat) : Near x x :=
  ⟨Nat.le_succ x, Nat.le_succ x⟩

theorem nearSymmetric {x y : Nat} (h : Near x y) : Near y x :=
  ⟨h.2, h.1⟩

theorem nearCounterexample : Near 0 1 ∧ Near 1 2 ∧ ¬ Near 0 2 := by
  unfold Near
  decide

#print axioms keyEqualityLaws
#print axioms compatibleProjectedHash
#print axioms nearReflexive
#print axioms nearSymmetric
#print axioms nearCounterexample
