import Cpc.SmtModel
import LogosScalarEvaluation

namespace LLMLang.LogosScalarDenotation

open Smtm

def Scalar.embed : Scalar → SmtValue
  | .int value => .Numeral value
  | .bool value => .Boolean value

/-- Constants evaluated by the restricted model agree with the pinned upstream model. -/
def modelAgrees (upstream : SmtModel) (valuation : Valuation) : Prop :=
  ∀ name row, valuation.find? (fun entry => entry.1 == name) = some row →
    native_model_lookup upstream name row.2.sort = row.2.embed

private theorem intUnary {value : Except String Scalar} {op : Int → Scalar}
    {result : Scalar} (computed : (do pure (op (← needInt (← value)))) = .ok result) :
    ∃ n, value = .ok (.int n) ∧ result = op n := by
  cases value with
  | error _ => cases computed
  | ok value =>
      cases value with
      | int n =>
          change Except.ok (op n) = Except.ok result at computed
          exact ⟨n, rfl, (Except.ok.inj computed).symm⟩
      | bool _ => cases computed

private theorem intBinary {left right : Except String Scalar} {op : Int → Int → Scalar}
    {result : Scalar}
    (computed : (do pure (op (← needInt (← left)) (← needInt (← right)))) = .ok result) :
    ∃ a b, left = .ok (.int a) ∧ right = .ok (.int b) ∧ result = op a b := by
  cases left with
  | error _ => cases computed
  | ok l =>
      cases l with
      | bool _ => cases computed
      | int a =>
          cases right with
          | error _ => cases computed
          | ok r =>
              cases r with
              | bool _ => cases computed
              | int b =>
                  change Except.ok (op a b) = Except.ok result at computed
                  exact ⟨a, b, rfl, rfl, (Except.ok.inj computed).symm⟩

private theorem boolUnary {value : Except String Scalar} {op : Bool → Scalar}
    {result : Scalar} (computed : (do pure (op (← needBool (← value)))) = .ok result) :
    ∃ b, value = .ok (.bool b) ∧ result = op b := by
  cases value with
  | error _ => cases computed
  | ok value =>
      cases value with
      | bool b =>
          change Except.ok (op b) = Except.ok result at computed
          exact ⟨b, rfl, (Except.ok.inj computed).symm⟩
      | int _ => cases computed

private theorem boolBinary {left right : Except String Scalar} {op : Bool → Bool → Scalar}
    {result : Scalar}
    (computed : (do
      let l ← needBool (← left)
      let r ← needBool (← right)
      pure (op l r)) = .ok result) :
    ∃ a b, left = .ok (.bool a) ∧ right = .ok (.bool b) ∧ result = op a b := by
  cases left with
  | error _ => cases computed
  | ok l =>
      cases l with
      | int _ => cases computed
      | bool a =>
          cases right with
          | error _ => cases computed
          | ok r =>
              cases r with
              | int _ => cases computed
              | bool b =>
                  change Except.ok (op a b) = Except.ok result at computed
                  exact ⟨a, b, rfl, rfl, (Except.ok.inj computed).symm⟩

private theorem scalarEq (a b : Scalar) : native_veq a.embed b.embed = (a == b) := by
  cases a <;> cases b <;>
    simp [native_veq, Scalar.embed, BEq.beq, instBEqScalar.beq]

