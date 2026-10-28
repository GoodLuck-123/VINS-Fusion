#include "gnw_protocol.h"
#include <cassert>
#include <limits>
int main() {
    std::array<uint8_t,54> f{}; f[0]=0x55;f[1]=0xd1;f[3]=2;
    float acceleration=9.81f;std::memcpy(f.data()+4+3*4,&acceleration,4);
    auto checksum=[](std::array<uint8_t,54>& x){uint16_t s=0;for(int i=0;i<52;++i)s+=x[i];x[52]=s&255;x[53]=s>>8;};checksum(f);
    gnw::Parser p;
    for(size_t split=0;split<=54;++split) {
        gnw::Parser q;auto a=q.feed(f.data(),split);auto b=q.feed(f.data()+split,54-split);
        assert(a.size()+b.size()==1);auto out=a.empty()?b[0]:a[0];assert(out.values[3]==acceleration);
    }
    std::vector<uint8_t> noise(20000,0x55);assert(p.feed(noise.data(),noise.size()).empty());
    auto corrupt=f;corrupt[20]^=1;assert(p.feed(corrupt.data(),54).empty());
    std::vector<uint8_t> pair(f.begin(),f.end());pair.insert(pair.end(),f.begin(),f.end());
    auto result=p.feed(pair.data(),pair.size());assert(result.size()==2 && p.bad_checksum>0);
    assert(result[0].bytes==f);
    // Preserve protocol values (including invalid floats); the adapter rejects them.
    float nan=std::numeric_limits<float>::quiet_NaN();std::memcpy(f.data()+4,&nan,4);checksum(f);
    assert(std::isnan(p.feed(f.data(),54)[0].values[0]));
}
