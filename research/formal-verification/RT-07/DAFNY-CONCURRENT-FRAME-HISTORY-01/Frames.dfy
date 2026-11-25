class Cell {
  var value: int

  constructor(initial: int)
    reads {}
    ensures value == initial
  {
    value := initial;
  }
}

function {:concurrent} IsolatedValue(initial: int): int
{
  initial + 1
}

method {:concurrent} FreshCell(initial: int) returns (result: int)
  reads {}
  modifies {}
  ensures result == initial + 1
{
  var cell := new Cell(initial);
  cell.value := cell.value + 1;
  return cell.value;
}

method {:concurrent} EmptyUnderPremise(cell: Cell, touch: bool)
  requires !touch
  reads if touch then {cell} else {}
  modifies if touch then {cell} else {}
{
}

method SequentialBump(cell: Cell) returns (result: int)
  reads cell
  modifies cell
  ensures cell.value == old(cell.value) + 1
  ensures result == cell.value
{
  var before := cell.value;
  cell.value := before + 1;
  return cell.value;
}

method {:concurrent} AssumedSharedBump(cell: Cell) returns (result: int)
  reads {:assume_concurrent} cell
  modifies {:assume_concurrent} cell
  ensures cell.value == old(cell.value) + 1
  ensures result == cell.value
{
  var before := cell.value;
  cell.value := before + 1;
  return cell.value;
}
