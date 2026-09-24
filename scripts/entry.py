"""PyInstaller entry point for the suravidl desktop binary."""
import multiprocessing

from suravidl_engine.__main__ import main

if __name__ == "__main__":
    main()
