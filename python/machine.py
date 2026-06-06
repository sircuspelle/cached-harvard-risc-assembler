from __future__ import annotations

import argparse
import ast
import os
import struct


class CacheL1:
    def __init__(self, data_memory: bytearray):
        self.data_memory = data_memory
        self.cache_lines = {i: {"valid": False, "tag": -1, "data": 0} for i in range(8)}
        self.hit_cycles = 1
        self.miss_cycles = 10
        self.hits = 0
        self.misses = 0

    def _get_index_and_tag(self, address: int):
        word_addr = address // 4
        index = word_addr % 8
        tag = word_addr // 8
        return index, tag

    def read(self, address: int) -> tuple[int, int]:
        if address >= 0x10000:
            address = address - 0x10000

        index, tag = self._get_index_and_tag(address)
        line = self.cache_lines[index]

        if line["valid"] and line["tag"] == tag:
            self.hits += 1
            return line["data"], self.hit_cycles

        self.misses += 1
        if address + 4 > len(self.data_memory):
            raise IndexError(f"data memory access out of bounds: {address}")
        val = struct.unpack("<I", self.data_memory[address : address + 4])[0]
        self.cache_lines[index] = {"valid": True, "tag": tag, "data": val}
        return val, self.miss_cycles

    def write(self, address: int, value: int) -> int:
        if address >= 0x10000:
            address = address - 0x10000

        index, tag = self._get_index_and_tag(address)
        struct.pack_into("<I", self.data_memory, address, value)

        self.cache_lines[index] = {"valid": True, "tag": tag, "data": value}
        return self.miss_cycles


class IOController:
    def __init__(self, input_schedule: list[tuple[int, int]], output_buffer: list):
        self.input_schedule = input_schedule
        self.output_buffer = output_buffer
        self.port_in_data = 0
        self.interrupt_pending = False

    def tick_check(self, current_tick: int):
        if not self.input_schedule:
            return

        next_event_tick, ascii_code = self.input_schedule[0]
        if current_tick >= next_event_tick:
            self.port_in_data = ascii_code
            self.interrupt_pending = True
            self.input_schedule.pop(0)

    def read_port(self, port: int) -> int:
        if port == 1:
            self.interrupt_pending = False
            return self.port_in_data
        return 0

    def write_port(self, port: int, value: int):
        if port == 0:
            char = chr(value & 0xFF)
            self.output_buffer.append(char)
            print(char, end="", flush=True)


class ImmGenerator:
    @staticmethod
    def generate(instruction: int) -> int:
        opcode = instruction & 0x7F
        funct3 = (instruction >> 12) & 0x7

        if opcode in (0x13, 0x03, 0x67) or (opcode == 0x73 and funct3 in (0x0, 0x2)):
            imm = (instruction >> 20) & 0xFFF
            return imm if (imm & 0x800) == 0 else imm - 0x1000

        if opcode == 0x23 or (opcode == 0x73 and funct3 == 0x3):
            imm_11_5 = (instruction >> 25) & 0x7F
            imm_4_0 = (instruction >> 7) & 0x1F
            imm = (imm_11_5 << 5) | imm_4_0
            return imm if (imm & 0x800) == 0 else imm - 0x1000

        if opcode == 0x63:
            imm_12 = (instruction >> 31) & 0x1
            imm_11 = (instruction >> 7) & 0x1
            imm_10_5 = (instruction >> 25) & 0x3F
            imm_4_1 = (instruction >> 8) & 0xF
            imm = (imm_12 << 12) | (imm_11 << 11) | (imm_10_5 << 5) | (imm_4_1 << 1)
            return imm if (imm & 0x1000) == 0 else imm - 0x2000

        if opcode == 0x37:
            imm = (instruction >> 12) & 0xFFFFF
            return imm << 12

        if opcode == 0x6F:
            imm_20 = (instruction >> 31) & 0x1
            imm_19_12 = (instruction >> 12) & 0xFF
            imm_11 = (instruction >> 20) & 0x1
            imm_10_1 = (instruction >> 21) & 0x3FF
            imm = (imm_20 << 20) | (imm_19_12 << 12) | (imm_11 << 11) | (imm_10_1 << 1)
            return imm if (imm & 0x100000) == 0 else imm - 0x200000

        return 0


