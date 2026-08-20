# 交接书 — NV Learning Cloud

> 交接对象：**2070 + 5060Ti 机器上的 agent**
> 交接人：3080 侧的 opencode agent ｜ 日期：2026-08-19
> 前提：`<NAS 挂载点>` 是 NAS NFS 共享家目录，你在本机挂载后即可看到本目录所有文件。

## 0. 30 秒版

项目名 **hami-learning-cloud**：在 3 台家用机（5 卡：5060Ti+2070S / 2×3080-20G / 7900XTX）上建
**一个 K3s 集群 + 一个 JupyterHub** 的 GPU 教学云，设计为 **AUP Learning Cloud**（github.com/AMDResearch/aup-learning-cloud）
**与 HAMi** 的共同后继——复用 AUP 的 UI、设计、配额体系；GPU 共享用 **HAMi vGPU 硬配额**（NV 侧）+ time-slicing（AMD 侧）。
**计划文档是唯一事实来源：`./PLAN.md`（v1.0 已定稿）。先通读它，再做任何事。**

## 1. 当前状态

- 计划 **v1.0 已定稿**（Q1/Q2/Q3 已批：项目名 hami-learning-cloud / 无硬期限 / 最小镜像清单），**尚未开始写代码**
- 用户已确认的事实：7900XTX 跑 torch 没问题（用户自己训过小模型）
- 5 月份在 3080 机器上已验证过：K3s + Z2JH + HAMi v2.9.0 单卡 4 路（4G 显存/25% 算力）共享跑通，
  资产在 `<gpu-sharing 根目录>/nv-hami/`（install-z2jh.sh / train.py / train-pods.yaml / z2jh-values.yaml）
- `<本地 AUP 克隆目录>` 是 AUP 上游最新克隆（main @ 27f4190），**临时克隆会丢，你需要时重新 clone**：
  `git clone --depth 50 https://github.com/AMDResearch/aup-learning-cloud`
  参考要点：`runtime/hub/core/spawner/kubernetes.py`（`_configure_spawner`，1230 行，NV 移植唯一的大改动点）、
  `runtime/hub/core/quota/manager.py`（配额，原样移植）、`runtime/values.yaml`（accelerators/resources/quota 配置模型）、
  `runtime/chart/`（Z2JH 4.3.3 fork，**零改动使用**）、`dockerfiles/Hub/Dockerfile`（hub 镜像：pnpm 前端 3 apps + core）

## 2. 硬件与当前约束

| 节点 | 卡 | 状态 |
|---|---|---|
| **N1 = 本机（2070S + 5060Ti）** | 8G + 16G | **临时集群 master（K3s server）+ GPU 节点**（PLAN.md v1.0 已按此命名） |
| N2 = 3080×2 机器 | 2×20G | **VRAM 被推理模型占满，暂时不可用**。等推理结束后作为 GPU 节点加入（或届时迁移 master 角色，P5 运维文档覆盖） |
| N3 = 7900XTX 机器 | 24G | 空闲，作为 AMD 节点加入 |

**铁律：3080 机器上有正在跑的推理负载——不要动它的 GPU、不要杀进程、不要重启那台机器。**

机器要点：
- 本机 5060Ti 是 Blackwell：需要 **570+/580 系 NVIDIA 驱动 + CUDA 12.8/13** 镜像；2070S（Turing, sm_75）共用同一驱动。装驱动时锁版本，写进安装脚本
- 7900XTX：ROCm + amdgpu 内核模块，消费级 RDNA3（gfx1101），time-slicing 共享（无显存隔离，slice 数保守取 3）
- 用户目录放 NAS（NFS，地址本地配置，勿写入仓库），集群 RWX
- 外网入口：cloudflared tunnel（P5），AUP 的 `publicScheme=https + allowedOrigins` 机制现成

## 3. 你现在就可以做（不等审批）

1. 通读 `./PLAN.md`（重点：§2 非目标、§4 配额表、§5 P0~P5 任务与验收、§10 待决事项）
2. **已决事项**（PLAN.md §10，勿再问）：Q1=项目名 hami-learning-cloud；Q2=无硬期限；
   Q3=最小镜像清单：`cpu` + `gpu` 两个资源，NV 侧镜像 = `quay.io/jupyter/pytorch-notebook:cuda13-notebook-7.5.6`（已验证），
   AMD 侧 = `rocm/pytorch:2.7.1-rocm6.3` + jupyterlab，**Dockerfile 已写好：`./images/Dockerfile.amd`**（构建推镜像在 P3；P1 先在 N3 裸机验证 torch 可用，tag 以 N3 实测为准）
   其余 Q4~Q8 有默认值（见 PLAN.md §10），执行中不要擅自改默认值。**所有决策已闭环，不要再向用户提问，除非遇到计划外阻塞。**
