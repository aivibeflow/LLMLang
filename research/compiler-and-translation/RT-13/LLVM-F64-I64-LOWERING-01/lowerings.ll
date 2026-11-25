source_filename = "llmlang-rt13-f64-i64"
target datalayout = "e-m:e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

declare i64 @llvm.fptosi.sat.i64.f64(double)

; Return {0, value} on success, {1, 0} on a range refusal, and {2, 0} for nonfinite.
; Compare unsigned magnitude bits against the encoding of exactly 2^63.
define { i32, i64 } @bits_branch(double %x) {
entry:
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %negative = icmp slt i64 %bits, 0
  %below = icmp ult i64 %magnitude, 4890909195324358656
  %at_edge = icmp eq i64 %magnitude, 4890909195324358656
  %negative_edge = and i1 %negative, %at_edge
  %inside = or i1 %below, %negative_edge
  br i1 %inside, label %convert, label %refuse
convert:
  %value = fptosi double %x to i64
  %result = insertvalue { i32, i64 } zeroinitializer, i64 %value, 1
  ret { i32, i64 } %result
refuse:
  %status = select i1 %finite, i32 1, i32 2
  %failure = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  ret { i32, i64 } %failure
}

define { i32, i64 } @ordered_branch(double %x) {
entry:
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %lower = fcmp oge double %x, 0xC3E0000000000000
  %upper = fcmp olt double %x, 0x43E0000000000000
  %inside = and i1 %lower, %upper
  br i1 %inside, label %convert, label %refuse
convert:
  %value = fptosi double %x to i64
  %result = insertvalue { i32, i64 } zeroinitializer, i64 %value, 1
  ret { i32, i64 } %result
refuse:
  %status = select i1 %finite, i32 1, i32 2
  %failure = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  ret { i32, i64 } %failure
}

define { i32, i64 } @ordered_select(double %x) {
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %lower = fcmp oge double %x, 0xC3E0000000000000
  %upper = fcmp olt double %x, 0x43E0000000000000
  %inside = and i1 %lower, %upper
  %raw = fptosi double %x to i64
  %value = select i1 %inside, i64 %raw, i64 0
  %category = select i1 %finite, i32 1, i32 2
  %status = select i1 %inside, i32 0, i32 %category
  %tagged = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  %result = insertvalue { i32, i64 } %tagged, i64 %value, 1
  ret { i32, i64 } %result
}

define { i32, i64 } @guarded_saturate(double %x) {
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %lower = fcmp oge double %x, 0xC3E0000000000000
  %upper = fcmp olt double %x, 0x43E0000000000000
  %inside = and i1 %lower, %upper
  %raw = call i64 @llvm.fptosi.sat.i64.f64(double %x)
  %value = select i1 %inside, i64 %raw, i64 0
  %category = select i1 %finite, i32 1, i32 2
  %status = select i1 %inside, i32 0, i32 %category
  %tagged = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  %result = insertvalue { i32, i64 } %tagged, i64 %value, 1
  ret { i32, i64 } %result
}

define { i32, i64 } @saturate(double %x) {
  %value = call i64 @llvm.fptosi.sat.i64.f64(double %x)
  %result = insertvalue { i32, i64 } zeroinitializer, i64 %value, 1
  ret { i32, i64 } %result
}

define { i32, i64 } @inclusive_upper(double %x) {
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %lower = fcmp oge double %x, 0xC3E0000000000000
  %upper = fcmp ole double %x, 0x43E0000000000000
  %inside = and i1 %lower, %upper
  %raw = fptosi double %x to i64
  %value = select i1 %inside, i64 %raw, i64 0
  %category = select i1 %finite, i32 1, i32 2
  %status = select i1 %inside, i32 0, i32 %category
  %tagged = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  %result = insertvalue { i32, i64 } %tagged, i64 %value, 1
  ret { i32, i64 } %result
}

define { i32, i64 } @unmasked_value(double %x) {
  %bits = bitcast double %x to i64
  %magnitude = and i64 %bits, 9223372036854775807
  %finite = icmp ult i64 %magnitude, 9218868437227405312
  %lower = fcmp oge double %x, 0xC3E0000000000000
  %upper = fcmp olt double %x, 0x43E0000000000000
  %inside = and i1 %lower, %upper
  %value = fptosi double %x to i64
  %category = select i1 %finite, i32 1, i32 2
  %status = select i1 %inside, i32 0, i32 %category
  %tagged = insertvalue { i32, i64 } zeroinitializer, i32 %status, 0
  %result = insertvalue { i32, i64 } %tagged, i64 %value, 1
  ret { i32, i64 } %result
}
