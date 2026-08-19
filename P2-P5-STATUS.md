# P2–P5 实施状态（as-built）

> 日期：2026-08-19  
> 集群形态：N1（2070S + 5060Ti，K3s server + NV GPU）+ N3（7900XTX，AMD）；N2（3080×2）仍按铁律保留给推理，未加入。

## P2 — AUP runtime 移植（完成）

- `runtime/hub/core/config.py`：`AcceleratorConfig` 增加 `vendor` / `scheduler_name` / `runtime_class_name` 字段。
- `runtime/hub/core/spawner/kubernetes.py`：
  - NV：`nvidia.com/gpu=1`、`nvidia.com/gpumem=4000`、`nvidia.com/gpucores=25`、`runtimeClassName=nvidia`、`schedulerName=hami-scheduler`。
  - AMD：`amd.com/gpu=1`、`schedulerName=default-scheduler`，并给 pod 打 `hami.io/webhook=ignore`，避免 HAMi webhook 把 AMD/CPU pod 改成 HAMi scheduler。
  - CPU：无 GPU 资源，保留默认 scheduler。
- `runtime/values.yaml`：dummy auth、两个 accelerator（`nvidia`/`amd`）、最小 `cpu`/`gpu` 资源表、NV/AMD 镜像 override、NFS static home、quota enabled、admin user。
- `runtime/chart` 保持零改动。
- Hub 镜像：本地构建 `hami-lc-hub:v1`（前端三应用 + rebranded core），导入 N1 K3s。
- AMD singleuser 镜像：`hami-lc-amd:v1`（ROCm PyTorch + `jupyterhub-singleuser` + JupyterLab），导入 N3 K3s。

验收（已实测）：

| 路径 | Pod | Node | schedulerName | runtimeClass | 容器内可见 GPU |
|---|---|---|---|---|---|
| NV | `jupyter-student-nv` | N1 | `hami-scheduler` | `nvidia` | 1× NVIDIA RTX 5060 Ti，显存上限 4000 MiB |
| AMD | `jupyter-student-amd` | N3 | `default-scheduler` | — | 1× AMD Radeon RX 7900 XTX |
| CPU | `jupyter-student-cpu` | N3 | `default-scheduler` | — | CUDA unavailable |

## P3 — 镜像契约 + spawn 全流程（完成）

- NV/CPU 镜像：`quay.io/jupyter/pytorch-notebook:cuda13-notebook-7.5.6`，`/home/jovyan` 可写，JupyterLab 可启动。
- AMD 镜像：`hami-lc-amd:v1`，root 用户下 `jupyterhub-singleuser --allow-root`，`/home/jovyan` 挂载 NFS 子路径。
- 持久化：三个用户均在 `/home/jovyan/persist-test.txt` 写文件 → 删除 server → 重新 spawn → 文件仍在。
- 镜像预拉：当前 MVP 采用“节点本地导入/`crictl pull`”方式；`join.sh` 后续新节点需要按 vendor 预拉对应课程镜像（见运维手册）。

## P4 — 配额 + 监控 + 用户管理（完成）

- Quota：
  - `custom.quota.enabled=true`、`defaultQuota=100`、`minimumToStart=10`。
  - 低额 spawn 被拒：`Cannot start container: Insufficient quota for 20 min (balance: 5, need: 20, max: 5 min)`。
  - admin 加额后立即 spawn 成功。
- Admin quota 脚本：
  - `scripts/manage_quota.py list/set/add`，支持 CSV 批量。
  - 认证支持 `JUPYTERHUB_TOKEN`（推荐）或 `JUPYTERHUB_COOKIE`/`JUPYTERHUB_XSRF` 回退。
  - admin token 可用 `kubectl -n jupyterhub exec deployment/hub -- jupyterhub token admin` 生成。
- 监控：
  - 复用已有 Prometheus + DCGM exporter + HAMi vGPUmonitor 指标。
  - 新增 Grafana：`monitoring/grafana`，NodePort `30300`，默认面板 `hami-learning-cloud GPU`。
  - 面板指标：`hami_container_memory_used`、`hami_container_core_used`、`DCGM_FI_DEV_GPU_UTIL`。

## P5 — 收尾（大部分完成）

- 公网入口：cloudflared quick tunnel 已暴露 Hub（临时 URL 见运行日志 `/tmp/cloudflared.log`，不写入仓库）。
- 运维/安全修正：
  - HAMi/DCGM DaemonSet 收紧到 `gpu-vendor=nvidia`，避免误调度到 AMD 节点。
  - `join.sh` AMD 节点不再打 `gpu=on`，只打 `gpu-vendor=amd` 和 `amd.com/gpu.present=true`。
- 文档：本文件 + `README.md` + `PLAN.md`。
- 未完成/需人工：
  - N2 3080×2 仍不可加入（铁律：推理负载未结束）。
  - Demo 视频未录制（需要人工录屏/讲解）。
  - 上游 AUP PR 未提交（stretch，需用户确认 fork/PR 流程）。

## 当前入口

- 局域网 Hub：`http://192.168.X.1:30890`
- Grafana：`http://192.168.X.1:30300`（账号 `admin` / `admin`，演示环境默认值，正式使用前请改密）
- 公网 tunnel：临时 quick tunnel，URL 在 `/tmp/cloudflared.log` 中，重启后会变化。
