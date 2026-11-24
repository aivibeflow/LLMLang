import LogosScalarDenotation

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding
open LLMLang.SourceQuerySemantics (Expr Env evalExpr translateExpr)
open LLMLang.LogosQueryAdapter (toLogosQueryTerm)

private abbrev Bindings := List (String × Eo.Term)

private def render (bindings : Bindings) {sort : QuerySort} (expr : Expr sort) :=
  renderQueryTerm bindings (toLogosQueryTerm (translateExpr expr))

private def evaluate (valuation : Valuation) (term : Eo.Term) :=
  evalSmt valuation (__eo_to_smt term)

/-- The explicit interpretation agrees with every constant resolved by the adapter. -/
def Corresponds (bindings : List (String × Eo.Term)) (input : Env) (valuation : Valuation) : Prop :=
  ∀ name sort {constant},
    resolveQuerySymbol bindings name sort = .ok constant →
    evalSmt valuation (__eo_to_smt constant) = .ok (fromSource (input name sort))

private theorem simpleBinary {left right : Except String Eo.Term} {op : Eo.UserOp} {result : Eo.Term}
    (built : apply2 op <$> left <*> right = .ok result) :
    ∃ a b, left = .ok a ∧ right = .ok b ∧ result = apply2 op a b := by
  cases left with
  | error _ => cases right <;> cases built
  | ok a =>
      cases right with
      | error _ => cases built
      | ok b =>
          change Except.ok (apply2 op a b) = Except.ok result at built
          exact ⟨a, b, rfl, rfl, (Except.ok.inj built).symm⟩

private theorem foldedBinary {left right : Except String Eo.Term} {op : Eo.UserOp} {result : Eo.Term}
    (built : (do
      let a ← left
      let b ← right
      applyRightAssocNil op [a, b]) = .ok result) :
    ∃ a b, left = .ok a ∧ right = .ok b ∧
      result = apply2 op a (apply2 op b (Eo.__eo_nil (.UOp op) (Eo.__eo_typeof a))) := by
  cases left with
  | error _ => cases built
  | ok a =>
      cases right with
      | error _ => cases built
      | ok b =>
          change Except.ok (apply2 op a (apply2 op b (Eo.__eo_nil (.UOp op) (Eo.__eo_typeof a)))) =
            Except.ok result at built
          exact ⟨a, b, rfl, rfl, (Except.ok.inj built).symm⟩

private theorem foldTwoTerms (renderTerm : QueryTerm .bool → Except String Eo.Term)
    (a b : QueryTerm .bool) (op : Eo.UserOp) :
    (do
      let terms ← [a, b].mapM renderTerm
      applyRightAssocNil op terms) =
    (do
      let left ← renderTerm a
      let right ← renderTerm b
      applyRightAssocNil op [left, right]) := by
  simp only [List.mapM_cons, List.mapM_nil]
  cases renderTerm a <;> cases renderTerm b <;> rfl

private theorem simpleTernary {cond yes no : Except String Eo.Term} {result : Eo.Term}
    (built : apply3 .ite <$> cond <*> yes <*> no = .ok result) :
    ∃ g a b, cond = .ok g ∧ yes = .ok a ∧ no = .ok b ∧ result = apply3 .ite g a b := by
  cases cond with
  | error _ => cases yes <;> cases no <;> cases built
  | ok g =>
      cases yes with
      | error _ => cases no <;> cases built
      | ok a =>
          cases no with
          | error _ => cases built
          | ok b =>
              change Except.ok (apply3 .ite g a b) = Except.ok result at built
              exact ⟨g, a, b, rfl, rfl, rfl, (Except.ok.inj built).symm⟩

private theorem renderSort (bindings : Bindings) {sort : QuerySort}
    {expr : Expr sort} {term : Eo.Term} (built : render bindings expr = .ok term) :
    Eo.__eo_typeof term = logosSort sort :=
  renderQueryTerm_sort bindings (toLogosQueryTerm (translateExpr expr)) built

