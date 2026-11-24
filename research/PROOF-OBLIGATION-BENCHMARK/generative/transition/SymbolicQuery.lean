import SymbolicState
import Lean

namespace TransitionState.Symbolic.Query

private def truth (value : Bool) : Predicate :=
  .eq (.literal 0) (.literal (if value then 0 else 1))

def equalRow : Symbols → Symbols → Predicate
  | [], [] => truth true
  | a :: left, b :: right => .and (.eq a b) (equalRow left right)
  | _, _ => truth false

def equalRows : List Symbols → List Symbols → Predicate
  | [], [] => truth true
  | a :: left, b :: right => .and (equalRow a b) (equalRows left right)
  | _, _ => truth false

theorem equalRow_eval (input : Registers) (left right : Symbols) :
    evalPredicate input (equalRow left right) = (evaluate input left == evaluate input right) := by
  induction left generalizing right with
  | nil => cases right <;> rfl
  | cons head tail ih =>
      cases right with
      | nil => rfl
      | cons other rest =>
          simp [equalRow, evalPredicate, ih rest, evaluate]

theorem equalRows_eval (input : Registers) (left right : List Symbols) :
    evalPredicate input (equalRows left right) =
      (left.map (evaluate input) == right.map (evaluate input)) := by
  induction left generalizing right with
  | nil => cases right <;> rfl
  | cons head tail ih =>
      cases right with
      | nil => rfl
      | cons other rest =>
          simp [equalRows, evalPredicate, equalRow_eval, ih rest]

inductive ObservationScope where
  | allBoundaries
  | finalOnly

def ObservationScope.select {α : Type} (scope : ObservationScope) (values : List α) : List α :=
  match scope with
  | .allBoundaries => values
  | .finalOnly => values.reverse.take 1

theorem ObservationScope.map_select {α β : Type} (scope : ObservationScope)
    (values : List α) (f : α → β) :
    (scope.select values).map f = scope.select (values.map f) := by
  cases scope <;> simp [ObservationScope.select, List.map_take, List.map_reverse]

/-- Ask whether any register observation differs from the corresponding specified term. -/
def mismatch (scope : ObservationScope) (registerCount : Nat) (trace : List Program)
    (specified : List Symbols) : Predicate :=
  .not (equalRows (scope.select (compileTrace (initialSymbols registerCount) trace))
    (scope.select specified))

theorem mismatch_correct (scope : ObservationScope) (input : Registers)
    (trace : List Program) (specified : List Symbols) :
    evalPredicate input (mismatch scope input.length trace specified) =
      !(scope.select (observe input trace) == scope.select (specified.map (evaluate input))) := by
  simp only [mismatch, evalPredicate, equalRows_eval, ObservationScope.map_select, correspondence]

private def symbol (index : Nat) : String := "v" ++ toString index

private def smtInteger (value : Int) : String :=
  if value < 0 then s!"(- {value.natAbs})" else toString value

mutual
  private def renderTerm : Term → String
    | .literal value => smtInteger value
    | .input index => symbol index
    | .add a b => s!"(+ {renderTerm a} {renderTerm b})"
    | .sub a b => s!"(- {renderTerm a} {renderTerm b})"
    | .choose g a b => s!"(ite {renderPredicate g} {renderTerm a} {renderTerm b})"

  private def renderPredicate : Predicate → String
    | .eq a b => s!"(= {renderTerm a} {renderTerm b})"
    | .le a b => s!"(<= {renderTerm a} {renderTerm b})"
    | .and a b => s!"(and {renderPredicate a} {renderPredicate b})"
    | .or a b => s!"(or {renderPredicate a} {renderPredicate b})"
    | .not a => s!"(not {renderPredicate a})"
end

private def absoluteValueIntoSecond : Program :=
  .branch (.le (.register 0) (.literal 0))
    (.assign 1 (.sub (.literal 0) (.register 0)) .done)
    (.assign 1 (.register 0) .done) .done

private def trace : List Program := [absoluteValueIntoSecond, .assign 1 (.literal 0) .done]

private structure Fixture where
  scope : ObservationScope
  specified : List Symbols

private def fixture : String → Option Fixture
  | "absolute" =>
      let x := Term.input 0
      let absolute := Term.choose (.le (.literal 0) x) x (.sub (.literal 0) x)
      some ⟨.allBoundaries, [[x, absolute], [x, .literal 0]]⟩
  | "zero-all" => some ⟨.allBoundaries, [[.input 0, .literal 0], [.input 0, .literal 0]]⟩
  | "zero-final" => some ⟨.finalOnly, [[.input 0, .literal 0], [.input 0, .literal 0]]⟩
  | _ => none

private def queryText (test : Fixture) (model : Bool) : String :=
  let commands := ["(set-logic QF_LIA)"] ++
    (if model then ["(set-option :produce-models true)"] else []) ++
    ["(declare-const v0 Int)", "(declare-const v1 Int)",
      s!"(assert {renderPredicate (mismatch test.scope 2 trace test.specified)})", "(check-sat)"] ++
    (if model then ["(get-value (v0 v1))"] else []) ++ ["(exit)", ""]
  String.intercalate "\n" commands

private def replay (test : Fixture) (x y : Int) : Lean.Json :=
  let input := [x, y]
  let actual := test.scope.select (observe input trace)
  let expected := test.scope.select (test.specified.map (evaluate input))
  Lean.Json.mkObj [
    ("input", Lean.toJson input), ("observed", Lean.toJson actual),
    ("specified", Lean.toJson expected), ("mismatch", Lean.toJson (!(actual == expected)))]


def run : List String → IO Unit
  | [mode, name] => do
      unless mode == "query" || mode == "model" do
        throw (IO.userError "expected query or model mode")
      let some test := fixture name | throw (IO.userError "unknown fixture")
      IO.print (queryText test (mode == "model"))
  | ["replay", name, x, y] => do
      let some test := fixture name | throw (IO.userError "unknown fixture")
      let some (a, b) := (·, ·) <$> x.toInt? <*> y.toInt? | throw (IO.userError "invalid Int value")
      IO.println (replay test a b).compress
  | _ => throw (IO.userError "expected a query, model or replay request")

end TransitionState.Symbolic.Query

def main := TransitionState.Symbolic.Query.run
