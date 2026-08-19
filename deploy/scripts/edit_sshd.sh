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

# login info
USER="aup"
PASS="your_password"

# CHANGE this to include all your node IPs
IPS=(
    "YOUR_IP_1"
    "YOUR_IP_2"
)

# Check whether sshpass is installed
if ! command -v sshpass >/dev/null; then
    echo "Please install sshpass (sudo apt install sshpass)"
    exit 1
fi

for ip in "${IPS[@]}"; do
    echo "===> Solving $ip"

    if sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$USER@$ip" "echo '$PASS' | sudo -S bash -c '
        sed -i \"s/^#PermitRootLogin.*/PermitRootLogin yes/\" /etc/ssh/sshd_config
        sed -i \"s/^PermitRootLogin.*/PermitRootLogin yes/\" /etc/ssh/sshd_config
        systemctl restart sshd
    '"; then
        echo "[OK] $ip change successfully"
    else
        echo "[FAIL] $ip change failed"
    fi
done
