"""Which files of a Zeus and Poseidon folder eZeus needs.

Shared by make_client.py and server.py. Keep in sync with targetPath() in
shell.html.
"""
import os

# Installers, Windows binaries, manuals, FMV videos and the original game's
# text and setup files (eZeus has its own .xml copies).
SKIP_EXT = {"exe", "dll", "pdf", "zip", "lnk", "ico", "asi", "m3d", "msg",
            "hashdb", "bik", "eng", "dat", "info", "inf", "ini"}
SKIP_DIRS = {"binks"}
# eZeus only checks that these exist; their contents are never read.
EMPTY_DIRS = ["DATA"]


def find_ezeus_dir(game_dir):
    """Name of the eZeus release folder inside the game folder, or None."""
    try:
        names = os.listdir(game_dir)
    except OSError:
        return None
    for name in names:
        path = os.path.join(game_dir, name)
        if (name.lower().startswith("ezeus") and os.path.isdir(path)
                and os.path.isfile(os.path.join(path, "interface.e"))):
            return name
    return None


def needed(rel_parts):
    """Whether a file (path parts relative to the game folder) is needed."""
    name = rel_parts[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    dirs = [d.lower() for d in rel_parts[:-1]]
    if ext in SKIP_EXT or any(d in SKIP_DIRS for d in dirs):
        return False
    if dirs and dirs[0] in (d.lower() for d in EMPTY_DIRS):
        return False
    return True


def walk_needed(game_dir):
    """Yields (parts, full_path) for every needed file.

    Skips hidden folders and eZeus folders other than the release one (e.g. a
    source checkout). The release folder keeps its own name in parts.
    """
    ezeus = find_ezeus_dir(game_dir)
    for root, dirs, files in os.walk(game_dir):
        rel_root = os.path.relpath(root, game_dir)
        if rel_root == ".":
            dirs[:] = [d for d in dirs if not d.startswith(".") and
                       not (d.lower().startswith("ezeus") and d != ezeus)]
        dirs.sort()
        for name in sorted(files):
            parts = [] if rel_root == "." else rel_root.split(os.sep)
            parts.append(name)
            if needed(parts):
                yield parts, os.path.join(root, name)
