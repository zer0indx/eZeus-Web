#include "ebinaryimageloader.h"

#include <cstdio>

#include "esplitbinary.h"
#include "egamedir.h"

std::shared_ptr<eTexture> eBinaryImageLoader::load(SDL_Renderer* const r,
                                                   const std::string& path) {
    const auto it = eBinaryDataMap.find(path);
    if(it == eBinaryDataMap.end()) {
        printf("Could not find '%s' image\n", path.c_str());
        return nullptr;
    }
    const auto& bd = it->second;
    std::string epath;
    switch(bd.fFileId) {
    case eFileId::i:
        epath = eGameDir::iBinaryPath();
        break;
    case eFileId::i15:
        epath = eGameDir::i15BinaryPath();
        break;
    case eFileId::i30:
        epath = eGameDir::i30BinaryPath();
        break;
    case eFileId::i45:
        epath = eGameDir::i45BinaryPath();
        break;
    case eFileId::i60:
        epath = eGameDir::i60BinaryPath();
        break;
    }

    // stdio reads the whole image in one call; std::ifstream splits it into
    // small buffered reads, which are very slow on browser storage.
    const auto file = std::fopen(epath.c_str(), "rb");
    if(!file) {
        printf("Could not open '%s'\n", epath.c_str());
        return nullptr;
    }

    const auto data = new char[bd.fSize];
    std::fseek(file, bd.fPos, SEEK_SET);
    std::fread(data, 1, bd.fSize, file);
    std::fclose(file);
    const auto rw = SDL_RWFromMem(data, bd.fSize);
    const auto surf = IMG_Load_RW(rw, SDL_FALSE);
    if(!surf) {
        printf("Unable to load image %s! SDL_image Error: %s\n",
               path.c_str(), IMG_GetError());
        return nullptr;
    }
    delete[] data;

    const auto tex = std::make_shared<eTexture>();
    tex->load(r, surf);

    return tex;
}
