structure Worker where
  delivered : Nat
  budget : Nat
  done : Bool

def remaining (worker : Worker) : Nat :=
  worker.budget - worker.delivered + if worker.done then 0 else 1

def tick (worker : Worker) : Worker :=
  { worker with delivered := worker.delivered + 1 }

def finish (worker : Worker) : Worker :=
  { worker with done := true }

theorem tickWithinBudget (worker : Worker) (h : worker.delivered < worker.budget) :
    (tick worker).delivered ≤ worker.budget := by
  exact Nat.succ_le_of_lt h

theorem tickConsumesProgress (worker : Worker) (h : worker.delivered < worker.budget) :
    remaining (tick worker) + 1 = remaining worker := by
  let pending := if worker.done then 0 else 1
  change (worker.budget - (worker.delivered + 1) + pending) + 1 =
    worker.budget - worker.delivered + pending
  rw [Nat.sub_succ, Nat.add_right_comm _ pending 1,
    ← Nat.succ_eq_add_one (worker.budget - worker.delivered).pred,
    Nat.succ_pred_eq_of_pos (Nat.sub_pos_of_lt h)]

theorem finishConsumesProgress (worker : Worker)
    (budgetReached : worker.delivered = worker.budget) (live : worker.done = false) :
    remaining (finish worker) = 0 ∧ remaining worker = 1 := by
  change worker.budget - worker.delivered + 0 = 0 ∧
    worker.budget - worker.delivered + (if worker.done then 0 else 1) = 1
  rw [budgetReached, live, Nat.sub_self]
  exact ⟨rfl, rfl⟩

theorem tickConsumesJointProgress (current peer : Worker)
    (budgetOpen : current.delivered < current.budget) :
    remaining (tick current) + remaining peer < remaining current + remaining peer := by
  apply Nat.lt_of_succ_le
  change (remaining (tick current) + remaining peer) + 1 ≤ remaining current + remaining peer
  rw [Nat.add_right_comm _ (remaining peer) 1, tickConsumesProgress current budgetOpen]
  exact Nat.le_refl _

#print axioms tickWithinBudget
#print axioms tickConsumesProgress
#print axioms finishConsumesProgress
#print axioms tickConsumesJointProgress
