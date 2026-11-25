namespace PartialOutput

def drain : List (List Nat) → Nat → List Nat
  | [], _ => []
  | chunk :: rest, budget => chunk.take budget ++ drain rest (budget - chunk.length)

theorem acceptedPrefix (chunks : List (List Nat)) (budget : Nat) :
    drain chunks budget = chunks.flatten.take budget := by
  induction chunks generalizing budget with
  | nil => simp [drain]
  | cons chunk rest ih =>
    simp only [drain, List.flatten_cons, ih, List.take_append]

def observation (chunks : List (List Nat)) (budget : Nat) : List Nat × Bool :=
  (drain chunks budget, decide (budget < chunks.flatten.length))

theorem coalesce (chunks : List (List Nat)) (budget : Nat) :
    observation chunks budget = observation [chunks.flatten] budget := by
  simp [observation, acceptedPrefix]

#print axioms acceptedPrefix
#print axioms coalesce

end PartialOutput
