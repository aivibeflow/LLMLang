FROM makarius/isabelle@sha256:9bd33b183c399327c5d554fc8cde27c29b5d2b20cdc6fe7a604caa3f951018fc
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git make cmake ninja-build gcc gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu rsync python3 python3-pexpect python3-psutil python3-jinja2 python3-lxml python3-pyelftools python3-yaml device-tree-compiler libxml2-utils && rm -rf /var/lib/apt/lists/*
USER isabelle
