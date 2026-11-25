structure Sample where
  before : Nat
  left : Nat
  right : Nat
  after : Nat

def Ordered (sample : Sample) : Prop :=
  sample.before ≤ sample.left ∧ sample.left ≤ sample.right ∧ sample.right ≤ sample.after

theorem coherent_of_equal_generation (sample : Sample) (ordered : Ordered sample)
    (same : sample.before = sample.after) :
    sample.left = sample.before ∧ sample.right = sample.before := by
  obtain ⟨beforeLeft, leftRight, rightAfter⟩ := ordered
  have leftBefore : sample.left ≤ sample.before :=
    same.symm ▸ Nat.le_trans leftRight rightAfter
  have rightBefore : sample.right ≤ sample.before := same.symm ▸ rightAfter
  exact ⟨Nat.le_antisymm leftBefore beforeLeft,
    Nat.le_antisymm rightBefore (Nat.le_trans beforeLeft leftRight)⟩

theorem equal_token_within_same_quotient (first last period : Nat)
    (token : first % period = last % period) (quotient : first / period = last / period) :
    first = last := by
  calc
    first = first % period + period * (first / period) := (Nat.mod_add_div first period).symm
    _ = last % period + period * (last / period) :=
      (congrArg (fun residue => residue + period * (first / period)) token).trans
        (congrArg (fun block => last % period + period * block) quotient)
    _ = last := Nat.mod_add_div last period

theorem wraps_allow_mixed_origins :
    ∃ sample : Sample, Ordered sample ∧
      sample.before % 4 = sample.after % 4 ∧ sample.left ≠ sample.right :=
  ⟨⟨0, 0, 4, 4⟩, ⟨Nat.zero_le 0, Nat.zero_le 4, Nat.le_refl 4⟩, rfl, by decide⟩

#print axioms coherent_of_equal_generation
#print axioms equal_token_within_same_quotient
#print axioms wraps_allow_mixed_origins
