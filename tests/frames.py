"""Helpers for tests that need in-memory screen frames without touching the real screen."""

import numpy as np

import macos


def fake_frame(width=200, height=120, shade=240, marks=()):
    """A macos.Frame (no CGImage) of a flat colour, with filled rectangles `marks=[(x, y, w, h, shade)]`."""
    pixels = np.full((height, width, 4), shade, np.uint8)
    pixels[..., 3] = 255
    for x, y, w, h, value in marks:
        pixels[y:y + h, x:x + w, :3] = value
    return macos.Frame(None, bytearray(pixels.tobytes()), width, height)
