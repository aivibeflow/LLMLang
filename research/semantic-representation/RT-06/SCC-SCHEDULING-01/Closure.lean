inductive Reach (edge : Node → Node → Prop) : Node → Node → Prop where
  | self : Reach edge node node
  | step : edge source next → Reach edge next last → Reach edge source last

theorem schedules_must_propagate_reachable_fact (edge : Node → Node → Prop)
    (known : Node → Fact → Prop)
    (step : ∀ source next fact, edge source next → known next fact → known source fact)
    {source target : Node} (path : Reach edge source target) (fact : Fact)
    (present : known target fact) : known source fact := by
  induction path with
  | self => exact present
  | step found rest induction => exact step _ _ fact found (induction present)

theorem mutual_reach_same_facts (edge : Node → Node → Prop) (known : Node → Fact → Prop)
    (step : ∀ source next fact, edge source next → known next fact → known source fact)
    {first second : Node} (forward : Reach edge first second) (back : Reach edge second first)
    (fact : Fact) : known first fact ↔ known second fact :=
  ⟨schedules_must_propagate_reachable_fact edge known step back fact,
    schedules_must_propagate_reachable_fact edge known step forward fact⟩

#print axioms schedules_must_propagate_reachable_fact
#print axioms mutual_reach_same_facts
