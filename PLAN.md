# HAMi Learning Cloud — 实施计划

> 状态：**v1.0 定稿**（Q1/Q2/Q3 已批）｜ 作者：luyzh ｜ 日期：2026-08-19
> 项目名：**hami-learning-cloud** —— 设计为 **AUP Learning Cloud 与 HAMi 的共同后继**：
> AUP 提供教学云的形态（UI / 课程模型 / 配额体系），HAMi 提供 vGPU 硬隔离内核，本项目是两者在 NVIDIA 硬件上的合体。
>
> ⚠️ **硬件现状（2026-08-19）**：3080×2 机器（N2）VRAM 被推理模型占满暂不可用，
> **临时集群 master 在 2070+5060Ti 机器（N1）**。节点命名以用户口径为准：
> N1=2070S+5060Ti（临时 master）/ N2=3080×2（稍后加入）/ N3=7900XTX。
> 执行细节与当前约束见 **`HANDOVER.md`**。

---

## 0. 一句话概述

把 3 台家用机（5 卡：2×3080-20G / 5060Ti+2070S / 7900XTX）组成**一个 K3s 集群 + 一个 JupyterHub**，
以 AUP Learning Cloud 的 UI / 设计 / 配额体系为蓝本，用 **HAMi vGPU 硬配额**（NV 侧）+ time-slicing（AMD 侧）
做 GPU 共享，交付一个可演示、可交接、有完整文档的多租户 GPU 教学云。

## 1. 项目定位（为什么值得做 / 高屋建瓴）

| # | 论点 | 说明 |
|---|------|------|
| 1 | **真隔离** | AUP（AMD 消费级硬件）只有 time-slicing，无显存/算力隔离；本项目用 HAMi 提供 `gpumem`（MB）+ `gpucores`（%）硬配额，单卡可承载 4~5 个互不干扰的学生 |
| 2 | **AUP + HAMi 的合体** | 教学云形态（AUP）与 vGPU 隔离内核（HAMi）第一次在消费级 NVIDIA 硬件上完整落地：HAMi 侧有现成的多厂商设备抽象，AUP 侧有现成的加速器选择模型，两者拼接 delta 极小 |
| 3 | **架构普适性证明** | AUP 的 `custom.accelerators` 抽象被验证为厂商无关：移植到 NV 的代码 delta 收敛在 spawner 一个资源分支 + values + GPU 栈三处（chart / quota / UI / auth 全部零改动） |
| 4 | **异构车队** | NV+AMD、跨代际（Turing/Ampere/Blackwell/RDNA3）、家用机混部成一个集群——AUP 与 HAMi 官方示例都未覆盖的场景 |
| 5 | **成本叙事** | 5 张二手/消费级卡 ≈ 17 个并发教学席位（基础档），单机方案做不到 |
| 6 | **开源遗产（stretch）** | 可向 AUP 上游提 NV/HAMi accelerator backend PR，实习产出从"内部部署"升级为"开源贡献" |

收尾叙事线：**"AUP 教会我 GPU 教学云的形态，HAMi 教会我 vGPU 隔离的内核；hami-learning-cloud 证明这两者在异构消费级硬件上可以低成本合体，并做出比 AUP 更强的隔离。"**

## 2. 目标与非目标

### 目标（完成线 = 全部达成）
- G1：1 个 K3s 集群，3 节点 5 卡全部入网，NV 走 HAMi 硬配额，AMD 走 time-slicing（N2 受限时以 2 节点 3 卡交付，N2 恢复后补齐并复验）
- G2：单一 JupyterHub（AUP UI：home / spawn / admin 三应用 + hami-learning-cloud branding），学生按课程 spawn
- G3：资源 → 镜像 + GPU 配额映射，按 accelerator 区分 CUDA/ROCm 镜像（override 机制），**最小清单见 §4**
- G4：AUP 配额体系（时计费、quotaRate、CronJob 刷新、admin 批量操作、unlimited）原样移植并启用
- G5：监控面板（Prometheus + DCGM + HAMi vGPUmonitor 指标），管理员可看每学生显存/算力实时占用
- G6：用户 home 持久化（NFS），pod 重建后数据不丢
- G7：一键 `join.sh` 把一台 GPU 机器加入集群；完整 README + 架构图 + 运维手册
- G8：最终 Demo（见 §8）+ 实习总结报告

