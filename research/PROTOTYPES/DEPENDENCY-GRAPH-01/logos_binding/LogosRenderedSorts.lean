import LLMLangLogosBinding

namespace LLMLang.LogosBinding

def logosSort : QuerySort → Eo.Term
  | .int => .UOp .Int
  | .bool => .Bool

theorem hasExpectedSort_correct {sort : QuerySort} {term : Eo.Term}
    (accepted : hasExpectedSort term sort.expected = true) :
    Eo.__eo_typeof term = logosSort sort := by
  cases sort <;> unfold QuerySort.expected hasExpectedSort at accepted <;>
    split at accepted <;> first | contradiction | rfl

theorem resolveQuerySymbol_sort {bindings : List (String × Eo.Term)} {name : String}
    {sort : QuerySort} {term : Eo.Term} (accepted : resolveQuerySymbol bindings name sort = .ok term) :
    Eo.__eo_typeof term = logosSort sort := by
  unfold resolveQuerySymbol at accepted
  split at accepted
  · rename_i pair entries
    split at accepted
    · rename_i valid
      simp only [pure, Except.pure, Except.ok.injEq] at accepted
      subst term
      exact hasExpectedSort_correct valid
    · contradiction
  · contradiction
  · contradiction

private inductive FoldOperator where
  | plus
  | times
  | and
  | or

private def FoldOperator.operator : FoldOperator → Eo.UserOp
  | .plus => .plus
  | .times => .mult
  | .and => .and
  | .or => .or

private def FoldOperator.sort : FoldOperator → Eo.Term
  | .plus | .times => logosSort .int
  | .and | .or => logosSort .bool

private theorem foldOperator_step (fold : FoldOperator) (a b : Eo.Term)
    (ha : Eo.__eo_typeof a = fold.sort) (hb : Eo.__eo_typeof b = fold.sort) :
    Eo.__eo_typeof (apply2 fold.operator a b) = fold.sort := by
  cases fold with
  | plus | times =>
      change Eo.__eo_typeof_plus (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ha, hb]
      rfl
  | and | or =>
      change Eo.__eo_typeof_or (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ha, hb]
      rfl

private theorem foldOperator_type (fold : FoldOperator) (terms : List Eo.Term)
    (typed : ∀ term ∈ terms, Eo.__eo_typeof term = fold.sort) :
    Eo.__eo_typeof (terms.foldr (apply2 fold.operator)
      (Eo.__eo_nil (.UOp fold.operator) fold.sort)) = fold.sort := by
  induction terms with
  | nil => cases fold <;> rfl
  | cons first rest ih =>
      exact foldOperator_step fold first _ (typed first (by simp))
        (ih (fun term mem => typed term (List.mem_cons_of_mem _ mem)))

private theorem applyRightAssocNil_sort (fold : FoldOperator) {terms : List Eo.Term}
    {output : Eo.Term} (typed : ∀ term ∈ terms, Eo.__eo_typeof term = fold.sort)
    (accepted : applyRightAssocNil fold.operator terms = .ok output) :
    Eo.__eo_typeof output = fold.sort := by
  cases terms with
  | nil =>
      change Except.error _ = .ok output at accepted
      cases accepted
  | cons first rest =>
      change Except.ok ((first :: rest).foldr (apply2 fold.operator)
        (Eo.__eo_nil (.UOp fold.operator) (Eo.__eo_typeof first))) = .ok output at accepted
      injection accepted with same
      rw [← same, typed first (by simp)]
      exact foldOperator_type fold (first :: rest) typed

private theorem mapM_preserves {α β : Type} {f : α → Except String β} {p : β → Prop}
    (inputs : List α) {outputs : List β}
    (each : ∀ input ∈ inputs, ∀ output, f input = .ok output → p output)
    (accepted : inputs.mapM f = .ok outputs) :
    ∀ output ∈ outputs, p output := by
  induction inputs generalizing outputs with
  | nil =>
      simp [List.mapM_nil, pure, Except.pure] at accepted
      subst outputs
      simp
  | cons first rest ih =>
      rw [List.mapM_cons] at accepted
      cases hf : f first with
      | error reason =>
          rw [hf] at accepted
          change Except.error reason = .ok outputs at accepted
          cases accepted
      | ok initial =>
          cases hr : rest.mapM f with
          | error reason =>
              rw [hf, hr] at accepted
              change Except.error reason = .ok outputs at accepted
              cases accepted
          | ok tail =>
              rw [hf, hr] at accepted
              change Except.ok (initial :: tail) = .ok outputs at accepted
              injection accepted with same
              subst outputs
              intro output mem
              rcases List.mem_cons.mp mem with head | later
              · rw [head]
                exact each first (by simp) initial hf
              · exact ih (fun input membership => each input (List.mem_cons_of_mem _ membership))
                  hr output later

