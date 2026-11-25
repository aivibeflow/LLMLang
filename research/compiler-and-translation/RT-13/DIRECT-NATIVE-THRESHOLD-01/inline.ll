target triple = "x86_64-unknown-linux-gnu"

define double @inline_loads() {
  %result = call double asm sideeffect "movabsq $$0x3ff0000000000000, %rax\0A\09movq %rax, %xmm0\0A\09movabsq $$0xbff0000000000000, %rax\0A\09movq %rax, %xmm1\0A\09addsd %xmm1, %xmm0", "={xmm0},~{rax},~{xmm1}"()
  ret double %result
}
