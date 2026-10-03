#include "qfile.h"

#include <algorithm>
#include <cstring>
#include <fstream>

QFile::QFile(const std::string& filename) {
    std::ifstream file(filename, std::ios::in | std::ios::binary);
    if(!file) return;
    file.seekg(0, std::ios::end);
    const auto size = file.tellg();
    file.seekg(0, std::ios::beg);
    if(size < 0) return;
    mData.resize(static_cast<size_t>(size));
    file.read(mData.data(), size);
    mOpen = static_cast<bool>(file);
}

void QFile::reset() {
    seek(0);
}

bool QFile::isReadable() {
    return mOpen;
}

bool QFile::atEnd() {
    return mPos >= size();
}

void QFile::close() {
    mOpen = false;
    mData.clear();
    mData.shrink_to_fit();
    mPos = 0;
}

int64_t QFile::size() const {
    return static_cast<int64_t>(mData.size());
}

int64_t QFile::pos() {
    return mPos;
}

void QFile::seek(const int64_t pos) {
    mPos = std::max<int64_t>(0, pos);
}

int64_t QFile::read(char* const data, const int64_t maxSize) {
    const int64_t remLen = std::max<int64_t>(0, size() - mPos);
    const int64_t len = std::min(remLen, maxSize);
    if(len <= 0) return 0;
    std::memcpy(data, mData.data() + mPos, static_cast<size_t>(len));
    mPos += len;
    return len;
}

bool QFile::getChar(char* const data) {
    if(atEnd()) return false;
    *data = mData[static_cast<size_t>(mPos)];
    mPos++;
    return true;
}
