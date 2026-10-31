"""Tests for bake diagnostics through real subprocesses and the pytest fixture."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from rugix_testkit.bakery import BakeryBuilder

pytest_plugins = ["pytester"]

_OUTPUT = b"first\nrepeat\nrepeat\n\nprogress\rfinished\nstderr\nlast"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A Bakery project whose launcher emits output and writes small artifacts."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "rugix-bakery.toml").write_text("")
    launcher = project / "run-bakery"
    launcher.write_text(
        "#!/bin/sh\nset -eu\n"
        "printf 'first\\nrepeat\\nrepeat\\n\\nprogress\\rfinished\\n'\n"
        "printf 'stderr\\n' >&2\n"
        "printf last\n"
        "mkdir -p build/test-efi\n"
        "printf image > build/test-efi/system.img\n"
        "printf bundle > build/test-efi/system.rugixb\n"
    )
    launcher.chmod(0o755)
    return project


@pytest.mark.parametrize("artifact", ["image", "bundle"])
def test_bake_logs_preserve_output_and_survive_reuse(
    project: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    artifact: str,
) -> None:
    """Save stdout and stderr faithfully, log at DEBUG, and retain logs on reuse."""
    bakery = BakeryBuilder(project, tmp_path / "run")
    bake = getattr(bakery, f"bake_{artifact}")
    with caplog.at_level(logging.DEBUG, logger="rugix_testkit.bakery"):
        result = bake("test-efi")

    log = project / "test-outputs" / "bakery" / f"{artifact}-test-efi.log"
    assert result.is_file()
    assert log.read_bytes() == _OUTPUT
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert messages.count("repeat") == 2
    assert "stderr" in messages
    assert "last" in messages

    (project / "run-bakery").unlink()
    assert bake("test-efi") == result
    assert log.read_bytes() == _OUTPUT


def test_bake_streams_partial_output_before_exit(
    project: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Partial output reaches disk and DEBUG live, including split UTF-8 bytes."""
    release = project / "release"
    log = project / "test-outputs" / "bakery" / "image-test-efi.log"
    (project / "run-bakery").write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        "import time\n"
        "from pathlib import Path\n"
        "os.write(1, b'progress \\xc3')\n"
        "deadline = time.monotonic() + 5\n"
        "while not Path('release').exists():\n"
        "    if time.monotonic() >= deadline:\n"
        "        raise SystemExit(23)\n"
        "    time.sleep(0.01)\n"
        "os.write(1, b'\\xa9\\n')\n"
        "Path('build/test-efi').mkdir(parents=True)\n"
        "Path('build/test-efi/system.img').write_bytes(b'image')\n"
    )

    class ReleaseOnOutput(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno == logging.DEBUG:
                assert log.read_bytes().startswith(b"progress ")
                release.touch()

    logger = logging.getLogger("rugix_testkit.bakery")
    handler = ReleaseOnOutput()
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            BakeryBuilder(project, tmp_path / "run").bake_image("test-efi")
    finally:
        logger.removeHandler(handler)

    assert log.read_bytes() == "progress é\n".encode()
    debug = "".join(
        record.getMessage().removeprefix("bakery: ")
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )
    assert debug == "progress é"


def test_failed_bake_reports_tail_and_can_be_retried(
    project: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Keep full failure output, show a bounded tail by default, and allow retries."""
    launcher = project / "run-bakery"
    successful_script = launcher.read_text()
    output = b"first\n" + b"repeat\n" * 25 + b"stderr: build failed\nlast"
    launcher.write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        f"os.write(1, {output!r})\n"
        "raise SystemExit(23)\n"
    )
    run_dir = tmp_path / "run"
    logs = tmp_path / "outputs" / "bakery"
    bakery = BakeryBuilder(project, run_dir, bake_log_dir=logs)

    with pytest.raises(subprocess.CalledProcessError) as failure:
        bakery.bake_image("test-efi")

    log = logs / "image-test-efi.log"
    assert failure.value.returncode == 23
    assert log.read_bytes() == output
    tail = b"".join(output.splitlines(keepends=True)[-20:]).decode()
    assert failure.value.output == tail
    errors = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
    ]
    assert errors == [f"bakery failed (exit 23). Log: {log}\n{tail}"]
    assert not (run_dir / "baked-image-test-efi").exists()

    launcher.write_text(successful_script)
    assert bakery.bake_image("test-efi").is_file()
    assert log.read_bytes() == _OUTPUT


def test_bakery_fixture_uses_test_outputs_directory(
    pytester: pytest.Pytester, project: Path, tmp_path: Path
) -> None:
    """The plugin saves logs under --test-outputs-dir and streams them to pytest."""
    pytester.makeconftest(
        f"""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def rugix_project():
    return Path({str(project)!r})
"""
    )
    pytester.makepyfile(
        """
def test_bake(bakery):
    assert bakery.bake_image("test-efi").is_file()
"""
    )
    outputs = tmp_path / "test outputs"
    result = pytester.runpytest_subprocess(
        "--test-outputs-dir", str(outputs), "--log-cli-level=DEBUG"
    )
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*bakery: first*", "*stderr*", "*last*"])
    assert (outputs / "bakery" / "image-test-efi.log").read_bytes() == _OUTPUT
    assert not (project / "test-outputs").exists()
