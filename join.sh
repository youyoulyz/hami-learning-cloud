#!/bin/bash
# hami-learning-cloud: one-command GPU node join.
#
# Usage (on the joining node):
#   sudo ./join.sh --server <K3S_SERVER_IP> --token <K3S_TOKEN> [--vendor nvidia|amd] [--force] [--nas-mount /opt/hami-lc-home]
#
# Local values live in .env.local (gitignored; copy it to the joining node too):
#   set -a; . ./.env.local; set +a
#   sudo -E ./join.sh --server "$K3S_SERVER_IP" --token "$K3S_TOKEN" [--vendor nvidia|amd]
# NAS home mount is driven by NAS_SERVER + NAS_HOME_EXPORT from that env file;
# if NAS_SERVER is unset the NAS step is skipped.
#
# K3S_TOKEN on the master (N1):  sudo cat /var/lib/rancher/k3s/server/token
#
# What it does:
#   1. pre-flight checks (OS, sudo, server reachability, GPU detection)
#   2. stops/wipes an existing k3s instance (--force required)
#   3. installs k3s agent (pinned version, containerd)
#   4. installs the per-vendor GPU stack:
#        nvidia: nvidia-container-toolkit (CDI + containerd runtime), labels gpu=on
#                (cluster-scoped HAMi daemonsets pick the node up automatically)
#        amd:    hami-learning-cloud AMD time-slicing device plugin (custom binary),
#                labels gpu=on + gpu-vendor=amd + amd.com/gpu.present=true
#   5. mounts the NAS home share (NFS) if absent (default /opt/hami-lc-home)
set -euo pipefail

K3S_VERSION="v1.35.4+k3s1"
SERVER_IP=""
TOKEN=""
VENDOR=""
FORCE=0
SLICE_COUNT="${SLICE_COUNT:-3}"
NAS_SERVER="${NAS_SERVER:-}"
NAS_HOME_EXPORT="${NAS_HOME_EXPORT:-/hami-lc-home}"
NAS_HOME_MOUNT="/opt/hami-lc-home"
AMD_PLUGIN_HOST_PATH="/opt/hami-lc/amd-time-slice"
AMD_PLUGIN_CONTAINER_PATH="/opt/amd-time-slice"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

###############################################################################
# arg parsing
###############################################################################
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server)    SERVER_IP="$2"; shift 2 ;;
    --token)     TOKEN="$2"; shift 2 ;;
    --vendor)    VENDOR="$2"; shift 2 ;;
    --force)     FORCE=1; shift ;;
    --nas-mount) NAS_HOME_MOUNT="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^#//;s/^ //'; exit 0 ;;
    *) log_error "unknown arg: $1"; exit 1 ;;
  esac
done

[[ -n "$SERVER_IP" ]] || { log_error "--server <ip> required"; exit 1; }
[[ -n "$TOKEN"   ]] || { log_error "--token <k3s-token> required (on master: sudo cat /var/lib/rancher/k3s/server/token)"; exit 1; }
[[ $EUID -eq 0 ]]   || { log_error "run with sudo"; exit 1; }

###############################################################################
# 1. pre-flight
###############################################################################
log_info "Pre-flight checks"
. /etc/os-release
log_info "OS: $PRETTY_NAME (kernel $(uname -r))"
# any HTTP answer (even 401) proves the server is reachable
if ! curl -sk --max-time 5 "https://${SERVER_IP}:6443/healthz" >/dev/null 2>&1; then
  log_error "cannot reach k3s server ${SERVER_IP}:6443"
  exit 1
fi
log_info "server ${SERVER_IP}:6443 reachable"

if [[ -z "$VENDOR" ]]; then
  if command -v rocm-smi >/dev/null 2>&1 && ls /dev/kfd >/dev/null 2>&1; then
    VENDOR="amd"; log_info "auto-detected vendor: amd ($(rocm-smi --showproductname 2>/dev/null | grep -m1 'Card' || echo 'ROCm GPU'))"
  elif command -v nvidia-smi >/dev/null 2>&1; then
    VENDOR="nvidia"; log_info "auto-detected vendor: nvidia ($(nvidia-smi --query-gpu=name --format=csv,noheader | head -1))"
  else
    log_error "no GPU detected (neither rocm-smi+/dev/kfd nor nvidia-smi); pass --vendor explicitly"
    exit 1
  fi
