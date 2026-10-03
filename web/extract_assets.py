"""Copies the Zeus font from the game files into web/assets.

Usage: python web/extract_assets.py <eZeus folder>

The eZeus folder is the one with interface.e and Fonts/Zeus.ttf (e.g.
"Zeus and Poseidon/eZeus-0.8.2-beta"). The start page uses the font for its
title and buttons. It is not ours to distribute, so web/assets is not tracked
by git; the build copies it next to the page. Without it the page uses a
serif font.
"""
import os
import shutil
import sys

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(WEB_DIR, "assets")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    font = os.path.join(sys.argv[1], "Fonts", "Zeus.ttf")
    if not os.path.isfile(font):
        sys.exit(f"{font} not found")
    os.makedirs(ASSETS_DIR, exist_ok=True)
    shutil.copyfile(font, os.path.join(ASSETS_DIR, "Zeus.ttf"))
    print(f"Font in {ASSETS_DIR}")


if __name__ == "__main__":
    main()
