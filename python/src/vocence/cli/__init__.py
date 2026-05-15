"""Command-line entry point for the `vocence` CLI.

Users get this on the PATH after ``pip install vocence``:

.. code-block:: bash

    vocence login
    vocence account
    vocence keys list
    vocence voices
    vocence speak "Hello" --voice design-aria -o out.wav
    vocence transcribe clip.wav --language English
"""

from .main import app

__all__ = ["app"]
