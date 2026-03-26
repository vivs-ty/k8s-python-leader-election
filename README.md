# Kubernetes Python Leader Election

This project demonstrates leader election in Kubernetes using Python and the Lease resource, enabling pods to dynamically elect a leader.

## How it works

- Multiple pods run the same Python app.
- Each pod attempts to acquire a `Lease` resource in Kubernetes.
- The pod holding the lease acts as the **leader** (master); all others are workers.
- The leader continuously renews the lease. If it fails to renew within `LEASE_DURATION_SECONDS`, another pod takes over.
- On graceful shutdown (SIGTERM) the leader immediately releases the lease so failover is instant.

## Prerequisites

- Docker
- A Kubernetes cluster (local or remote), `kubectl` configured
- A Docker Hub account

## Usage

### Manual build & deploy

```bash
# 1. Build the image
docker build -t <dockerhub-username>/k8s-python-leader-election:latest .

# 2. Push to Docker Hub
docker push <dockerhub-username>/k8s-python-leader-election:latest

# 3. Update k8s/deployment.yaml — replace <your-dockerhub-username> with your username

# 4. Apply all manifests
kubectl apply -f k8s/
```

### CI/CD (GitHub Actions)

The included workflow (`.github/workflows/ci-cd.yaml`) builds and pushes the image automatically on every push to `main`.

**Required GitHub repository secrets:**

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub access token (Settings → Security → Access Tokens) |

Set these under **Settings → Secrets and variables → Actions** in your repository.

The workflow:
- Builds the image on every push and pull request.
- Pushes two tags on `main` push: `:latest` and `:<commit-sha>`.
- Skips the push (build-only) on pull requests.

## Project structure

```
k8s-python-leader-election/
├── app.py                 # Leader election logic
├── Dockerfile             # Multi-stage container build
├── .dockerignore
├── requirements.txt       # Python dependencies
├── k8s/
│   ├── deployment.yaml    # Namespace, ServiceAccount, and Deployment
│   ├── lease.yaml         # Lease resource
│   └── rbac.yaml          # Role and RoleBinding for lease access
├── README.md
└── .github/
    └── workflows/
        └── ci-cd.yaml     # GitHub Actions build & push workflow
```

## Contributing

Feel free to fork, raise issues, and submit pull requests!

## License

MIT