### 非目标（明确不做，控制范围）
- ❌ 新课程内容 / 新教学镜像（用已验证的现有镜像，最小清单）
- ❌ 中档/大档配额（8000/50%、12000/75%）——架构支持，values 一行即可加，MVP 不做
- ❌ 离线镜像包（`pack` 模式）、PXE netboot（在线环境，机器只有 3 台）
- ❌ GitHub App 认证（用 dummy/native）
- ❌ code-server 模式（现有镜像无 `start-code-server.sh` 契约）
- ❌ 多集群/联邦、企业级审计、计费出账
- ❌ 单 pod 跨机多卡（K8s 限制，HAMi 仅支持同节点多卡，文档中注明）

## 3. 总体架构

```
 学生浏览器 ──(cloudflared tunnel / 直连)──► N1: 2070S + 5060Ti（临时 K3s server + GPU）
   http(s)://<domain>                          ├─ JupyterHub (AUP hub 镜像: core + React apps, haml-branding)
                                               ├─ HAMi: scheduler-extender + device-plugin + vGPUmonitor
                                               ├─ Prometheus + DCGM-exporter + Grafana
                                               └─ cloudflared (TLS 终结)
 N2: 2×3080-20G（K3s GPU agent）               N3: 7900 XTX（K3s GPU agent, AMD）
   ├─ nvidia-container-toolkit                 ├─ ROCm + amdgpu driver
   ├─ HAMi device-plugin + vGPUmonitor         └─ ROCm k8s-device-plugin (time-slicing ×3)
   ├─ label: gpu-vendor=nvidia                 └─ label: gpu-vendor=amd
   └─ ⚠️ 当前 VRAM 被推理占用，恢复后加入       └─ 空闲，首批加入
                          ┌──────────────────────────────┐
                          │  TrueNAS NAS (NFS, 192.168.X.2) │
                          │  <NAS_SHARE>/.../home/<user> │
                          └──────────────────────────────┘

 调度: NV pod → schedulerName=hami-scheduler (vGPU fit/score, 跨节点 binpack/spread)
       AMD pod → schedulerName=default (amd.com/gpu 为普通 extended resource)
 镜像: nvidia accelerator → quay.io/jupyter/pytorch-notebook:cuda13-notebook-7.5.6 (已验证)
       amd accelerator   → ROCm 镜像 (acceleratorOverrides.image, 见 §4 待确认项)
```

## 4. 车队、资源与配额（最小清单）

### 车队

| 节点 | 卡（显存） | 角色 | 共享机制 | base 档席位 |
|---|---|---|---|---|
| N1 | 2070S 8G + 5060Ti 16G | **临时 K3s server + GPU agent** | HAMi | 2 + 4 = 6 |
| N2 | 2× RTX 3080 20G | GPU agent（**暂被推理占用**，恢复后加入；届时可选：保持 N1 为 master（推荐，改动最小）或迁移 master） | HAMi | 4 + 4 = 8 |
| N3 | RX 7900 XTX 24G | AMD agent | time-slicing ×3（无显存隔离，UI 注明"AMD 卡为时间共享"） | 3 |

并发容量（名义值，base 档）：**N1+N3 先行 = 9 人；N2 恢复后 = 17 人**。

### 资源清单（MVP 最小集，Q3 已批）

| 资源 | 镜像 | GPU 配额 | CPU/Mem | quotaRate |
|---|---|---|---|---|
| `cpu` | `quay.io/jupyter/pytorch-notebook:cuda13-notebook-7.5.6`（不带 GPU 资源） | — | 2C / 4-6G | 1 |
| `gpu` | 同上（nvidia accelerator）；`acceleratorOverrides.amd` → ROCm 镜像（见下） | nvidia: `gpumem=4000, gpucores=25%`（HAMi 硬配额）；amd: `amd.com/gpu=1`（时共享） | 4C / 16G | 2 |