3. 以下工作可立即并行推进：
   - **P1 前置 spike（本机）**：装 580 系驱动 + nvidia-container-toolkit；用 `nv-hami/train.py`
     在 5060Ti 和 2070S 上各跑一次（验证 cu13 镜像同时覆盖 sm_120/sm_75，镜像用 Q3 定稿的 pytorch-notebook:cuda13）
   - **K3s server 安装准备（本机）**：参考 `nv-hami/install-z2jh.sh` 的 K3s 部分（v1.35.x，containerd，无 Docker），
     但 Z2JH/HAMi 的 helm 部署等 P0 仓库定下来后再做
   - **仓库准备**：clone AUP 上游（见 §1）到工作区；先在本目录 `git init` 起步（Q4 默认值）
4. 用户审批计划后：按 P0→P5 执行，**本机为 master**

## 4. 不可更改的设计决策（改动需先问用户）

1. **D1 — accelerator 只建 `nvidia`/`amd` 两个，不按 GPU SKU 分**。
   理由：2070+5060Ti 混合卡机器上 K8s 无法在 pod 级选卡；NV 三卡共用同一 CUDA 镜像；
   **配额表即路由**——要 12G 的 pod 自然落不到 8G 的 2070S 上。这是整个方案能成立的支点。
2. **D2 — schedulerName 按 accelerator 分派**：nvidia pod → `hami-scheduler`（HAMi extender，vGPU fit/score）；
   amd pod → 默认 scheduler（`amd.com/gpu` time-slice 是普通 extended resource）。
3. **配额表**（PLAN.md §4）：base 4000MB/25%、中档 8000/50%、大档 12000/75%、AMD 各档 = `amd.com/gpu:1` 时共享。
   HAMi 单位：`nvidia.com/gpumem`=MB、`nvidia.com/gpucores`=%。
4. **AUP `runtime/chart` 零改动原则**：chart 已审计过无 amd.com 硬编码（资源经 `singleuser.extraResource`
   透传）。如果你发现必须改 chart，停下来先查为什么——那通常意味着 values 或 spawner 用错了。
5. HAMi 用 **v2.9.0**（`nv-hami/HAMi/charts/hami`，imageTag v2.9.0，schedulerName `hami-scheduler`），不升级版本。
6. 移植范围收敛在：`spawner/kubernetes.py` 的 `_configure_spawner` 资源分支（`if "amd.com/gpu" in requirements`
   处）+ `config.py` accelerator 模型加 vendor/scheduler 字段 + `values.yaml`。
   quota / handlers / 前端 / auth **原样移植**。

## 5. 安全与纪律

- `nv-hami/k3s-kubeconfig.yaml` **含集群凭据：永不 commit、永不贴进仓库/聊天**
- 任何 NAS 密码、kubeconfig、token 不进 repo
- commit 前 `git status` 过一遍；**永远不要 push 到 AMDResearch/aup-learning-cloud**（那是上游，只读参考；
   stretch 的上游 PR 走用户自己的 fork + PR 流程，且需用户点头）
- 3080 机器：见 §2 铁律

## 6. 汇报与验收

- 每阶段按 PLAN.md §5 的**验收标准**向用户汇报，过了才算过
- 卡住时汇报格式：现象 + 跑过的命令 + 输出 + 你的原因猜测。**不要静默改方案**
- 每周五（或阶段边界）给用户一个"本周可演示的东西"（PLAN.md §6 的里程碑）

## 7. 关键文件地图

| 路径 | 内容 |
|---|---|
| `.../hami-learning-cloud/PLAN.md` | 计划（唯一事实来源，v1.0 已定稿） |
| `.../hami-learning-cloud/HANDOVER.md` | 本文件 |
| `.../hami-learning-cloud/images/Dockerfile.amd` | AMD (7900XTX) 课程镜像 Dockerfile（已定稿，P3 构建） |
| `<本地 AUP 快照目录>` | AUP 本地快照（用户 fork，5 月版 @ PR#93；含用户自己的课程 commit，**只读**） |
| AUP 上游最新 | 需重新 clone（§1）；比本地快照新 ~75 个 PR（Python installer、PXE、code-server、quota 修复等） |
| `.../nv-hami/HAMi` | HAMi v2.9.0 源码 + `charts/hami` + `skill/`（调试参考：hami-vgpu-metrics-summary 等） |
| `.../nv-hami/HAMi-WebUI` | 可选监控前端（stretch 才用） |
| `.../nv-hami/{install-z2jh,train-pods.yaml,train.py,z2jh-values}.sh/yaml` | 5 月验证过的 K3s+Z2JH+HAMi 4 路共享资产 |
| `.../amd-hami/manifests/amd-device-plugin.yaml` | N3 要用的 AMD time-slicing manifest（**sliceCount 从 6 改 3**） |
| `.../amd-hami/setup-k3s.sh` | AMD 侧 K3s 参考（5 月写的） |

（`...` = `<gpu-sharing 根目录>`）
