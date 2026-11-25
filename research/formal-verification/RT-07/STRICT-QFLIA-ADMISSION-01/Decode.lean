import LLMLangLogosBinding

open Lean LLMLang.LogosBinding

def main (arguments : List String) : IO UInt32 := do
  let [path] := arguments | throw (IO.userError "expected one JSON-lines file")
  for line in (← IO.FS.readFile path).splitOn "\n" do
    unless line.isEmpty do
      let row ← IO.ofExcept (Json.parse line)
      let label ← IO.ofExcept (row.getObjValAs? String "label")
      let wire ← IO.ofExcept (row.getObjValAs? String "wire")
      let observed := match decodeCanonicalRelationalQuery wire with
        | .ok _ => [("label", toJson label), ("accepted", toJson true)]
        | .error reason => [("label", toJson label), ("accepted", toJson false), ("reason", toJson reason)]
      IO.println (Json.mkObj observed).compress
  return 0
