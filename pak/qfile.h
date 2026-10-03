#ifndef QFILE_H
#define QFILE_H

#include <string>
#include <vector>
#include <cstdint>

// Read-only file loaded into memory at once. The pak parser reads mostly
// single bytes and asks for the position all the time, which is very slow
// on a stream backed by browser storage.
class QFile {
public:
    QFile(const std::string& filename);

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
    bool mOpen = false;
    std::vector<char> mData;
    int64_t mPos = 0;
};

#endif // QFILE_H