theorem evaluation_matches_upstream (upstream : SmtModel)
    (valuation : Valuation) (related : modelAgrees upstream valuation)
    (term : SmtTerm) {result : Scalar} (computed : evalSmt valuation term = .ok result) :
    __smtx_model_eval upstream term = result.embed := by
  cases term <;>
    rw [evalSmt] at computed <;> try contradiction
  case Boolean value =>
    cases computed
    rfl
  case Numeral value =>
    cases computed
    rfl
  case UConst name ty =>
    cases entry : valuation.find? (fun row => row.1 == name) with
    | none =>
        rw [entry] at computed
        cases computed
    | some row =>
        rcases row with ⟨key, value⟩
        rw [entry] at computed
        change (if (value.sort == ty) = true then pure value else throw "wrong SMT constant sort") =
          Except.ok result at computed
        split at computed
        · rename_i valid
          change Except.ok value = Except.ok result at computed
          have exactResult := Except.ok.inj computed
          subst result
          have sort : value.sort = ty := eq_of_beq valid
          subst ty
          exact related name (key, value) entry
        · cases computed
  case uneg term =>
    obtain ⟨n, accepted, rfl⟩ := intUnary (op := fun n => .int (-n)) computed
    change __smtx_model_eval_uneg (__smtx_model_eval upstream term) = _
    rw [evaluation_matches_upstream upstream valuation related term accepted]
    rfl
  case not term =>
    obtain ⟨b, accepted, rfl⟩ := boolUnary (op := fun b => .bool (!b)) computed
    change __smtx_model_eval_not (__smtx_model_eval upstream term) = _
    rw [evaluation_matches_upstream upstream valuation related term accepted]
    rfl
  case plus a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := intBinary (op := fun a b => .int (a + b)) computed
    change __smtx_model_eval_plus (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case neg a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := intBinary (op := fun a b => Scalar.int (a - b)) computed
    change __smtx_model_eval__ (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    simp [Scalar.embed, __smtx_model_eval__, SmtEval.native_zplus,
      SmtEval.native_zneg, Int.sub_eq_add_neg]
  case mult a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := intBinary (op := fun a b => Scalar.int (a * b)) computed
    change __smtx_model_eval_mult (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case lt a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := intBinary (op := fun a b => Scalar.bool (decide (a < b))) computed
    change __smtx_model_eval_lt (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case leq a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := intBinary (op := fun a b => Scalar.bool (decide (a ≤ b))) computed
    change __smtx_model_eval_leq (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case and a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := boolBinary (op := fun a b => .bool (a && b)) computed
    change __smtx_model_eval_and (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case or a b =>
    obtain ⟨left, right, leftOk, rightOk, rfl⟩ := boolBinary (op := fun a b => .bool (a || b)) computed
    change __smtx_model_eval_or (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
    rw [evaluation_matches_upstream upstream valuation related a leftOk,
      evaluation_matches_upstream upstream valuation related b rightOk]
    rfl
  case eq a b =>
    cases leftOk : evalSmt valuation a with
    | error _ =>
        rw [leftOk] at computed
        cases computed
    | ok l =>
        cases rightOk : evalSmt valuation b with
        | error _ =>
            rw [leftOk, rightOk] at computed
            cases computed
        | ok r =>
            rw [leftOk, rightOk] at computed
            change (if (l.sort == r.sort) = true then pure (.bool (l == r)) else throw "mixed equality") =
              Except.ok result at computed
            split at computed
            · cases computed
              change __smtx_model_eval_eq (__smtx_model_eval upstream a) (__smtx_model_eval upstream b) = _
              rw [evaluation_matches_upstream upstream valuation related a leftOk,
                evaluation_matches_upstream upstream valuation related b rightOk]
              cases l <;> cases r <;> simp [Scalar.embed, __smtx_model_eval_eq, ← scalarEq]
            · cases computed
  case ite guard yes no =>
    cases guardOk : evalSmt valuation guard with
    | error _ =>
        rw [guardOk] at computed
        cases computed
    | ok g =>
        cases g with
        | int _ =>
            rw [guardOk] at computed
            cases computed
        | bool chosen =>
            cases leftOk : evalSmt valuation yes with
            | error _ =>
                rw [guardOk, leftOk] at computed
                cases computed
            | ok l =>
                cases rightOk : evalSmt valuation no with
                | error _ =>
                    rw [guardOk, leftOk, rightOk] at computed
                    cases computed
                | ok r =>
                    rw [guardOk, leftOk, rightOk] at computed
                    change (if (l.sort != r.sort) = true then throw "mixed conditional arms"
                      else pure (if chosen then l else r)) = Except.ok result at computed
                    split at computed
                    · cases computed
                    · cases computed
                      change __smtx_model_eval_ite (__smtx_model_eval upstream guard)
                        (__smtx_model_eval upstream yes) (__smtx_model_eval upstream no) = _
                      rw [evaluation_matches_upstream upstream valuation related guard guardOk,
                        evaluation_matches_upstream upstream valuation related yes leftOk,
                        evaluation_matches_upstream upstream valuation related no rightOk]
                      cases chosen <;> rfl

termination_by structural term

#print axioms evaluation_matches_upstream

end LLMLang.LogosScalarDenotation