fi
log_info "vendor: ${VENDOR}"

###############################################################################
# 2. existing k3s
###############################################################################
if systemctl is-active k3s >/dev/null 2>&1 || command -v k3s >/dev/null 2>&1; then
  if [[ $FORCE -ne 1 ]]; then
    log_error "k3s already present on this machine. Re-running with --force will STOP it and WIPE /var/lib/rancher/k3s (etcd data lost). Confirm and re-run."
    exit 1
  fi
  log_warn "--force: stopping k3s and wiping /var/lib/rancher/k3s"
  systemctl stop k3s 2>/dev/null || true
  rm -rf /var/lib/rancher/k3s
  rm -f /usr/local/bin/k3s /usr/local/bin/kubectl /usr/local/bin/krictl
  rm -f /etc/rancher/k3s/k3s.yaml
fi

###############################################################################
# 3. k3s agent
###############################################################################
log_info "installing k3s agent ${K3S_VERSION}"
curl -sfL "https://github.com/k3s-io/k3s/releases/download/${K3S_VERSION}/k3s" -o /usr/local/bin/k3s
chmod +x /usr/local/bin/k3s
ln -sf /usr/local/bin/k3s /usr/local/bin/kubectl
ln -sf /usr/local/bin/k3s /usr/local/bin/krictl

cat > /etc/systemd/system/k3s.service <<EOF
[Unit]
Description=K3s Agent
Documentation=https://docs.k3s.io
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
Environment="K3S_URL=https://${SERVER_IP}:6443"
Environment="K3S_TOKEN=${TOKEN}"
ExecStart=/usr/local/bin/k3s agent
KillMode=process
Delegate=yes
LimitNOFILE=1048576
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
TimeoutStartSec=0
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable k3s --now
for i in $(seq 1 30); do
  systemctl is-active k3s >/dev/null 2>&1 && break
  sleep 2
done
systemctl is-active k3s >/dev/null 2>&1 || { log_error "k3s agent failed to start"; journalctl -u k3s | tail -20; exit 1; }
log_info "k3s agent running"

