# 开发环境限制记录

初次 CMake 自动选中 /usr/lib/ccache/c++，沙箱无法创建 /run/user/1000/ccache-tmp；原 CMake 错误见 initial_cmake_error.log。使用 /usr/bin/g++ 的独立主机构建后通过，未修改系统 ccache 配置

一次安装规则验证在沙箱内以 /tmp 为目标，但 CMake 仍需写父工作区 build 的 install_manifest.txt，因只读限制失败；在已授权父工作区执行后通过。未将这些开发环境失败计作功能测试通过，未重新伪造原终端 stderr

首次隔离部署功能通过，但板端未同步时钟导致 tar 大量时间提示，完整日志保留在主机 deploy-success01。后续 deploy-success02 将成功解压诊断存 unpack.stderr 并实时显示摘要，失败路径仍打印完整错误；未更改板端时钟或冻结文件