class ControlUnit:
    @staticmethod
    def decode(instruction: int) -> dict:
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        funct7 = (instruction >> 25) & 0x7F

        signals = {
            "RegWr": False,
            "MemRd": False,
            "MemWr": False,
            "PortRd": False,
            "PortWr": False,
            "PCWr": True,
            "ALUSrc": "REG",
            "SelPC": "PC+4",
            "BranchOp": "BEQ",
            "Halt": False,
            "IntEnWr": False,
            "IntEnData": False,
            "ALUOp": "ADD",
            "rs1": rs1,
            "rs2": rs2,
            "rd": rd,
        }

        # R-type (add, sub, and, ...)
        if opcode == 0x33:
            signals["RegWr"] = True
            if funct3 == 0x0 and funct7 == 0x00:
                signals["ALUOp"] = "ADD"
            elif funct3 == 0x0 and funct7 == 0x20:
                signals["ALUOp"] = "SUB"
            elif funct3 == 0x7 and funct7 == 0x00:
                signals["ALUOp"] = "AND"
            elif funct3 == 0x6 and funct7 == 0x00:
                signals["ALUOp"] = "OR"
            elif funct3 == 0x4 and funct7 == 0x00:
                signals["ALUOp"] = "XOR"

            elif funct3 == 0x0 and funct7 == 0x01:
                signals["ALUOp"] = "MUL"
            elif funct3 == 0x4 and funct7 == 0x01:
                signals["ALUOp"] = "DIV"
            elif funct3 == 0x6 and funct7 == 0x01:
                signals["ALUOp"] = "REM"

        # I-type (addi, andi)
        elif opcode == 0x13:
            signals["RegWr"] = True
            signals["ALUSrc"] = "IMM"
            if funct3 == 0x0:
                signals["ALUOp"] = "ADD"
            elif funct3 == 0x7:
                signals["ALUOp"] = "AND"
            elif funct3 == 0x6:
                signals["ALUOp"] = "OR"
            elif funct3 == 0x4:
                signals["ALUOp"] = "XOR"

        # Load
        elif opcode == 0x03:  # Load
            signals["RegWr"] = True
            signals["MemRd"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "ADD"

        # Store
        elif opcode == 0x23:
            signals["MemWr"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "ADD"

        # Branch
        elif opcode == 0x63:
            signals["SelPC"] = "BT"
            if funct3 == 0x0:
                signals["BranchOp"] = "BEQ"
            elif funct3 == 0x1:
                signals["BranchOp"] = "BNE"
            elif funct3 == 0x4:
                signals["BranchOp"] = "BLT"
            elif funct3 == 0x5:
                signals["BranchOp"] = "BGE"
            elif funct3 == 0x6:
                signals["BranchOp"] = "BLTU"

        # LUI
        elif opcode == 0x37:
            signals["RegWr"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "COPY_B"

        # JAL
        elif opcode == 0x6F:
            signals["RegWr"] = True
            signals["SelPC"] = "BT"
            signals["BranchOp"] = "JUMP"

        # JALR
        elif opcode == 0x67:
            signals["RegWr"] = True
            signals["SelPC"] = "ALU"
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "ADD"

        # порты, прерывания, halt
        elif opcode == 0x73:
            # IN (I-type)
            if funct3 == 0x2:
                signals["RegWr"] = True
                signals["PortRd"] = True

            # OUT (S-type)
            elif funct3 == 0x3:
                signals["PortWr"] = True

            elif funct3 == 0x0:
                funct12 = (instruction >> 20) & 0xFFF
                if funct12 == 0x000:
                    signals["Halt"] = True
                elif funct12 == 0x302:
                    signals["IRET"] = True
                    signals["IntEnWr"] = True
                    signals["IntEnData"] = True
                    signals["SelPC"] = "EPC"
                elif funct12 == 0x001:
                    signals["IntEnWr"] = True
                    signals["IntEnData"] = True
                elif funct12 == 0x002:
                    signals["IntEnWr"] = True
                    signals["IntEnData"] = False

        return signals


class Processor:
    def __init__(self, text_mem: list[int], data_mem: bytearray, io_ctrl: IOController):
        self.instruction_memory = text_mem
        self.cache = CacheL1(data_mem)
        self.io = io_ctrl
        self.cu = ControlUnit()

        self.registers = [0] * 32
        self.pc = 0
        self.epc = 0
        self.interrupts_enabled = False

        self.ticks = 0
        self.stall_cycles = 0
        self.halted = False

        self.journal: list[str] = []

    def tick(self):
        # защёлкнули PC
        self.ticks += 1

        self.io.tick_check(self.ticks)

        # Instruction Fetch
        if self.pc // 4 >= len(self.instruction_memory):
            self.halted = True
            return

        instruction = self.instruction_memory[self.pc // 4]

        # Decode
        sig = self.cu.decode(instruction)
        imm_val = ImmGenerator.generate(instruction)

        # thats going on in CU
        if self.stall_cycles > 0:
            self.stall_cycles -= 1
            self.log_state("STALL")
            sig["RegWr"] = False
            sig["MemWr"] = False
            sig["PCWr"] = False
            return

        if sig["Halt"]:
            self.halted = True
            self.log_state("HALT")
            sig["RegWr"] = False
            sig["MemWr"] = False
            sig["PCWr"] = False
            return

        # Execution
        val_a = self.registers[sig["rs1"]]
        val_b = imm_val if sig["ALUSrc"] == "IMM" else self.registers[sig["rs2"]]
        alu_result = 0

        if sig["ALUOp"] == "ADD":
            alu_result = val_a + val_b
        elif sig["ALUOp"] == "SUB":
            alu_result = val_a - val_b
        elif sig["ALUOp"] == "AND":
            alu_result = val_a & val_b
        elif sig["ALUOp"] == "OR":
            alu_result = val_a | val_b
        elif sig["ALUOp"] == "XOR":
            alu_result = val_a ^ val_b
        elif sig["ALUOp"] == "COPY_B":
            alu_result = val_b
        elif sig["ALUOp"] == "MUL":
            alu_result = (val_a * val_b) & 0xFFFFFFFF
        elif sig["ALUOp"] == "DIV":
            alu_result = (val_a // val_b) if val_b != 0 else 0
        elif sig["ALUOp"] == "REM":
            alu_result = (val_a % val_b) if val_b != 0 else val_a
        next_pc = self.pc + 4
        write_back_val = alu_result

        if sig["MemRd"]:
            write_back_val, stalls = self.cache.read(alu_result)
            self.stall_cycles += stalls

        elif sig["MemWr"]:
            val_to_store = self.registers[sig["rs2"]]
            stalls = self.cache.write(alu_result, val_to_store)
            self.stall_cycles += stalls

        elif sig["PortRd"]:
            write_back_val = self.io.read_port(imm_val)

        elif sig["PortWr"]:
            self.io.write_port(imm_val, self.registers[sig["rs2"]])

        if sig["SelPC"] in ("BT", "ALU") and sig["RegWr"]:
            write_back_val = self.pc + 4

        if sig["RegWr"] and sig["rd"] != 0:
            self.registers[sig["rd"]] = write_back_val & 0xFFFFFFFF

        # D-триггер прерываний
        if sig["IntEnWr"]:
            self.interrupts_enabled = sig["IntEnData"]

        # Branch Unit
        cond = False
        if sig["BranchOp"] == "JUMP":
            cond = True
        if sig["BranchOp"] is not None:
            val_a_s = val_a if val_a < 0x80000000 else val_a - 0x100000000
            val_b_s = val_b if val_b < 0x80000000 else val_b - 0x100000000

            b_op = sig["BranchOp"]
            if b_op == "BEQ":
                cond = val_a == val_b
            elif b_op == "BNE":
                cond = val_a != val_b
            elif b_op == "BLT":
                cond = val_a_s < val_b_s
            elif b_op == "BGE":
                cond = val_a_s >= val_b_s
            elif b_op == "BLTU":
                cond = val_a < val_b

        # branch target summator multpilexor
        mux_in_sum = imm_val if cond else 4
        bt_val = self.pc + mux_in_sum

        # SelPC mux
        sel_pc_src = sig["SelPC"]

        if sel_pc_src == "EPC":
            next_pc = self.epc
        elif sel_pc_src == "ALU":
            next_pc = alu_result
        elif sel_pc_src == "BT":
            next_pc = bt_val
        else:
            next_pc = self.pc + 4

        # логируем до изменения PC
        self.log_state(f"0x{instruction:08X}")

        # trap Controller
        if self.interrupts_enabled and self.io.interrupt_pending:
            self.epc = next_pc
            next_pc = 0x004
            self.interrupts_enabled = False
            self.log_state("TRAP FIRED!")

        if sig["PCWr"]:
            self.pc = next_pc

    def log_state(self, action: str):
        if self.ticks > 200:
            if self.ticks == 200:
                self.journal.append("... log cutted on 200 tacts ...")
            return

        regs = f"t0:{self.registers[5]} a0:{self.registers[10]} a1:{self.registers[11]}"
        self.journal.append(f"Tick: {self.ticks:4} | PC: {self.pc:04X} | Act: {action:10} | {regs}")


def load_binary(file_path: str) -> tuple[list[int], bytearray]:
    with open(file_path, "rb") as f:
        header = f.read(12)
        magic, text_size, data_size = struct.unpack("<I I I", header)

        if magic != 0xDEADDEAD:
            raise ValueError("invalid binary file, magic number mismatch.")

        text_data = f.read(text_size)
        data_data = f.read(data_size)

        text_mem = [struct.unpack("<I", text_data[i : i + 4])[0] for i in range(0, text_size, 4)]

        data_mem = bytearray(4096)
        data_mem[:data_size] = data_data

        return text_mem, data_mem


def load_schedule(file_path: str) -> list[tuple[int, int]]:
    if not file_path:
        return []
    with open(file_path) as f:
        content = f.read()
        raw_schedule = ast.literal_eval(content)

        schedule = []
        for tick, char in raw_schedule:
            ascii_code = ord(char) if isinstance(char, str) else char
            schedule.append((tick, ascii_code))
        return schedule


def main():
    parser = argparse.ArgumentParser(description="RISC-IV Processor Simulator")
    parser.add_argument("binary", help="compiled binary file (.bin)")
    parser.add_argument("--input", help="interrupt schedule file (.txt)", default=None)
    parser.add_argument("--log", help="output execution log", default="execution.log")
    args = parser.parse_args()

    text_mem, data_mem = load_binary(args.binary)
    schedule = load_schedule(args.input)
    output_buffer = []

    io_ctrl = IOController(schedule, output_buffer)
    processor = Processor(text_mem, data_mem, io_ctrl)

    max_ticks = 100000000
    try:
        while not processor.halted and processor.ticks < max_ticks:
            processor.tick()
    except Exception as e:
        print(f"\napparat error {e} on PC=0x{processor.pc:04X}")

    if processor.ticks >= max_ticks:
        print(f"\nreached ticks limit ({max_ticks})")

    print("\nstop")

    print(f"Total ticks: {processor.ticks}")
    print(f"L1 cache hits: {processor.cache.hits}")
    print(f"L1 cache misses: {processor.cache.misses}")
    print(f"output buffer: {''.join(output_buffer)}")

    with open(args.log, "w") as f:
        f.write("\n".join(processor.journal))
    print(f"logged in {os.path.basename(args.log)}")


if __name__ == "__main__":
    main()
