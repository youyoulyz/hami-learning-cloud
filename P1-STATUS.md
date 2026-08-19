# P1 进度记录 — N1 (2070S+5060Ti) + N3 (7900XTX)

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

## N3 (7900XTX) — 已加入 + AMD 3 路时间切片验收

| 验收项 | 状态 | 证据 |
|---|---|---|
| 旧独立 k3s 清空 + 加入 N1 集群 | ✅ 用户批准后 `--force` 清空，agent v1.35.4 加入，`amd-gpu-node Ready` | `kubectl get nodes` |
| 节点打标 | ✅ `gpu=on gpu-vendor=amd amd.com/gpu.present=true` | `kubectl get nodes --show-labels` |
| AMD 时间切片 | ✅ 官方 `rocm/k8s-device-plugin` 不支持 `sliceCount`；已构建 hami-learning-cloud 自定义 time-slice 插件，节点上报 `amd.com/gpu: 3` | `kubectl get node amd-gpu-node -o jsonpath='{.status.allocatable}'` |
| 3 个 pod 共享 1 张 7900XTX | ✅ 3 个 `amd.com/gpu: 1` pod 全部调度到 N3 并 `Completed` | `deploy/amd/tests/amd-time-slice-test.yaml` |
| ROCm torch 真实可用 | ✅ `torch 2.10.0+rocm7.2.4`，`cuda_available=True`，设备 `AMD Radeon RX 7900 XTX`，1024x1024 matmul 通过 | pod 日志 `AMD_TIME_SLICE_OK` |
| join.sh 修复 | ✅ NAS 默认不再盖 `/home`；agent kubeconfig server 重写为 master IP；AMD 栈改用自定义 time-slice 插件 | `bash -n join.sh` |

### AMD 时间切片实现

- 官方 ROCm device plugin（`rocm/k8s-device-plugin:latest`，源码 `ROCm/k8s-device-plugin@ed764684`）
  只支持整卡上报，不解析 `sharing.timeSlicing.sliceCount`，也没有 `AMDGPU_DEVICE_MAX_PER_GPU`。
- hami-learning-cloud 自定义插件：
  - 补丁：`deploy/amd/amd-time-slice.patch`
  - 构建脚本：`deploy/amd/build-time-slice-plugin.sh`
  - 部署清单：`deploy/amd/amd-time-slice-device-plugin.yaml`
  - N3 二进制位置：`/opt/hami-lc/amd-time-slice/k8s-device-plugin`
  - 行为：`ListAndWatch` 上报 `sliceCount` 个 slice ID，`Allocate` 将所有 slice 映射回同一物理 GPU 的 `/dev/kfd` + `/dev/dri/*`
- 验收镜像（N3 实际拉取）：
  `swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0`
  （Dockerfile 用 canonical tag：`rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0`）

## 待办 / 风险

- **CIFAR-10 数据集**：`www.cs.toronto.edu` 与 S3 镜像在本机带宽下 ~300B/s，不可用。
  已改用合成数据验证 CUDA 栈（模型/训练循环与 train.py 一致，仅数据源替换）。
  真实数据集可后续放 NAS 共享卷（`/mnt/<HOST>`）再跑 train.py 原版。
- **AMD time-slice 二进制依赖 hostPath**：当前 N3 通过 `/opt/hami-lc/amd-time-slice/k8s-device-plugin`
  挂载进插件容器。未来新增 AMD 节点前，需要先构建并安装该二进制，或改成自定义镜像/registry 分发。
- **Docker Hub 拉取不稳定**：N3 上 `docker.io/rocm/pytorch` 经 daocloud/1ms mirror 均失败，
  已用 SWR mirror 拉取。P2/P3 镜像分发需要固定可用的 mirror 或本地 registry。
- 本机 `/etc/cdi/nvidia.yaml` 是 5 月旧驱动（595.58.03）残留，与当前 610 驱动不匹配；
  已重生成到 `~/.config/cdi/nvidia.yaml`（docker 会读）。**驱动升级后需重新 `nvidia-ctk cdi generate`**。
  注意：k3s 的 containerd 用的是 k3s 自己的 CDI 路径，若 N1 上用 k8s 跑 GPU pod 报错，
  先 `sudo nvidia-ctk cdi generate && systemctl restart k3s`。

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

# AMD time-slice 插件
kubectl apply -f deploy/amd/amd-time-slice-device-plugin.yaml
kubectl get node amd-gpu-node -o jsonpath='{.status.allocatable}' | python3 -m json.tool

# AMD 3 路验收
kubectl apply -f deploy/amd/tests/amd-time-slice-test.yaml
kubectl logs -l app=amd-time-slice-test

# 重建 AMD time-slice 二进制
./deploy/amd/build-time-slice-plugin.sh /tmp/k8s-device-plugin
scp /tmp/k8s-device-plugin amd-gpu-node:/tmp/k8s-device-plugin
# 在 N3 上: sudo install -m 0755 /tmp/k8s-device-plugin /opt/hami-lc/amd-time-slice/k8s-device-plugin
```
