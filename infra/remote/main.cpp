#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "agent.hpp"

namespace fs = std::filesystem;
using Args = std::vector<std::string>;

std::string quote(const std::string& s) {
    std::string r = "'";
    for (char c : s) r += c == '\'' ? "'\\''" : std::string(1, c);
    return r + "'";
}
std::string json(const std::string& s) {
    std::string r = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { r += '\\'; r += c; }
        else if (c == '\n') r += "\\n";
        else if (c == '\r') r += "\\r";
        else if (c == '\t') r += "\\t";
        else if (c < 32) throw std::runtime_error("Control characters are not allowed in paths");
        else r += c;
    }
    return r + '"';
}
std::string read(const fs::path& p) {
    std::ifstream in(p);
    if (!in) throw std::runtime_error("Cannot read " + p.string());
    return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}
void write(const fs::path& p, const std::string& s) {
    std::ofstream out(p);
    if (!(out << s)) throw std::runtime_error("Cannot write " + p.string());
}
int execute(const Args& args, std::string* output = nullptr) {
    int pipes[2] = {-1, -1};
    if (output && pipe(pipes)) throw std::runtime_error(std::strerror(errno));
    // Ctrl-C interrupts the child/SSH viewer, not this client's job receipt.
    struct sigaction ignore{}, previous{};
    ignore.sa_handler = SIG_IGN;
    sigemptyset(&ignore.sa_mask);
    sigaction(SIGINT, &ignore, &previous);
    pid_t pid = fork();
    if (pid < 0) throw std::runtime_error(std::strerror(errno));
    if (!pid) {
        signal(SIGINT, SIG_DFL);
        if (output) { close(pipes[0]); dup2(pipes[1], STDOUT_FILENO); close(pipes[1]); }
        std::vector<char*> argv;
        for (const auto& arg : args) argv.push_back(const_cast<char*>(arg.c_str()));
        argv.push_back(nullptr);
        execvp(argv[0], argv.data());
        std::cerr << "Cannot execute " << args[0] << ": " << std::strerror(errno) << '\n';
        _exit(127);
    }
    if (output) {
        close(pipes[1]); char buffer[4096]; ssize_t n;
        while ((n = ::read(pipes[0], buffer, sizeof buffer)) != 0) {
            if (n > 0) output->append(buffer, static_cast<size_t>(n));
            else if (errno != EINTR) break;
        }
        close(pipes[0]);
    }
    int status = 0;
    while (waitpid(pid, &status, 0) < 0) if (errno != EINTR) throw std::runtime_error(std::strerror(errno));
    sigaction(SIGINT, &previous, nullptr);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
void require(int code, const std::string& action) {
    if (code) throw std::runtime_error(action + " failed (exit " + std::to_string(code) + ")");
}
Args ssh(const std::string& target, const std::string& command, bool tty = false) {
    Args a = {"ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o",
              "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"};
    if (tty) a.push_back("-t");
    a.push_back(target); a.push_back(command); return a;
}
int transfer(const std::string& src, const std::string& dst, bool quiet = false) {
    return execute({"rsync", "-a", "--no-owner", "--no-group", quiet ? "--quiet" : "--info=progress2", "--outbuf=L",
                    "--partial-dir=.rsync-partial", "-s", "-e",
                    "ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3",
                    "--", src, dst});
}
std::string resolved(const std::string& p, const std::string& home) {
    if (p.empty()) throw std::runtime_error("Empty remote path");
    json(p); // validate control characters before invoking a shell
    if (p == "~") return home;
    if (p.rfind("~/", 0) == 0) return home + p.substr(1);
    return p[0] == '/' ? p : home + '/' + p;
}
std::string trim(std::string s) {
    auto first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    return s.substr(first, s.find_last_not_of(" \t\r\n") - first + 1);
}
struct Defaults {
    std::string target = "firefly@10.106.0.220", root = "vins-workspace";
    std::string cwd, env;
    void load(const fs::path& file) {
        std::istringstream in(read(file)); std::string line;
        while (std::getline(in, line)) {
            line = trim(line); if (line.empty() || line[0] == '#') continue;
            auto at = line.find('=');
            if (at == std::string::npos) throw std::runtime_error("Expected key=value in " + file.string());
            auto key = trim(line.substr(0, at)), value = trim(line.substr(at + 1));
            if (key == "target") target = value;
            else if (key == "root") root = value;
            else if (key == "cwd") cwd = value;
            else if (key == "env") env = value;
            else throw std::runtime_error("Unknown config key: " + key);
        }
    }
};
struct Temporary {
    fs::path path;
    Temporary() { char pattern[] = "/tmp/vins-remote-XXXXXX"; auto p = mkdtemp(pattern);
        if (!p) throw std::runtime_error(std::strerror(errno));
        path = p; }
    ~Temporary() { std::error_code error; fs::remove_all(path, error); }
};
void usage() {
    std::cout << "vins-remote [USER@HOST] FILE_OR_DIR [--send] [--dest REMOTE_PARENT]\n"
                 "vins-remote [USER@HOST] REMOTE_PATH --receive [--dest LOCAL_PARENT]\n"
                 "vins-remote [USER@HOST] --remote [--cwd DIR] [--env FILE]\n"
                 "vins-remote [USER@HOST] --exec [--cwd DIR] [--env FILE|--no-env] -- COMMAND [ARGS...]\n"
                 "vins-remote [USER@HOST] PAYLOAD --run SCRIPT --output NEW_DIR [--timeout SEC] [--detach] [--job-name NAME]\n"
                 "vins-remote [USER@HOST] REMOTE_JOB --follow [--events-only] [--output DIR]\n"
                 "vins-remote [USER@HOST] REMOTE_JOB --stop [--output DIR]\n"
                 "vins-remote [USER@HOST] REMOTE_JOB --collect LOCAL_DIR\n"
                 "Common: --config FILE --root DIR --cwd DIR --env FILE; --print-config\n"
                 "Ctrl-C detaches the log viewer; --stop explicitly stops the owned job.\n";
}
void receipt(const fs::path& out, const std::string& target, const std::string& job, bool fresh) {
    auto text = target + '\n' + job + '\n';
    if (fs::exists(out)) {
        if (fresh || !fs::is_regular_file(out / "remote_job.txt") || read(out / "remote_job.txt") != text)
            throw std::runtime_error("Output exists and is not this job's receipt: " + out.string());
    } else fs::create_directories(out);
    write(out / "remote_job.txt", text);
    write(out / "remote_job.json", "{\"target\":" + json(target) + ",\"job\":" + json(job) + "}\n");
}
int main(int argc, char** argv) {
    try {
        Defaults d; fs::path config;
        if (auto e = getenv("VINS_REMOTE_CONFIG")) config = e;
        for (int i = 1; i + 1 < argc; ++i) {
            if (std::string(argv[i]) == "--") break;
            if (std::string(argv[i]) == "--config") config = argv[i + 1];
        }
        if (config.empty()) {
            auto nearby = fs::read_symlink("/proc/self/exe").parent_path() / "vins-remote.conf";
            if (fs::exists(nearby)) config = nearby;
        }
        if (!config.empty()) d.load(config);
        std::string source, mode, destination, script, output, collect, job_name;
        bool no_env = false, detach = false, events_only = false, print_config = false;
        unsigned timeout = 3600;
        Args command;
        bool cwd_set = false, env_set = false;
        for (int i = 1; i < argc; ++i) {
            std::string option = argv[i];
            auto value = [&]() { if (++i >= argc) throw std::runtime_error("Missing value: " + option); return std::string(argv[i]); };
            auto select = [&](const std::string& m) { if (!mode.empty()) throw std::runtime_error("Choose one operation"); mode = m; };
            if (option == "--") { while (++i < argc) command.push_back(argv[i]); break; }
            if (option == "--help" || option == "-h") { usage(); return 0; }
            if (option == "--version") { std::cout << "vins-remote 2\n"; return 0; }
            if (option == "--config") { value(); }
            else if (option == "--root") { d.root = value(); if (!cwd_set) d.cwd.clear(); if (!env_set) d.env.clear(); }
            else if (option == "--cwd") { d.cwd = value(); cwd_set = true; }
            else if (option == "--env") { d.env = value(); env_set = true; }
            else if (option == "--no-env") no_env = true;
            else if (option == "--print-config") print_config = true;
            else if (option == "--dest") destination = value();
            else if (option == "--output") output = value();
            else if (option == "--job-name") { job_name = value(); if (job_name.empty()) throw std::runtime_error("Empty --job-name"); }
            else if (option == "--timeout") {
                auto v = value(); if (!std::regex_match(v, std::regex("[0-9]+"))) throw std::runtime_error("Invalid timeout");
                auto n = std::stoul(v); if (n < 1 || n > 604800) throw std::runtime_error("Timeout must be 1..604800");
                timeout = static_cast<unsigned>(n);
            } else if (option == "--run") { select("run"); script = value(); }
            else if (option == "--collect") { select("collect"); collect = value(); }
            else if (option == "--detach") detach = true;
            else if (option == "--events-only") events_only = true;
            else if (option == "--send" || option == "--receive" || option == "--remote" || option == "--exec" || option == "--follow" || option == "--stop") select(option.substr(2));
            else if (option.rfind("--", 0) == 0) throw std::runtime_error("Unknown option: " + option);
            else if (std::regex_match(option, std::regex("[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*")) && source.empty()) d.target = option;
            else if (source.empty()) source = option;
            else throw std::runtime_error("Unexpected argument: " + option);
        }
        if (d.cwd.empty()) d.cwd = d.root + "/projects/vins";
        if (d.env.empty()) d.env = d.root + "/install/env.sh";
        if (!std::regex_match(d.target, std::regex("[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*"))) throw std::runtime_error("Use USER@HOST with an IPv4 address or hostname");
        if (print_config) {
            std::cout << "{\"target\":" << json(d.target) << ",\"root\":" << json(d.root) << ",\"cwd\":" << json(d.cwd) << ",\"env\":" << json(d.env) << "}\n"; return 0;
        }
        if (argc == 1) { usage(); return 2; }
        if (mode.empty()) mode = "send";
        if (!command.empty() && mode != "exec") throw std::runtime_error("COMMAND requires --exec");
        if (mode == "exec" && command.empty()) throw std::runtime_error("Provide --exec -- COMMAND [ARGS]");
        if ((mode == "send" || mode == "receive" || mode == "run" || mode == "collect" || mode == "follow" || mode == "stop") && source.empty()) throw std::runtime_error("Missing file/path/job");
        if ((mode == "remote" || mode == "exec") && !source.empty()) throw std::runtime_error("Unexpected file/path");
        if (!job_name.empty() && (mode != "run" || !std::regex_match(job_name, std::regex("[A-Za-z0-9][A-Za-z0-9_.-]{0,79}"))))
            throw std::runtime_error("--job-name requires --run and 1..80 letters/digits/._- starting with a letter or digit");
        if (detach && mode != "run") throw std::runtime_error("--detach requires --run");
        if (events_only && mode != "run" && mode != "follow" && mode != "stop") throw std::runtime_error("--events-only requires a managed job");
        if (!destination.empty() && mode != "send" && mode != "receive" && mode != "run") throw std::runtime_error("--dest is only for transfers/job creation");
        if (!output.empty() && mode != "run" && mode != "follow" && mode != "stop") throw std::runtime_error("--output is only for jobs");
        if (!collect.empty() && (!output.empty() || !destination.empty())) throw std::runtime_error("--collect cannot use --output/--dest");
        if ((mode == "send" || mode == "run") && !fs::exists(source)) throw std::runtime_error("Payload does not exist: " + source);
        if (mode == "run" && (!fs::is_regular_file(script) || output.empty())) throw std::runtime_error("Provide a script and new --output directory");
        if (mode == "run" && fs::exists(output)) throw std::runtime_error("Output already exists: " + output);
        if (mode == "remote" && !isatty(STDIN_FILENO)) throw std::runtime_error("--remote requires a terminal; use --exec for scripts");
        std::string home;
        require(execute(ssh(d.target, "printf '%s' \"$HOME\""), &home), "SSH home lookup");
        if (home.empty() || home[0] != '/' || home.find('\n') != std::string::npos) throw std::runtime_error("Invalid SSH home response");
        auto root = resolved(d.root, home), cwd = resolved(d.cwd, home), env = resolved(d.env, home);
        if (mode == "remote" || mode == "exec") {
            std::string init = "set -e; mkdir -p -- " + quote(cwd) + "; ";
            if (!no_env) init += "test -r " + quote(env) + " || { echo " + quote("Missing environment: " + env) + " >&2; exit 2; }; source " + quote(env) + " >&2; ";
            init += "cd -- " + quote(cwd) + "; ";
            if (mode == "exec") {
                init += "exec"; for (const auto& a : command) init += ' ' + quote(a);
                return execute(ssh(d.target, "bash -c " + quote(init)));
            }
            auto rc = "test ! -f ~/.bashrc || source ~/.bashrc; " + init + "set +e; printf '[REMOTE_READY] %s %s\\n' \"$(hostname)\" \"$PWD\"; ";
            auto shell = "exec bash --rcfile <(printf '%s' " + quote(rc) + ") -i";
            return execute(ssh(d.target, "bash -c " + quote(shell), true));
        }
        if (mode == "send") {
            auto local = fs::absolute(source).lexically_normal();
            while (local.filename().empty()) {
                if (local == local.parent_path()) throw std::runtime_error("Cannot send filesystem root");
                local = local.parent_path();
            }
            auto parent = resolved(destination.empty() ? d.cwd : destination, home);
            require(execute(ssh(d.target, "mkdir -p -- " + quote(parent))), "Remote directory creation");
            return transfer(local.string(), d.target + ':' + parent + '/');
        }
        if (mode == "receive") {
            // Relative receive sources are relative to the configured workspace.
            auto remote = source[0] == '/' || source[0] == '~' ? resolved(source, home) : root + '/' + source;
            auto path = fs::path(remote).lexically_normal();
            while (path.filename().empty()) {
                if (path == path.parent_path()) throw std::runtime_error("Cannot receive filesystem root");
                path = path.parent_path();
            }
            remote = path.string();
            fs::path parent = destination.empty() ? fs::current_path() : fs::absolute(destination);
            fs::create_directories(parent);
            return transfer(d.target + ':' + remote, parent.string() + '/');
        }
        std::string job;
        if (mode == "run") {
            auto payload = fs::absolute(source).lexically_normal();
            // Remove trailing slash so copying a directory preserves its name.
            while (payload.filename().empty()) {
                if (payload == payload.parent_path()) throw std::runtime_error("Cannot send filesystem root");
                payload = payload.parent_path();
            }
            auto name = payload.filename().string();
            if (name == "logs" || name == "run-script.sh" || name == "remote_agent.py") throw std::runtime_error("Reserved payload name");
            auto parent = resolved(destination.empty() ? d.root + "/jobs" : destination, home);
            auto now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
            job = parent + '/' + (job_name.empty() ? std::to_string(now) + '-' + std::to_string(getpid()) : job_name);
            std::cerr << "Remote job: " << d.target << ':' << job << '\n';
            receipt(output, d.target, job, true);
            require(execute(ssh(d.target, "mkdir -p -- " + quote(parent) + " && mkdir -- " + quote(job) + " && mkdir -- " + quote(job + "/logs"))), "Job creation");
            Temporary temp; write(temp.path / "remote_agent.py", remote_agent);
            require(transfer(payload.string(), d.target + ':' + job + '/', events_only), "Payload upload");
            require(transfer(fs::absolute(script).string(), d.target + ':' + job + "/run-script.sh", events_only), "Script upload");
            require(transfer((temp.path / "remote_agent.py").string(), d.target + ':' + job + '/', events_only), "Agent upload");
            auto launch = "nohup setsid /usr/bin/python3 " + quote(job + "/remote_agent.py") + " worker " + quote(job) + ' ' + std::to_string(timeout) + ' ' + quote(name) + ' ' + quote(root) + ' ' + quote(cwd) + ' ' + quote(env) + " </dev/null >" + quote(job + "/logs/launcher.log") + " 2>&1 &";
            require(execute(ssh(d.target, launch)), "Job launch");
            if (detach) { std::cerr << "[DETACHED] Receipt: " << fs::absolute(output) << '\n'; return 0; }
        } else job = resolved(source, home);
        if (mode == "collect") output = collect;
        if (!output.empty() && mode != "run") receipt(output, d.target, job, false);
        if (mode == "stop") require(execute(ssh(d.target, "/usr/bin/python3 " + quote(job + "/remote_agent.py") + " stop " + quote(job))), "Job stop request");
        int code = 0;
        if (mode != "collect") {
            auto watch = "/usr/bin/python3 -u " + quote(job + "/remote_agent.py") + " follow " + quote(job) + (events_only ? " --events-only" : "");
            code = execute(ssh(d.target, watch));
            if (code == 130 || code == 255) {
                // Distinguish a durable task exit 130/255 from a lost viewer.
                auto state = execute(ssh(d.target, "test -f " + quote(job + "/logs/exit_code")));
                if (state) {
                    std::cerr << "[VIEW_DISCONNECTED] Job may still be running; --follow/--stop/--collect " << job << '\n';
                    return code;
                }
            }
        }
        if (!output.empty()) {
            int copied = transfer(d.target + ':' + job + "/logs/", fs::absolute(output).string() + '/', events_only);
            if (copied) { std::cerr << "[COLLECT_FAILED] Retry --collect using the same job receipt\n"; return copied; }
            std::cerr << "[COLLECT_OK] " << fs::absolute(output) << "; remote exit=" << code << '\n';
        }
        return code;
    } catch (const std::exception& e) { std::cerr << "vins-remote: " << e.what() << '\n'; return 2; }
}