private theorem bindResult {first : Except String α} {f : α → Except String β} {output : β}
    (accepted : (first >>= f) = .ok output) :
    ∃ item, first = .ok item ∧ f item = .ok output := by
  cases first with
  | error reason =>
      change Except.error reason = .ok output at accepted
      cases accepted
  | ok item => exact ⟨item, rfl, accepted⟩

private theorem mapResult {source : Except String α} {f : α → β} {output : β}
    (accepted : f <$> source = .ok output) :
    ∃ item, source = .ok item ∧ f item = output := by
  cases source with
  | error reason =>
      change Except.error reason = .ok output at accepted
      cases accepted
  | ok item =>
      change Except.ok (f item) = .ok output at accepted
      exact ⟨item, rfl, Except.ok.inj accepted⟩

private theorem seqResult {fn : Except String (α → β)} {arg : Except String α} {output : β}
    (accepted : fn <*> arg = .ok output) :
    ∃ f item, fn = .ok f ∧ arg = .ok item ∧ f item = output := by
  cases fn with
  | error reason =>
      change Except.error reason = .ok output at accepted
      cases accepted
  | ok f =>
      cases arg with
      | error reason =>
          change Except.error reason = .ok output at accepted
          cases accepted
      | ok item =>
          change Except.ok (f item) = .ok output at accepted
          exact ⟨f, item, rfl, rfl, Except.ok.inj accepted⟩

private theorem binaryResult {x y : Except String Eo.Term} {f : Eo.Term → Eo.Term → Eo.Term}
    {output : Eo.Term} (accepted : f <$> x <*> y = .ok output) :
    ∃ a b, x = .ok a ∧ y = .ok b ∧ f a b = output := by
  obtain ⟨partialFn, b, partialResult, hb, same⟩ := seqResult accepted
  obtain ⟨a, ha, rfl⟩ := mapResult partialResult
  exact ⟨a, b, ha, hb, same⟩

private theorem ternaryResult {x y z : Except String Eo.Term}
    {f : Eo.Term → Eo.Term → Eo.Term → Eo.Term} {output : Eo.Term}
    (accepted : f <$> x <*> y <*> z = .ok output) :
    ∃ a b c, x = .ok a ∧ y = .ok b ∧ z = .ok c ∧ f a b c = output := by
  obtain ⟨fn, c, second, hc, same⟩ := seqResult accepted
  obtain ⟨partialFn, b, first, hb, rfl⟩ := seqResult second
  obtain ⟨a, ha, rfl⟩ := mapResult first
  exact ⟨a, b, c, ha, hb, hc, same⟩

