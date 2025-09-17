import sys
from pathlib import Path


def add_project_to_path(file_path, levels_up=1, insert_at_start=False):
    """Add project root to sys.path if not already present.

    Args:
        file_path: Pass __file__ from the calling script
        levels_up: How many directory levels up to go
        insert_at_start: If True, insert at beginning of sys.path
    """
    project_root = str(Path(file_path).parents[levels_up - 1])
    if project_root not in sys.path:
        if insert_at_start:
            sys.path.insert(0, project_root)
        else:
            sys.path.append(project_root)
