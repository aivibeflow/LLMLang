# RT-04 lifetime polymorphism and erased provider interfaces

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

Rust 1.85.1 compiles a provider library separately from each client. The clients exercise universally quantified input lifetimes, static instantiation, trait objects, associated output types and generic methods at two optimization levels. Fourteen of 24 compile decisions admit the client. Every admitted implementation matches its independent result vector across 1,024 native observations.

| Interface or control | Checked result |
| --- | --- |
| `for<'a> fn(&'a i32, &'a i32) -> &'a i32` | A generic selector accepts local references. A selector restricted to static references is refused as an inhabitant of this type and still works when called with static inputs. |
| Generic signature whose implementation returns a static reference | It satisfies the quantified signature. A client using the quantified interface cannot retain its result beyond the input region, even for this implementation. |
| Trait object with a method generic over lifetimes | Admitted for two providers. The right-input provider and static-value provider produce different results under the same erased signature. |
| Associated output type | Dynamic use requires the concrete associated type. An omitted associated output is rejected. |
| Type-parametric method | Concrete calls work at two instantiations. An unrestricted type-parametric method blocks dynamic erasure. A method qualified by `Self: Sized` leaves the other trait-object methods available and is itself unavailable through that interface. |

The lifetime declares a valid access interval. The choice of which input or static value supplies the result belongs to a separate behavior contract. A candidate design can make generic input and output type relationships explicit and state which methods remain callable through erasure. The experiment uses native Rust language and ABI choices. Higher-ranked LLMLang inference, coherence, cross-version ABI and production lowering remain open.

Reproduce with Rust 1.85.1 and CPython 3.12.14 from the repository root.

```bash
study=research/language-design/RT-04/POLYMORPHIC-LIFETIMES-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Rust path remapping makes the provider archive digest independent of the temporary directory in this fixture. After setting that remapping, two fresh runs reproduce provider bytes, diagnostics and observations.
