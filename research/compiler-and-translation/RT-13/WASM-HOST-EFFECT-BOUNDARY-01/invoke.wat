(module
  (import "llmlang" "commit" (func $commit (param i32)))
  (func (export "invoke") (param $requested i64) (result i32)
    local.get $requested
    i64.const 255
    i64.gt_u
    if (result i32)
      i32.const 256
    else
      local.get $requested
      i32.wrap_i64
      call $commit
      local.get $requested
      i32.wrap_i64
    end))
