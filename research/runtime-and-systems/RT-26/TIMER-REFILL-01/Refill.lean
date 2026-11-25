import Std

def refill (cap current ticks : Nat) : Nat :=
  min cap (current + ticks)

theorem refill_bounded (cap current ticks : Nat) :
    refill cap current ticks ≤ cap := by
  exact Nat.min_le_left _ _

theorem split_refill (cap current first second : Nat) :
    refill cap (refill cap current first) second =
      refill cap current (first + second) := by
  unfold refill
  by_cases bounded : current + first ≤ cap
  · rw [Nat.min_eq_right bounded, Nat.add_assoc]
  · have capLe : cap ≤ current + first := by omega
    rw [Nat.min_eq_left capLe]
    rw [Nat.min_eq_left (show cap ≤ cap + second by omega)]
    rw [Nat.min_eq_left (show cap ≤ current + (first + second) by omega)]

def admit (parent child demand : Nat) : Nat :=
  min parent (min child demand)

theorem two_children_share_parent (parent firstChild secondChild firstDemand secondDemand : Nat) :
    admit parent firstChild firstDemand +
      admit (parent - admit parent firstChild firstDemand) secondChild secondDemand ≤ parent := by
  have firstLe : admit parent firstChild firstDemand ≤ parent :=
    Nat.min_le_left _ _
  have secondLe :
      admit (parent - admit parent firstChild firstDemand) secondChild secondDemand ≤
        parent - admit parent firstChild firstDemand :=
    Nat.min_le_left _ _
  omega

#print axioms refill_bounded
#print axioms split_refill
#print axioms two_children_share_parent
