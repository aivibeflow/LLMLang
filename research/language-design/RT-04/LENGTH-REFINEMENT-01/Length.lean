namespace LengthRefinement

def Sized (α : Type) (n : Nat) := {xs : List α // xs.length = n}

def Bounded (α : Type) (max : Nat) := {xs : List α // xs.length ≤ max}

def pack (xs : List α) (declared : Nat) : Option (Sized α declared) :=
  if h : xs.length = declared then some ⟨xs, h⟩ else none

def checkedZip (xs : List α) (ys : List β) : Option (List (α × β)) :=
  if xs.length = ys.length then some (xs.zip ys) else none

def sizedZip (xs : Sized α n) (ys : Sized β n) : Sized (α × β) n :=
  ⟨xs.val.zip ys.val, by simp [List.length_zip, xs.property, ys.property]⟩

theorem packPresentIff (xs : List α) (declared : Nat) :
    (pack xs declared).isSome = true ↔ xs.length = declared := by
  by_cases h : xs.length = declared
  · rw [pack, dite_eq_left h]
    exact ⟨fun _ => h, fun _ => rfl⟩
  · rw [pack, dite_eq_right h]
    exact ⟨fun impossible => Bool.noConfusion impossible, fun equal => (h equal).elim⟩

theorem checkedPresentIff (xs : List α) (ys : List β) :
    (checkedZip xs ys).isSome = true ↔ xs.length = ys.length := by
  by_cases h : xs.length = ys.length <;> simp [checkedZip, h]

theorem checkedMatchesSized (xs : Sized α n) (ys : Sized β n) :
    checkedZip xs.val ys.val = some (sizedZip xs ys).val := by
  simp [checkedZip, sizedZip, xs.property, ys.property]

theorem sizedLength (xs : Sized α n) (ys : Sized β n) :
    (sizedZip xs ys).val.length = n :=
  (sizedZip xs ys).property

theorem boundedCounterexample :
    ∃ (xs ys : Bounded Bool 2), xs.val.length ≠ ys.val.length ∧
      (xs.val.zip ys.val).length < ys.val.length := by
  exact ⟨⟨[true], by decide⟩, ⟨[false, true], by decide⟩, by decide, by decide⟩

example : Sized (Bool × Bool) 1 :=
  sizedZip ⟨[true], rfl⟩ ⟨[false], rfl⟩

example : True := by
  fail_if_success
    have bad := sizedZip (⟨[true], rfl⟩ : Sized Bool 1)
                        (⟨[false, true], rfl⟩ : Sized Bool 2)
  trivial

#print axioms packPresentIff
#print axioms checkedPresentIff
#print axioms checkedMatchesSized
#print axioms sizedLength
#print axioms boundedCounterexample

end LengthRefinement
