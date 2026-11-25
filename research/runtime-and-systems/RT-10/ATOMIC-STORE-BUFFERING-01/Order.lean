theorem no_both_old_in_a_total_order (storeX loadY storeY loadX : Nat)
    (programA : storeX < loadY) (programB : storeY < loadX)
    (oldY : loadY < storeY) (oldX : loadX < storeX) :
    False := by
  exact (Nat.lt_irrefl storeX)
    (Nat.lt_trans programA (Nat.lt_trans oldY (Nat.lt_trans programB oldX)))

theorem release_acquire_edges_need_observed_writes
    (readsNewX readsNewY : Bool) (oldX : readsNewX = false) (oldY : readsNewY = false) :
    (readsNewX || readsNewY) = false := by
  simp [oldX, oldY]

#print axioms no_both_old_in_a_total_order
#print axioms release_acquire_edges_need_observed_writes
