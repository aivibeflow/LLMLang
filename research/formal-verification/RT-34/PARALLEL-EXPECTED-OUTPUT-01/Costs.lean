def triangular : Nat → Nat
  | 0 => 0
  | n + 1 => triangular n + (n + 1)

theorem uniform_probe_sum (n : Nat) : 2 * triangular n = n * (n + 1) := by
  induction n with
  | zero => decide
  | succ n ih =>
    rw [triangular, Nat.mul_add, ih]
    simp only [Nat.add_mul, Nat.mul_add, Nat.mul_one, Nat.one_mul]
    omega

def leaves : Nat → Nat
  | 0 => 1
  | d + 1 => 2 * leaves d

def branchNodes : Nat → Nat
  | 0 => 0
  | d + 1 => 1 + 2 * branchNodes d

theorem full_tree_nodes (d : Nat) : branchNodes d + 1 = leaves d := by
  induction d with
  | zero => decide
  | succ d ih =>
    rw [branchNodes, leaves, ← ih]
    omega

def edges : Nat → Nat
  | 0 => 0
  | d + 1 => 2 + 2 * edges d

theorem tree_messages (d : Nat) : edges d = 2 * branchNodes d := by
  induction d with
  | zero => decide
  | succ d ih =>
    rw [edges, branchNodes, ih]
    omega

def pathFromLeaf (q : Nat) : Nat → Nat
  | 0 => q
  | d + 1 => pathFromLeaf q d + 1

theorem padded_path (q d : Nat) : pathFromLeaf q d = q + d := by
  induction d with
  | zero => simp [pathFromLeaf]
  | succ d ih => simp [pathFromLeaf, ih, Nat.add_assoc]

def outputBytes (k width : Nat) : Nat := k * width

theorem bounded_width (n k width cap : Nat) (count : k ≤ n) (size : width ≤ cap) :
    outputBytes k width ≤ n * cap := by
  unfold outputBytes
  exact Nat.le_trans (Nat.mul_le_mul_right width count) (Nat.mul_le_mul_left n size)

theorem no_n_only_bound (n budget : Nat) (nonempty : n > 0) :
    ∃ k width, 0 < width ∧ k ≤ n ∧ budget < outputBytes k width := by
  refine ⟨1, budget + 1, by omega, by omega, ?_⟩
  simp [outputBytes]

#print axioms uniform_probe_sum
#print axioms full_tree_nodes
#print axioms tree_messages
#print axioms padded_path
#print axioms bounded_width
#print axioms no_n_only_bound
