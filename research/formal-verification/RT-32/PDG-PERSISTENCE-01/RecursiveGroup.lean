namespace ReceiptGroup

mutual
  def left : Nat → Nat
    | 0 => 0
    | n + 1 => right n + 1

  def right : Nat → Nat
    | 0 => 0
    | n + 1 => left n + 1
end

theorem simultaneous (n : Nat) : left n = n ∧ right n = n := by
  induction n with
  | zero => exact ⟨left.eq_1, right.eq_1⟩
  | succ n ih =>
    constructor
    · exact (left.eq_2 n).trans (congrArg (fun value => value + 1) ih.2)
    · exact (right.eq_2 n).trans (congrArg (fun value => value + 1) ih.1)

end ReceiptGroup

#print axioms ReceiptGroup.simultaneous
