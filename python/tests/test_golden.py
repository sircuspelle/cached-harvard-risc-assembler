import os
import subprocess
import pytest

TRANSLATOR = "python/translator.py"
MACHINE = "python/machine.py"


@pytest.mark.parametrize(
    "asm_file, input_file, expected_output",
    [
        ("algorithms/cat.s", "golden/cat_input.txt", "Test"),
        pytest.param("algorithms/prob1.s", "", "906609"),
        pytest.param("algorithms/sort.s", "", "11 12 22 25 34 64 90 "),
        ("algorithms/double.s", "", "21"),
        ("examples/hello.s", "examples/input.txt", "What? Hi, Alice"),
    ],
)
def test_pipeline(asm_file, input_file, expected_output, tmp_path):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    bin_file = tmp_path / "out.bin"
    log_build = tmp_path / "build.log"
    log_exec = tmp_path / "execute.log"

    compile_cmd = [
        "python",
        TRANSLATOR,
        asm_file,
        str(bin_file),
        "--log",
        str(log_build),
    ]
    comp_res = subprocess.run(compile_cmd, capture_output=True, text=True, cwd=project_root)
    assert comp_res.returncode == 0, f"Compilation failed: {comp_res.stderr}"

    run_cmd = ["python", MACHINE, str(bin_file), "--log", str(log_exec)]
    if input_file:
        run_cmd.extend(["--input", input_file])

    run_res = subprocess.run(run_cmd, capture_output=True, text=True, cwd=project_root)
    assert run_res.returncode == 0, f"Execution failed: {run_res.stderr}"

    assert "[АППАРАТНАЯ ОШИБКА]" not in run_res.stdout

    output_line = ""
    for line in run_res.stdout.splitlines():
        if line.startswith("Output buffer:"):
            output_line = line.replace("Output buffer: ", "").lstrip()

    assert output_line == expected_output, f"Expected '{expected_output}', got '{output_line}'"
