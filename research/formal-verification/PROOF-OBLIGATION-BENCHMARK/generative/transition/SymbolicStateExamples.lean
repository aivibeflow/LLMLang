import SymbolicState

namespace TransitionState.Symbolic.Examples

def absoluteValueIntoSecond : Program :=
  .branch (.le (.register 0) (.literal 0))
    (.assign 1 (.sub (.literal 0) (.register 0)) .done)
    (.assign 1 (.register 0) .done) .done

def restoreSecond : Program := .assign 1 (.literal 0) .done

def exampleTrace : List Program := [absoluteValueIntoSecond, restoreSecond]

example (x y : Int) :
    (compileTrace (initialSymbols 2) exampleTrace).map (evaluate [x, y]) =
      [[x, if x ≤ 0 then 0 - x else x], [x, 0]] := by
  rw [show 2 = ([x, y] : Registers).length from rfl, correspondence]
  simp [exampleTrace, absoluteValueIntoSecond, restoreSecond, observe, run, evalInt, evalBool]
  split <;> simp [List.set]

def lastOnly (states : List Registers) : Option Registers := states.getLast?

example :
    lastOnly ((compileTrace (initialSymbols 2) exampleTrace).map (evaluate [-3, 17])) =
      some [-3, 0] := rfl

example :
    (compileTrace (initialSymbols 2) exampleTrace).map (evaluate [-3, 17]) ≠
      [[-3, 0], [-3, 0]] := by decide

end TransitionState.Symbolic.Examples