log_info "rewriting agent kubeconfig server to ${SERVER_IP}"
if [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
  sed -i "s|server: https://127.0.0.1:6443|server: https://${SERVER_IP}:6443|" /etc/rancher/k3s/k3s.yaml
fi

###############################################################################
# 4. GPU stack
###############################################################################
if [[ "$VENDOR" == "amd" ]]; then
  # AMD nodes must not carry gpu=on: HAMi/DCGM daemonsets select gpu=on and are
  # NVIDIA-only. The custom AMD time-slice plugin selects amd.com/gpu.present.
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl label node "$(hostname)" --overwrite gpu-vendor=amd amd.com/gpu.present=true
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl label node "$(hostname)" gpu- || true
else
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl label node "$(hostname)" --overwrite gpu=on gpu-vendor=nvidia
fi

if [[ "$VENDOR" == "nvidia" ]]; then
  log_info "nvidia stack: nvidia-container-toolkit + CDI + containerd runtime"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | tee /etc/apt/keyrings/nvidia-container-toolkit-keyring.gpg >/dev/null 2>&1 || \
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL -o /etc/apt/sources.list.d/nvidia-container-toolkit.list \
    "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list"
  . /etc/apt/sources.list.d/nvidia-container-toolkit.list 2>/dev/null || true
  apt-get update -qq
  apt-get install -y -qq nvidia-container-toolkit
  nvidia-ctk cdi generate
  nvidia-ctk runtime configure --runtime=containerd
  systemctl restart k3s
  sleep 10
  log_info "nvidia stack done (HAMi daemonsets will pick up the gpu=on node automatically)"
else
  log_info "amd stack: hami-learning-cloud time-slicing plugin (sliceCount=${SLICE_COUNT})"
  modprobe amdgpu || log_warn "amdgpu module not loaded"
  if [[ ! -x "${AMD_PLUGIN_HOST_PATH}/k8s-device-plugin" ]]; then
    log_error "AMD time-slice binary not found at ${AMD_PLUGIN_HOST_PATH}/k8s-device-plugin"
    log_error "Build it with deploy/amd/build-time-slice-plugin.sh and install it as root at ${AMD_PLUGIN_HOST_PATH}/k8s-device-plugin, then re-run join.sh"
    exit 1
  fi
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: amd-gpu
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: amdgpu-device-plugin-config
  namespace: amd-gpu
data:
  config.yaml: |
    version: "1.0"
    sharing:
      timeSlicing:
        enabled: true
        sliceCount: ${SLICE_COUNT}
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: amdgpu-device-plugin
  namespace: amd-gpu
  labels:
    app.kubernetes.io/name: amdgpu-device-plugin
    app.kubernetes.io/component: device-plugin
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: amdgpu-device-plugin
  template:
    metadata:
      labels:
        app.kubernetes.io/name: amdgpu-device-plugin
    spec:
      priorityClassName: system-node-critical
      tolerations:
        - key: CriticalAddonsOnly
          operator: Exists
        - effect: NoSchedule
          operator: Exists
        - effect: NoExecute
          operator: Exists
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: amd.com/gpu.present
                    operator: In
                    values:
                      - "true"
      volumes:
        - name: dev-kfd
          hostPath:
            path: /dev/kfd
        - name: dev-dri
          hostPath:
            path: /dev/dri
        - name: device-plugin
          hostPath:
            path: /var/lib/kubelet/device-plugins
            type: Directory
        - name: sys-amdgpu
          hostPath:
            path: /sys/class/drm
            type: Directory
        - name: sys-kfd
          hostPath:
            path: /sys/class/kfd
            type: Directory
        - name: config
          configMap:
            name: amdgpu-device-plugin-config
        - name: time-slice-binary
          hostPath:
            path: ${AMD_PLUGIN_HOST_PATH}
            type: Directory
      containers:
        - name: amdgpu-dp
          image: docker.io/rocm/k8s-device-plugin:latest
          imagePullPolicy: IfNotPresent
          command:
            - ${AMD_PLUGIN_CONTAINER_PATH}/k8s-device-plugin
          env:
            - name: CONFIG_FILE_PATH
              value: /etc/amdgpu-dp/config.yaml
            - name: AMD_TIME_SLICE_COUNT
              value: "${SLICE_COUNT}"
          securityContext:
            privileged: true
          volumeMounts:
            - name: dev-kfd
              mountPath: /dev/kfd
            - name: dev-dri
              mountPath: /dev/dri
            - name: device-plugin
              mountPath: /var/lib/kubelet/device-plugins
            - name: sys-amdgpu
              mountPath: /sys/class/drm
              readOnly: true
            - name: sys-kfd
              mountPath: /sys/class/kfd
              readOnly: true
            - name: config
              mountPath: /etc/amdgpu-dp
              readOnly: true
            - name: time-slice-binary
              mountPath: ${AMD_PLUGIN_CONTAINER_PATH}
              readOnly: true
          resources:
            requests:
              cpu: 50m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 64Mi
EOF
  log_info "amd stack done"
fi

###############################################################################
# 5. NAS home (NFS)
###############################################################################
if [[ "$NAS_HOME_MOUNT" == "/home" ]]; then
  log_warn "mounting NAS over /home can hide local user homes; use --nas-mount for a dedicated path unless intended"
fi

if [[ -z "$NAS_SERVER" ]]; then
  log_info "NAS_SERVER not set; skipping NAS home mount"
elif ! grep -qs "$NAS_SERVER" /etc/fstab && ! mountpoint -q "$NAS_HOME_MOUNT"; then
  log_info "mounting NAS home ${NAS_SERVER}:${NAS_HOME_EXPORT} -> ${NAS_HOME_MOUNT}"
  apt-get install -y -qq nfs-common >/dev/null 2>&1 || true
  mkdir -p "$NAS_HOME_MOUNT"
  echo "${NAS_SERVER}:${NAS_HOME_EXPORT} ${NAS_HOME_MOUNT} nfs4 defaults,_netdev,nofail 0 0" >> /etc/fstab
  mount -a
else
  log_info "NAS home already mounted"
fi

echo ""
echo "========================================="
echo "  node joined: $(hostname) (${VENDOR})"
echo "========================================="
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes -o wide
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get node "$(hostname)" -o json | python3 -c "
import json,sys
a=json.load(sys.stdin)['status']['allocatable']
print('allocatable GPU-ish:', {k:v for k,v in a.items() if 'gpu' in k.lower()})
"
