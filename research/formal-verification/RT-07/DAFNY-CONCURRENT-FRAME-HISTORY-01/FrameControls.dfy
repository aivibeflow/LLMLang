include "Frames.dfy"

function {:concurrent} SharedRead(cell: Cell): int
  reads cell
{
  cell.value
}

method {:concurrent} DefaultReadFrame(cell: Cell)
{
}

method {:concurrent} DistinctButShared(left: Cell, right: Cell)
  requires left != right
  reads {}
  modifies left
{
  left.value := 0;
}

function {:concurrent} AssumedFunctionRead(cell: Cell): int
  reads {:assume_concurrent} cell
{
  cell.value
}
