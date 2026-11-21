import SourceCpcRefutation

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.SourceCpcRefutation

private def factor : Declaration := ⟨⟨1⟩, "factor", .input, .int⟩
private def scope : SourceScope := ⟨⟨[factor]⟩, [factor.id], [factor.id]⟩
private def observesReturn : ObservationContract := ⟨[]⟩
private def constant : Program .int := ⟨.skip, .intLit 7⟩
private def dependent : Program .int := ⟨.skip, .intVar "factor"⟩

private def header := "(declare-const i_4 Int)\n(declare-const i_5 Int)\n"
private def first := "(assume @p1 (not (= i_4 i_5)))\n"
private def second := "(assume @p2 (or (not (= (ite true 7 0) (ite true 7 0))) false))\n"

-- cvc5 1.4.2, CPC dsl-rewrite proof with the outer printer envelope omitted.
private def aliasedProof := header ++ "(define @t1 () (ite true 7 0))\n" ++
  "(define @t2 () (= @t1 @t1))\n(define @t3 () (not @t2))\n" ++
  "(define @t4 () (or @t3 false))\n" ++ first ++ "(assume @p2 @t4)\n" ++
  "(step @p3 :rule evaluate :args ((not true)))\n" ++
  "(step @p4 :rule evaluate :args (@t2))\n" ++
  "(step @p5 :rule cong :premises (@p4) :args (@t3))\n" ++
  "(step @p6 :rule trans :premises (@p5 @p3))\n" ++
  "(step @p7 :rule evaluate :args (@t3))\n" ++
  "(step @p8 :rule symm :premises (@p7))\n" ++
  "(step @p9 :rule evaluate :args (@t4))\n" ++
  "(step @p10 :rule trans :premises (@p9 @p8))\n" ++
  "(step @p11 :rule trans :premises (@p10 @p6))\n" ++
  "(step @p12 false :rule eq_resolve :premises (@p2 @p11))\n"

-- The direct source gate uses the existing closed declaration-table policy.
private def correctProof : String :=
  let commands := (aliasedProof.splitOn "\n").filter (fun line => !line.startsWith "(define")
  let body := "\n".intercalate commands
  let body := body.replace "@t4" "(or @t3 false)"
  let body := body.replace "@t3" "(not @t2)"
  let body := body.replace "@t2" "(= @t1 @t1)"
  body.replace "@t1" "(ite true 7 0)"

private def wrongQueryProof := header ++ first ++ "(assume @p2 false)\n" ++
  "(step @p3 (= false false) :rule refl :args (false))\n" ++
  "(step @p4 false :rule eq_resolve :premises (@p2 @p3))\n"

private def requireFailure (label : String) (result : Except String α) : Except String Unit :=
  if result.isOk then .error s!"unexpected success: {label}" else .ok ()

private def controls : Except String Unit := do
  checkSourceRefutation constant observesReturn scope factor.id correctProof
  let aliased ← Eo.logos_check_proof aliasedProof
  if aliased != .correct then
    throw "aliased CPC fixture should be accepted by the standalone checker"
  requireFailure "alias table outside the source gate's admitted declaration shape"
    (checkSourceAssumptions constant observesReturn scope factor.id aliasedProof)
  let oracle ← Eo.logos_check_proof wrongQueryProof
  if oracle != .correct then
    throw "wrong-query control must be a valid refutation of its own assumptions"
  requireFailure "valid proof of the wrong query"
    (checkSourceRefutation constant observesReturn scope factor.id wrongQueryProof)
  requireFailure "valid proof replayed on an input-dependent source"
    (checkSourceRefutation dependent observesReturn scope factor.id correctProof)
  let missingDerivation := header ++ first ++ second
  let _ ← checkSourceAssumptions constant observesReturn scope factor.id missingDerivation
  requireFailure "matching assumptions without a derivation"
    (checkSourceRefutation constant observesReturn scope factor.id missingDerivation)
  requireFailure "reordered assumptions"
    (checkSourceAssumptions constant observesReturn scope factor.id (header ++ second ++ first))
  requireFailure "undeclared factor"
    (checkSourceAssumptions constant observesReturn scope ⟨2⟩ correctProof)

def main : IO Unit :=
  match controls with
  | .ok () => IO.println "Source-derived CPC refutation controls passed"
  | .error reason => throw (IO.userError reason)
