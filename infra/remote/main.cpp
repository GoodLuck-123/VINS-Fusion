#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using Args = std::vector<std::string>;

std::string quote(const std::string& text) {
    std::string result = "'";
    for (char c : text) result += c == '\'' ? "'\\''" : std::string(1, c);
    return result + "'";
}

int execute(const Args& args) {
    std::vector<char*> argv;
    for (const auto& arg : args) argv.push_back(const_cast<char*>(arg.c_str()));
    argv.push_back(nullptr);
    pid_t child = fork();
    if (child < 0) throw std::runtime_error(std::strerror(errno));
    if (child == 0) {
        execvp(argv.front(), argv.data());
        std::cerr << "Cannot execute " << args.front() << ": " << std::strerror(errno) << '\n';
        _exit(127);
    }
    int status;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) throw std::runtime_error(std::strerror(errno));
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}

Args ssh(const std::string& target, const std::string& command) {
    return {"ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o",
            "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", target, command};
}

int copy(const std::string& source, const std::string& destination) {
    // Explicit legacy scp gives remote paths a defined POSIX shell quoting rule.
    // Authentication/encryption still use OpenSSH; no password is stored here.
    return execute({"scp", "-O", "-r", "-p", "-o", "BatchMode=yes", "-o",
                    "ConnectTimeout=10", "--", source, destination});
}

void require(int code, const std::string& action) {
    if (code) throw std::runtime_error(action + " failed (exit " + std::to_string(code) + ")");
}

int main(int argc, char** argv) {
    try {
        if (argc < 3) {
            std::cerr << "Usage: vins-remote USER@HOST FILE_OR_DIR [--dest REMOTE_DIR]\n"
                         "       vins-remote USER@HOST PAYLOAD --run SCRIPT --output LOCAL_DIR"
                         " [--dest JOB_PARENT] [--timeout SECONDS]\n"
                         "       vins-remote USER@HOST REMOTE_JOB --collect LOCAL_DIR\n";
            return 2;
        }
        const std::string target = argv[1], source = argv[2];
        if (!std::regex_match(target, std::regex("[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*")))
            throw std::runtime_error("Use USER@HOST with an IPv4 address or hostname");
        std::string destination, script, output, collect;
        unsigned timeout = 3600;
        for (int i = 3; i < argc; ++i) {
            const std::string option = argv[i];
            if (++i >= argc) throw std::runtime_error("Missing value for " + option);
            const std::string value = argv[i];
            if (option == "--dest") destination = value;
            else if (option == "--run") script = value;
            else if (option == "--output") output = value;
            else if (option == "--collect") collect = value;
            else if (option == "--timeout") {
                if (!std::regex_match(value, std::regex("[0-9]+")))
                    throw std::runtime_error("Timeout must be an integer");
                auto number = std::stoul(value);
                if (number < 1 || number > 604800) throw std::runtime_error("Timeout must be 1..604800 seconds");
                timeout = static_cast<unsigned>(number);
            } else throw std::runtime_error("Unknown option: " + option);
        }
        if (!collect.empty()) {
            if (!script.empty() || !output.empty() || !destination.empty())
                throw std::runtime_error("Collect cannot be combined with upload/run options");
            if (fs::exists(collect)) throw std::runtime_error("Local result already exists");
            if (!fs::path(collect).parent_path().empty()) fs::create_directories(fs::path(collect).parent_path());
            return copy(target + ":" + quote(source + "/logs"), collect);
        }
        const auto payload = fs::absolute(source).lexically_normal();
        if (!fs::exists(payload) || payload.filename().empty())
            throw std::runtime_error("Payload must be an existing file or directory");
        if (script.empty()) {
            if (!output.empty()) throw std::runtime_error("--output requires --run");
            if (destination.empty()) destination = "vins-workspace/incoming";
            require(execute(ssh(target, "mkdir -p -- " + quote(destination))), "Remote directory creation");
            return copy(payload.string(), target + ":" + quote(destination + "/"));
        }
        if (!fs::is_regular_file(script)) throw std::runtime_error("Run script must be a regular file");
        if (output.empty() || fs::exists(output)) throw std::runtime_error("Provide a new --output directory");
        if (payload.filename() == "run-script.sh" || payload.filename() == "logs")
            throw std::runtime_error("Payload name conflicts with reserved job files");
        if (destination.empty()) destination = "vins-workspace/jobs";
        const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        const auto job = destination + "/" + std::to_string(now) + "-" + std::to_string(getpid());
        std::cout << "Remote job: " << target << ':' << job << '\n' << std::flush;
        require(execute(ssh(target, "mkdir -p -- " + quote(destination) + " && mkdir -- " + quote(job)
                                     + " && mkdir -- " + quote(job + "/logs"))), "Job creation");
        require(copy(payload.string(), target + ":" + quote(job + "/")), "Payload upload");
        require(copy(fs::absolute(script).string(), target + ":" + quote(job + "/run-script.sh")), "Script upload");
        // The detached job survives a lost SSH session. A subsequent --collect
        // can recover its logs without uploading or running the experiment again.
        const auto body = "cd -- " + quote(job) + " || exit 125; "
            "export VINS_REMOTE_ROOT=\"$PWD\" VINS_REMOTE_PAYLOAD=\"$PWD/\"" + quote(payload.filename().string()) + "; "
            "date -u +%FT%TZ > logs/start_utc; "
            "timeout --signal=INT --kill-after=30 " + std::to_string(timeout) + " bash run-script.sh "
            "> logs/console.log 2>&1; code=$?; date -u +%FT%TZ > logs/end_utc; "
            "printf '%s\\n' \"$code\" > logs/exit_code.tmp; mv logs/exit_code.tmp logs/exit_code";
        const auto command = "nohup setsid bash -c " + quote(body) + " </dev/null >"
            + quote(job + "/logs/launcher.log") + " 2>&1 & "
            "pid=$!; printf '%s\\n' \"$pid\" > " + quote(job + "/logs/pid") + "; "
            "while test ! -f " + quote(job + "/logs/exit_code") + "; do "
            "kill -0 \"$pid\" 2>/dev/null || exit 125; sleep 1; done; "
            "exit \"$(cat " + quote(job + "/logs/exit_code") + ")\"";
        int code = execute(ssh(target, command));
        if (!fs::path(output).parent_path().empty()) fs::create_directories(fs::path(output).parent_path());
        const int downloaded = copy(target + ":" + quote(job + "/logs"), output);
        if (downloaded) {
            std::cerr << "Log download failed; recover with --collect using the remote job above\n";
            return downloaded;
        }
        std::cout << "Logs: " << fs::absolute(output) << "; remote exit: " << code << '\n';
        return code;
    } catch (const std::exception& error) {
        std::cerr << "vins-remote: " << error.what() << '\n';
        return 2;
    }
}
