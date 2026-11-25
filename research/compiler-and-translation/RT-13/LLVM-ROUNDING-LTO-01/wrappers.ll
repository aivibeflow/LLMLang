target triple = "x86_64-unknown-linux-gnu"

@operands = internal global [2 x double] [double 1.000000e+00, double -1.000000e+00], align 8

declare double @dynamic_sum(double, double) #0

define double @inline_literals() #0 {
  %sum = call double @dynamic_sum(double 1.000000e+00, double -1.000000e+00) #1
  ret double %sum
}

define double @keep_call() #0 {
  %sum = call double @dynamic_sum(double 1.000000e+00, double -1.000000e+00) #2
  ret double %sum
}

define double @inline_loads() #0 {
  %left = load volatile double, ptr @operands, align 8
  %right_ptr = getelementptr inbounds [2 x double], ptr @operands, i32 0, i32 1
  %right = load volatile double, ptr %right_ptr, align 8
  %sum = call double @dynamic_sum(double %left, double %right) #1
  ret double %sum
}

attributes #0 = { strictfp }
attributes #1 = { alwaysinline strictfp }
attributes #2 = { noinline strictfp }
