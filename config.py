# pyright: reportIgnoreCommentWithoutRule = false
import inspect
import json
import os
import sys
import traceback
import PyQt5.QtGui as G
from typing import Any


def _get_paths() -> tuple[str, str]:
    current_frame = inspect.currentframe()
    assert current_frame is not None
    config_path = os.path.dirname(
        os.path.abspath(inspect.getfile(current_frame))
    )

    return (
        os.path.join(config_path, "photo-organizer.json"),
        os.path.join(config_path, "icons"),
    )


config_file_name, icons_path = _get_paths()

config: Any = None


def load_config() -> None:
    global config
    global config_file_name
    try:
        with open(config_file_name) as f:
            config = json.load(f)
        return
    except FileNotFoundError:
        pass
    except KeyboardInterrupt:
        raise
    except Exception:
        print("Failed to load config.", file=sys.stderr)
        traceback.print_exc()
    config = {
        "maximized": False,
        "width": 800,
        "height": 600,
        "picture_size": 100,
    }


def save_config() -> None:
    global config
    global config_file_name
    try:
        with open(config_file_name, "w") as f:
            json.dump(config, f)
    except Exception:
        print("Failed to save config.", file=sys.stderr)
        traceback.print_exc()


def get_icon(name: str) -> G.QIcon:
    return G.QIcon(os.path.join(icons_path, name + ".svg"))
