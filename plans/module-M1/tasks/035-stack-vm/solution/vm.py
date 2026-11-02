def run(program: list[tuple]) -> list[int]:
    stack = []
    output = []
    ip = 0

    def pop():
        if not stack:
            raise ValueError("stack underflow")
        return stack.pop()

    while ip < len(program):
        instruction = program[ip]
        if not instruction:
            raise ValueError("empty instruction")
        opcode = instruction[0]
        if opcode == "PUSH":
            if len(instruction) != 2:
                raise ValueError("PUSH needs a value")
            stack.append(instruction[1])
        elif opcode == "ADD":
            stack.append(pop() + pop())
        elif opcode == "SUB":
            right = pop()
            left = pop()
            stack.append(left - right)
        elif opcode == "MUL":
            stack.append(pop() * pop())
        elif opcode == "DUP":
            value = pop()
            stack.extend([value, value])
        elif opcode == "SWAP":
            right = pop()
            left = pop()
            stack.extend([right, left])
        elif opcode == "JZ":
            if len(instruction) != 2:
                raise ValueError("JZ needs an address")
            target = instruction[1]
            if not 0 <= target <= len(program):
                raise ValueError("jump out of range")
            if pop() == 0:
                ip = target
                continue
        elif opcode == "JMP":
            if len(instruction) != 2:
                raise ValueError("JMP needs an address")
            target = instruction[1]
            if not 0 <= target <= len(program):
                raise ValueError("jump out of range")
            ip = target
            continue
        elif opcode == "PRINT":
            output.append(pop())
        else:
            raise ValueError(f"unknown opcode: {opcode}")
        ip += 1
    return output
