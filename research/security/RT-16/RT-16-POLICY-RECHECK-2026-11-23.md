# RT-16: Authorization and verification-evidence policy recheck

**Date:** 2026-11-23  
**Baseline:** `775d5e8d78ed9a47f7f37d09ff13cbc300be7f03` (`main`)  
**Scope:** refresh the bounded authorization-policy test evidence and compare the prototype's decision boundary with the unresolved production trust mechanisms.

## Result

On CPython 3.12.14, the current-main RT-16 suite passed **24/24** tests:

```sh
python3 -B -m unittest discover -s research/security/PROTOTYPES/RT-16-AUTHORIZATION-01 -p 'test_*.py' -v
```

The fixtures demonstrate exact principal/repository/action/base binding, human approval binding to action/repository/base/target, one-time nonce behavior in a single-process ledger, and fail-closed handling of missing, duplicate, failed, unknown, stale-context, or untrusted-verifier evidence. SHA-256 inputs: `policy.py` `9bde40efd58f19ff9fbd79d3bef49bfba4d13e887aff04a283e9ca03cad12b86`; `test_policy.py` `5a4850fe8b867deff1d2c2e7ca38df77a2f359129367720a9c8ee1b53c0770e2`.

## Option boundary

| Mechanism | What current evidence says | Status |
|---|---|---|
| Broad/implicit authorization | Risks confused-deputy, stale-base, and approval-replay cases represented in tests | Rejected as a sufficient policy model |
| Exact-scoped capabilities and approval | Prototype requires exact bindings for modeled privileged actions and separately permits validation | Supported as a policy invariant for this fixture |
| Evidence digest alone | Digest changes when verifier/result fields change, but an unkeyed digest does not authenticate who produced a record | Insufficient for production provenance |
| Trusted-verifier allowlist in policy model | Untrusted verifier records are rejected by the fixture | Necessary modeled input; provisioning/revocation of trust is unspecified |
| In-memory nonce ledger | Single process, finite unit tests only | Not evidence for concurrent or crash-safe replay protection |

The tests support an authorization rule shape, not a credential, signature, sandbox, or production service design. A content hash binds bytes/fields; it does not authenticate an approver or evidence producer. Signed or authenticated evidence must be evaluated separately, and any human approval requirement remains a maintainer policy decision.

## Remaining external and integration dependencies

- Persistent multi-client nonce reservation/consumption with concurrency and crash-injection around side effects.
- Authenticated approver and verifier identity, signed evidence/provenance, key rotation/revocation, and independent trust-root review.
- Sandbox tests for secrets, network, filesystem, process persistence, and resource exhaustion.
- Repository-specific approval policy, authority delegation, and recovery/revocation decisions.
- Integration with actual Toolchain acceptance, export, commit, push, publication, cache, and package flows.

This refresh closes only the reproducibility gap for the fixture run. PLAN §7.4 remains open; it does not validate operational security or select a signing/trust architecture.
