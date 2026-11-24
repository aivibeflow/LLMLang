import QfLiaQuery

namespace LLMLang.LogosBinding

private def atomEq [DecidableEq α] (left right : α) : Option (PLift (left = right)) :=
  if h : left = right then some ⟨h⟩ else none

private def ctor1 (make : α → β) {a b : α}
    (one : Option (PLift (a = b))) : Option (PLift (make a = make b)) :=
  one.map fun h => ⟨congrArg make h.down⟩

private def ctor2 (make : α → β → γ) {a b : α} {c d : β}
    (one : Option (PLift (a = b))) (two : Option (PLift (c = d))) :
    Option (PLift (make a c = make b d)) := do
  let h ← one
  let g ← two
  pure ⟨by rw [h.down, g.down]⟩

private def ctor3 (make : α → β → γ → δ) {a b : α} {c d : β} {e f : γ}
    (one : Option (PLift (a = b))) (two : Option (PLift (c = d)))
    (three : Option (PLift (e = f))) : Option (PLift (make a c e = make b d f)) := do
  let h ← one
  let g ← two
  let k ← three
  pure ⟨by rw [h.down, g.down, k.down]⟩

mutual
  /-- A successful structural comparison carries equality of typed terms. -/
  def QueryTerm.exactEq : {sort : QuerySort} → (left right : QueryTerm sort) →
      Option (PLift (left = right))
    | _, .intLit a, .intLit b => ctor1 QueryTerm.intLit (atomEq a b)
    | _, .boolLit a, .boolLit b => ctor1 QueryTerm.boolLit (atomEq a b)
    | _, .intSymbol a, .intSymbol b => ctor1 QueryTerm.intSymbol (atomEq a b)
    | _, .boolSymbol a, .boolSymbol b => ctor1 QueryTerm.boolSymbol (atomEq a b)
    | _, .not a, .not b => ctor1 QueryTerm.not (a.exactEq b)
    | _, .neg a, .neg b => ctor1 QueryTerm.neg (a.exactEq b)
    | _, .add a c, .add b d => ctor2 QueryTerm.add (a.exactEq b) (c.exactEq d)
    | _, .sub a c, .sub b d => ctor2 QueryTerm.sub (a.exactEq b) (c.exactEq d)
    | _, .mul a c, .mul b d => ctor2 QueryTerm.mul (a.exactEq b) (c.exactEq d)
    | _, .eqInt a c, .eqInt b d => ctor2 QueryTerm.eqInt (a.exactEq b) (c.exactEq d)
    | _, .eqBool a c, .eqBool b d => ctor2 QueryTerm.eqBool (a.exactEq b) (c.exactEq d)
    | _, .lt a c, .lt b d => ctor2 QueryTerm.lt (a.exactEq b) (c.exactEq d)
    | _, .le a c, .le b d => ctor2 QueryTerm.le (a.exactEq b) (c.exactEq d)
    | _, .and a, .and b => ctor1 QueryTerm.and (QueryTerm.exactEqList a b)
    | _, .or a, .or b => ctor1 QueryTerm.or (QueryTerm.exactEqList a b)
    | _, .iteInt g a c, .iteInt h b d =>
        ctor3 QueryTerm.iteInt (g.exactEq h) (a.exactEq b) (c.exactEq d)
    | _, .iteBool g a c, .iteBool h b d =>
        ctor3 QueryTerm.iteBool (g.exactEq h) (a.exactEq b) (c.exactEq d)
    | _, _, _ => none
  termination_by structural _ left _ => left

  private def QueryTerm.exactEqList : (left right : List (QueryTerm .bool)) →
      Option (PLift (left = right))
    | [], [] => some ⟨rfl⟩
    | a :: rest, b :: tail => ctor2 List.cons (a.exactEq b) (QueryTerm.exactEqList rest tail)
    | _, _ => none
  termination_by structural left _ => left
end

end LLMLang.LogosBinding
