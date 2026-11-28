# 0010 — Balance Transfer

- **Task ID** — `0010`
- **Difficulty** — Intermediate
- **Status** — Proposed
- **Prerequisites** — Command-line arguments and checked integer arithmetic
- **Related tasks** — [0002 — Echo](0002-echo.md) · [0003 — Integer calculator](0003-calculator.md)

## 1. Purpose

Exercise atomic state changes and a contract that relates two account
balances to a transaction journal. The example takes its invariants from
[RT-20](../research/toolchain-and-collaboration/RT-20/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md#7-illustrative-example)
and its first test case from the
[RT-01 transfer scenario](../research/language-design/RT-01/LLMLang-CONCEPT.md#102-scenario-tests).

## 2. Problem Statement

Transfer a requested amount from one account to another. When the transfer
commits, publish both new balances and exactly one journal entry for the
amount. If funds are insufficient or the destination balance would overflow,
keep both original balances and the empty journal.

## 3. Behavior and Interface

### Inputs

Accept exactly three command-line arguments in order: source balance,
destination balance, and transfer amount. Each argument consists of one or
more ASCII decimal digits and denotes an integer in `0..=18446744073709551615`.
Leading zeroes are allowed. The amount must be positive. The two accounts
are distinct by construction. Each invocation starts with an empty journal.

### Outputs

For valid inputs, write one line to standard output with the outcome,
source balance, destination balance, and journal entry count. Separate
fields by one space and end with LF. Print numbers in decimal without
leading zeroes. Standard error is empty.

- `committed SOURCE DESTINATION 1` and exit status `0`.
- `insufficient funds SOURCE DESTINATION 0` and exit status `1`.
- `balance overflow SOURCE DESTINATION 0` and exit status `1`.

### Errors and Edge Cases

Write `invalid input\n` to standard error and exit with status `2` for
malformed inputs, out-of-range inputs, or zero amount. Standard output is
empty. If the source has insufficient funds and a destination overflow
would also occur, report insufficient funds. A failed report write returns
status `2`.

## 4. Requirements

- **R-0010-01**. Validate the three arguments and reject invalid input
  before considering a transfer.
- **R-0010-02**. A successful transfer debits and credits exactly the
  requested amount and adds one journal entry with that debit and credit.
- **R-0010-03**. Before commit, reconcile each candidate balance with its
  initial value and the corresponding journal delta. Balances remain
  nonnegative and the mathematical sum of both balances is conserved.
- **R-0010-04**. A refusal leaves both original balances and the journal
  unchanged. Evaluate insufficient funds before destination overflow.
- **R-0010-05**. Report the final state and exit status using the specified
  interface. Handle report write failure.

## 5. Constraints and Non-Goals

### Constraints

The two balances use a fixed unsigned 64-bit range. Conservation is stated
over mathematical integers, including when the combined balance exceeds
that range. A transfer has one commit boundary for both balances and its
journal entry.

### Non-Goals

The exercise is a single in-memory transaction. Durable storage,
concurrent callers, commissions, and external payment systems are outside
its scope.

## 6. Acceptance Criteria

- [ ] The transfer from `100 50` by `30` commits exactly one journal entry
  and reports `70 80`. This covers R-0010-02, R-0010-03, and R-0010-05.
- [ ] Every refusal reports the original balances with an empty journal.
  This covers R-0010-04 and R-0010-05.
- [ ] Invalid input and report write failures use status `2`. This covers
  R-0010-01 and R-0010-05.

## 7. Test Scenarios

The lines shown in the table end with LF. `MAX` stands for
`18446744073709551615`.

| Test ID | Scenario | Arguments or action | Expected result | Requirements |
| --- | --- | --- | --- | --- |
| T-0010-01 | Normal transfer | `100 50 30` | Status 0, stdout `committed 70 80 1` | R-0010-02, R-0010-03, R-0010-05 |
| T-0010-02 | Spend the full balance | `30 50 30` | Status 0, stdout `committed 0 80 1` | R-0010-02, R-0010-03, R-0010-05 |
| T-0010-03 | Insufficient funds | `20 50 30` | Status 1, stdout `insufficient funds 20 50 0` | R-0010-04, R-0010-05 |
| T-0010-04 | Destination overflow | `100 MAX 1` | Status 1, stdout `balance overflow 100 MAX 0` | R-0010-04, R-0010-05 |
| T-0010-05 | Both refusal conditions | `0 MAX 1` | Status 1, stdout `insufficient funds 0 MAX 0` | R-0010-04, R-0010-05 |
| T-0010-06 | Sum exceeds the balance type | `MAX 1 1` | Status 0, stdout `committed 18446744073709551614 2 1` | R-0010-02, R-0010-03 |
| T-0010-07 | Zero amount | `100 50 0` | Status 2, stderr `invalid input` | R-0010-01 |
| T-0010-08 | Malformed or out-of-range value | `-1 50 1` or `100 18446744073709551616 1` | Status 2, stderr `invalid input` | R-0010-01 |
| T-0010-09 | Missing or extra argument | `100 50` or `100 50 30 1` | Status 2, stderr `invalid input` | R-0010-01 |
| T-0010-10 | Report cannot be written | `100 50 30` with a failing stdout | Status 2 | R-0010-05 |

## 8. Concepts Exercised

Checked arithmetic, state invariants, journal reconciliation, commit
visibility, and rollback on a rejected transfer.

## 9. Completion Definition

Supply a runnable candidate in `draft/examples/0010-balance-transfer/`, with
build instructions and evidence for the scenarios. State the scope of
any verification evidence.

## 10. Implementation Notes

A transaction can prepare candidate balances and a journal entry privately.
Publish the complete candidate after reconciliation.
