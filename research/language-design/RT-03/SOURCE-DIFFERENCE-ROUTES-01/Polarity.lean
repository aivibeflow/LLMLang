import Lean

theorem complementOfIntegerDifference (source destination bound : Int) :
    (¬ (destination - source ≤ bound)) ↔ source - destination ≤ -bound - 1 := by
  omega

#print axioms complementOfIntegerDifference
