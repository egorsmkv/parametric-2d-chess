"""Hugging Face Space entrypoint.

The ``chess2d`` package is copied in next to this file by
``scripts/deploy_space.py``, so a plain import works.
"""

from chess2d.gradio_app import main

if __name__ == "__main__":
    main()
