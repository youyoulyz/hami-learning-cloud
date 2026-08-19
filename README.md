<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.  Portions of this notebook consist of AI-generated content. -->
<!--
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

# hami-learning-cloud

**AUP Learning Cloud 与 HAMi 的共同后继**：AUP 提供教学云的形态（UI / 课程模型 / 配额体系），
HAMi 提供 vGPU 硬隔离内核（显存 MB + 算力 % 的 per-container 硬配额）。本项目是两者在
**消费级 NVIDIA + AMD 异构硬件**上的合体：一个 K3s 集群、一个 JupyterHub、5 张二手卡，
≈17 个并发教学席位。

> 计划与验收标准见 [`PLAN.md`](PLAN.md)（唯一事实来源），交接背景见 [`HANDOVER.md`](HANDOVER.md)。

## 为什么值得做

| # | 论点 | 说明 |
|---|------|------|
| 1 | **真隔离** | AUP 官方只有 time-slicing，无显存/算力隔离；本项目用 HAMi 提供 `gpumem` + `gpucores` 硬配额，单卡可承载 4~5 个互不干扰的学生（4 路 4G/25% 已验证） |
| 2 | **AUP + HAMi 的合体** | 教学云形态与 vGPU 隔离内核第一次在消费级 NVIDIA 硬件上完整落地，两者拼接 delta 极小 |
| 3 | **架构普适性证明** | AUP `custom.accelerators` 抽象被验证为厂商无关：NV 移植的 delta 收敛在 spawner 一个资源分支 + values 两处，chart / quota / UI / auth 全部零改动 |
| 4 | **异构车队** | NV+AMD、跨代际（Turing/Ampere/Blackwell/RDNA3）、家用机混部成一个集群——AUP 与 HAMi 官方示例都未覆盖 |
| 5 | **成本叙事** | 5 张二手/消费级卡 ≈ 17 个并发教学席位（基础档），单机方案做不到 |
| 6 | **开源遗产（stretch）** | 可向 AUP 上游提 NV/HAMi accelerator backend PR |

## 车队与共享机制

| 节点 | 卡（显存） | 角色 | 共享机制 |
|---|---|---|---|
| N1 | 2070S 8G + 5060Ti 16G | K3s server + GPU 节点 | HAMi vGPU 硬配额 |
| N2 | 2× RTX 3080 20G | GPU 节点 | HAMi vGPU 硬配额 |
| N3 | RX 7900 XTX 24G | AMD 节点 | ROCm time-slicing ×3（无显存隔离，UI 已注明） |

- 调度：NV pod → `schedulerName: hami-scheduler`（HAMi extender，vGPU fit/score）；
  AMD pod → 默认 scheduler（`amd.com/gpu` 为普通 extended resource）。
- 配额即路由：accelerator 只建 `nvidia`/`amd` 两个（不按 SKU），要 12G 的 pod 自然落不到 8G 卡上。
- 镜像：nvidia → `quay.io/jupyter/pytorch-notebook:cuda13-notebook-7.5.6`（cu13 覆盖
  sm_75/sm_86/sm_120，已验证）；amd → `rocm/pytorch` + jupyterlab（[`images/Dockerfile.amd`](images/Dockerfile.amd)）。

## 配额（MVP 最小档）

| 资源 | 镜像 | GPU 配额 | CPU/Mem | quotaRate |
|---|---|---|---|---|
| `cpu` | 同上（不带 GPU 资源） | — | 2C / 4-6G | 1 |
| `gpu` | nvidia / amd（accelerator override） | nvidia: `gpumem=4000, gpucores=25%`；amd: `amd.com/gpu=1` | 4C / 16G | 2 |

HAMi 单位：`nvidia.com/gpumem`=MB、`nvidia.com/gpucores`=%。中档（8000/50%）、大档（12000/75%）
架构支持，values 加行即可（MVP 不做）。

## 快速开始

单节点开发环境（AUP installer 路径，详见 `auplc-installer`）：

```bash
git clone <this repo> && cd hami-learning-cloud
./auplc-installer        # TUI 交互安装
```

多节点 GPU 集群：

```bash
# master 已在 N1；新节点一行加入（P1 交付 join.sh 后启用）
./join.sh <node>
```

用户 home 持久化：TrueNAS NFS RWX（`<NAS_SHARE>/.../home/<user>`），pod 重建数据不丢。
公网入口：cloudflared tunnel（`publicScheme=https` + allowedOrigins）。

## 目录

```
runtime/            AUP runtime（hub core + React 前端 + Z2JH chart fork，零改动）
  hub/core/         spawner / quota / handlers / auth（NV/AMD 移植点收敛在 spawner 资源分支）
  chart/            Z2JH 4.3.3 fork — 零改动原则
projects/           课程（CV / DL / LLM / PhySim，沿用 AUP 课程）
images/             本项目自定义镜像（Dockerfile.amd）
deploy/             部署脚本 / manifests / Ansible
scripts/            用户批量管理、values schema 生成、资源契约校验
auplc-installer/    Python 单节点 installer（TUI）
PLAN.md             实施计划 v1.0（唯一事实来源）
HANDOVER.md         3080 → 2070 机器交接书
```

## 路线图

P0 仓库与品牌 → P1 集群 + GPU 栈（N1/N3，N2 恢复后补齐）→ P2 AUP runtime 移植 +
dummy 三路径 spawn → P3 镜像契约 + spawn 全链路 → P4 配额 + 监控 + 用户管理 →
P5 TLS + 运维手册 + Demo + 报告。各阶段验收标准见 [PLAN.md §5](PLAN.md)。

## Contributing

见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## Acknowledgment

本项目 fork 自 [AUP Learning Cloud](https://github.com/AMDResearch/aup-learning-cloud)
（AMD，MIT），并复用其课程套件：

| University | Professors and Labs | Toolkits |
|---|---|---|
| National Taiwan University | [Prof. Chun-Yi Lee](https://www.csie.ntu.edu.tw/en/member/Faculty/Chun-Yi-Lee-67240464), [ELSA Lab](https://elsalab.ai/) | DL, CV |
| Nanjing University | [Prof. Jingwei Xu](https://njudeepengine.github.io/jingweixu/), [NJUDeepEngine](https://github.com/NJUDeepEngine) | LLM |

GPU 隔离内核来自 [HAMi](https://github.com/Project-HAMi/HAMi)（v2.9.0）。
