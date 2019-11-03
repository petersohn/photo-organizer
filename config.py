import inspect
import json
import os
import sys
import traceback
from typing import Any

config_path = os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())))  # type: ignore
config_file_name = os.path.join(config_path, 'config.json')

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
        print('Failed to load config.', file=sys.stderr)
        traceback.print_exc()
    config = {
        'maximized': False,
        'width': 800,
        'height': 600,
        'picture_size': 100,
    }


def save_config() -> None:
    global config
    global config_file_name
    try:
        with open(config_file_name, 'w') as f:
            json.dump(config, f)
    except Exception:
        print('Failed to save config.', file=sys.stderr)
        traceback.print_exc()
