# Scalar Contract IR

The `scalar-v1` profile covers pure, typed LLMLang functions and acyclic direct calls. It implements the scalar work in [PLAN §1.3](../../PLAN.md#13-contracts-and-compatible-implementations). The [verification coverage matrix](../../research/formal-verification/VERIFICATION-COVERAGE.ru.md) describes the broader roadmap. The schema, evaluator and rendering in this document apply to the scalar CLI milestone.

## Meaning and observations

| Item | Meaning in `scalar-v1` |
| --- | --- |
| Callable signature | Ordered, uniquely named parameters and a result in `Bool` or signed `I64`. An `I64` value ranges from −2⁶³ to 2⁶³−1 inclusive. |
| Input domain | The conjunction of `requires`, with access to parameters. An empty conjunction is true. The caller must provide an input in the public domain. |
| Success | An in-range value of the result type satisfying the conjunction of `ensures`. These clauses see parameters and the reserved binder `result`. |
| Error | A declared error label whose `errors` clauses are all true. Those clauses see parameters. A label with an empty clause list is admitted on every input in the domain. |
| Observations | The input tuple and one outcome, consisting of either a value or an error label. The Contract IR has no mutable state, effect trace, foreign or temporal environment in this profile. |
| Termination | The admitted SPG has no loops or cyclic calls. All paths end in a return or failure, and expressions evaluate finitely. |
| Numeric model | Predicates lift `I64` inputs and results into mathematical `Int`. Addition, subtraction, multiplication and negation are unbounded. `quotient(a,b)` truncates toward zero, with value zero when `b` is zero. |
| Machine arithmetic | Executable arithmetic uses checked signed `I64` operations. Division by zero yields `DivisionByZero`. An out-of-range arithmetic result yields `ArithmeticOverflow`. Operands and arguments are evaluated left to right. |

An error predicate admits that outcome when true. It can be true at the same input as another outcome's predicate. Verification checks the observed runtime outcome against the allowed set. The reference denotation is executable through `holds` and `admits_outcome` in [the scalar implementation](contract.py).

## Versioned exchange

The JSON document has exactly three top-level members. `schema` is `llmlang-contract-ir/v1`, `profile` is `scalar-v1`, and `contracts` maps implementation names to `public` and `provided` contract pairs. Each contract uses the members in this table.

| Member | JSON representation |
| --- | --- |
| `parameters` | Ordered array of `[name,type]` pairs. Names are ASCII identifiers. `result` and `quotient` are reserved binder names. |
| `returns` | The scalar boundary type `I64` or `Bool`. |
| `requires`, `ensures` | Ordered arrays of typed `Bool` expressions. |
| `errors` | An object mapping named error outcomes to ordered arrays of typed `Bool` expressions. |

Each predicate node has an `op` and an explicit result `type` of `Bool` or `Int`. The reader checks that every node's type, arguments and binder scope agree with the grammar below. Equality is available on values of the same type.

| Operator | Extra member | Inputs | Result |
| --- | --- | --- | --- |
| `literal` | `value` | JSON boolean or a nonnegative decimal string for an integer, with no leading zeros except `0` | `Bool` or `Int` |
| `ref` | `name` | An in-scope binder | The binder's predicate type |
| `not`, `negate` | `args` | One `Bool` or one `Int` respectively | Same as operand |
| `add`, `subtract`, `multiply`, `quotient` | `args` | Two `Int` operands | `Int` |
| `equal`, `not-equal` | `args` | Two operands of the same type | `Bool` |
| `less-than`, `less-or-equal`, `greater-than`, `greater-or-equal` | `args` | Two `Int` operands | `Bool` |
| `and`, `or` | `args` | Two or more `Bool` operands | `Bool` |

This tree encodes the success clause `result == left + right`.

```json
{
  "op": "equal",
  "type": "Bool",
  "args": [
    {"op": "ref", "type": "Int", "name": "result"},
    {"op": "add", "type": "Int", "args": [
      {"op": "ref", "type": "Int", "name": "left"},
      {"op": "ref", "type": "Int", "name": "right"}
    ]}
  ]
}
```

See the [complete typed Calculator fixture](calculator.contracts.json) and its [legacy source](calculator.contracts.legacy.json). The reader rejects duplicate JSON keys, unknown members, unsupported schema or profile identifiers, mismatched expression types, unknown binders, and invalid operator arity. For a legacy document, each contract may specify `profile: scalar-v1`, with scalar-v1 also the default when omitted. Legacy expressions have Python-style syntax and are checked against the same operator and scope rules. Typed documents encode integers as strings to avoid rounding through a JSON number type.

## Normalization, versions and identities

Legacy comparison chains elaborate to conjunctions of adjacent comparisons. Both readers flatten nested instances of the same Boolean connective, preserve operand, parameter and clause order, and canonicalize error label order. They preserve declaration and error role even when a clause array is empty. Canonical JSON output sorts object keys and uses compact separators and a final newline.

`ContractHash` computes SHA-256 over the domain prefix `LLMLang Contract IR` with a terminal NUL, followed by the compact, sorted-key JSON encoding of the semantic profile, ordered parameters, return type and normalized clause roles. The hash uses canonical parenthesized predicate expressions. This preserves the baseline scalar identity across legacy syntax, typed exchange and checked CNL. Source spelling, artifact paths, review metadata and the interchange envelope are outside that hash. A changed predicate or binder order is material even if a proof could show the resulting contract equivalent.

The implementation identity includes the provided `ContractHash`, the typed body and the selected callees' implementation hashes. A binding record keeps public, provided and required references distinct. The approval packet also pins exact input bytes. Migrating a legacy input to the typed wire format retains semantic hashes and requires fresh approval of that input revision. Future wire or semantic versions require an explicit support and migration decision.

## Controlled natural language

The header names the semantic profile and declares its numeric model. Ordered signature lines declare each parameter and the result. Every clause has an ordinal identifier scoped by its role. Identifiers use `requirement-N`, `guarantee-N`, or `error-NAME-N`, where `N` starts at 1 in each scope. An error always has its own declaration even when no error clause follows.

```text
The parameter PARAMETER has type TYPE.
The success result has type TYPE.
Clause requirement-N. The caller must ensure that EXPRESSION.
Clause guarantee-N. On success, guarantee that EXPRESSION.
The error NAME is declared.
Clause error-NAME-N. On error NAME, guarantee that EXPRESSION.
```

An `EXPRESSION` is `true`, `false`, a nonnegative integer, `the value NAME`, a unary form or a binary form. Unary forms are `it is false that (EXPRESSION)` and `the negation of (EXPRESSION)`. The binary forms below use explicit parentheses for both operands. There are no implicit precedence rules or quantifiers. The negative integer −1, for example, is `the negation of (1)`.

| Form | Operator |
| --- | --- |
| `the sum of (A) and (B)` | Addition |
| `the difference between (A) and (B)` | Subtraction |
| `the product of (A) and (B)` | Multiplication |
| `the truncating quotient of (A) by (B)` | Quotient |
| `it is true that (A) equals (B)` | Equality |
| `it is true that (A) differs from (B)` | Inequality |
| `it is true that (A) is less than (B)` | Strict less-than |
| `it is true that (A) is at most (B)` | Inclusive less-than |
| `it is true that (A) is greater than (B)` | Strict greater-than |
| `it is true that (A) is at least (B)` | Inclusive greater-than |
| `both (A) and (B)` | Conjunction |
| `either (A) or (B)` | Inclusive disjunction |

The renderer encodes each operator with a phrase and each subtree with parentheses, so the parser can unambiguously recover the operator and its operands. N-ary Boolean nodes render as left-associated binary trees. Re-elaboration flattens them to the same normalized operand sequence. The parser checks the reconstructed clause types and roles, and review output requires structural equivalence after normalization. This checks the relation between Contract IR and review text. Scenarios and human approval check the relation to the requirements.

## Executable checks

- `python -B -m unittest tools.llmlang_mvp.test_contract_wire` checks exchange, migration, exact semantic identities, big integers, binder and type restrictions, and CNL round trips.
- `python -B -m tools.llmlang_mvp.controls` exercises exact bindings, review and the separated provider conformance and refinement checks.
- `lean tools/llmlang_mvp/ScalarChecks.lean` checks the shared addition claims in the designated Lean model.

The CLI checks body conformance and public refinement using [Boogie and Z3](verify.py). Conformance checks that every admitted input produces an outcome allowed by the provided contract. Refinement checks that the provided domain contains the public domain and that, on public inputs, each provided outcome is allowed publicly. The scalar runtime and contract evaluator provide separate observations for replay. The [MVP README](README.md) describes tooling and proof scope.
