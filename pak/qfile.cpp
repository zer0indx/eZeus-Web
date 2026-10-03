#include "qfile.h"

#include <algorithm>
#include <cstring>

namespace {
    const int64_t gBlockSize = 64*1024;
}

QFile::QFile(const std::string& filename) {
    mFile = std::fopen(filename.c_str(), "rb");
    if(!mFile) return;
    std::fseek(mFile, 0, SEEK_END);
    mSize = std::max<int64_t>(0, std::ftell(mFile));
}

QFile::~QFile() {
    close();
}

void QFile::reset() {
    seek(0);
}

bool QFile::isReadable() {
    return mFile;
}

bool QFile::atEnd() {
    return mPos >= mSize;
}

void QFile::close() {
    if(mFile) std::fclose(mFile);
    mFile = nullptr;
    mBlock.clear();
    mBlockStart = -1;
}

int64_t QFile::size() const {
    return mSize;
}

int64_t QFile::pos() {
    return mPos;
}

void QFile::seek(const int64_t pos) {
    mPos = std::max<int64_t>(0, pos);
}

bool QFile::loadBlock(const int64_t pos) {
    if(!mFile) return false;
    const int64_t start = pos - pos % gBlockSize;
    if(start == mBlockStart) return true;
    const int64_t len = std::min(gBlockSize, mSize - start);
    if(len <= 0) return false;
    mBlock.resize(static_cast<size_t>(len));
    std::fseek(mFile, static_cast<long>(start), SEEK_SET);
    const auto r = std::fread(mBlock.data(), 1, mBlock.size(), mFile);
    mBlock.resize(r);
    mBlockStart = start;
    return r > 0;
}

int64_t QFile::read(char* const data, const int64_t maxSize) {
    const int64_t remLen = std::max<int64_t>(0, mSize - mPos);
    const int64_t len = std::min(remLen, maxSize);
    int64_t done = 0;
    while(done < len) {
        if(!loadBlock(mPos)) break;
        const int64_t off = mPos - mBlockStart;
        const int64_t avail = static_cast<int64_t>(mBlock.size()) - off;
        if(avail <= 0) break;
        const int64_t n = std::min(len - done, avail);
        std::memcpy(data + done, mBlock.data() + off, static_cast<size_t>(n));
        done += n;
        mPos += n;
    }
    return done;
}

bool QFile::getChar(char* const data) {
    if(atEnd()) return false;
    return read(data, 1) == 1;
}
