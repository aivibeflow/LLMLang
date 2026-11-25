def checkedResult (value : Int) : Int := value

theorem returnsInput (value : Int) : checkedResult value = value := rfl

#print axioms returnsInput
