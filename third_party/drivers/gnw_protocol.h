#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

// GNW-500 observed wire format: 55 d1 00 02, 12 little-endian floats,
// then little-endian SUM16 over the preceding 52 bytes. No device clock.
namespace gnw {
struct Frame { std::array<uint8_t,54> bytes; std::array<float,12> values; };
class Parser {
    std::vector<uint8_t> pending;
public:
    unsigned long bad_checksum=0, discarded=0;
    std::vector<Frame> feed(const uint8_t* data, size_t n) {
        std::vector<Frame> frames;
        // Consume incrementally: storage remains bounded even for arbitrary input.
        for(size_t i=0;i<n;++i) {
            pending.push_back(data[i]);
            while(!pending.empty() && (pending[0]!=0x55 ||
                  (pending.size()>1 && pending[1]!=0xd1) ||
                  (pending.size()>2 && pending[2]!=0) ||
                  (pending.size()>3 && pending[3]!=2))) {
                pending.erase(pending.begin()); ++discarded;
            }
            if(pending.size()!=54) continue;
            uint16_t sum=0;
            for(size_t j=0;j<52;++j) sum+=pending[j];
            if(sum!=static_cast<uint16_t>(pending[52]|(pending[53]<<8))) {
                ++bad_checksum; pending.erase(pending.begin()); continue;
            }
            Frame f;
            std::copy(pending.begin(),pending.end(),f.bytes.begin());
            for(size_t j=0;j<12;++j) {
                uint32_t bits=0;
                for(size_t b=0;b<4;++b) bits|=uint32_t(pending[4+j*4+b])<<(8*b);
                std::memcpy(&f.values[j],&bits,4);
            }
            frames.push_back(f); pending.clear();
        }
        return frames;
    }
};
}
