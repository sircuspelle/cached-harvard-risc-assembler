import contextlib
import io
import os
import tempfile
from unittest.mock import patch

import pytest

import machine
import translator


@pytest.mark.golden_test("golden/*.yml")
def test_translator_and_machine(golden):
    with tempfile.TemporaryDirectory() as tmpdirname:
        source = os.path.join(tmpdirname, "source.s")
        input_stream = os.path.join(tmpdirname, "input.txt")
        target = os.path.join(tmpdirname, "target.bin")
        build_log = os.path.join(tmpdirname, "build.log")
        exec_log = os.path.join(tmpdirname, "exec.log")

        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])

        try:
            stdin_content = golden["in_stdin"]
            has_input = True
        except KeyError:
            has_input = False

        if has_input:
            with open(input_stream, "w", encoding="utf-8") as file:
                file.write(stdin_content)

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            with patch("sys.argv", ["translator.py", source, target, "--log", build_log]):
                translator.main()

            print("============================================================")

            machine_args = ["machine.py", target, "--log", exec_log]
            if has_input:
                machine_args.extend(["--input", input_stream])

            with patch("sys.argv", machine_args):
                machine.main()

        with open(target, "rb") as file:
            code = file.read()
        with open(build_log, encoding="utf-8") as file:
            code_hex = file.read()
        with open(exec_log, encoding="utf-8") as file:
            machine_log = file.read()

        assert code == golden.out["out_code"]
        assert code_hex == golden.out["out_code_hex"]
        assert stdout.getvalue() == golden.out["out_stdout"]
        assert machine_log == golden.out["out_log"]
