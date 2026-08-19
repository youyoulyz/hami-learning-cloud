# hami-learning-cloud 实习总结报告

## 一句话结论

**AUP 教会我 GPU 教学云的形态，HAMi 教会我 vGPU 隔离的内核；hami-learning-cloud 证明这两者在异构消费级硬件上可以低成本合体，并做出比 AUP 更强的隔离。**

## 项目背景

AUP Learning Cloud 是面向 AMD 消费级 GPU 的教学云：它有完整的 UI、课程模型、团队/配额体系，但 GPU 共享只有 time-slicing，没有显存/算力硬隔离。HAMi 提供 Kubernetes vGPU 硬配额（显存 MB + 算力 %），但缺少教学云形态。本项目把两者结合：用 AUP 的 Hub/UI/配额体系作为外壳，用 HAMi 作为 NVIDIA 侧 vGPU 内核，用 ROCm time-slicing 作为 AMD 侧共享机制，最终在一个 K3s 集群 + 一个 JupyterHub 里交付一个可演示、可交接的多租户 GPU 教学云。

## 硬件与集群

当前交付形态为 2 节点 3 卡：

| 节点 | 硬件 | 角色 | 共享机制 |
|---|---|---|---|
| N1 | 2070S 8G + 5060Ti 16G | K3s server + NV GPU 节点 | HAMi vGPU 硬配额 |
| N3 | RX 7900 XTX 24G | AMD GPU 节点 | ROCm time-slicing ×3 |
| N2 | 2× RTX 3080 20G | 未加入 | 因推理负载占用，按铁律不动 |

集群入口：
- JupyterHub：`http://192.168.X.1:30890`
- Grafana：`http://192.168.X.1:30300`
- 公网：cloudflared quick tunnel（临时 URL）

## 核心架构

```
学生浏览器
  └─ cloudflared / 局域网
      └─ JupyterHub（AUP UI，hami-learning-cloud branding）
          ├─ nvidia accelerator → hami-scheduler + nvidia runtimeClass + HAMi gpumem/gpucores
          ├─ amd accelerator    → default-scheduler + amd.com/gpu time-slice
          └─ cpu resource       → default-scheduler + no GPU
用户 home
  └─ TrueNAS NFS RWX（/home/jovyan/<username>）
监控
  └─ Prometheus + DCGM exporter + HAMi vGPUmonitor + Grafana per-user panel
```

## 关键设计决策

1. **accelerator 只建 `nvidia` 和 `amd` 两个，不按 SKU 分。**  
   原因是 N1 是混合卡机器，K8s pod 级不能直接选具体 SKU；通过配额表做路由：要 12G 的 pod 自然落不到 8G 卡上。
2. **schedulerName 按 accelerator 分派。**  
   NV 走 `hami-scheduler`，利用 HAMi extender 做 vGPU fit/score；AMD 走默认 scheduler，因为 `amd.com/gpu` 是普通 extended resource。
3. **AUP `runtime/chart` 零改动。**  
   GPU 资源、调度器、runtimeClass、镜像 override 全部通过 AUP values + spawner 注入，chart 保持厂商无关。
4. **HAMi webhook 只对 NV pod 生效。**  
   实测发现 HAMi mutating webhook 会把带 GPU 的 pod 改成 `hami-scheduler`。因此 AMD/CPU pod 打 `hami.io/webhook=ignore`，NV pod 不忽略，保持 HAMi 注入。
5. **用户 home 用 NFS static PVC + subPath。**  
   避免 local-path RWO 与 GPU nodeAffinity 冲突，同时满足 pod 重建后数据不丢。

## 已完成验收

### P1
- N1 K3s + HAMi v2.9.0 + nvidia-container-toolkit 就绪。
- N3 通过 `join.sh` 加入，ROCm 自定义 time-slice device plugin 提供 `amd.com/gpu: 3`。
- NV 单卡 4 路 4G/25% 硬隔离已验证。
- NFS RWX home 已验证。

