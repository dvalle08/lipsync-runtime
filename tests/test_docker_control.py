from unittest.mock import patch

from talking_head_runtime.config import RuntimeSettings
from talking_head_runtime.docker_control import ComposeController


def test_compose_up_uses_project_and_file() -> None:
    settings = RuntimeSettings(
        COMPOSE_PROJECT_NAME="demo-stack",
        COMPOSE_FILE="/srv/demo/compose.yaml",
    )
    controller = (settings)

    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        controller.up("musetalk-api")

    command = run.call_args.args[0]
    assert command == [
        "docker",
        "compose",
        "-p",
        "demo-stack",
        "-f",
        "/srv/demo/compose.yaml",
        "up",
        "-d",
        "musetalk-api",
    ]
