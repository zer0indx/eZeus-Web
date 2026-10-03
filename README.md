<h1 align="center">eZeus Web</h1>

eZeus Web is a browser (WebAssembly) port of [eZeus](https://github.com/MaurycyLiebner/eZeus), the open-source implementation of Zeus: Master of Olympus by Maurycy Liebner.

The game runs in Chrome, Edge, Firefox or Safari. It does not include any game files: on the first launch you choose your own Zeus and Poseidon folder, with an eZeus release inside, and the files are copied into the browser's storage. Saves are kept in the browser and can be downloaded and uploaded as a ZIP.

**[How to build and run the web version](web/README.md)**

It can also be self-hosted as a private Docker service with a sign-in, the game files provided by the server and saves that follow you between browsers: see [Self-hosting](web/README.md#self-hosting).

The desktop build still works as in eZeus; everything below is the original eZeus README.

---

<h1 align="center">eZeus</h1>

eZeus is an open-source implementation of Zeus: Master of Olympus game

[Watch trailers](https://www.youtube.com/@eZeus-e)

Please note that eZeus is not an exact copy of the original game. There are some minor differences, most of which are accidental, as well as optional additional features (such as a new walker implementation and the ability to build two cities at once). eZeus supports the original game’s adventures, and the overall experience should be similar to the original.

## How To Play

To play eZeus you will need original game files (Zeus: Master of Olympus base game and Poseidon expansion).

Currently only English and Polish versions are supported due to font glyphs limitations.

Only windows binaries are provided. If you want to play on Linux you have to build eZeus yourself.

[You can download eZeus from GitHub](https://github.com/MaurycyLiebner/eZeus/releases)

## How To Build on macOS

You need these dependencies for x86 and ARM Builds: 
```
softwareupdate --install-rosetta
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
arch -x86_64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install sdl2 sdl2_mixer sdl2_image sdl2_ttf git qt make dylibbundler fluid-synth
arch -x86_64 /usr/local/bin/brew install sdl2 sdl2_mixer sdl2_image sdl2_ttf git qt make dylibbundler fluid-synth
```
Clone the eZeus repository:
```
git clone --recurse-submodules https://github.com/MaurycyLiebner/eZeus
```
Than simply execute compile_apple.sh script. All is done automatic. At the End you should have 2 new folders. build_arm and build_x86. Follow the instructions at the end of the script.

Or you could DL ready to go Binaries straight forward here:
https://github.com/MacThings/eZeus/releases/tag/Zeus-Binaries

## How To Build on Linux

Make sure you have **git** installed on your system.

Clone the eZeus repository:
```
git clone --recurse-submodules https://github.com/MaurycyLiebner/eZeus
```

You will need to install following packages:

```
sudo apt install libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev libsdl2-mixer-dev libnoise-dev g++
```

You will need Qt Creator (qt.io).

Open eZeus.pro in Qt Creator and use it to build eZeus.

Before running eZeus binary make sure to setup all files as specified in **How To Play** section and the release description. Put eZeus binary in (...)/Zeus and Poseidon/eZeus/Bin directory and run it.

## Authors

**Maurycy Liebner** - 2021 - 2025 - [MaurycyLiebner](https://github.com/MaurycyLiebner)
