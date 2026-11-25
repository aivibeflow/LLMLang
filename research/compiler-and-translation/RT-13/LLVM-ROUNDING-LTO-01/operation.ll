target triple = "x86_64-unknown-linux-gnu"

declare double @llvm.experimental.constrained.fadd.f64(double, double, metadata, metadata)

define double @dynamic_sum(double %a, double %b) #0 {
  %sum = call double @llvm.experimental.constrained.fadd.f64(double %a, double %b,
    metadata !"round.dynamic", metadata !"fpexcept.strict") #0
  ret double %sum
}

attributes #0 = { strictfp }
