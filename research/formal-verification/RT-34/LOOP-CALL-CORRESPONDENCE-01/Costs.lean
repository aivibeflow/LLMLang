def calls (left right : Nat) : Bool → Nat → Nat
  | _, 0 => 0
  | true, n + 1 => left + calls left right false n
  | false, n + 1 => right + calls left right true n

theorem uniformly_bounded (left right cap : Nat) (hl : left ≤ cap) (hr : right ≤ cap)
    (n : Nat) (side : Bool) : calls left right side n ≤ cap * n := by
  induction n generalizing side with
  | zero => cases side <;> simp [calls]
  | succ n ih =>
    cases side
    · simp only [calls, Nat.mul_succ]
      have step := ih true
      omega
    · simp only [calls, Nat.mul_succ]
      have step := ih false
      omega

def loop (left right : Nat) (side : Bool) : Nat → Nat
  | 0 => 0
  | n + 1 => loop left right side n + calls left right side (n + 1)

def triangular : Nat → Nat
  | 0 => 0
  | n + 1 => triangular n + (n + 1)

theorem loop_cost_bound (left right cap : Nat) (hl : left ≤ cap) (hr : right ≤ cap)
    (n : Nat) (side : Bool) : loop left right side n ≤ cap * triangular n := by
  induction n with
  | zero => simp [loop, triangular]
  | succ n ih =>
    simp only [loop, triangular, Nat.mul_add]
    have step := uniformly_bounded left right cap hl hr (n + 1) side
    rw [Nat.mul_add, Nat.mul_one] at step
    omega

theorem exact_call_count (n : Nat) (side : Bool) : calls 1 1 side n = n := by
  induction n generalizing side with
  | zero => cases side <;> rfl
  | succ n ih => cases side <;> simp [calls, ih, Nat.add_comm]

theorem full_call_count (n : Nat) (side : Bool) : loop 1 1 side n = triangular n := by
  induction n with
  | zero => rfl
  | succ n ih => simp [loop, ih, exact_call_count, triangular]

theorem rebind_invalidates : 5 * triangular 1 < loop 2 9 false 1 := by decide

#print axioms uniformly_bounded
#print axioms loop_cost_bound
#print axioms exact_call_count
#print axioms full_call_count
#print axioms rebind_invalidates
