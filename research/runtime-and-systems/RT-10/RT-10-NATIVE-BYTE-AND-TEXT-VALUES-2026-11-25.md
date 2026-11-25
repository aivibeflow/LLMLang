# RT-10 — Byte spans, C strings and validated UTF-8 across native calls

Which data and length survive when the same initialized buffer is passed through three different native contracts? This fixture compares a C byte span, a C NUL-terminated string and a Rust UTF-8 span exposed through a C-callable boundary. The branch baseline is `ec5174c3fd3f23757eb2ac27001fd49dd41d5cc0`. [Runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md)

The caller allocates an exact byte payload and an extra terminal zero. The length-delimited functions receive the original byte count, excluding that extra byte. The C string copy obtains the count from the first zero. The Rust text function checks that the selected span is valid UTF-8, then counts Unicode scalar values. An independent Python oracle compares all bytes, two text interpretations and every capacity control. [C carrier](NATIVE-BYTE-TEXT-01/copy.c) · [Rust text validator](NATIVE-BYTE-TEXT-01/text.rs)

| Payload | Length-delimited bytes | C string bytes | UTF-8 scalar count of full span |
|---|---:|---:|---:|
| `x`, zero and 😀 | 6 | 1 | 3 |
| Precomposed é | 2 | 2 | 1 |
| `e` plus combining acute accent | 3 | 3 | 2 |
| Zero followed by invalid octet `ff` | 2 | 0 | Refused |
| UTF-8 bytes for a surrogate | 3 | 3 | Refused |

A sufficiently sized byte copy preserves all 16 original payloads. The C string contract returns a shorter prefix in five cases. Strict UTF-8 refuses seven full inputs. In the zero-plus-invalid-octet control, computing UTF-8 validity after C-string truncation sees a valid empty span and loses the original failure. All 196 copy-capacity controls pass at each optimization level. Insufficient capacity leaves the destination unchanged, and successful copies preserve the sentinel bytes after the copied prefix. [All payloads and observations](NATIVE-BYTE-TEXT-01/evidence.json)

The result supports naming the carrier and its length unit in a semantic call contract. A raw byte count, a NUL-terminated prefix and a scalar count are different values even on the same memory. The fixture assumes initialized, live, correctly bounded input spans. Embedded NUL policy for particular foreign APIs, foreign ownership, normalization, grapheme segmentation, layout beyond this target, and LLMLang value representation remain open. [Runtime architecture issue](https://github.com/aivibeflow/LLMLang/issues/325)

## Reproduction

Use x86-64 Linux with glibc 2.41, GCC 14.2.0 (Debian 14.2.0-19), rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181` and CPython 3.12.14. Both libraries are built at optimization levels 0 and 2. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/NATIVE-BYTE-TEXT-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt10-native-byte-text.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-native-byte-text.json
```
