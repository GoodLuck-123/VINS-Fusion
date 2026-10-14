# ARM 构建完成但混链验收不通过

编译器退出 0，链接警告显示 SDK 的 cv_bridge 引入 OpenCV 4.5，同时项目使用 4.2；不接受为里程碑，未部署到板端

完整原控制台以 console.log.gz 保存，压缩解开后的 SHA256 在 validation.json；包选择缓存摘录证明选中了 SDK cv_bridge。固定重建包的 CMake 路径与优先库搜索顺序，在 ros2_ws_overlay 全量重新构建，旧目录和产物保留
