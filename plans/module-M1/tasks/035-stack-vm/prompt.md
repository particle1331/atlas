Implement `run(program)` in `vm.py` for a small stack machine.

Instructions are tuples:
- `("PUSH", value)`
- `("ADD",)`, `("SUB",)`, `("MUL",)`
- `("DUP",)`, `("SWAP",)`
- `("JZ", address)`: pop a value and jump to `address` if it is zero
- `("JMP", address)`
- `("PRINT",)`: pop a value and append it to the output

Execution starts at index 0. `JMP` and `JZ` addresses are instruction
indices. Return the list of printed values.

Raise `ValueError` for stack underflow, an unknown instruction, or a jump
outside the program.
