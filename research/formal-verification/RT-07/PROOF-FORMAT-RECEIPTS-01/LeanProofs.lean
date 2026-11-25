namespace ProofFormatFixture

def selected (literal : Int) : Int := if true then literal else 0

theorem seven : ∀ (left right : Int), left ≠ right →
    ((selected 7 ≠ selected 7) ∨ False) → False := by
  intro _ _ _ difference
  rcases difference with impossible | contradiction
  · exact impossible rfl
  · exact contradiction

theorem eight : ∀ (left right : Int), left ≠ right →
    ((selected 8 ≠ selected 8) ∨ False) → False := by
  intro _ _ _ difference
  rcases difference with impossible | contradiction
  · exact impossible rfl
  · exact contradiction

#print axioms seven
#print axioms eight

end ProofFormatFixture
