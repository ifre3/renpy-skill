"""
Ren'Py test runner -- thin wrapper around cli.py.
"""

# All core logic has been merged into cli.RenPyCLI.
# Use directly:
#   from cli import RenPyCLI
#   cli = RenPyCLI()
#   cli.inject_test(code)
#   cli.run_tests(path)
#   cli.remove_injected()

from cli import RenPyCLI, make_scene_test, make_menu_test  # noqa: F401
