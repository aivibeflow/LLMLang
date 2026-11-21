import LogosQueryAdapter

namespace LLMLang.QuerySymbolRenaming

open LLMLang.SourceQuerySemantics (Env Value asBool)
open LLMLang.LogosBinding (QuerySort QueryTerm)
open LLMLang.LogosQueryAdapter (evalLogosQuery evalLogosQueryList)

mutual
  /-- Rename symbol occurrences, retaining the sort index and term structure. -/
  def rename (f : String → String) : {s : QuerySort} → QueryTerm s → QueryTerm s
    | _, .intLit value => .intLit value
    | _, .boolLit value => .boolLit value
    | _, .intSymbol name => .intSymbol (f name)
    | _, .boolSymbol name => .boolSymbol (f name)
    | _, .neg value => .neg (rename f value)
    | _, .not value => .not (rename f value)
    | _, .add a b => .add (rename f a) (rename f b)
    | _, .sub a b => .sub (rename f a) (rename f b)
    | _, .mul a b => .mul (rename f a) (rename f b)
    | _, .eqInt a b => .eqInt (rename f a) (rename f b)
    | _, .eqBool a b => .eqBool (rename f a) (rename f b)
    | _, .lt a b => .lt (rename f a) (rename f b)
    | _, .le a b => .le (rename f a) (rename f b)
    | _, .and values => .and (renameList f values)
    | _, .or values => .or (renameList f values)
    | _, .iteInt test yes no => .iteInt (rename f test) (rename f yes) (rename f no)
    | _, .iteBool test yes no => .iteBool (rename f test) (rename f yes) (rename f no)

  def renameList (f : String → String) : List (QueryTerm .bool) → List (QueryTerm .bool)
    | [] => []
    | term :: rest => rename f term :: renameList f rest
end

/-- Interpret an original name through the related environment on renamed names. -/
def pullback (f : String → String) (env : Env) : Env :=
  fun name sort => env (f name) sort

mutual
  theorem eval_rename (f : String → String) (env : Env) :
      {s : QuerySort} → (term : QueryTerm s) →
        evalLogosQuery (rename f term) env = evalLogosQuery term (pullback f env)
    | _, .intLit _ => rfl
    | _, .boolLit _ => rfl
    | _, .intSymbol _ => rfl
    | _, .boolSymbol _ => rfl
    | _, .neg a => by
        simp only [rename, evalLogosQuery, eval_rename f env a]
    | _, .not a => by
        simp only [rename, evalLogosQuery, eval_rename f env a]
    | _, .add a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .sub a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .mul a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .eqInt a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .eqBool a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .lt a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .le a b => by
        simp only [rename, evalLogosQuery, eval_rename f env a, eval_rename f env b]
    | _, .iteInt test yes no => by
        simp only [rename, evalLogosQuery, eval_rename f env test, eval_rename f env yes, eval_rename f env no]
    | _, .iteBool test yes no => by
        simp only [rename, evalLogosQuery, eval_rename f env test, eval_rename f env yes, eval_rename f env no]
    | _, .and terms => by
        simp only [rename, evalLogosQuery, eval_renameList f env terms]
    | _, .or terms => by
        simp only [rename, evalLogosQuery, eval_renameList f env terms]

  theorem eval_renameList (f : String → String) (env : Env) :
      (terms : List (QueryTerm .bool)) →
        evalLogosQueryList (renameList f terms) env =
        evalLogosQueryList terms (pullback f env)
    | [] => rfl
    | term :: rest => by
        simp only [renameList, evalLogosQueryList, eval_rename f env term, eval_renameList f env rest]
end

end LLMLang.QuerySymbolRenaming
