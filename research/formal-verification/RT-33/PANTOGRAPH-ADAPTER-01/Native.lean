import Repl

open Lean Pantograph Pantograph.Repl

def replayTerm (claim term : String) : EMainM String := do
  let .ok value ← liftTermElabM ((parseElabExpr term (some claim)).run)
    | return "refused"
  let env ← getEnv
  if value.hasSorry || value.hasExprMVar || env.hasUnsafe value then
    return "unchecked"
  let .ok expected ← liftTermElabM ((parseElabType claim).run)
    | return "refused"
  if expected.hasSorry || expected.hasExprMVar || env.hasUnsafe expected then
    return "unchecked"
  let sameType ← liftMetaM do
    Meta.isDefEq (← Meta.inferType value) expected
  if !sameType then
    return "type-mismatch"
  return "elaborated"

unsafe def main : List String → IO Unit
  | [claim, term] => do
    Pantograph.initSearch
    let env ← Lean.importModules #[{ module := `Defs }] {} (trustLevel := 1) (loadExts := true)
    let context ← Pantograph.createCoreContext #[]
    let outcome ← ((replayTerm claim term).run.run { coreContext := context }).run' { env }
    match outcome with
    | .ok result => IO.println result
    | .error error => IO.println s!"error: {error.error}"
  | _ => throw (IO.userError "expected exact claim and proof term")
