def Image (observe : α → β) (runs : α → Prop) (output : β) : Prop :=
  ∃ run, runs run ∧ observe run = output

def Refines (candidate reference : α → Prop) : Prop :=
  ∀ run, candidate run → reference run

theorem image_mono (observe : α → β) {candidate reference : α → Prop}
    (refines : Refines candidate reference) :
    Refines (Image observe candidate) (Image observe reference) := by
  intro output observed
  obtain ⟨run, member, equal⟩ := observed
  exact ⟨run, refines run member, equal⟩

theorem context_refines_iff_constant_on_projection (project : α → β) (observe : α → γ) :
    (∀ (candidate reference : α → Prop),
        Refines (Image project candidate) (Image project reference) →
          Refines (Image observe candidate) (Image observe reference)) ↔
    (∀ x y, project x = project y → observe x = observe y) := by
  constructor
  · intro preserves x y equal
    have projected : Refines (Image project (· = x)) (Image project (· = y)) := by
      intro output result
      obtain ⟨run, rfl, seen⟩ := result
      exact ⟨y, rfl, equal.symm.trans seen⟩
    have result := preserves (· = x) (· = y) projected (observe x) ⟨x, rfl, rfl⟩
    obtain ⟨run, rfl, seen⟩ := result
    exact seen.symm
  · intro constant candidate reference projected output result
    obtain ⟨run, admitted, seen⟩ := result
    obtain ⟨other, member, equal⟩ := projected (project run) ⟨run, admitted, rfl⟩
    exact ⟨other, member, (constant other run equal).trans seen⟩

def diagonal : Bool × Bool → Prop := fun pair => pair.1 = pair.2
def offDiagonal : Bool × Bool → Prop := fun pair => pair.1 ≠ pair.2

theorem marginals_agree :
    Refines (Image Prod.fst diagonal) (Image Prod.fst offDiagonal) ∧
    Refines (Image Prod.fst offDiagonal) (Image Prod.fst diagonal) ∧
    Refines (Image Prod.snd diagonal) (Image Prod.snd offDiagonal) ∧
    Refines (Image Prod.snd offDiagonal) (Image Prod.snd diagonal) := by
  have diag (bit : Bool) : diagonal (bit, bit) := rfl
  have first (bit : Bool) : offDiagonal (bit, !bit) := by unfold offDiagonal; cases bit <;> decide
  have second (bit : Bool) : offDiagonal (!bit, bit) := by unfold offDiagonal; cases bit <;> decide
  exact ⟨fun bit _ => ⟨(bit, !bit), first bit, rfl⟩,
    fun bit _ => ⟨(bit, bit), diag bit, rfl⟩,
    fun bit _ => ⟨(!bit, bit), second bit, rfl⟩,
    fun bit _ => ⟨(bit, bit), diag bit, rfl⟩⟩

theorem marginals_can_disagree_in_context :
    ¬ Refines (Image (fun pair => pair.1 && pair.2) diagonal)
      (Image (fun pair => pair.1 && pair.2) offDiagonal) := by
  intro refines
  obtain ⟨⟨left, right⟩, off, result⟩ := refines true ⟨(true, true), rfl, rfl⟩
  cases left <;> cases right <;> contradiction

#print axioms image_mono
#print axioms context_refines_iff_constant_on_projection
#print axioms marginals_agree
#print axioms marginals_can_disagree_in_context
