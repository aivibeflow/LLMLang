import Std.Tactic

namespace Affine

structure Row where
  left : Int
  right : Int
  offset : Int
  deriving Repr, DecidableEq

def eval (row : Row) (x y : Int) : Int :=
  row.left * x + row.right * y + row.offset

def add (a b : Row) : Row :=
  ⟨a.left + b.left, a.right + b.right, a.offset + b.offset⟩

def scale (n : Nat) (row : Row) : Row :=
  ⟨(n : Int) * row.left, (n : Int) * row.right, (n : Int) * row.offset⟩

theorem eval_add (a b : Row) (x y : Int) :
    eval (add a b) x y = eval a x y + eval b x y := by
  simp only [eval, add, Int.add_mul]
  omega

theorem eval_scale (n : Nat) (row : Row) (x y : Int) :
    eval (scale n row) x y = (n : Int) * eval row x y := by
  simp only [eval, scale, Int.mul_add, Int.mul_assoc]

def holds (x y : Int) : List Row → Prop
  | [] => True
  | row :: rest => eval row x y ≤ 0 ∧ holds x y rest

def sum : List Row → List Nat → Row
  | row :: rows, n :: weights => add (scale n row) (sum rows weights)
  | _, _ => ⟨0, 0, 0⟩

theorem sum_nonpos (x y : Int) (rows : List Row) (weights : List Nat)
    (admitted : holds x y rows) : eval (sum rows weights) x y ≤ 0 := by
  induction rows generalizing weights with
  | nil => simp [sum, eval]
  | cons row rest ih =>
    cases weights with
    | nil => simp [sum, eval]
    | cons n restWeights =>
      change eval row x y ≤ 0 ∧ holds x y rest at admitted
      simp only [sum, eval_add, eval_scale]
      exact Int.add_nonpos
        (Int.mul_nonpos_of_nonneg_of_nonpos (Int.natCast_nonneg n) admitted.1)
        (ih restWeights admitted.2)

def check (rows : List Row) (weights : List Nat) : Bool :=
  let combined := sum rows weights
  decide (rows.length = weights.length ∧ combined.left = 0 ∧
          combined.right = 0 ∧ 0 < combined.offset)

theorem sound (x y : Int) (rows : List Row) (weights : List Nat)
    (accepted : check rows weights = true) : ¬ holds x y rows := by
  intro admitted
  have result := sum_nonpos x y rows weights admitted
  have fields : rows.length = weights.length ∧ (sum rows weights).left = 0 ∧
      (sum rows weights).right = 0 ∧ 0 < (sum rows weights).offset := of_decide_eq_true accepted
  simp only [eval, fields.2.1, fields.2.2.1, Int.zero_mul, Int.zero_add] at result
  exact (Int.not_lt_of_ge result) fields.2.2.2

def possible (x y : Int) : List (List Row) → Prop
  | [] => False
  | rows :: branches => holds x y rows ∨ possible x y branches

def checkBranches : List (List Row) → List (List Nat) → Bool
  | [], [] => true
  | rows :: branches, weights :: certificates =>
    check rows weights && checkBranches branches certificates
  | _, _ => false

theorem branches_sound (x y : Int) (branches : List (List Row))
    (certificates : List (List Nat)) (accepted : checkBranches branches certificates = true) :
    ¬ possible x y branches := by
  induction branches generalizing certificates with
  | nil => simp [possible]
  | cons rows branches ih =>
    cases certificates with
    | nil => simp [checkBranches] at accepted
    | cons weights tail =>
      have checks := Bool.and_eq_true_iff.mp accepted
      intro candidate
      cases candidate with
      | inl localRows => exact sound x y rows weights checks.1 localRows
      | inr remaining => exact ih tail checks.2 remaining

end Affine
