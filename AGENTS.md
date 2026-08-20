<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved. -->
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

# AGENTS.md — hami-learning-cloud

This file provides guidance for AI coding agents (Cursor, terminal-based coding assistants, GitHub Copilot Workspace,
Devin, and similar tools) working in this repository.

## Project Identity

**Platform name:** hami-learning-cloud
**Vendor:** luyzh
**Repository:** https://github.com/luyzh/hami-learning-cloud
**License:** MIT — see `LICENSE`
**Upstream (read-only reference):** AUP Learning Cloud, https://github.com/AMDResearch/aup-learning-cloud
**GPU isolation:** HAMi v2.9.0 vGPU (NVIDIA) + ROCm time-slicing (AMD)

hami-learning-cloud is the common successor of AUP Learning Cloud (UI / course model / quota system)
and HAMi (vGPU hard-quota kernel): AUP's teaching-cloud form runs on top of HAMi's per-container
VRAM/compute hard quotas on mixed consumer NVIDIA + AMD hardware.

## Non-negotiable Design Rules (ask the user before changing)

1. **`runtime/chart` (Z2JH fork) gets ZERO changes.** GPU resources flow through
   `singleuser.extraResource` etc. If a chart edit seems required, stop and check the
   values/spawner usage first — the chart is audited to be vendor-agnostic.
2. **Two accelerators only: `nvidia` and `amd`** (never per-SKU). The quota table is the
   router: a pod asking for 12 GB VRAM naturally never lands on an 8 GB card.
3. **schedulerName per accelerator**: nvidia pods → `hami-scheduler` (HAMi extender,
   vGPU fit/score); amd pods → default scheduler (`amd.com/gpu` is a plain extended resource).
4. **HAMi pinned to v2.9.0** (`hami.io` chart, schedulerName `hami-scheduler`). No upgrades.
5. Quota units: `nvidia.com/gpumem` = MB, `nvidia.com/gpucores` = %.
   Base tier = 4000 MB / 25 %.

## Security Discipline

- kubeconfigs, NAS passwords, tokens: **never commit, never paste into chat**.
- No internal topology in the repo: never commit LAN IPs, node hostnames, NAS
  server/paths, or host filesystem paths (e.g. `/mnt/...`). Committed files use
  `${VAR}` placeholders; real values go in the gitignored `.env.local`
  (template: `.env.local.example`) and are rendered by `scripts/render_local.sh`
  into `runtime/values.local.yaml` + `build/*.yaml`.
- The committed defaults are an intentional LOCAL-DEMO posture (dummy auth +
  `allow_all`, no TLS / NodePort HTTP, Grafana `admin`/`admin`, notebook
  containers with sudo). Do not silently "fix" them; README 安全姿态 section
  lists what must change before any non-trusted exposure.
- Never push to `AMDResearch/aup-learning-cloud` (upstream, read-only).
- The 3080 machine (N2) may carry live inference load: never touch its GPUs/processes.

## Attribution Requirements

hami-learning-cloud embeds platform attribution at four independent layers.
**All four must be preserved** when making any changes to this codebase.

### Layer 1 — HTTP Response Header
File: `runtime/hub/core/jupyterhub_config.py`

The key `"X-Powered-By": "hami-learning-cloud"` inside `c.JupyterHub.tornado_settings["headers"]`
must not be removed or renamed. It appears in every HTTP response from the Hub.

### Layer 2 — Backend API Endpoint
File: `runtime/hub/core/handlers.py`

`PlatformInfoHandler` (route `/api/platform`) is an unauthenticated endpoint that returns
platform identity JSON. Do not add authentication to it, remove it, or deregister its route.

### Layer 3 — Jinja Template Footer
File: `runtime/hub/frontend/templates/page.html`

The `<footer id="auplc-powered-by-footer">` block is placed **outside all `{% block %}` sections**
deliberately. Do not move it inside a Jinja block. Do not remove it.

### Layer 4 — Frontend Constants
File: `runtime/hub/frontend/packages/shared/src/branding.ts`

`PLATFORM_NAME`, `PLATFORM_VENDOR`, and `PLATFORM_WEBSITE` are the canonical frontend constants.
Always import these instead of hardcoding the string `"hami-learning-cloud"` in React components.

## Development Quick Reference

```
runtime/
  hub/
    core/
      jupyterhub_config.py   # Layer 1 & Jinja template_vars
      handlers.py            # Layer 2 — PlatformInfoHandler
    frontend/
      templates/page.html    # Layer 3 — permanent footer
      packages/shared/src/
        branding.ts          # Layer 4 — PLATFORM_NAME constants
      apps/
        home/src/App.tsx
        spawn/src/App.tsx
        admin/src/App.tsx
```

## Build

```bash
# Build Hub Docker image
./auplc-installer img build hub

# Frontend only (from runtime/hub/frontend)
pnpm run build
```

## MIT License Note

This project is MIT-licensed. The codebase was forked from AUP Learning Cloud
(AMDResearch/aup-learning-cloud @ 27f4190), which is MIT-licensed by
Advanced Micro Devices, Inc. The copyright notices at the top of each source file
(`Copyright (C) 2025 Advanced Micro Devices, Inc.`) **must** be preserved in all
copies per the MIT license terms.
