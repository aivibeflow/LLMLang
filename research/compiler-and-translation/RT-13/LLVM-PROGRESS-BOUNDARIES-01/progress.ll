@device = global i32 0

define i32 @unannotated(i32 %stop) {
entry:
  %done = icmp eq i32 %stop, 1
  br i1 %done, label %ret, label %wait
wait:
  br label %wait
ret:
  ret i32 7
}

define i32 @function_progress(i32 %stop) mustprogress {
entry:
  %done = icmp eq i32 %stop, 1
  br i1 %done, label %ret, label %wait
wait:
  br label %wait
ret:
  ret i32 7
}

define i32 @loop_progress(i32 %stop) {
entry:
  %done = icmp eq i32 %stop, 1
  br i1 %done, label %ret, label %wait
wait:
  br label %wait, !llvm.loop !0
ret:
  ret i32 7
}

define i32 @volatiles_make_progress(i32 %stop) mustprogress {
entry:
  %done = icmp eq i32 %stop, 1
  br i1 %done, label %ret, label %wait
wait:
  %read = load volatile i32, ptr @device
  br label %wait
ret:
  ret i32 7
}

!0 = distinct !{!0, !1}
!1 = !{!"llvm.loop.mustprogress"}
