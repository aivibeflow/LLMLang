target datalayout = "e-p:64:64"

define i8 @src(ptr %p, ptr %q) {
  store i8 7, ptr %p
  store i8 9, ptr %q
  %r = load i8, ptr %p
  ret i8 %r
}
define i8 @tgt(ptr %p, ptr %q) {
  store i8 9, ptr %q
  store i8 7, ptr %p
  %r = load i8, ptr %p
  ret i8 %r
}

define i8 @case_src_alias() {
  %p = alloca i8
  %r = call i8 @src(ptr %p, ptr %p)
  ret i8 %r
}
define i8 @case_tgt_alias() {
  %p = alloca i8
  %r = call i8 @tgt(ptr %p, ptr %p)
  ret i8 %r
}
define i8 @case_src_distinct() {
  %p = alloca i8
  %q = alloca i8
  %r = call i8 @src(ptr %p, ptr %q)
  ret i8 %r
}
define i8 @case_tgt_distinct() {
  %p = alloca i8
  %q = alloca i8
  %r = call i8 @tgt(ptr %p, ptr %q)
  ret i8 %r
}

; ASSERT EQ: i8 9 = call i8 @case_src_alias()
; ASSERT EQ: i8 7 = call i8 @case_tgt_alias()
; ASSERT EQ: i8 7 = call i8 @case_src_distinct()
; ASSERT EQ: i8 7 = call i8 @case_tgt_distinct()
