namespace DelegatedQuota

structure Ledger where
  parentAvailable : Nat
  childAvailable : Nat
  unsettled : Nat
  spent : Nat

def total (state : Ledger) : Nat :=
  state.parentAvailable + state.childAvailable + state.unsettled + state.spent

def reclaimUnused (state : Ledger) : Ledger :=
  { state with parentAvailable := state.parentAvailable + state.childAvailable, childAvailable := 0 }

def settle (state : Ledger) (used : Nat) : Ledger :=
  { state with parentAvailable := state.parentAvailable + (state.unsettled - used),
               unsettled := 0, spent := state.spent + used }

theorem reclaimConserves (state : Ledger) :
    total (reclaimUnused state) = total state := by
  simp [total, reclaimUnused]

theorem reclaimIdempotent (state : Ledger) :
    reclaimUnused (reclaimUnused state) = reclaimUnused state := by
  simp [reclaimUnused]

theorem settleConserves (state : Ledger) (used : Nat) (bound : used ≤ state.unsettled) :
    total (settle state used) = total state := by
  simp [total, settle]
  omega

theorem admissionSafe (state : Ledger) (request : Nat) (permit : request ≤ (reclaimUnused state).parentAvailable)
    (laterUsage : Nat) (bound : laterUsage ≤ state.unsettled) :
    request + state.spent + laterUsage ≤ total state := by
  simp [reclaimUnused] at permit
  unfold total
  omega

theorem fullReturnCanOvercommit :
    let state : Ledger := ⟨1, 1, 1, 2⟩
    let delegated := state.childAvailable + state.unsettled + state.spent
    state.parentAvailable + delegated + state.spent > total state := by
  decide

#print axioms reclaimConserves
#print axioms reclaimIdempotent
#print axioms settleConserves
#print axioms admissionSafe
#print axioms fullReturnCanOvercommit

end DelegatedQuota
