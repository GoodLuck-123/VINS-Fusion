// Local, single-producer/single-consumer experiment. Pixel storage is shared;
// Unix SOCK_SEQPACKET carries bounded metadata and actual SCM_RIGHTS handles.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <vins/shared_frames.hpp>
#include <openssl/evp.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>
#include <linux/dma-heap.h>
#include <linux/dma-buf.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <vector>
#include <chrono>
#include <stdexcept>
#include <cstdio>
#include <algorithm>

namespace vins_ros {
namespace {
using Clock = std::chrono::steady_clock;
void require(bool condition, const char *message) { if (!condition) throw std::runtime_error(message); }
void checked(int result, const char *operation) {
    if (result < 0) throw std::runtime_error(std::string(operation) + ": " + std::strerror(errno));
}
struct Fd {
    int value = -1;
    explicit Fd(int fd = -1) : value(fd) {}
    ~Fd() { if (value >= 0) close(value); }
    Fd(const Fd &) = delete;
    Fd &operator=(const Fd &) = delete;
};
enum Kind : uint16_t { Hello=1, Buffer=2, Ready=3, Frame=4, Release=5, Done=6 };
enum Backend : uint32_t { Memfd=1, DmaHeap=2, Vgem=3 };
#pragma pack(push, 1)
struct Packet {
    uint32_t magic = 0x56465331;
    uint16_t version = 1, kind = 0;
    uint32_t backend = 0, slot = 0, slots = 0, width = 0, height = 0, stride = 0, camera = 0;
    uint64_t generation = 0, bytes = 0, device = 0, inode = 0;
    int64_t stamp_ns = 0;
    PixelHash hash{};
    uint32_t verify = 0;
};
#pragma pack(pop)
sockaddr_un address(const std::string &path) {
    sockaddr_un result{}; result.sun_family = AF_UNIX;
    require(!path.empty() && path.size() < sizeof(result.sun_path), "Unix socket path too long/empty");
    std::memcpy(result.sun_path, path.c_str(), path.size()+1);
    return result;
}
void sendPacket(int fd, const Packet &packet, int descriptor = -1) {
    iovec io{const_cast<Packet *>(&packet), sizeof(packet)};
    char control[CMSG_SPACE(sizeof(int))]{};
    msghdr message{}; message.msg_iov = &io; message.msg_iovlen = 1;
    if (descriptor >= 0) {
        message.msg_control = control; message.msg_controllen = sizeof(control);
        auto *header = CMSG_FIRSTHDR(&message);
        header->cmsg_level = SOL_SOCKET; header->cmsg_type = SCM_RIGHTS;
        header->cmsg_len = CMSG_LEN(sizeof(int));
        std::memcpy(CMSG_DATA(header), &descriptor, sizeof(int));
    }
    ssize_t count;
    do { count = sendmsg(fd, &message, MSG_NOSIGNAL); } while (count < 0 && errno == EINTR);
    checked(static_cast<int>(count), "sendmsg");
    require(count == sizeof(packet), "Incomplete metadata send");
}
bool receivePacket(int fd, Packet &packet, int &descriptor, const std::atomic<bool> &stop) {
    descriptor = -1;
    while (!stop.load()) {
        pollfd wait{fd, POLLIN, 0};
        int ready = poll(&wait, 1, 100);
        if (ready < 0 && errno == EINTR) continue;
        checked(ready, "poll");
        if (!ready) continue;
        char control[CMSG_SPACE(sizeof(int)*4)]{};
        iovec io{&packet, sizeof(packet)};
        msghdr message{}; message.msg_iov=&io; message.msg_iovlen=1;
        message.msg_control=control; message.msg_controllen=sizeof(control);
        const auto count=recvmsg(fd, &message, MSG_CMSG_CLOEXEC);
        if (count < 0 && errno == EINTR) continue;
        checked(static_cast<int>(count), "recvmsg");
        std::vector<int> handles;
        for (auto *header=CMSG_FIRSTHDR(&message); header; header=CMSG_NXTHDR(&message,header)) {
            if (header->cmsg_level==SOL_SOCKET && header->cmsg_type==SCM_RIGHTS) {
                const auto number=(header->cmsg_len-CMSG_LEN(0))/sizeof(int);
                const auto *values=reinterpret_cast<const int *>(CMSG_DATA(header));
                handles.insert(handles.end(),values,values+number);
            }
        }
        if (!count) { for (int handle:handles) close(handle); return false; }
        if (count!=sizeof(packet) || (message.msg_flags&(MSG_TRUNC|MSG_CTRUNC)) || handles.size()>1 ||
            packet.magic!=0x56465331 || packet.version!=1) {
            for (int handle:handles) close(handle);
            throw std::runtime_error("Malformed shared-frame packet");
        }
        if (!handles.empty()) descriptor=handles.front();
        return true;
    }
    return false;
}
void cpuSync(int fd, bool dma, uint64_t flags) {
    if (!dma) return;
    dma_buf_sync request{flags};
    int result;
    do { result=ioctl(fd,DMA_BUF_IOCTL_SYNC,&request); } while (result<0 && (errno==EINTR || errno==EAGAIN));
    checked(result,"DMA_BUF_IOCTL_SYNC");
}
struct Mapping {
    Fd fd;
    void *data = MAP_FAILED;
    size_t size = 0;
    uint32_t stride = 0;
    bool dma = false;
    std::atomic<bool> leased{false};
    uint64_t generation = 0;
    ~Mapping() { if (data != MAP_FAILED) munmap(data,size); }
    void map(bool writable) {
        data=mmap(nullptr,size,PROT_READ|(writable?PROT_WRITE:0),MAP_SHARED,fd.value,0);
        require(data!=MAP_FAILED,"Shared buffer mmap failed");
    }
};
std::shared_ptr<Mapping> allocate(const SharedOptions &options, uint32_t backend) {
    auto result=std::make_shared<Mapping>();
    result->stride=options.width; result->size=((uint64_t(options.width)*options.height+4095)/4096)*4096;
    result->dma=backend!=Memfd;
    if (backend==Memfd) {
        result->fd.value=memfd_create("vins-euroc-frame",MFD_CLOEXEC|MFD_ALLOW_SEALING);
        checked(result->fd.value,"memfd_create");
        checked(ftruncate(result->fd.value,result->size),"ftruncate");
        checked(fcntl(result->fd.value,F_ADD_SEALS,F_SEAL_SHRINK|F_SEAL_GROW|F_SEAL_SEAL),"memfd seals");
    } else if (backend==DmaHeap) {
        Fd allocator(open(options.device.c_str(),O_RDWR|O_CLOEXEC));
        checked(allocator.value,"open DMA heap");
        dma_heap_allocation_data request{}; request.len=result->size; request.fd_flags=O_RDWR|O_CLOEXEC;
        checked(ioctl(allocator.value,DMA_HEAP_IOCTL_ALLOC,&request),"DMA heap allocate");
        result->fd.value=request.fd;
    } else {
        Fd allocator(open(options.device.c_str(),O_RDWR|O_CLOEXEC));
        checked(allocator.value,"open VGEM");
        // Refuse unrelated graphics devices; this fixture does not allocate on a real GPU.
        char name[32]{}; drm_version version{}; version.name_len=sizeof(name)-1; version.name=name;
        checked(ioctl(allocator.value,DRM_IOCTL_VERSION,&version),"DRM version");
        require(std::string(name)=="vgem","Expected VGEM DRM device");
        drm_mode_create_dumb request{}; request.width=options.width; request.height=options.height; request.bpp=8;
        checked(ioctl(allocator.value,DRM_IOCTL_MODE_CREATE_DUMB,&request),"VGEM allocate");
        drm_prime_handle export_fd{}; export_fd.handle=request.handle; export_fd.flags=DRM_CLOEXEC|DRM_RDWR;
        const int status=ioctl(allocator.value,DRM_IOCTL_PRIME_HANDLE_TO_FD,&export_fd);
        const int saved_errno=errno;
        drm_mode_destroy_dumb release{}; release.handle=request.handle;
        ioctl(allocator.value,DRM_IOCTL_MODE_DESTROY_DUMB,&release);
        errno=saved_errno; checked(status,"VGEM DMA-BUF export");
        result->fd.value=export_fd.fd; result->stride=request.pitch; result->size=request.size;
    }
    require(result->stride>=options.width && result->size>=uint64_t(result->stride)*options.height,"Invalid allocator layout");
    result->map(true);
    return result;
}
struct Session {
    Fd fd;
    std::mutex send_mutex;
    void attach(int descriptor) { std::lock_guard<std::mutex> lock(send_mutex); fd.value=descriptor; }
    void shutdownSocket(int how) { std::lock_guard<std::mutex> lock(send_mutex); if(fd.value>=0) shutdown(fd.value,how); }
    void send(const Packet &packet) { std::lock_guard<std::mutex> lock(send_mutex); sendPacket(fd.value,packet); }
};
struct Lease {
    std::shared_ptr<Session> session;
    std::shared_ptr<Mapping> mapping;
    Packet packet;
    ~Lease() {
        try {
            cpuSync(mapping->fd.value,mapping->dma,DMA_BUF_SYNC_END|DMA_BUF_SYNC_READ);
            mapping->leased.store(false);
            packet.kind=Release; session->send(packet);
        } catch (const std::exception &error) { fprintf(stderr,"shared_release_error %s\n",error.what()); }
    }
};
} // namespace

PixelHash pixelHash(const cv::Mat &image) {
    require(image.type()==CV_8UC1,"Shared frame requires grayscale 8-bit pixels");
    std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> context(EVP_MD_CTX_new(),EVP_MD_CTX_free);
    require(context && EVP_DigestInit_ex(context.get(),EVP_sha256(),nullptr)==1,"SHA256 initialize");
    for (int row=0;row<image.rows;++row) require(EVP_DigestUpdate(context.get(),image.ptr(row),image.cols)==1,"SHA256 update");
    PixelHash hash{}; require(EVP_DigestFinal_ex(context.get(),hash.data(),nullptr)==1,"SHA256 finalize");
    return hash;
}
std::string hashText(const PixelHash &hash) {
    static const char digits[]="0123456789abcdef";
    std::string result; result.reserve(64);
    for (auto byte:hash) { result.push_back(digits[byte>>4]); result.push_back(digits[byte&15]); }
    return result;
}
struct ImageDigest::Impl {
    using Context=std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)>;
    Context context[2]{{nullptr,EVP_MD_CTX_free},{nullptr,EVP_MD_CTX_free}};
    Impl() { for (auto &item:context) { item.reset(EVP_MD_CTX_new()); require(item && EVP_DigestInit_ex(item.get(),EVP_sha256(),nullptr)==1,"Digest initialize"); } }
};
ImageDigest::ImageDigest() : impl_(std::make_unique<Impl>()) {}
ImageDigest::~ImageDigest() = default;
void ImageDigest::add(unsigned camera,int64_t stamp,const PixelHash &hash) {
    require(camera<2,"Invalid camera");
    require(EVP_DigestUpdate(impl_->context[camera].get(),&stamp,sizeof(stamp))==1 &&
            EVP_DigestUpdate(impl_->context[camera].get(),hash.data(),hash.size())==1,"Digest update");
}
std::string ImageDigest::value(unsigned camera) const {
    require(camera<2,"Invalid camera");
    std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> copy(EVP_MD_CTX_new(),EVP_MD_CTX_free);
    PixelHash hash{};
    require(copy && EVP_MD_CTX_copy_ex(copy.get(),impl_->context[camera].get())==1 &&
            EVP_DigestFinal_ex(copy.get(),hash.data(),nullptr)==1,"Digest finalize");
    return hashText(hash);
}

