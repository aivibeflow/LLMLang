import Lake
open Lake DSL

package llmlangLogosBinding where
  -- Treat warnings in this package as compilation errors.
  -- Dependency packages (including Logos) retain their own warning policy.
  leanOptions := #[⟨`warningAsError, true⟩]

require Cpc from git
  "https://github.com/cvc5/logos" @ "cf18742973861b3718d04c5f25775448098ff474"

lean_lib LLMLangLogosBinding where
  roots := #[`LLMLangLogosBinding, `SourceQuerySemantics, `SourceSyntax, `RelationalSourceQuerySemantics, `QuerySymbolRenaming,
    `LogosQueryAdapter, `LogosRenderedSorts, `SourceWireRefutation, `CheckedSourceSemantics, `SourceCoreTests, `SourceCommandSemantics,
    `SourceCommandTests, `LogosVerdictConditions, `SymbolicCommandSemantics, `SymbolicCommandTests,
    `CpcNullaryAliases, `SymbolicCpcCertificate, `SourceCpcRefutation, `ProgramObservationSemantics, `ProgramObservationTests,
    `PairedObservationSemantics, `PairedObservationTests, `CanonicalQuerySymbols,
    `ProgramRelationalQuery, `QfLiaQuery, `QfLiaAdmissibility, `SolverRelationalQuery,
    `ProgramRelationalQueryTests, `TypedQueryEquality, `SourceQueryEnvelope]

lean_exe testParserBinding where
  root := `Main
