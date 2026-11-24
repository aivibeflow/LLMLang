target triple = "thumbv7m-none-eabi"

define i32 @step(i32 %previous, i32 %sample, i32 %valid) nounwind {
entry:
  %flag = icmp eq i32 %valid, 1
  %cool = icmp ult i32 %sample, 100
  %admitted = and i1 %flag, %cool
  br i1 %admitted, label %normal, label %reset

normal:
  %highPrev = icmp ugt i32 %previous, 255
  %bounded = select i1 %highPrev, i32 255, i32 %previous
  %hot = icmp uge i32 %sample, 80
  %raised = add i32 %bounded, 13
  %excess = icmp ugt i32 %raised, 255
  %saturated = select i1 %excess, i32 255, i32 %raised
  %cold = icmp ult i32 %sample, 20
  %floor = icmp ult i32 %bounded, 9
  %lowered = sub i32 %bounded, 9
  %clamped = select i1 %floor, i32 0, i32 %lowered
  %warm = select i1 %cold, i32 %clamped, i32 %bounded
  %result = select i1 %hot, i32 %saturated, i32 %warm
  ret i32 %result

reset:
  ret i32 0
}