struct SharedWriter::Impl {
    SharedOptions options;
    uint32_t backend;
    Fd listener;
    std::shared_ptr<Session> session=std::make_shared<Session>();
    std::vector<std::shared_ptr<Mapping>> mappings;
    std::vector<bool> busy;
    std::mutex pool_mutex;
    std::condition_variable wake;
    std::thread worker;
    std::atomic<bool> stopped{false}, connected{false}, finished{false}, failed{false};
    uint64_t frames=0, copied_bytes=0, waits=0, reuses=0;
    ImageDigest digest;
    bool bound=false;
    explicit Impl(const SharedOptions &input) : options(input) {
        require(options.width>0 && options.height>0 && options.width<=16384 && options.height<=16384 &&
                options.slots>=4 && options.slots<=128,"Invalid pool dimensions/count");
        require(options.backend=="memfd" || options.backend=="dma_heap" || options.backend=="vgem","Unknown shared backend");
        backend=options.backend=="memfd"?Memfd:options.backend=="dma_heap"?DmaHeap:Vgem;
        auto addr=address(options.socket_path);
        // Never unlink a pre-existing socket that might belong to another run.
        require(access(options.socket_path.c_str(),F_OK)!=0,"Shared socket already exists");
        for (unsigned i=0;i<options.slots;++i) mappings.push_back(allocate(options,backend));
        busy.resize(options.slots,false);
        listener.value=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0); checked(listener.value,"socket");
        checked(bind(listener.value,reinterpret_cast<sockaddr *>(&addr),sizeof(addr)),"bind");
        bound=true;
        try {
        checked(chmod(options.socket_path.c_str(),0600),"socket permissions");
        checked(listen(listener.value,1),"listen");
        worker=std::thread([this] { serve(); });
        } catch (...) { unlink(options.socket_path.c_str()); throw; }
    }
    void serve() {
        try {
            while (!stopped.load()) {
                pollfd item{listener.value,POLLIN,0};
                int ready=poll(&item,1,100);
                if (ready<0 && errno==EINTR) continue;
                checked(ready,"accept poll"); if (!ready) continue;
                int client=accept4(listener.value,nullptr,nullptr,SOCK_CLOEXEC);
                checked(client,"accept"); session->attach(client); break;
            }
            if (stopped.load()) return;
            ucred peer{}; socklen_t peer_size=sizeof(peer);
            checked(getsockopt(session->fd.value,SOL_SOCKET,SO_PEERCRED,&peer,&peer_size),"peer credentials");
            require(peer.uid==getuid(),"Shared peer UID differs");
            printf("shared_peer local_pid=%d peer_pid=%d uid=%d\n",getpid(),peer.pid,peer.uid);
            timeval timeout{2,0}; setsockopt(session->fd.value,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
            Packet packet; packet.kind=Hello; packet.backend=backend; packet.slots=options.slots;
            packet.width=options.width; packet.height=options.height; packet.verify=options.verify_pixels;
            session->send(packet);
            for (unsigned i=0;i<mappings.size();++i) {
                struct stat info{}; checked(fstat(mappings[i]->fd.value,&info),"fstat");
                packet.kind=Buffer; packet.slot=i; packet.stride=mappings[i]->stride; packet.bytes=mappings[i]->size;
                packet.device=info.st_dev; packet.inode=info.st_ino;
                sendPacket(session->fd.value,packet,mappings[i]->fd.value);
            }
            int received_fd=-1;
            require(receivePacket(session->fd.value,packet,received_fd,stopped),"Consumer disconnected during registration");
            Fd guard(received_fd); require(packet.kind==Ready && received_fd<0,"Expected consumer Ready");
            connected.store(true); wake.notify_all();
            while (!stopped.load() && receivePacket(session->fd.value,packet,received_fd,stopped)) {
                Fd handle(received_fd);
                require(received_fd<0 && packet.kind==Release && packet.slot<busy.size(),"Invalid release");
                std::lock_guard<std::mutex> lock(pool_mutex);
                require(busy[packet.slot] && packet.generation==mappings[packet.slot]->generation,"Stale/duplicate release");
                busy[packet.slot]=false; wake.notify_all();
            }
            if (!stopped.load()) {
                std::lock_guard<std::mutex> lock(pool_mutex);
                require(finished.load() && std::none_of(busy.begin(),busy.end(),[](bool b){return b;}),"Consumer disconnected with active frames");
            }
        } catch (const std::exception &error) {
            if (!stopped.load()) { failed.store(true); fprintf(stderr,"shared_writer_error %s\n",error.what()); }
        }
        connected.store(false); wake.notify_all();
    }
    void stop() {
        stopped.store(true); wake.notify_all();
        session->shutdownSocket(SHUT_RDWR);
        if (worker.joinable()) worker.join();
    }
    ~Impl() {
        stop();
        unsigned outstanding=0; for (bool value:busy) outstanding+=value;
        printf("shared_writer backend=%s frames=%lu source_materializations=%lu source_bytes=%lu waits=%lu reuses=%lu outstanding=%u failed=%d sha0=%s sha1=%s\n",
               options.backend.c_str(),frames,frames,copied_bytes,waits,reuses,outstanding,failed.load(),
               digest.value(0).c_str(),digest.value(1).c_str());
        if (bound) unlink(options.socket_path.c_str());
    }
};
SharedWriter::SharedWriter(const SharedOptions &options) : impl_(std::make_unique<Impl>(options)) {}
SharedWriter::~SharedWriter() = default;
bool SharedWriter::ready() const { return impl_->connected.load() && !impl_->failed.load(); }
void SharedWriter::stop() { impl_->stop(); }
void SharedWriter::write(unsigned camera,int64_t stamp,const cv::Mat &image) {
    auto &p=*impl_;
    require(camera<2 && image.type()==CV_8UC1 && image.cols==int(p.options.width) &&
            image.rows==int(p.options.height),"Input does not match shared grayscale pool");
    unsigned slot=0;
    {
        std::unique_lock<std::mutex> lock(p.pool_mutex);
        auto free=[&] { return p.stopped.load() || p.failed.load() ||
            std::any_of(p.busy.begin(),p.busy.end(),[](bool value){return !value;}); };
        if (!free()) ++p.waits;
        require(p.wake.wait_for(lock,std::chrono::seconds(10),free),"Shared pool exhausted for 10 seconds");
        require(!p.stopped.load() && !p.failed.load() && p.connected.load(),"Shared producer stopped/disconnected");
        while (p.busy[slot]) ++slot;
        p.busy[slot]=true;
        if (p.mappings[slot]->generation++) ++p.reuses;
    }
    auto &mapping=*p.mappings[slot];
    cpuSync(mapping.fd.value,mapping.dma,DMA_BUF_SYNC_START|DMA_BUF_SYNC_WRITE);
    for (int row=0;row<image.rows;++row)
        std::memcpy(static_cast<unsigned char *>(mapping.data)+row*mapping.stride,image.ptr(row),image.cols);
    cpuSync(mapping.fd.value,mapping.dma,DMA_BUF_SYNC_END|DMA_BUF_SYNC_WRITE);
    Packet packet; packet.kind=Frame; packet.backend=p.backend; packet.slot=slot;
    packet.generation=mapping.generation; packet.camera=camera; packet.stamp_ns=stamp;
    if (p.options.verify_pixels) packet.hash=pixelHash(image);
    p.digest.add(camera,stamp,packet.hash);
    p.session->send(packet);
    ++p.frames; p.copied_bytes+=image.total();
}
void SharedWriter::finish() { impl_->finished.store(true); Packet packet; packet.kind=Done; impl_->session->send(packet); }

