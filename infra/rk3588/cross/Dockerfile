FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg build-essential cmake ninja-build pkg-config \
    gcc-aarch64-linux-gnu g++-aarch64-linux-gnu binutils-aarch64-linux-gnu \
    python3 python3-dev python3-numpy python3-yaml python3-setuptools \
    python3-empy python3-catkin-pkg python3-rospkg git \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 3 \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    --output /usr/share/keyrings/ros-archive-keyring.gpg \
    && printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main' \
    > /etc/apt/sources.list.d/ros2.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       ros-humble-ros-base ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*
COPY prepare_sdk.sh /usr/local/bin/prepare-vins-sdk
ENTRYPOINT ["bash", "/usr/local/bin/prepare-vins-sdk"]
