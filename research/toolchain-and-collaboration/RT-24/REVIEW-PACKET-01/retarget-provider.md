# Review bundle for retarget provider

## Revision pair

| Role | Commit | Tree |
| --- | --- | --- |
| Base | `8d670b067e63dacd9a7eb57db5839c33b62159ec` | `0dd85fb74a4af317eea862a06d6742d99c6537f8` |
| Candidate | `b530d9b2f4a69bb34c238eabbd92f24542ce618c` | `3c2efa3dfbe2d21175174643bde10b5b9cd54cad` |

Review bundle SHA-256 `f33424b1c710338d76cf100bbd95c667059e3f0332b4dd36ca8532a94672a8be`.

## Semantic changes

Base semantic root `43e7af334ca223919e0eb12ee02d67558cf23156c508f85d50ab64a148ebd8bc`.
Candidate semantic root `c842ba6a21739bbf0b696acc7c59cc95b6ad4ba41f6ec23803c06672ed3ad3ba`.

| Changed slot | Before | After |
| --- | --- | --- |
| `binding:compute` | `f1e24bc0265aee2453f3b7d6e6f6e49b18866039650c13ae737ec5abe71b447e` | `01339c6807010441d520014b0f9959b8cc92b1c291d55363f84efae15686a277` |

Previous exact provider `996e3a6fa2063161ff1f290cbc481f2f61bb743750a31ddc08c3f5e9c367a678`.
Selected exact provider `204c8562b1941f3baf339826dcf550d63842d3cd797c75695ec8789bdab9ddca`.

## Bounded interpreter observations

| Input | Base result and trace | Candidate result and trace |
| ---: | --- | --- |
| -2 | `[-1, []]` | `[-3, []]` |
| -1 | `[0, []]` | `[-2, []]` |
| 0 | `[1, []]` | `[-1, []]` |
| 1 | `[2, []]` | `[0, []]` |
| 2 | `[3, []]` | `[1, []]` |

## Exact source patch

Patch SHA-256 `d4623aff6124d9da0869b5f407b5168f72570a4468028cd95d5977c809a69660`.

````diff
diff --git a/program.json b/program.json
index 066a5d2..a6fd7b4 100644
--- a/program.json
+++ b/program.json
@@ -1 +1 @@
-{"surface": "infix", "entry": "op(\"compute\", x)", "binding": "plus"}
+{"surface": "infix", "entry": "op(\"compute\", x)", "binding": "minus"}
````
