#define SDL_MAIN_HANDLED
#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL_mixer.h>

#include <string>
#include <algorithm>

#include <filesystem>

#include "emainwindow.h"
#include "textures/egametextures.h"

#include "egamedir.h"
#include "enumbers.h"

#include "audio/emusic.h"
#include "audio/esounds.h"

#ifdef __EMSCRIPTEN__
#include <emscripten/wasmfs.h>

// The browser loader copies the game files into the Origin Private File
// System; mount it where eGameDir expects the Zeus installation.
static bool mountGameFiles() {
    const auto opfs = wasmfs_create_opfs_backend();
    if(!opfs) return false;
    return wasmfs_create_directory("/zeus", 0777, opfs) == 0;
}
#endif

bool init() {
    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) < 0) {
        printf("SDL could not initialize! SDL Error: %s\n",
               SDL_GetError());
        return false;
    }

    if(!SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "1")) {
        printf("Warning: Linear texture filtering not enabled!");
    }

    const int imgFlags = IMG_INIT_PNG;
    if(!(IMG_Init(imgFlags) & imgFlags)) {
        printf("SDL_image could not initialize! SDL_image Error: %s\n",
               IMG_GetError());
        return false;
    }

    if(Mix_OpenAudio(44100, MIX_DEFAULT_FORMAT, 2, 2048) < 0) {
        printf("SDL_mixer could not initialize! SDL_mixer Error: %s\n",
               Mix_GetError());
        return false;
    }

    if(TTF_Init()) {
        printf("SDL_ttf could not initialize! SDL_ttf Error: %s\n",
               TTF_GetError());
        return false;
    }

    return true;
}

void close() {
    TTF_Quit();
    IMG_Quit();
    Mix_Quit();
    SDL_Quit();
}

bool getDisplayResolution(SDL_DisplayMode& mode) {
    int display_count = 0, display_index = 0, mode_index = 0;
    mode = { SDL_PIXELFORMAT_UNKNOWN, 0, 0, 0, 0 };

    if((display_count = SDL_GetNumVideoDisplays()) < 1) {
        SDL_Log("SDL_GetNumVideoDisplays returned: %i", display_count);
        return false;
    }

    if(SDL_GetDisplayMode(display_index, mode_index, &mode) != 0) {
        SDL_Log("SDL_GetDisplayMode failed: %s", SDL_GetError());
        return false;
    }
    SDL_Log("SDL_GetDisplayMode(0, 0, &mode):\t\t%i bpp\t%i x %i",
    SDL_BITSPERPIXEL(mode.format), mode.w, mode.h);

    return true;
}

bool getDisplayResolutions(std::vector<SDL_DisplayMode>& resolutions) {
    const int display_count = SDL_GetNumVideoDisplays();

    SDL_Log("Number of displays: %i", display_count);

    for(int display_index = 0; display_index <= display_count; display_index++) {
        SDL_Log("Display %i:", display_index);

        const int modes_count = SDL_GetNumDisplayModes(display_index);

        for(int mode_index = 0; mode_index <= modes_count; mode_index++) {
            SDL_DisplayMode mode = { SDL_PIXELFORMAT_UNKNOWN, 0, 0, 0, 0 };

            if (SDL_GetDisplayMode(display_index, mode_index, &mode) == 0) {
                SDL_Log(" %i bpp\t%i x %i @ %iHz",
                    SDL_BITSPERPIXEL(mode.format), mode.w, mode.h, mode.refresh_rate);

                resolutions.push_back(mode);
            }
        }
    }
    return true;
}

int main() {
#ifdef __EMSCRIPTEN__
    if(!mountGameFiles()) {
        printf("Failed to mount browser storage!\n");
        return 1;
    }
#endif
    if(!init()) {
        printf("Failed to initialize!\n");
        close();
        return 1;
    }

    eGameDir::initialize();

//    SDL_DisplayMode mode;
//    const bool r0 = getDisplayResolution(mode);
//    eResolution resolution;
//    if(r0) {
//        resolution = eResolution(mode.w, mode.h);
//    } else {
//        resolution = eResolution(1280, 720);
//    }

//    std::vector<SDL_DisplayMode> resolutions;
//    const bool r1 = getDisplayResolutions(resolutions);
//    if(r1 && !resolutions.empty()) {
//        eResolution::sResolutions = std::vector<eResolution>();
//        for(const auto& m : resolutions) {
//            eResolution::sResolutions.emplace_back(m.w, m.h);
//        }
//    }
    std::vector<SDL_DisplayMode> ress;
    const int displayCount = SDL_GetNumVideoDisplays();

    for(int i = 0; i < displayCount; i++) {
        SDL_DisplayMode dm;
        SDL_GetCurrentDisplayMode(i, &dm);
        bool contains = false;
        for(const auto& rr : eResolution::sResolutions) {
            contains = dm.w == rr.width() &&
                       dm.h == rr.height();
            if(contains) break;
        }
        if(!contains) {
            const auto res = eResolution(dm.w, dm.h);
            eResolution::sResolutions.push_back(res);
        }
    }

    if(!std::filesystem::exists(eGameDir::iBinaryPath())) {
        printf("Could not find interface textures!\n"
               "Make sure you have interface.e file in eZeus directory.\n");
        close();
        return 1;
    }

    eNumbers::sLoad();
    eSettings settings;
    settings.read();
#ifdef __EMSCRIPTEN__
    settings.fRes = eMainWindow::sViewportResolution();
    if(std::find(eResolution::sResolutions.begin(),
                 eResolution::sResolutions.end(),
                 settings.fRes) == eResolution::sResolutions.end()) {
        eResolution::sResolutions.push_back(settings.fRes);
    }
#endif
    bool found = false;
    const auto checkTextureSize = [&found](const std::string& path,
                                           bool& setting) {
        if(!setting) return;
        setting = std::filesystem::exists(path);
        if(setting) found = true;
    };
    checkTextureSize(eGameDir::i15BinaryPath(), settings.fTinyTextures);
    checkTextureSize(eGameDir::i30BinaryPath(), settings.fSmallTextures);
    checkTextureSize(eGameDir::i45BinaryPath(), settings.fMediumTextures);
    checkTextureSize(eGameDir::i60BinaryPath(), settings.fLargeTextures);
    if(!found) {
        printf("Could not find any textures!\n"
               "Make sure you have i15.e, i30.e, i45.e, or i60.e file in eZeus directory.\n");
        close();
        return 1;
    }

    int r = 0;
#ifdef __EMSCRIPTEN__
    // The browser main loop outlives main(), so keep everything on the heap.
    new eMusic;
    new eSounds;
    const auto w = new eMainWindow;
    if(!w->initialize(settings)) return 1;
    if(!eGameTextures::initialize(w->renderer())) return 1;
    return w->exec();
#endif
    {
        eMusic music;
        eSounds sounds;
        eMainWindow w;
        const bool i = w.initialize(settings);
        if(!i) return 1;
        const bool e = eGameTextures::initialize(w.renderer());

        if(e) r = w.exec();
    }

    close();

    return r;
}
