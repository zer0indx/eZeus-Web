#ifndef QFILE_H
#define QFILE_H

#include <string>
#include <vector>
#include <cstdint>
#include <cstdio>

// Read-only file read through a block cache. The pak parser reads mostly
// single bytes and asks for the position all the time, which is very slow
// on a plain stream backed by browser storage, while some callers only
// need a few bytes from far into the file.
class QFile {
public:
    QFile(const std::string& filename);
    ~QFile();

    QFile(const QFile&) = delete;
    QFile& operator=(const QFile&) = delete;

    void reset();

    bool isReadable();
    bool atEnd();

    void close();
    int64_t size() const;
    int64_t pos();

    void seek(const int64_t pos);

    int64_t read(char* const data, const int64_t maxSize);

    bool getChar(char* const data);
private:
    bool loadBlock(const int64_t pos);

    std::FILE* mFile = nullptr;
    int64_t mSize = 0;
    int64_t mPos = 0;

    std::vector<char> mBlock;
    int64_t mBlockStart = -1;
};

#endif // QFILE_H
