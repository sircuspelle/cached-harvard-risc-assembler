from __future__ import annotations

import argparse
import ast
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


class ControlUnit:
    @staticmethod
    def decode(instruction: int) -> dict:
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        funct7 = (instruction >> 25) & 0x7F

        # TODO: PortRd, PortWr согласовать со схемой
        # TODO: Branch и Jump согласовать со схемой
        # TODO: Halt сигнал согласовать со схемой и ещё подумать над ним
        # TODO: EI и DI пока, но мб один оставить
        # TODO: IRET может и не нужен, надо согласовать со схемой
        # TODO: Imm пока костыль
        signals = {
            "RegWr": False,
            "MemRd": False,
            "MemWr": False,
            "PortRd": False,
            "PortWr": False,
            "ALUSrc": "REG",
            "Branch": False,
            "Jump": False,
            "Halt": False,
            "IRET": False,
            "EI": False,
            "DI": False,
            "ALUOp": "ADD",
            "Imm": 0,
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

        # TODO: пока скорее задумка чем что-то готовое
        # I-type (addi, andi)
        elif opcode == 0x13:
            signals["RegWr"] = True
            signals["ALUSrc"] = "IMM"
            imm = (instruction >> 20) & 0xFFF
            signals["Imm"] = imm if (imm & 0x800) == 0 else imm - 0x1000

            if funct3 == 0x0:
                signals["ALUOp"] = "ADD"
            elif funct3 == 0x7:
                signals["ALUOp"] = "AND"
            # TODO: докинуты прямые команды ORI и XORI потому что могу но надо думать ещё
            elif funct3 == 0x6:
                signals["ALUOp"] = "OR"
            elif funct3 == 0x4:
                signals["ALUOp"] = "XOR"

        # TODO: учесть word/byte
        # Load
        elif opcode == 0x03:  # Load
            signals["RegWr"] = True
            signals["MemRd"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "ADD"
            imm = (instruction >> 20) & 0xFFF
            signals["Imm"] = imm if (imm & 0x800) == 0 else imm - 0x1000

        # Store
        elif opcode == 0x23:
            signals["MemWr"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "ADD"
            imm = ((instruction >> 25) << 5) | ((instruction >> 7) & 0x1F)
            signals["Imm"] = imm if (imm & 0x800) == 0 else imm - 0x1000

        # TODO: обдумать описанную на схеме петлю с обработкой проверки условия от аккумултора
        # Branch
        elif opcode == 0x63:
            signals["Branch"] = True
            signals["ALUOp"] = "SUB"
            imm_12 = (instruction >> 31) & 0x1
            imm_11 = (instruction >> 7) & 0x1
            imm_10_5 = (instruction >> 25) & 0x3F
            imm_4_1 = (instruction >> 8) & 0xF
            imm = (imm_12 << 12) | (imm_11 << 11) | (imm_10_5 << 5) | (imm_4_1 << 1)
            signals["Imm"] = imm if (imm & 0x1000) == 0 else imm - 0x2000
            # TODO: костыльное появление Funct3 в сигналах
            signals["Funct3"] = funct3

        # LUI
        elif opcode == 0x37:
            signals["RegWr"] = True
            signals["ALUSrc"] = "IMM"
            signals["ALUOp"] = "COPY_B"
            signals["Imm"] = (instruction >> 12) & 0xFFFFF
            imm_value = (instruction >> 12) & 0xFFFFF
            signals["Imm"] = imm_value << 12

        # JAL
        elif opcode == 0x6F:
            signals["RegWr"] = True
            signals["Jump"] = True
            # imm[20|10:1|11|19:12])
            imm_20 = (instruction >> 31) & 0x1
            imm_19_12 = (instruction >> 12) & 0xFF
            imm_11 = (instruction >> 20) & 0x1
            imm_10_1 = (instruction >> 21) & 0x3FF
            imm = (imm_20 << 20) | (imm_19_12 << 12) | (imm_11 << 11) | (imm_10_1 << 1)
            if imm & 0x100000:
                imm = imm - 0x200000
            signals["Imm"] = imm

        # JALR
        elif opcode == 0x67:
            signals["RegWr"] = True
            signals["Jump"] = True
            signals["ALUSrc"] = "IMM"
            # TODO: костыть ADD_REG_IMM, перенести на ADD
            signals["ALUOp"] = "ADD_REG_IMM"
            imm = (instruction >> 20) & 0xFFF
            if imm & 0x800:
                imm = imm - 0x1000
            signals["Imm"] = imm

        # порты, прерывания, halt
        elif opcode == 0x73:
            imm = (instruction >> 20) & 0xFFF
            # IN (I-type)
            if funct3 == 0x2:
                signals["RegWr"] = True
                signals["PortRd"] = True
                signals["Imm"] = imm  # номер порта

            # OUT (S-type)
            elif funct3 == 0x3:
                signals["PortWr"] = True
                # S-type: imm находится в битах [11:5] и [4:0]
                # TODO: пока костыль, это должен делать IMM генератор со схемы
                imm_11_5 = (instruction >> 25) & 0x7F
                imm_4_0 = (instruction >> 7) & 0x1F
                port = (imm_11_5 << 5) | imm_4_0
                signals["Imm"] = port

            # EI, DI, IRET, Halt
            elif funct3 == 0x0:
                if imm == 0x000:
                    signals["Halt"] = True
                elif imm == 0x302:
                    signals["IRET"] = True
                elif imm == 0x001:
                    signals["EI"] = True
                elif imm == 0x002:
                    signals["DI"] = True

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

        if self.stall_cycles > 0:
            self.stall_cycles -= 1
            self.log_state("STALL")
            return

        # Instruction Fetch
        if self.pc // 4 >= len(self.instruction_memory):
            self.halted = True
            return

        instruction = self.instruction_memory[self.pc // 4]

        # Decode
        sig = self.cu.decode(instruction)

        if sig["Halt"]:
            self.halted = True
            self.log_state("HALT")
            return

        # Execution
        val_a = self.registers[sig["rs1"]]
        val_b = sig["Imm"] if sig["ALUSrc"] == "IMM" else self.registers[sig["rs2"]]
        alu_result = 0

        if sig["ALUOp"] == "ADD":
            alu_result = val_a + val_b
        elif sig["ALUOp"] == "ADD_REG_IMM":
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
            write_back_val = self.io.read_port(sig["Imm"])

        elif sig["PortWr"]:
            self.io.write_port(sig["Imm"], self.registers[sig["rs2"]])

        # control flow: conditional
        if sig["Branch"]:

            def to_signed(x):
                return x if x < 0x80000000 else x - 0x100000000

            val_a_s = to_signed(val_a)
            val_b_s = to_signed(val_b)

            if sig["Funct3"] == 0 and alu_result == 0:  # beq
                next_pc = self.pc + sig["Imm"]
            elif sig["Funct3"] == 1 and alu_result != 0:  # bne
                next_pc = self.pc + sig["Imm"]
            elif sig["Funct3"] == 4 and val_a_s < val_b_s:  # blt знаковое
                next_pc = self.pc + sig["Imm"]
            elif sig["Funct3"] == 5 and val_a_s >= val_b_s:  # bge знаковое
                next_pc = self.pc + sig["Imm"]
            elif sig["Funct3"] == 6 and val_a < val_b:  # bltu беззнаковое <
                next_pc = self.pc + sig["Imm"]

        if sig["Jump"]:
            write_back_val = self.pc + 4
            if sig["ALUOp"] == "ADD_REG_IMM":  # JALR
                next_pc = alu_result
            else:  # JAL
                next_pc = self.pc + sig["Imm"]

        if sig["EI"]:
            self.interrupts_enabled = True
        elif sig["DI"]:
            self.interrupts_enabled = False
        elif sig["IRET"]:
            next_pc = self.epc
            self.interrupts_enabled = True

        if sig["RegWr"] and sig["rd"] != 0:
            self.registers[sig["rd"]] = write_back_val & 0xFFFFFFFF

        # логируем до изменения PC
        self.log_state(f"0x{instruction:08X}")

        # trap
        if self.interrupts_enabled and self.io.interrupt_pending:
            self.epc = next_pc
            next_pc = 0x0004
            self.interrupts_enabled = False
            self.log_state("TRAP FIRED!")

        self.pc = next_pc

    def log_state(self, action: str):
        if self.ticks > 50000:
            if self.ticks == 50001:
                self.journal.append("... log cutted on 50000 tacts ...")
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
    print(f"logged in {args.log}")


if __name__ == "__main__":
    main()