/-- The existing renderer outputs only the exact Logos sort of a typed admitted term. -/
theorem renderQueryTerm_sort (bindings : List (String × Eo.Term)) {sort : QuerySort}
    (term : QueryTerm sort) {output : Eo.Term} (accepted : renderQueryTerm bindings term = .ok output) :
    Eo.__eo_typeof output = logosSort sort := by
  induction sort, term using renderQueryTerm.induct generalizing output with
  | case1 value =>
      rw [renderQueryTerm] at accepted
      change Except.ok (.Numeral value) = .ok output at accepted
      cases accepted
      rfl
  | case2 name | case9 name =>
      rw [renderQueryTerm] at accepted
      exact resolveQuerySymbol_sort accepted
  | case3 value ih =>
      rw [renderQueryTerm] at accepted
      obtain ⟨inner, typed, rfl⟩ := mapResult accepted
      change Eo.__eo_typeof_abs (Eo.__eo_typeof inner) = _
      rw [ih typed]
      rfl
  | case4 left right ihLeft ihRight | case6 left right ihLeft ihRight =>
      rw [renderQueryTerm] at accepted
      obtain ⟨a, ha, rest⟩ := bindResult accepted
      obtain ⟨b, hb, done⟩ := bindResult rest
      have haType := ihLeft ha
      have hbType := ihRight hb
      first
      | exact applyRightAssocNil_sort .plus (by simp [haType, hbType, FoldOperator.sort]) done
      | exact applyRightAssocNil_sort .times (by simp [haType, hbType, FoldOperator.sort]) done
  | case5 left right ihLeft ihRight =>
      rw [renderQueryTerm] at accepted
      obtain ⟨a, b, ha, hb, rfl⟩ := binaryResult accepted
      change Eo.__eo_typeof_plus (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ihLeft ha, ihRight hb]
      rfl
  | case7 guard yes no ihGuard ihYes ihNo | case19 guard yes no ihGuard ihYes ihNo =>
      rw [renderQueryTerm] at accepted
      obtain ⟨g, a, b, hg, ha, hb, rfl⟩ := ternaryResult accepted
      change Eo.__eo_typeof_ite (Eo.__eo_typeof g) (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ihGuard hg, ihYes ha, ihNo hb]
      rfl
  | case8 value =>
      rw [renderQueryTerm] at accepted
      change Except.ok (.Boolean value) = .ok output at accepted
      cases accepted
      rfl
  | case10 value ih =>
      rw [renderQueryTerm] at accepted
      obtain ⟨inner, hi, rfl⟩ := mapResult accepted
      change Eo.__eo_typeof_not (Eo.__eo_typeof inner) = _
      rw [ih hi]
      rfl
  | case11 left right ihLeft ihRight | case12 left right ihLeft ihRight =>
      rw [renderQueryTerm] at accepted
      obtain ⟨a, b, ha, hb, rfl⟩ := binaryResult accepted
      change Eo.__eo_typeof_eq (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ihLeft ha, ihRight hb]
      rfl
  | case13 left right ihLeft ihRight | case14 left right ihLeft ihRight =>
      rw [renderQueryTerm] at accepted
      obtain ⟨a, b, ha, hb, rfl⟩ := binaryResult accepted
      change Eo.__eo_typeof_lt (Eo.__eo_typeof a) (Eo.__eo_typeof b) = _
      rw [ihLeft ha, ihRight hb]
      rfl
  | case15 terms short | case17 terms short =>
      rw [renderQueryTerm, ite_eq_left short] at accepted
      cases accepted
  | case16 terms enough ih | case18 terms enough ih =>
      rw [renderQueryTerm, ite_eq_right enough] at accepted
      obtain ⟨rendered, termsOk, done⟩ := bindResult accepted
      have allBool : ∀ value ∈ rendered, Eo.__eo_typeof value = logosSort .bool :=
        mapM_preserves terms (fun input mem _ result => ih input mem result) termsOk
      first
      | exact applyRightAssocNil_sort .and allBool done
      | exact applyRightAssocNil_sort .or allBool done

/-- Both positions of every accepted ordered relational assumption pair are Logos Bool. -/
theorem renderRelationalAssumptions_sorts (bindings : List (String × Eo.Term))
    (factorSort : QuerySort) (leftName rightName : String)
    (factor observation : QueryTerm .bool) {output : List Eo.Term}
    (accepted : renderRelationalAssumptions bindings factorSort leftName rightName
      factor observation = .ok output) :
    output.map Eo.__eo_typeof = [.Bool, .Bool] := by
  unfold renderRelationalAssumptions at accepted
  obtain ⟨left, leftOk, remaining⟩ := bindResult accepted
  obtain ⟨right, rightOk, remaining⟩ := bindResult remaining
  obtain ⟨observed, observedOk, remaining⟩ := bindResult remaining
  obtain ⟨expected, _, final⟩ := bindResult remaining
  split at final
  · cases final
  · change Except.ok [apply1 .not (apply2 .eq left right), observed] = .ok output at final
    cases final
    have factorType : Eo.__eo_typeof (apply1 .not (apply2 .eq left right)) = .Bool := by
      change Eo.__eo_typeof_not
        (Eo.__eo_typeof_eq (Eo.__eo_typeof left) (Eo.__eo_typeof right)) = _
      rw [resolveQuerySymbol_sort leftOk, resolveQuerySymbol_sort rightOk]
      cases factorSort <;> rfl
    change [Eo.__eo_typeof (apply1 .not (apply2 .eq left right)), Eo.__eo_typeof observed] = _
    rw [factorType, renderQueryTerm_sort bindings observation observedOk]
    rfl

private def exampleSymbols : List (String × Eo.Term) :=
  [("flag", .UConst 0 .Bool), ("input", .UConst 1 (.UOp .Int))]

#guard
  match renderQueryTerm exampleSymbols (.and [
    .eqInt (.neg (.intSymbol "input")) (.intLit (-2)),
    .iteBool (.boolSymbol "flag") (.boolLit true) (.boolLit false)]) with
  | .ok rendered => Eo.__eo_typeof rendered == .Bool
  | .error _ => false

#guard !(renderQueryTerm exampleSymbols (.intSymbol "flag")).isOk
#guard !(renderQueryTerm (exampleSymbols ++ exampleSymbols) (.intSymbol "input")).isOk

#print axioms renderQueryTerm_sort
#print axioms renderRelationalAssumptions_sorts

end LLMLang.LogosBinding
