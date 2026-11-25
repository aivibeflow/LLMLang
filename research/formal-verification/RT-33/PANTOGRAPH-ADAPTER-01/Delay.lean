import Lean

open Lean Elab Tactic

private def fixturePause : TacticM Unit := do
  for _ in [0:1000] do
    liftM (m := CoreM) Core.checkInterrupted
    IO.sleep 2

elab "fixture_pause" : tactic => fixturePause

elab "fixture_announced_pause" : tactic => do
  IO.FS.writeFile "pending.signal" "pending\n"
  fixturePause