- **NV 镜像**：`pytorch-notebook:cuda13-notebook-7.5.6` —— 5 月在 HAMi 侧 4 路共享已验证（`nv-hami/train-pods.yaml`）；cu13 同时覆盖 5060Ti(sm_120)/3080(sm_86)/2070S(sm_75)
- **AMD 镜像（已定稿）**：`rocm/pytorch:2.7.1-rocm6.3` + 3 行 Dockerfile 加 jupyterlab —— 见 `images/Dockerfile.amd`（已写好）；
  鉴权边界 = hub proxy（AUP code-server 同款模式）；**P1 在 N3 裸机先验证 `torch.cuda.is_available()` 再进集群**（tag 如有出入以 N3 实测为准）
- **扩展性**：加课程/加档位 = 往 values 表加行（`images`/`requirements`/`metadata`/`teams`），AUP 多课程模型已验证该机制；MVP 不做

### 设计决策
- **D1 — accelerator 只建 `nvidia`/`amd` 两个，不按 GPU SKU 分**。
  理由：N1 是混合卡机器，K8s 无法在 pod 级选卡；NV 三卡共用同一 CUDA 镜像；配额表即路由（要 12G 的 pod 自然落不到 8G 卡上）。
- **D2 — schedulerName 按 accelerator 分派**：nvidia → `hami-scheduler`，amd → 默认 scheduler。
- **配额单位**：HAMi `nvidia.com/gpumem`=MB、`nvidia.com/gpucores`=%。

## 5. 分阶段计划

### P0 — 仓库与品牌（0.5d）
- [ ] fork AUP 仓库（@ `27f4190`）→ 项目 **hami-learning-cloud**（位置：默认先在本目录 git init，后推私有 GitHub，见 §10 Q4）
- [ ] 品牌替换：AGENTS.md 4 层归因 → hami-learning-cloud（home 页 / footer / HTTP header / `branding.ts` 常量）
- [ ] 清理 AMD 专属内容（ROCm 文档等），README 按 §1 叙事线重写
- **验收**：repo 可 clone，`git log` 干净，品牌一致

### P1 — 集群 + GPU 栈（3d）
- [ ] N1 装 K3s server（v1.35.x，containerd，无 Docker）+ Helm + NFS client
- [ ] N3 `join.sh`：k3s agent + ROCm + amdgpu + ROCm k8s-device-plugin（time-slicing sliceCount=3，复用 `amd-hami/manifests` 资产改 slice 数）
- [ ] N1 GPU 部分：nvidia-container-toolkit（**580 系驱动锁版本**）+ HAMi v2.9.0 chart（scheduler-extender + device-plugin + vGPUmonitor）
- [ ] 节点打标：`gpu-vendor=nvidia|amd`（join.sh 直接打）
- [ ] TrueNAS NFS PV/PVC（RWX）挂载测试
- [ ] **N2 保持现状**：等推理结束再按 join.sh 加入（GPU 栈 + 打标 + 复验 4 路共享）
- **验收**（N2 缺席版）：
  - `kubectl get nodes`：N1/N3 Ready，allocatable 含 `nvidia.com/gpumem`/`gpucores` 与 `amd.com/gpu`
  - N1 上 5060Ti 与 2070S 各跑一次 `train.py`（cu13 镜像 sm_120/sm_75 兼容确认）
  - 单卡 4 路（4G/25%）隔离复跑（5060Ti 或 2070S 上，nvidia-smi + vGPUmonitor 指标佐证）
  - N3 ROCm torch 跑通（集群内验证）
- **验收**（N2 恢复后补齐）：N2 加入 + 3080 上 4 路共享复跑

### P2 — AUP runtime 移植（5d，核心工作量）
- [ ] `runtime/hub/core/config.py`：accelerator 模型加 `vendor`/`scheduler` 字段
- [ ] `runtime/hub/core/spawner/kubernetes.py`（1230 行，改动收敛在 `_configure_spawner`）：
      `if "amd.com/gpu" in requirements` 分支 → 按 vendor 分派：
      - nvidia：`extra_resource_*` = `nvidia.com/gpu:1 + gpumem + gpucores`，`runtime_class_name="nvidia"`，`scheduler_name="hami-scheduler"`
      - amd：`amd.com/gpu:1`，`scheduler_name=default`
