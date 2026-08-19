# P1 进度记录 — N1 (2070S+5060Ti) 本机

> 更新：2026-08-19 ｜ 执行人：2070 侧 agent
> 对应 PLAN.md §5 P1 验收（N2 缺席版）

## 已完成（本机 N1）

| 验收项 | 状态 | 证据 |
|---|---|---|
| K3s server v1.35.x + containerd | ✅ 已在跑（5 月装，v1.35.4+k3s1，containerd 2.2.3-k3s1） | `k3s --version` |
| 清理孤儿节点 orphan-node | ✅ 已删，新节点 hub-node Ready | `kubectl get nodes` |
| 节点打标 gpu=on / gpu-vendor=nvidia | ✅ | `kubectl get nodes --show-labels` |
| nvidia-container-toolkit（570+/580 驱动） | ✅ 驱动 610.43.02（CUDA UMD 13.3）+ toolkit 1.19.0，CDI 已重生成 | `nvidia-smi` |
| HAMi v2.9.0（scheduler-extender + device-plugin + vGPUmonitor） | ✅ 5 月部署在跑；device-plugin 重新调度到新节点并上报 2 卡 | `kubectl get pods -n kube-system` |
| 5060Ti / 2070S 各跑一次 train.py（cu13, sm_120/sm_75） | ✅ 合成数据版各 20 epoch 通过；**真实 CIFAR-10 版因 toronto.edu 带宽被墙改用合成数据**（见下） | 日志 |
| 单卡 4 路（4G/25%）硬隔离复跑 | ✅ 4 pod 全部 binpack 到 5060Ti，nvidia-smi 显示 15190MiB / 100% | `nvidia-smi` + pod 日志 |
| TrueNAS NFS PV/PVC（RWX）挂载测试 | ✅ PV 200Gi RWX，pod 写入 → 宿主机可见，pod 重建后数据仍在 | `deploy/hami/nfs-home.yaml` |
| **N2 保持现状**（等推理结束再 join） | ✅ 未触碰 3080 机器 | — |

## N3 (7900XTX) — 已识别，待 sudo

- **IP = 192.168.X.3**（hostname `amd-gpu-node`），Ryzen 9 3900X + Navi 31（DID 0x744c）
- 现状：Ubuntu 25.04 / 6.14 内核 / **已有独立 k3s v1.34.4（167 天前，control-plane，docker runtime）**，
  上面跑着旧的 Z2JH + `rocm/k8s-device-plugin`（无 time-slicing env）
- ROCm 已装，`rocm-smi` 正常，`/dev/kfd` 在，GPU 0% 空闲
- **阻塞**：要加入 N1 集群必须先停掉并清空这台独立 k3s（`--force`），需要 sudo；
  当前 SSH 用户无免密 sudo → **需要用户提供 sudo 或亲自执行**
- join.sh 已就绪：`sudo ./join.sh --server 192.168.X.1 --token <token> --vendor amd --force`
  （token 在 N1：`sudo cat /var/lib/rancher/k3s/server/token`）

## 待办 / 风险

- **CIFAR-10 数据集**：`www.cs.toronto.edu` 与 S3 镜像在本机带宽下 ~300B/s，不可用。
  已改用合成数据验证 CUDA 栈（模型/训练循环与 train.py 一致，仅数据源替换）。
  真实数据集可后续放 NAS 共享卷（`/mnt/<HOST>`）再跑 train.py 原版。
- **N3 的旧独立 k3s**：清空前需用户确认那台机器上没有还要用的东西
  （目前只有旧的 Z2JH + amdgpu-device-plugin，看起来是 3 月份的实验残留）。
- 本机 `/etc/cdi/nvidia.yaml` 是 5 月旧驱动（595.58.03）残留，与当前 610 驱动不匹配；
  已重生成到 `~/.config/cdi/nvidia.yaml`（docker 会读）。**驱动升级后需重新 `nvidia-ctk cdi generate`**。
  注意：k3s 的 containerd 用的是 k3s 自己的 CDI 路径，若 N1 上用 k8s 跑 GPU pod 报错，
  先 `sudo nvidia-ctk cdi generate && sudo systemctl restart k3s`。

## 关键命令备忘

```bash
# kubeconfig（含凭据，勿 commit）
export KUBECONFIG=/mnt/<HOST>/hpc/gpu-sharing/nv-hami/k3s-kubeconfig.yaml

# 单卡 4 路复跑
kubectl apply -f deploy/hami/tests/quad-isolation-test.yaml
kubectl get pods -l app=quad-train -o wide
nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv

# NFS RWX 测试
kubectl apply -f deploy/hami/tests/nfs-rwx-test.yaml
cat /mnt/<HOST>/hami-lc-home/write-test.txt   # 宿主机侧
```