/-- Successful rendering of a typed expression preserves its scalar value under related valuations. -/
theorem expression_preservation (bindings : List (String × Eo.Term)) (input : Env) (valuation : Valuation)
    (symbols : Corresponds bindings input valuation) {sort : QuerySort}
    (expr : Expr sort) {term : Eo.Term}
    (compiled : renderQueryTerm bindings (toLogosQueryTerm (translateExpr expr)) = .ok term) :
    evalSmt valuation (__eo_to_smt term) = .ok (fromSource (evalExpr expr input)) := by
  change render bindings expr = .ok term at compiled
  change evaluate valuation term = _
  induction expr generalizing term with
  | intLit _ | boolLit _ =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm, pure, Except.pure, Except.ok.injEq] at compiled
      subst term
      rfl
  | intVar name | boolVar name =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      exact symbols name _ compiled
  | neg value ih =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      change apply1 .__eoo_neg_2 <$> render bindings value = .ok term at compiled
      cases source : render bindings value with
      | error reason =>
          rw [source] at compiled
          cases compiled
      | ok rendered =>
          rw [source] at compiled
          change Except.ok (apply1 .__eoo_neg_2 rendered) = Except.ok term at compiled
          cases compiled
          change (do pure (Scalar.int (-(← needInt (← evaluate valuation rendered))))) = _
          rw [ih source, evalExpr]
          cases evalExpr value input
          rfl
  | sub a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := simpleBinary compiled
      change (do
        pure (Scalar.int ((← needInt (← evaluate valuation left)) -
          (← needInt (← evaluate valuation right))))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rfl
  | add a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := foldedBinary compiled
      have leftSort : Eo.__eo_typeof left = logosSort .int := renderSort bindings (expr := a) leftOk
      rw [leftSort]
      change evalSmt valuation (.plus (__eo_to_smt left) (.plus (__eo_to_smt right) (.Numeral 0))) = _
      rw [evalSmt, evalSmt]
      change (do
        pure (Scalar.int ((← needInt (← evaluate valuation left)) +
          (← needInt (← (do pure (Scalar.int ((← needInt (← evaluate valuation right)) + 0)))))))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rename_i x y
      change Except.ok (Scalar.int (x + (y + 0))) = Except.ok (Scalar.int (x + y))
      rw [Int.add_zero]
  | not value ih =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      change apply1 .not <$> render bindings value = .ok term at compiled
      cases source : render bindings value with
      | error reason =>
          rw [source] at compiled
          cases compiled
      | ok rendered =>
          rw [source] at compiled
          change Except.ok (apply1 .not rendered) = Except.ok term at compiled
          cases compiled
          change (do pure (Scalar.bool (!(← needBool (← evaluate valuation rendered))))) = _
          rw [ih source, evalExpr]
          cases evalExpr value input
          rfl
  | mulConst multiplier value ih =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨_, right, leftOk, rightOk, rfl⟩ := foldedBinary compiled
      change Except.ok (Eo.Term.Numeral multiplier) = Except.ok _ at leftOk
      cases leftOk
      change evalSmt valuation (.mult (.Numeral multiplier)
        (.mult (__eo_to_smt right) (.Numeral 1))) = _
      rw [evalSmt, evalSmt]
      change (do pure (Scalar.int (multiplier * (← needInt
        (← (do pure (Scalar.int ((← needInt (← evaluate valuation right)) * 1)))))))) = _
      rw [ih rightOk, evalExpr]
      cases evalExpr value input
      rename_i number
      change Except.ok (Scalar.int (multiplier * (number * 1))) =
        Except.ok (Scalar.int (multiplier * number))
      rw [Int.mul_one]
  | lt a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := simpleBinary compiled
      change (do pure (Scalar.bool (decide ((← needInt (← evaluate valuation left)) <
        (← needInt (← evaluate valuation right)))))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rfl
  | le a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := simpleBinary compiled
      change (do pure (Scalar.bool (decide ((← needInt (← evaluate valuation left)) ≤
        (← needInt (← evaluate valuation right)))))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rfl
  | eqInt a b ihA ihB | eqBool a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := simpleBinary compiled
      change (do
        let l ← evaluate valuation left
        let r ← evaluate valuation right
        if l.sort == r.sort then pure (Scalar.bool (l == r)) else throw "mixed equality") = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input <;> cases evalExpr b input <;> rfl
  | and a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      rw [ite_eq_right (by exact Nat.lt_irrefl 2), foldTwoTerms] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := foldedBinary
        (left := render bindings a) (right := render bindings b) (op := .and) compiled
      have leftSort : Eo.__eo_typeof left = logosSort .bool := renderSort bindings (expr := a) leftOk
      rw [leftSort]
      change evalSmt valuation (.and (__eo_to_smt left) (.and (__eo_to_smt right) (.Boolean true))) = _
      rw [evalSmt, evalSmt]
      change (do
        let l ← needBool (← evaluate valuation left)
        let r ← needBool (← (do
          let inner ← needBool (← evaluate valuation right)
          pure (Scalar.bool (inner && true))))
        pure (Scalar.bool (l && r))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rename_i x y
      change Except.ok (Scalar.bool (x && (y && true))) = Except.ok (Scalar.bool (x && y))
      rw [Bool.and_true]
  | or a b ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      rw [ite_eq_right (by exact Nat.lt_irrefl 2), foldTwoTerms] at compiled
      obtain ⟨left, right, leftOk, rightOk, rfl⟩ := foldedBinary
        (left := render bindings a) (right := render bindings b) (op := .or) compiled
      have leftSort : Eo.__eo_typeof left = logosSort .bool := renderSort bindings (expr := a) leftOk
      rw [leftSort]
      change evalSmt valuation (.or (__eo_to_smt left) (.or (__eo_to_smt right) (.Boolean false))) = _
      rw [evalSmt, evalSmt]
      change (do
        let l ← needBool (← evaluate valuation left)
        let r ← needBool (← (do
          let inner ← needBool (← evaluate valuation right)
          pure (Scalar.bool (inner || false))))
        pure (Scalar.bool (l || r))) = _
      rw [ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr a input
      cases evalExpr b input
      rename_i x y
      change Except.ok (Scalar.bool (x || (y || false))) = Except.ok (Scalar.bool (x || y))
      rw [Bool.or_false]
  | iteInt g a b ihG ihA ihB | iteBool g a b ihG ihA ihB =>
      simp only [render, translateExpr, toLogosQueryTerm, renderQueryTerm] at compiled
      obtain ⟨guard, left, right, guardOk, leftOk, rightOk, rfl⟩ := simpleTernary compiled
      change (do
        let chosen ← needBool (← evaluate valuation guard)
        let l ← evaluate valuation left
        let r ← evaluate valuation right
        if l.sort != r.sort then throw "mixed conditional arms"
        pure (if chosen then l else r)) = _
      rw [ihG guardOk, ihA leftOk, ihB rightOk, evalExpr]
      cases evalExpr g input with
      | boolValue chosen =>
          cases evalExpr a input <;> cases evalExpr b input <;> cases chosen <;> rfl

#print axioms expression_preservation

end LLMLang.LogosScalarDenotation
