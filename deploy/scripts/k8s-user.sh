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

# Script to create a new Kubernetes user with matching namespace and kubeconfig

# Check if username is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <username>"
  echo "Example: $0 developer"
  exit 1
fi

# Variables
USERNAME=$1
NAMESPACE=$USERNAME
CSR_NAME="${USERNAME}-csr"
TEMP_DIR=$(mktemp -d)
CONTEXT=$(kubectl config current-context)
CLUSTER_NAME=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
CLUSTER_CA=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
CLUSTER_SERVER=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}')

echo "Creating user with the following details:"
echo "- Username: $USERNAME"
echo "- Namespace: $NAMESPACE"
echo "- Context: $CONTEXT"
echo "- Cluster: $CLUSTER_NAME"

# Create namespace
echo "Creating namespace $NAMESPACE..."
kubectl create namespace "$NAMESPACE"

# Create private key
echo "Generating private key..."
openssl genrsa -out "$TEMP_DIR/$USERNAME.key" 4096

# Create certificate signing request (CSR)
echo "Creating certificate signing request..."
openssl req -new -key "$TEMP_DIR/$USERNAME.key" -out "$TEMP_DIR/$USERNAME.csr" -subj "/CN=$USERNAME/O=$USERNAME"

# Convert CSR to base64
CSR_BASE64=$(base64 < "$TEMP_DIR/$USERNAME.csr" | tr -d '\n')

# Create Kubernetes CSR object
echo "Creating Kubernetes CSR..."
cat <<EOF | kubectl apply -f -
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: $CSR_NAME
spec:
  request: $CSR_BASE64
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 31536000  # 1 year
  usages:
  - client auth
EOF

# Approve the CSR
echo "Approving CSR..."
kubectl certificate approve "$CSR_NAME"

# Wait for the CSR to be approved
echo "Waiting for CSR to be approved..."
sleep 2

# Get the signed certificate
echo "Retrieving signed certificate..."
CERT_DATA=$(kubectl get csr "$CSR_NAME" -o jsonpath='{.status.certificate}')

# Save the certificate
echo "$CERT_DATA" | base64 -d > "$TEMP_DIR/$USERNAME.crt"

# Create Role with full permissions in the user's namespace
echo "Creating Role for $USERNAME in namespace $NAMESPACE..."
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: $USERNAME-full-access
  namespace: $NAMESPACE
rules:
- apiGroups: [""]
  resources: ["*"]
  verbs: ["*"]
- apiGroups: ["apps"]
  resources: ["*"]
  verbs: ["*"]
- apiGroups: ["batch"]
  resources: ["*"]
  verbs: ["*"]
- apiGroups: ["extensions"]
  resources: ["*"]
  verbs: ["*"]
- apiGroups: ["networking.k8s.io"]
  resources: ["*"]
  verbs: ["*"]
EOF

# Create RoleBinding
echo "Creating RoleBinding for $USERNAME in namespace $NAMESPACE..."
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: $USERNAME-binding
  namespace: $NAMESPACE
subjects:
- kind: User
  name: $USERNAME
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: $USERNAME-full-access
  apiGroup: rbac.authorization.k8s.io
EOF

# Create kubeconfig
echo "Generating kubeconfig file for $USERNAME..."
cat <<EOF > "$USERNAME-kubeconfig.yaml"
apiVersion: v1
kind: Config
preferences: {}
clusters:
- cluster:
    certificate-authority-data: $CLUSTER_CA
    server: $CLUSTER_SERVER
  name: $CLUSTER_NAME
users:
- name: $USERNAME
  user:
    client-certificate-data: $(base64 < "$TEMP_DIR/$USERNAME.crt" | tr -d '\n')
    client-key-data: $(base64 < "$TEMP_DIR/$USERNAME.key" | tr -d '\n')
contexts:
- context:
    cluster: $CLUSTER_NAME
    namespace: $NAMESPACE
    user: $USERNAME
  name: $USERNAME-context
current-context: $USERNAME-context
EOF

echo ""
echo "======= DONE ======="
echo "User $USERNAME has been created with access to namespace $NAMESPACE"
echo "Kubeconfig file saved as: $USERNAME-kubeconfig.yaml"
echo ""
echo "To use this kubeconfig file, run:"
echo "  export KUBECONFIG=\$PWD/$USERNAME-kubeconfig.yaml"
echo "Or merge it with your existing config:"
echo "  KUBECONFIG=\$PWD/$USERNAME-kubeconfig.yaml:\$HOME/.kube/config kubectl config view --flatten > merged-config && mv merged-config \$HOME/.kube/config"
echo ""

# Clean up temporary files
rm -rf "$TEMP_DIR"
