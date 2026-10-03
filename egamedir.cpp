#include "egamedir.h"

#include <SDL2/SDL_filesystem.h>
#include <fstream>

std::string eGameDir::sPath;

void eGameDir::initialize() {
    sPath = exeDir() + "../../";
    const auto zp = exeDir() + "../zeus_path.txt";
    std::ifstream file(zp);
    if(!file.good()) return;
    std::string str;
    const bool g = !!std::getline(file, str);
    if(!g) return;
    sPath = exeDir() + str;
}

std::string eGameDir::path(const std::string& path) {
    return sPath + path;
}

std::string eGameDir::settingsPath() {
    return exeDir() + "../settings.txt";
}

std::string eGameDir::numbersPath() {
    return exeDir() + "../numbers.txt";
}

std::string eGameDir::iBinaryPath() {
    return exeDir() + "../interface.e";
}

std::string eGameDir::i15BinaryPath() {
    return exeDir() + "../i15.e";
}

std::string eGameDir::i30BinaryPath() {
    return exeDir() + "../i30.e";
}

std::string eGameDir::i45BinaryPath() {
    return exeDir() + "../i45.e";
}

std::string eGameDir::i60BinaryPath() {
    return exeDir() + "../i60.e";
}

std::string eGameDir::exeDir() {
#ifdef __EMSCRIPTEN__
    // Mirrors the native layout: <Zeus>/eZeus/Bin/eZeus.exe
    return "/zeus/eZeus/Bin/";
#endif
    const auto d = SDL_GetBasePath();
    const std::string str(d);
    return str;
}

std::string eGameDir::adventuresDir() {
    return exeDir() + "../Adventures/";
}

std::string eGameDir::pakAdventuresDir() {
    // return "/home/ailuropoda/.eZeus/Zeus/Adventures/"; // !!!
    return eGameDir::path("Adventures/");
}

std::string eGameDir::saveDir() {
    return exeDir() + "../Save/";
}

std::string eGameDir::texturesDir() {
    return exeDir() + "../Textures/";
}
