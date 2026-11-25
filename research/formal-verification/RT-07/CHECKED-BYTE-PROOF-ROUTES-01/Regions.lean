namespace CheckedByteRoutes

structure Region where
  overflow : Bool
  storesSum : Bool
  trace : Nat

def observe (region : Region) (sum initial : Int) : Bool × Int × Nat :=
  (region.overflow, if region.storesSum then sum else initial, region.trace)

theorem endpointsSuffice (source target : Region) (lo hi sum initial : Int)
    (lower : lo ≤ sum) (upper : sum ≤ hi)
    (first : observe source lo initial = observe target lo initial)
    (last : observe source hi initial = observe target hi initial) :
    observe source sum initial = observe target sum initial := by
  obtain ⟨sOverflow, sStore, sTrace⟩ := source
  obtain ⟨tOverflow, tStore, tTrace⟩ := target
  cases sStore <;> cases tStore <;> simp [observe] at first last ⊢
  all_goals
    first
    | exact first
    | obtain ⟨overflow, firstCell, trace⟩ := first
      obtain ⟨_, lastCell, _⟩ := last
      exact ⟨overflow, by omega, trace⟩

theorem byteSumBounds (a b : Int) (alo : -128 ≤ a) (ahi : a ≤ 127)
    (blo : -128 ≤ b) (bhi : b ≤ 127) :
    -256 ≤ a + b ∧ a + b ≤ 254 := by omega

theorem everySumReachable (sum : Int) (lo : -256 ≤ sum) (hi : sum ≤ 254) :
    ∃ a b : Int, -128 ≤ a ∧ a ≤ 127 ∧ -128 ≤ b ∧ b ≤ 127 ∧ a + b = sum := by
  by_cases belowZero : sum < 0
  · exact ⟨-128, sum + 128, by omega⟩
  · exact ⟨127, sum - 127, by omega⟩

#print axioms endpointsSuffice
#print axioms byteSumBounds
#print axioms everySumReachable

end CheckedByteRoutes
