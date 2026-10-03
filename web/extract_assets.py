"""Copies the start page's art from the game files into web/assets.

Usage: python web/extract_assets.py <eZeus folder>
       python web/extract_assets.py --index <file>

The eZeus folder is the one with interface.e and Fonts/Zeus.ttf (e.g.
"Zeus and Poseidon/eZeus-0.8.2-beta" or "eZeus Web Client/eZeus"). The
files belong to the game, so web/assets is not tracked by git; the build
copies it next to the page.

With --index it writes where the painting is inside the game files instead,
for web/server.py, which then takes the art from the game folder it serves.
"""
import json
import os
import re
import shutil
import sys

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(WEB_DIR, "assets")
# The main menu painting, as stored in interface.e.
MENU_IMAGE = "60/Zeus_Data_Images/Zeus_FE_Registry.jpg"


def binary_entry(name):
    path = os.path.join(WEB_DIR, "..", "esplitbinary.h")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'\{"' + re.escape(name) +
                  r'", eBinaryData\{eFileId::(\w+), (\d+), (\d+)\}\}', src)
    if not m:
        sys.exit(f"{name} not found in esplitbinary.h")
    files = {"i": "interface.e", "i15": "i15.e", "i30": "i30.e",
             "i45": "i45.e", "i60": "i60.e"}
    return files[m.group(1)], int(m.group(2)), int(m.group(3))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--index":
        file, pos, size = binary_entry(MENU_IMAGE)
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            json.dump({"menu.jpg": {"file": file, "pos": pos, "size": size}}, f)
        return
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ezeus_dir = sys.argv[1]
    os.makedirs(ASSETS_DIR, exist_ok=True)

    file, pos, size = binary_entry(MENU_IMAGE)
    with open(os.path.join(ezeus_dir, file), "rb") as f:
        f.seek(pos)
        data = f.read(size)
    if data[:3] != b"\xff\xd8\xff":
        sys.exit(f"{file} does not match this eZeus version")
    with open(os.path.join(ASSETS_DIR, "menu.jpg"), "wb") as f:
        f.write(data)

    shutil.copyfile(os.path.join(ezeus_dir, "Fonts", "Zeus.ttf"),
                    os.path.join(ASSETS_DIR, "Zeus.ttf"))
    print(f"Assets in {ASSETS_DIR}")


if __name__ == "__main__":
    main()
