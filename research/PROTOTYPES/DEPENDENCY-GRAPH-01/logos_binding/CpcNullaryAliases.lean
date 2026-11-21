import LLMLangLogosBinding

namespace LLMLang.CpcNullaryAliases

open LLMLang.LogosBinding

private structure Names where
  declarations : List String := []
  aliases : List String := []

/-- Classify actual top-level declarations separately from proof-local aliases. -/
private def classify (names : Names) (command : Logos.Sexp) : Except String Names :=
  match command with
  | .expr [.atom "declare-const", .atom name, .atom sort] =>
      if sort == "Int" || sort == "Bool" then
        pure { names with declarations := name :: names.declarations }
      else throw "only Int and Bool declarations are admitted"
  | .expr [.atom "define", .atom name, .expr [], _] =>
      pure { names with aliases := name :: names.aliases }
  | .expr (.atom name :: _) =>
      if ["assume", "assume-push", "step", "step-pop"].contains name then pure names
      else throw s!"unsupported command in closed CPC alias profile: {name}"
  | _ => throw "unexpected top-level CPC term"

/-- Admit disjoint nullary aliases without confusing an alias with a declaration. -/
def parseAndBind (proof : String) (expected : List ExpectedDeclaration) :
    Except String (List Eo.Term × Eo.CCmdList × List (String × Eo.Term)) := do
  let commands ← Logos.Sexp.Parser.manySexps!.run proof
  let names ← commands.foldlM classify {}
  let required := expected.map ExpectedDeclaration.name
  let seen := names.declarations ++ names.aliases
  if seen.eraseDups.length != seen.length then
    throw "repeated or shadowed CPC name"
  if required.eraseDups.length != required.length ||
     names.declarations.length != required.length ||
     required.any (fun name => !names.declarations.contains name) then
    throw "raw CPC constant declarations differ from the expected set"
  let (assumptions, steps, state) ← parseProofWithState proof
  if state.ufCount != required.length || seen.length != state.terms.toList.length ||
     seen.any (fun name => (state.terms.getD name []).length != 1) then
    throw "CPC parser state disagrees with the classified top-level names"
  let bindings ← expected.mapM fun declaration => do
    let term ← lookupDeclaration state declaration
    pure (declaration.name, term)
  pure (assumptions, steps, bindings)

end LLMLang.CpcNullaryAliases