- [ ] `values.yaml`：accelerators（D1 两 entry）+ resources（§4 最小清单）+ teams 映射
- [ ] hub 镜像构建：`dockerfiles/Hub/Dockerfile`（pnpm 前端 3 apps + core 打包，仅 branding 变）
- [ ] chart（`runtime/chart`，Z2JH 4.3.3 fork）**零改动**部署
- [ ] dummy-auth MVP 端到端：浏览器 spawn 一个 nvidia `gpu` + 一个 amd `gpu` + 一个 `cpu`
- **验收**：三种 spawn 均成功，pod spec 中资源/镜像/schedulerName/runtimeClass 正确

### P3 — 镜像契约 + spawn 全流程（2d，最小清单版）
- [ ] `pytorch-notebook:cuda13` 契约核查：workdir / `~/home` landing（无 start-code-server.sh → code-server 模式关闭，符合非目标）
- [ ] 构建 `images/Dockerfile.amd`（AMD override 镜像）并推入集群节点；AMD 侧契约核查（`rocm/pytorch` 的 home/workdir 与 Z2JH storage 挂载路径对齐）
- [ ] image-puller DaemonSet 预拉全部镜像到 GPU 节点
- [ ] teams → 资源访问权限打通（native 用户 + 团队）
- [ ] spawn form 全链路：资源选择 → accelerator 选择（nvidia/amd 下拉）→ git clone 选项 → 持久化选项
- **验收**：不同团队/资源组合 spawn 正确；新节点 join 后 5 分钟内镜像就绪

### P4 — 配额 + 监控 + 用户管理（2d）
- [ ] quota 启用：`quota.enabled`、`defaultQuota`、`refreshRules`（CronJob 生成）、`minimumToStart`
- [ ] admin 批量操作脚本（AUP `scripts/manage_users.py` 移植：CSV 批量建号/设额/刷新）
- [ ] home UI 分钟余额显示（AUP 现成）
- [ ] 监控栈：kube-prometheus-stack + dcgm-exporter（NV）+ HAMi vGPUmonitor 指标 + 1 块 Grafana 面板（按用户聚合显存&算力）
- **验收**：配额耗尽 → spawn 被拒并提示余额；admin 加额 → 立即可 spawn；Grafana 看到 per-pod 实时曲线

### P5 — 收尾：加固 + 文档 + Demo + 报告（2.5d）
- [ ] cloudflared tunnel + TLS（`publicScheme=https` + allowedOrigins）
- [ ] native auth 正式启用（dummy 保留为 dev profile）
- [ ] 运维手册：join.sh / 升级 / 备份（etcd 快照 + hub sqlite）/ N2 加入与 master 迁移 / 故障排查（复用 HAMi `skill/` 调试文档）
- [ ] 架构图更新为 as-built；README 终稿
- [ ] 按 §8 脚本录制 Demo 视频（5~8 分钟）
- [ ] 实习总结报告（叙事线见 §1）
- **验收**：§8 全流程无人工干预跑通；新人按 README 30 分钟内可复现集群

### Stretch（无硬期限，按优先级）
1. 上游 PR：AUP 仓库贡献 NV/HAMi accelerator backend（spawner 分支 + values schema）——**建议必保**
2. 中档/大档配额档（values 加行 + 复验）
3. 用 `auplc_installer` Python 包包装单节点 quickstart（TUI + GPU 检测改 `nvidia-smi`）
4. HAMi-WebUI 作为可选监控前端 / 3080 节点 soft affinity

## 6. 参考节奏（Q2 已批：无硬期限，按阶段推进）

| 阶段 | 内容 | 阶段末可演示物 |
|---|---|---|
| 第 1 段 | P0 + P1 | N1+N3 双节点集群 + 4 路硬隔离训练 + AMD 时共享跑通 |
| 第 2 段 | P2 | AUP UI（hami branding）上线，NV/AMD/CPU 三路径 spawn 成功 |
| 第 3 段 | P3 + P4 | spawn 全流程 + 配额计费 + Grafana 面板 |
| 第 4 段 | P5 + N2 加入 | TLS 公网访问 + N2 复验 + Demo 视频 + 报告 |

