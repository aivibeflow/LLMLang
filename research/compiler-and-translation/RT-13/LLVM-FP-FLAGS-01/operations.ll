target triple = "x86_64-unknown-linux-gnu"

declare double @llvm.fma.f64(double, double, double)

define double @split_expression(double %a, double %b, double %c) {
  %product = fmul double %a, %b
  %result = fadd double %product, %c
  ret double %result
}

define double @permit_contract(double %a, double %b, double %c) {
  %product = fmul contract double %a, %b
  %result = fadd contract double %product, %c
  ret double %result
}

define double @exact_fma(double %a, double %b, double %c) {
  %result = call double @llvm.fma.f64(double %a, double %b, double %c)
  ret double %result
}

define double @signed_zero(double %a) {
  %result = fadd double %a, 0.000000e+00
  ret double %result
}

define double @ignore_zero_sign(double %a) {
  %result = fadd nsz double %a, 0.000000e+00
  ret double %result
}

define i32 @inspect_nan(double %a) {
  %test = fcmp uno double %a, %a
  %result = zext i1 %test to i32
  ret i32 %result
}

define i32 @assume_no_nan(double %a) {
  %test = fcmp nnan uno double %a, %a
  %result = zext i1 %test to i32
  ret i32 %result
}
