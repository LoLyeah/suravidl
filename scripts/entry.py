"""PyInstaller entry point for the suravidl desktop binary."""
import multiprocessing

from suravidl_engine.__main__ import main

if __name__ == "__main__":
    # On Windows a frozen binary re-executes itself for worker processes;
    # without this the app spawns itself (and its window) in a loop — the
    # v0.21.2 audit flagged the missing call.
    multiprocessing.freeze_support()
    main()