（N2 恢复时点不确定，第 4 段弹性最大；N2 缺席不影响前三段完成线，仅 G1 以 2 节点 3 卡形态交付。）

## 7. 风险与缓解

| 风险 | 概率 | 缓解 |
|---|---|---|
| P2 移植超预期（spawner/handlers 体量大） | 中 | 改动面已审计收敛（§5-P2）；先 dummy-MVP 后加配额；无硬期限，可放慢 |
| 5060Ti 驱动/CUDA 13 与 2070S 同机冲突 | 低 | P1 首日 spike；最坏 2070S 退为 CPU 节点（N1 其余部分不受影响） |
| N1 单点（临时 master 在 2070 机器上，家用机断网/断电 = 全集群掉） | 中 | etcd 快照定时任务 + 运维手册恢复章节；**N2 恢复后评估 master 迁移**；N1 上 UPS（Q7，用户决定） |
| 7900XTX time-slicing 无隔离导致学生互相 OOM | 中 | slice=3 保守值 + UI 文案注明"AMD 卡为时间共享" |
| 现有镜像不满足 AUP 资源契约 | 低 | P3 首日契约核查；不满足 → 降级（code-server 已在非目标） |
| N2 推理长期不结束 | 中 | 计划已按 2 节点可交付设计（§6）；G1 验收拆为两档 |
| 家庭带宽不足 | 低 | 镜像全部预拉 + 数据集放 NFS 共享卷 |

## 8. 最终验收 Demo 脚本（≈7 分钟）

1. **0:00** 集群总览：`kubectl get nodes` + Grafana 集群视图（3 节点 5 卡，N2 缺席时 2 节点 3 卡）
2. **1:00** 学生 A 登录 → spawn `gpu`（nvidia）→ 落 NV 卡，4G/25%，日志确认
3. **2:30** 学生 B spawn `gpu`（amd）→ 7900XTX，ROCm 镜像，time-slice；学生 C spawn `cpu`
4. **4:00** 隔离性：4 人同时占一张 NV 卡，各自跑到 4G 显存上限 OOM，互不影响（HAMi 硬配额，全场最亮眼）
5. **5:00** 配额：学生 A 余额耗尽 → spawn 被拒；admin CSV 批量加额 → 成功
6. **6:00** 持久化：删除学生 B 的 pod → 重新 spawn → 文件还在（NFS）
7. **6:30** 扩展性：现场跑 `join.sh`（或演示 etcd 快照恢复 / N2 加入过程回放）
8. 收尾：成本与容量数字（5 卡 ≈ 17 席位），AUP+HAMi 合体叙事与开源贡献展望

## 9. 交付物清单

- [ ] Git 仓库 hami-learning-cloud（代码 + manifests + values + 脚本）
- [ ] 本计划文档（v1.0）+ 架构图（as-built）+ 运维手册 + README
- [ ] 运行中的集群 + 公网入口
- [ ] Demo 视频
- [ ] 实习总结报告（§1 叙事线）
- [ ] （stretch）AUP 上游 PR

## 10. 决策记录与默认值

| # | 事项 | 决定 |
|---|---|---|
| Q1 | 项目名 | ✅ **hami-learning-cloud**，AUP 与 HAMi 的共同后继（2026-08-19 已批） |
| Q2 | 期限 | ✅ 无硬期限，按 §6 阶段推进（已批） |
| Q3 | 课程镜像 | ✅ 最小清单：§4 表（NV=`pytorch-notebook:cuda13` 已验证；AMD=`rocm/pytorch:2.7.1-rocm6.3` + jupyterlab，`images/Dockerfile.amd` 已写好）（已批） |
| Q4 | 仓库位置 | 默认：本目录 git init 起步，后续推私有 GitHub（可随时改） |
| Q5 | 认证 | 默认：P2 dummy 起步 → P4 切 native |
| Q6 | Stretch | 默认：保上游 PR（建议必保），其余可选 |
| Q7 | UPS | 未定，不阻塞，用户自决 |
| Q8 | 报告形式 | 默认：中文报告文档 + Demo 视频；PPT/英文版可选 |
