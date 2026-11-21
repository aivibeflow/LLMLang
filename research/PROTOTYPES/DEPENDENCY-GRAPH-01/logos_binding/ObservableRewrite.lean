import Std

/-! A typed rewrite experiment with left-to-right evaluation and observable failure. -/
namespace ObservableRewrite

inductive ScalarSort where
  | int
  | bool

abbrev ScalarSort.value : ScalarSort → Type
  | .int => Int
  | .bool => Bool

abbrev Run (α : Type) := Except Nat α × List Nat

/-- Keep effects produced before a failure and skip the failed computation's continuation. -/
def sequence (first : Run α) (next : α → Run β) : Run β :=
  match first with
  | (.error code, trace) => (.error code, trace)
  | (.ok value, trace) =>
      let (result, tail) := next value
      (result, trace ++ tail)

inductive Expr : ScalarSort → Type where
  | integer : Int → Expr .int
  | boolean : Bool → Expr .bool
  | input : Expr .int
  | add : Expr .int → Expr .int → Expr .int
  | equal : Expr .int → Expr .int → Expr .bool
  | choose : Expr .bool → Expr s → Expr s → Expr s
  | emit : Nat → Expr s → Expr s
  | fail : Nat → Expr s

def evaluate (input : Int) : Expr s → Run s.value
  | .integer value => (.ok value, [])
  | .boolean value => (.ok value, [])
  | .input => (.ok input, [])
  | .add left right =>
      sequence (evaluate input left) fun l =>
        sequence (evaluate input right) fun r => (.ok (l + r), [])
  | .equal left right =>
      sequence (evaluate input left) fun l =>
        sequence (evaluate input right) fun r => (.ok (l == r), [])
  | .choose test yes no =>
      sequence (evaluate input test) fun takeYes =>
        if takeYes then evaluate input yes else evaluate input no
  | .emit event tail =>
      let (result, trace) := evaluate input tail
      (result, event :: trace)
  | .fail code => (.error code, [])

def foldAdd (left right : Expr .int) : Expr .int :=
  match left, right with
  | .integer l, .integer r => .integer (l + r)
  | .integer 0, right => right
  | left, .integer 0 => left
  | left, right => .add left right

def foldChoose (test : Expr .bool) (yes no : Expr s) : Expr s :=
  match test with
  | .boolean true => yes
  | .boolean false => no
  | test => .choose test yes no

private theorem sequence_return (run : Run α) :
    sequence run (fun value => (.ok value, [])) = run := by
  rcases run with ⟨result, trace⟩
  cases result <;> simp [sequence]

private theorem sequence_pure (value : α) (next : α → Run β) :
    sequence (.ok value, []) next = next value := by
  simp [sequence]

theorem foldAdd_preserves (input : Int) (left right : Expr .int) :
    evaluate input (foldAdd left right) = evaluate input (.add left right) := by
  unfold foldAdd
  split
  · rfl
  · rename_i right _
    simp only [evaluate, sequence_pure, Int.zero_add, sequence_return]
  · rename_i left _ _
    simp only [evaluate, sequence_pure, Int.add_zero, sequence_return]
  · rfl

theorem foldChoose_preserves (input : Int) (test : Expr .bool) (yes no : Expr s) :
    evaluate input (foldChoose test yes no) = evaluate input (.choose test yes no) := by
  unfold foldChoose
  split
  · simp [evaluate, sequence]
  · simp [evaluate, sequence]
  · rfl

def rewrite : Expr s → Expr s
  | .add left right => foldAdd (rewrite left) (rewrite right)
  | .equal left right => .equal (rewrite left) (rewrite right)
  | .choose test yes no => foldChoose (rewrite test) (rewrite yes) (rewrite no)
  | .emit event tail => .emit event (rewrite tail)
  | leaf => leaf

theorem rewrite_preserves (input : Int) (expr : Expr s) :
    evaluate input (rewrite expr) = evaluate input expr := by
  induction expr with
  | add left right leftIH rightIH =>
      simp [rewrite, foldAdd_preserves, evaluate, leftIH, rightIH]
  | equal left right leftIH rightIH =>
      simp [rewrite, evaluate, leftIH, rightIH]
  | choose test yes no testIH yesIH noIH =>
      simp [rewrite, foldChoose_preserves, evaluate, testIH, yesIH, noIH]
  | emit event tail tailIH => simp [rewrite, evaluate, tailIH]
  | integer | boolean | input | fail => rfl

theorem swapping_addends_changes_trace :
    evaluate 0 (.add (.emit 1 (.integer 2)) (.emit 2 (.integer 3))) ≠
    evaluate 0 (.add (.emit 2 (.integer 3)) (.emit 1 (.integer 2))) := by
  intro equality
  have traces := congrArg Prod.snd equality
  change [1, 2] = [2, 1] at traces
  contradiction

theorem discarding_equal_branch_guard_hides_failure :
    evaluate 0 (.choose (.emit 1 (.fail 7)) (.integer 2) (.integer 2)) ≠
    evaluate 0 (.integer 2) := by
  intro equality
  have traces := congrArg Prod.snd equality
  change [1] = [] at traces
  contradiction

theorem keeping_trace_before_failure :
    evaluate 0 (rewrite (.add (.integer 0) (.emit 1 (.fail 7)))) = (.error 7, [1]) := by
  rfl

#print axioms rewrite_preserves
#print axioms swapping_addends_changes_trace
#print axioms discarding_equal_branch_guard_hides_failure

end ObservableRewrite
