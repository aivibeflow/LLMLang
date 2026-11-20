import Lake
open Lake DSL

package llmlangLogosBinding

require Cpc from git
  "https://github.com/cvc5/logos" @ "cf18742973861b3718d04c5f25775448098ff474"

lean_lib LLMLangLogosBinding where
  roots := #[`LLMLangLogosBinding, `SourceQuerySemantics, `SourceSyntax, `RelationalSourceQuerySemantics,
    `LogosQueryAdapter, `CheckedSourceSemantics, `SourceCoreTests, `SourceCommandSemantics,
    `SourceCommandTests, `SymbolicCommandSemantics, `SymbolicCommandTests,
    `ProgramObservationSemantics, `ProgramObservationTests]

lean_exe testParserBinding where
  root := `Main
