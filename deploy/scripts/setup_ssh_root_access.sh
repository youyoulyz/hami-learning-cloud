#!/bin/bash
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Sub-node IP list (You should edit by yourself)
NODES=(
    "YOUR_NODE_IP_1"
    "YOUR_NODE_IP_2"
)

# Assure ssh-keygen existing
if ! command -v ssh-keygen &> /dev/null; then
    echo "ssh-keygen not found! Please install OpenSSH first."
    exit 1
fi

# If there is no ssh-key, generate one
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi

# Set this machine to allow log in on root（edit /etc/ssh/sshd_config）
echo "Configuring sshd on this host to allow root login..."
sed -i.bak 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart sshd

# Set root login permission and push host key to each machine.
for NODE in "${NODES[@]}"; do
    echo "Configuring $NODE..."

    echo ">> Copying key to $NODE, please input root password when prompted..."
    ssh-copy-id "root@$NODE"

    echo ">> Ensuring sshd_config allows root login on $NODE..."
    ssh "root@$NODE" "sed -i.bak 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && systemctl restart sshd"
done

echo "SSH root login setup complete for all nodes."