### P2
- AUP runtime 成功移植 NV/HAMi + AMD time-slicing。
- dummy auth 下三种 spawn 均成功：
  - NV pod：`schedulerName=hami-scheduler`、`runtimeClassName=nvidia`、`nvidia.com/gpumem=4000`、`nvidia.com/gpucores=25`。
  - AMD pod：`schedulerName=default-scheduler`、`amd.com/gpu=1`、ROCm 镜像可见 7900XTX。
  - CPU pod：无 GPU，正常启动。

### P3
- 镜像契约核查完成。
- 持久化验收通过：删除 pod/server 后重新 spawn，`/home/jovyan/persist-test.txt` 仍在。

### P4
- Quota 启用：默认 100，最低启动 10。
- 低额 spawn 被拒，admin 加额后立即可 spawn。
- `scripts/manage_quota.py` 支持 list/set/add 与 CSV 批量。
- Grafana 部署完成，面板展示 per-user VRAM/compute 与 DCGM GPU utilization。

### P5
- cloudflared quick tunnel 公网入口可用。
- HAMi/DCGM DaemonSet 收紧到 NV 节点，AMD 节点不再误跑 NVIDIA-only 组件。
- `join.sh` 修正 AMD 标签，避免未来新 AMD 节点被 HAMi/DCGM 选中。
- 文档与状态更新完成。

## 遇到的关键问题与解决

| 问题 | 现象 | 根因 | 解决 |
|---|---|---|---|
| 旧 local-path PVC 卡住 Hub | Hub Pending | 5 月残留 PVC 的 nodeAffinity 指向已删除孤儿节点 | 删除旧 PVC/PV，重建；后续用户 home 改 NFS static |
| K3s 镜像被 GC | `ErrImageNeverPull` / 课程镜像消失 | 磁盘 83% 触发 containerd GC | 释放磁盘并重新导入镜像；运维上需监控磁盘 |
| NV pod 看到双卡 | `torch.cuda.device_count()==2` | spawner 曾强设 `NVIDIA_VISIBLE_DEVICES=all` | 移除该默认，让 HAMi/NVIDIA runtime 自行注入 |
| AMD pod 被改成 hami-scheduler | AMD pod `schedulerName=hami-scheduler` | HAMi mutating webhook 匹配所有 pod | AMD/CPU pod 打 `hami.io/webhook=ignore`，NV 不忽略 |
| AMD 镜像不能跑 JupyterHub | base ROCm 镜像无 `jupyterhub-singleuser` | `rocm/pytorch` 只是训练镜像 | 构建 `hami-lc-amd:v1`，安装 `jupyterhub==4.1.6` + JupyterLab |
| HAMi/DCGM 误跑 AMD 节点 | DaemonSet 在 N3 ContainerCreating | `gpu=on` 标签被 AMD 节点继承 | DS 收紧到 `gpu-vendor=nvidia`，join.sh AMD 不再打 `gpu=on` |

## 容量与成本

基础档（NV 4000MB/25%，AMD 1 slice）：

- N1 2070S 8G：约 2 席
- N1 5060Ti 16G：约 4 席
- N3 7900XTX 24G（time-slice ×3，无显存隔离）：3 席
- 当前 N1+N3：9 席
- N2 恢复后（2×3080-20G）：+8 席，总计约 17 席

5 张二手/消费级卡 ≈ 17 个并发教学席位（基础档），这是单机教学环境难以做到的。

## 未完成与后续

1. **N2 加入**：等 3080×2 推理负载结束后，用 `join.sh nvidia` 加入，并复跑 4 路 HAMi 隔离。
2. **Demo 视频**：需要人工按 `PLAN.md §8` 录屏与讲解。
3. **上游 PR**：可把 spawner 的 NV/HAMi accelerator backend 和 values schema 经验整理成 AUP 上游 PR（stretch）。
4. **正式认证**：当前为 dummy auth 演示态；正式教学建议切 native/multi auth 并修改 Grafana/admin 默认密码。

## 交付物

- 公开仓库：`hami-learning-cloud`
- 可运行集群：N1 + N3
- 代码/manifests：`runtime/`、`deploy/`、`images/`、`scripts/`、`join.sh`
- 文档：`PLAN.md`、`README.md`、`P1-STATUS.md`、`P2-P5-STATUS.md`、本报告
