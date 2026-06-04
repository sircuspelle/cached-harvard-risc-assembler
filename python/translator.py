import argparse
import struct
import sys
import re
from typing import List, Dict, Tuple

# codes for source registers and destination regitsres
REGISTERS = {
    'zero': 0, 'ra': 1, 'sp': 2, 'gp': 3, 'tp': 4, 't0': 5, 't1': 6, 't2': 7,
    's0': 8, 's1': 9, 'a0': 10, 'a1': 11, 'a2': 12, 'a3': 13, 'a4': 14, 'a5': 15,
    'a6': 16, 'a7': 17, 's2': 18, 's3': 19, 's4': 20, 's5': 21, 's6': 22, 's7': 23,
    's8': 24, 's9': 25, 's10': 26, 's11': 27, 't3': 28, 't4': 29, 't5': 30, 't6': 31,
}

# safely collect 32-bit machine words from args
def encode_r_type(opcode: int, funct3: int, funct7: int, rd: int, rs1: int, rs2: int) -> int:
    return ((funct7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

def encode_i_type(opcode: int, funct3: int, rd: int, rs1: int, imm: int) -> int:
    return ((imm & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

def encode_s_type(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    imm_11_5 = (imm >> 5) & 0x7F
    imm_4_0  = imm & 0x1F
    return (imm_11_5 << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | (imm_4_0 << 7) | (opcode & 0x7F)

def encode_b_type(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    # B type imm[12|10:5|4:1|11]
    imm_12 = (imm >> 12) & 0x1
    imm_11 = (imm >> 11) & 0x1
    imm_10_5 = (imm >> 5) & 0x3F
    imm_4_1 = (imm >> 1) & 0xF
    return (imm_12 << 31) | (imm_10_5 << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | (imm_4_1 << 8) | (imm_11 << 7) | (opcode & 0x7F)

def encode_u_type(opcode: int, rd: int, imm: int) -> int:
    return ((imm & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

def encode_j_type(opcode: int, rd: int, imm: int) -> int:
    # J type imm[20|10:1|11|19:12]
    imm_20 = (imm >> 20) & 0x1
    imm_19_12 = (imm >> 12) & 0xFF
    imm_11 = (imm >> 11) & 0x1
    imm_10_1 = (imm >> 1) & 0x3FF
    return (imm_20 << 31) | (imm_10_1 << 21) | (imm_11 << 20) | (imm_19_12 << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


class Translator:
    def __init__(self):
        self.text_section: List[int] =[]  # commands saved in words
        self.data_section: bytearray = bytearray() # data saved by bytes
        
        self.labels: Dict[str, int] = {}       # label name linked with address
        self.label_sections: Dict[str, str] = {} # lable name linked with section ("text" | "data")

    def translate(self, source_code: str) -> Tuple[bytes, str]:
        # remove commets, divide label and code into lines, and later will be added macros preprocessing
        lines = self._preprocess(source_code)
        
        # prepare string for writnig, divide sequences of wors, preprocess adresses with offsets, fill self.labels and self.labels_sections processing, words and strings reading
        self._first_pass(lines)
        
        # machine code generation + human-read dump forming
        debug_log = self._second_pass(lines)
        
        # make hader and code machine comands from numbers to bytes
        binary_data = self._build_binary()
        
        return binary_data, debug_log

    def _preprocess(self, source_code: str) -> List[str]:
        lines =[]
        for line in source_code.splitlines():
            # remove comments
            line = line.split(';')[0].strip()
            if line:
                # search for label
                if ':' in line:
                    label_part, rest = line.split(':', 1)
                    if label_part.strip():
                        lines.append(label_part.strip() + ':')
                    if rest.strip():
                        lines.append(rest.strip())
                else:
                    lines.append(line)
        # TODO: need to add macros prepocessing but i dont have enough time
        return lines

    def _first_pass(self, lines: List[str]):
        current_section = ".text"
        text_address = 0
        data_address = 0x10000  # harvard offset
        text_base = 0
        data_base = 0x10000

        for line in lines:
            if line in (".text", ".data"):
                current_section = line
                continue

            if line.endswith(":"):
                label_name = line[:-1]
                if current_section == ".text":
                    self.labels[label_name] = text_base + text_address
                else:
                    self.labels[label_name] = data_base + data_address
                self.label_sections[label_name] = current_section
                continue

            if line.startswith(".org"):
                parts = line.split()
                # autodetect nuber system
                addr = int(parts[1], 0)
                if current_section == ".text":
                    text_address = addr
                else:
                    data_address = addr
                continue

            if current_section == ".text":
                text_address += 4
            elif current_section == ".data":
                if line.startswith(".word"):
                    # words can be written in line with separator
                    data_address += 4 * len(line.split(","))
                elif line.startswith(".string"):
                    # TODO: potential error
                    str_content = line[line.find('"')+1 : line.rfind('"')]
                    # \\n instead of real cariage return \n
                    str_content = str_content.replace("\\n", "\n")
                    data_address += len(str_content) + 1

    def _second_pass(self, lines: List[str]) -> str:
        debug_lines =[]
        current_section = ".text"
        text_address = 0
        data_address = 0x10000

        for line in lines:
            # machine code doesnt include labels sections and directives
            if line.endswith(":") or line in (".text", ".data") or line.startswith(".org"):
                if line in (".text", ".data"):
                    current_section = line
                elif line.startswith(".org"):
                    addr = int(line.split()[1], 0)
                    if current_section == ".text":
                        text_address = addr
                    else:
                        # TODO: data adress processing needs to be implemeted
                        data_address = addr
                continue

            if current_section == ".text":
                machine_code = self._assemble_instruction(line, text_address)
                self.text_section.append(machine_code)
                debug_lines.append(f"0x{text_address:08X} - {machine_code:08X} - {line}")
                text_address += 4

            elif current_section == ".data":
                # translate .word or .string
                self._assemble_data(line)
                # TODO: make log from data needs to be implemented and adress data processing as well

        return "\n".join(debug_lines)


    def _build_binary(self) -> bytes:
        magic = 0xDEADDEAD
        text_size = len(self.text_section) * 4 # each instruction is word
        data_size = len(self.data_section)
        
        # three unsigneed numbers in little endian order
        header = struct.pack("<I I I", magic, text_size, data_size)
        
        text_bytes = bytearray()
        for word in self.text_section:
            text_bytes.extend(struct.pack("<I", word))
            
        return header + text_bytes + self.data_section
    
    # give number of register, it easy to make later binary
    def _get_reg(self, reg_name: str) -> int:
        if reg_name not in REGISTERS:
            raise ValueError(f"unknown register: {reg_name}")
        return REGISTERS[reg_name]

    # immediate value can be ( label address with %hi or %lo \  number)
    def _resolve_imm(self, operand: str, current_address: int) -> int:
        if operand.startswith("%hi("):
            # '%hi(label_name)'
            label = operand[4:-1]
            addr = self.labels[label]
            return (addr >> 12) & 0xFFFFF
        if operand.startswith("%lo("):
            # '%lo(label_name)'
            label = operand[4:-1]
            addr = self.labels[label]
            return addr & 0xFFF
            
        # operand as a label without 
        if operand in self.labels:
            target_address = self.labels[operand]
            # B type or J type instructions compute offset PC-relatively
            return target_address - current_address
            
        # number can be hex
        if operand.startswith("0x"):
            return int(operand, 16)
        return int(operand)

    # parse line into machine code
    def _assemble_instruction(self, line: str, address: int) -> int:
        # split into opcode and args
        parts = line.replace(",", " ").split(maxsplit=1)
        mnemonic = parts[0]
        args = parts[1].split() if len(parts) > 1 else[]
        
        # R type
        if mnemonic in ("add", "sub", "and", "or", "xor", "sll", "srl", "sra", "mul", "div", "rem"):
            rd = self._get_reg(args[0])
            rs1 = self._get_reg(args[1])
            rs2 = self._get_reg(args[2])
            
            opcode = 0x33 # stolen from RISC-V
            funct7 = 0x00
            
            if mnemonic == "add": funct3 = 0x0
            elif mnemonic == "sub": funct3 = 0x0; funct7 = 0x20
            elif mnemonic == "and": funct3 = 0x7
            elif mnemonic == "or": funct3 = 0x6
            elif mnemonic == "xor": funct3 = 0x4
            elif mnemonic == "mul": funct3 = 0x0; funct7 = 0x01 
            elif mnemonic == "div": funct3 = 0x4; funct7 = 0x01
            elif mnemonic == "rem": funct3 = 0x6; funct7 = 0x01
            
            return encode_r_type(opcode, funct3, funct7, rd, rs1, rs2)

        # I type (arithmetic with imm value)
        elif mnemonic in ("addi", "andi", "ori", "xori"):
            rd = self._get_reg(args[0])
            rs1 = self._get_reg(args[1])
            imm = self._resolve_imm(args[2], address)
            
            opcode = 0x13
            if mnemonic == "addi": funct3 = 0x0
            elif mnemonic == "xori": funct3 = 0x4
            elif mnemonic == "ori": funct3 = 0x6
            elif mnemonic == "andi": funct3 = 0x7
            
            return encode_i_type(opcode, funct3, rd, rs1, imm)

        # I type (load from memory)
        elif mnemonic in ("lw", "lb"):
            rd = self._get_reg(args[0])
            # imm(rs1) like 16(sp)
            match = re.match(r"(-?\w+)\((\w+)\)", args[1])
            if not match:
                raise SyntaxError(f"invalid memory access format: {args[1]}")
            
            imm = self._resolve_imm(match.group(1), address)
            rs1 = self._get_reg(match.group(2))
            
            opcode = 0x03
            funct3 = 0x2 if mnemonic == "lw" else 0x0
            return encode_i_type(opcode, funct3, rd, rs1, imm)

        # S type (save in memory)
        elif mnemonic in ("sw", "sb"):
            rs2 = self._get_reg(args[0]) # value to save
            # imm(rs1) like 16(sp)
            match = re.match(r"(-?\w+)\((\w+)\)", args[1])
            imm = self._resolve_imm(match.group(1), address)
            rs1 = self._get_reg(match.group(2)) # get address

            opcode = 0x23
            funct3 = 0x2 if mnemonic == "sw" else 0x0
            return encode_s_type(opcode, funct3, rs1, rs2, imm)

        # U type
        elif mnemonic == "lui":
            rd = self._get_reg(args[0])
            imm = self._resolve_imm(args[1], address)
            return encode_u_type(0x37, rd, imm)

        # B type
        elif mnemonic in ("beq", "bne", "blt", "bge", "bltu", "ble"):
            rs1 = self._get_reg(args[0])
            rs2 = self._get_reg(args[1])
            imm = self._resolve_imm(args[2], address)

            opcode = 0x63
            if mnemonic == "beq": funct3 = 0x0
            elif mnemonic == "bne": funct3 = 0x1
            elif mnemonic == "blt": funct3 = 0x4
            elif mnemonic == "bge": funct3 = 0x5
            elif mnemonic == "bltu": funct3 = 0x6
            elif mnemonic == "ble": # ble rs1, rs2 -> bge rs2, rs1
                rs1, rs2 = rs2, rs1
                funct3 = 0x5
            return encode_b_type(opcode, funct3, rs1, rs2, imm)

        # J type (jump and link relative: PC = [ PC + offset ] = [ correct: label_addr | failure-safe: <offset>(<rs>)])
        # usually to call procedure
        elif mnemonic == "jal":
            rd = self._get_reg(args[0])
            # PC = [ PC + offset ] = [label_addr | <offset>(<rs>)])
            if "(" in args[1]:
                match = re.match(r"(-?\w+)\((\w+)\)", args[1])
                if match:
                    imm = self._resolve_imm(match.group(1), address)
                    rs1 = self._get_reg(match.group(2))
                    return encode_i_type(0x67, 0x0, rd, rs1, imm)
                
            # PC = label_addr
            imm = self._resolve_imm(args[1], address)
            return encode_j_type(0x6F, rd, imm)

        # I type (jump and link register: PC = [ RS1 + offset] = <offset>(<register>) )
        # usually to return from procedure
        elif mnemonic == "jalr":
            rd = self._get_reg(args[0])
            # <offset>(<rs>) e.g. 0(ra)
            match = re.match(r"(-?\w+)\((\w+)\)", args[1])
            if not match:
                raise SyntaxError(f"invalid memory access format: {args[1]}")

            imm = self._resolve_imm(match.group(1), address)
            rs1 = self._get_reg(match.group(2))

            opcode = 0x67
            funct3 = 0x0
            return encode_i_type(opcode, funct3, rd, rs1, imm)
            
        # I type (port-mapped IO)
        elif mnemonic == "in":
            # in rd, port
            rd = self._get_reg(args[0])
            port = int(args[1])
            return encode_i_type(0x73, 0x2, rd, 0, port)
            
        elif mnemonic == "out":
            # out rs, port
            rs = self._get_reg(args[0])
            port = int(args[1])
            return encode_s_type(0x73, 0x3, 0, rs, port)
            
        elif mnemonic == "halt":
            return encode_i_type(0x73, 0x0, 0, 0, 0x000)
        elif mnemonic == "iret":
            return encode_i_type(0x73, 0x0, 0, 0, 0x302)
        elif mnemonic == "ei":
            return encode_i_type(0x73, 0x0, 0, 0, 0x001)
        elif mnemonic == "di":
            return encode_i_type(0x73, 0x0, 0, 0, 0x002)

        # pseudo
        elif mnemonic == "j":  # j offset -> jal zero, offset
            imm = self._resolve_imm(args[0], address)
            return encode_j_type(0x6F, REGISTERS['zero'], imm)
        elif mnemonic == "beqz": # beqz rs, offset -> beq rs, zero, offset
            rs = self._get_reg(args[0])
            imm = self._resolve_imm(args[1], address)
            return encode_b_type(0x63, 0x0, rs, REGISTERS['zero'], imm)

        raise ValueError(f"unknown instruction: {line}")


    def _assemble_data(self, line: str):
        # must be able to process
        # line = .word 1, 2, 3
        # line = .word buffer
        # line = .string "Hello\n"

        parts = line.split(maxsplit=1)
        directive = parts[0]

        if directive == ".word":
            values = parts[1].split(',')
            for val in values:
                val_str = val.strip()
                # can be label
                if val_str in self.labels:
                    v = self.labels[val_str]
                # can be number
                else:
                    v = int(val_str, 0)
                # only positive numbers
                if v < 0 or v > 0xFFFFFFFF:
                    raise ValueError(f"value {v} out of 32-bit range")
                # < - little endian
                # I - unsigned 32
                self.data_section.extend(struct.pack("<I", v & 0xFFFFFFFF))

        elif directive == ".string":
            str_content = line[line.find('"')+1 : line.rfind('"')]
            str_content = str_content.replace("\\n", "\n").replace("\\t", "\t")
            byte_array = str_content.encode('utf-8') + b'\x00'

            self.data_section.extend(byte_array)
            # alignment
            padding = (4 - (len(self.data_section) % 4)) % 4
            self.data_section.extend(b'\x00' * padding)


# cli
def main():
    parser = argparse.ArgumentParser(description="modified risc-iv assembler")
    parser.add_argument("input", help="input assembly file (.asm)")
    parser.add_argument("output", help="output binary file (.bin)")
    parser.add_argument("--log", help="output debug log file (.log)", default="program.log")
    
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        source_code = f.read()
        
    translator = Translator()
    binary_data, debug_log = translator.translate(source_code)
    
    with open(args.output, "wb") as f:
        f.write(binary_data)
        
    with open(args.log, "w") as f:
        f.write(debug_log)
        
    print(f"compilation successful! bin: {args.output}, log: {args.log}")

if __name__ == "__main__":
    main()