struct SharedReader::Impl {
    std::string path;
    std::function<void(SharedImage)> deliver;
    std::shared_ptr<Session> session=std::make_shared<Session>();
    std::vector<std::shared_ptr<Mapping>> mappings;
    std::atomic<bool> stopped{false}, failed{false};
    std::thread worker;
    uint32_t width=0,height=0,backend=0;
    bool verify=false,done=false;
    uint64_t frames=0,verified=0;
    ImageDigest digest;
    Impl(const std::string &socket_path,std::function<void(SharedImage)> callback) : path(socket_path),deliver(std::move(callback)) {
        address(path);
        worker=std::thread([this] { receive(); });
    }
    void receive() {
        try {
            const auto deadline=Clock::now()+std::chrono::seconds(30);
            while (!stopped.load()) {
                Fd candidate(socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0)); checked(candidate.value,"socket");
                auto addr=address(path);
                if (connect(candidate.value,reinterpret_cast<sockaddr *>(&addr),sizeof(addr))==0) { session->attach(candidate.value); candidate.value=-1; break; }
                require(Clock::now()<deadline,"Shared producer did not connect within 30 seconds");
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            }
            if (stopped.load()) return;
            ucred peer{}; socklen_t peer_size=sizeof(peer);
            checked(getsockopt(session->fd.value,SOL_SOCKET,SO_PEERCRED,&peer,&peer_size),"peer credentials");
            require(peer.uid==getuid(),"Shared peer UID differs");
            printf("shared_peer local_pid=%d peer_pid=%d uid=%d\n",getpid(),peer.pid,peer.uid);
            timeval timeout{2,0}; setsockopt(session->fd.value,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
            Packet packet; int received_fd=-1;
            require(receivePacket(session->fd.value,packet,received_fd,stopped),"Missing shared Hello");
            Fd hello_fd(received_fd);
            require(packet.kind==Hello && received_fd<0 && packet.slots>=4 && packet.slots<=128 &&
                    packet.width>0 && packet.height>0 && packet.width<=16384 && packet.height<=16384 &&
                    packet.backend>=Memfd && packet.backend<=Vgem,"Invalid shared Hello");
            width=packet.width; height=packet.height; backend=packet.backend; verify=packet.verify;
            const unsigned slots=packet.slots;
            for (unsigned slot=0;slot<slots;++slot) {
                require(receivePacket(session->fd.value,packet,received_fd,stopped),"Missing buffer registration");
                Fd guard(received_fd);
                require(packet.kind==Buffer && packet.slot==slot && received_fd>=0 &&
                        packet.stride>=width && packet.bytes>=uint64_t(packet.stride)*height &&
                        packet.bytes<=512ull*1024*1024,"Invalid shared buffer");
                struct stat info{}; checked(fstat(received_fd,&info),"import fstat");
                const auto actual_bytes=lseek(received_fd,0,SEEK_END);
                require(actual_bytes>=0 && uint64_t(actual_bytes)>=packet.bytes,"Shared buffer size differs");
                require(uint64_t(info.st_dev)==packet.device && uint64_t(info.st_ino)==packet.inode,"Imported handle identity differs");
                auto mapping=std::make_shared<Mapping>(); mapping->fd.value=guard.value; guard.value=-1;
                mapping->stride=packet.stride; mapping->size=packet.bytes; mapping->dma=backend!=Memfd;
                mapping->map(false); mappings.push_back(mapping);
                if (slot<2) printf("shared_buffer slot=%u backend=%u device=%lu inode=%lu stride=%u bytes=%lu\n",
                                  slot,backend,packet.device,packet.inode,packet.stride,packet.bytes);
            }
            packet.kind=Ready; session->send(packet);
            while (!stopped.load() && receivePacket(session->fd.value,packet,received_fd,stopped)) {
                Fd guard(received_fd);
                require(received_fd<0,"Unexpected frame handle");
                if (packet.kind==Done) { done=true; continue; }
                require(packet.kind==Frame && packet.slot<mappings.size() && packet.camera<2 &&
                        packet.backend==backend,"Invalid shared frame");
                auto mapping=mappings[packet.slot];
                require(!mapping->leased.exchange(true) && packet.generation==mapping->generation+1,"Reused live/stale slot");
                mapping->generation=packet.generation;
                cpuSync(mapping->fd.value,mapping->dma,DMA_BUF_SYNC_START|DMA_BUF_SYNC_READ);
                auto lease=std::make_shared<Lease>(); lease->session=session; lease->mapping=mapping; lease->packet=packet;
                ImageFrame frame; frame.memory_owner=lease; frame.shared=true;
                frame.image=cv::Mat(height,width,CV_8UC1,mapping->data,mapping->stride);
                if (verify) { require(pixelHash(frame.image)==packet.hash,"Shared pixel SHA256 mismatch"); ++verified; }
                digest.add(packet.camera,packet.stamp_ns,packet.hash);
                ++frames;
                deliver(SharedImage{packet.camera,packet.stamp_ns,std::move(frame)});
            }
            require(stopped.load() || done,"Shared producer disconnected before Done");
        } catch (const std::exception &error) {
            if (!stopped.load()) { failed.store(true); fprintf(stderr,"shared_reader_error %s\n",error.what()); }
        }
    }
    void stop() {
        stopped.store(true);
        // Keep writes usable for outstanding leases' releases during node teardown.
        session->shutdownSocket(SHUT_RD);
        if (worker.joinable()) worker.join();
    }
    ~Impl() {
        stop();
        printf("shared_reader backend=%u frames=%lu verified=%lu failed=%d sha0=%s sha1=%s\n",
               backend,frames,verified,failed.load(),digest.value(0).c_str(),digest.value(1).c_str());
    }
};
SharedReader::SharedReader(const std::string &path,std::function<void(SharedImage)> deliver)
    : impl_(std::make_unique<Impl>(path,std::move(deliver))) {}
SharedReader::~SharedReader() = default;
void SharedReader::stop() { impl_->stop(); }
} // namespace vins_ros
