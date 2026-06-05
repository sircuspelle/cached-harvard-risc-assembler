import struct

import pytest

from translator import Translator


@pytest.fixture()
def translator():
    t = Translator()
    t.labels = {"my_label": 0x0000000C, "data_var": 0x00000010}
    return t


class TestInstructionEncoding:
    def test_r_type_encoding(self, translator):
        machine_code = translator._assemble_instruction("add t0, t1, t2", address=0)
        assert machine_code == 0x007302B3, f"expected 0x007302B3, got 0x{machine_code:08X}"

    def test_i_type_encoding(self, translator):
        machine_code = translator._assemble_instruction("addi a0, zero, 15", address=0)
        assert machine_code == 0x00F00513, f"expected 0x00F00513, got 0x{machine_code:08X}"

    def test_memory_load_encoding(self, translator):
        machine_code = translator._assemble_instruction("lw a0, 4(sp)", address=0)
        assert machine_code == 0x00412503

    def test_port_io_encoding(self, translator):
        machine_code = translator._assemble_instruction("in t0, 1", address=0)
        assert machine_code == 0x001022F3

    def test_branch_encoding(self, translator):
        machine_code = translator._assemble_instruction("beq t0, t1, my_label", address=0)
        assert machine_code == 0x00628663


class TestDataSection:
    def test_word_directive(self, translator):
        translator._assemble_data(".word 255, -1")
        expected = struct.pack("<i", 255) + struct.pack("<i", -1)
        assert translator.data_section == bytearray(expected)

    def test_string_directive_cstr(self, translator):
        translator._assemble_data('.string "Hi"')
        expected = bytearray([0x48, 0x69, 0x00, 0x00])
        assert translator.data_section == expected


class TestIntegration:
    def test_full_translation(self, translator):
        source_code = """
        .data
        .word 42
        .text
        start:
            addi t0, zero, 1
            halt
        """
        binary_data, debug_log = translator.translate(source_code)

        assert "0x00000000" in debug_log
        assert "addi t0, zero, 1" in debug_log

        magic, text_size, data_size = struct.unpack("<I I I", binary_data[:12])
        assert magic == 0xDEADDEAD
        assert text_size == 8
        assert data_size == 4

        assert len(binary_data) == 24
