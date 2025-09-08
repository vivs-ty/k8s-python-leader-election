# Kubernetes Python Leader Election

This project demonstrates leader election in Kubernetes using Python and Lease resource, enabling pods to elect a master node dynamically.

## How it works

- Multiple pods run the same Python app.
- Pods attempt to acquire a Lease resource in Kubernetes.
- The pod holding the lease acts as the master.
- Lease renews keep master status, others become workers.

## Usage

1. Build Docker image:
   docker build -t <dockerhub-username>/k8s-python-leader-election:latest .

2. Push the image to Docker Hub.

3. Apply Kubernetes manifests:
   kubectl apply -f k8s/

## Contributing

Feel free to fork, raise issues, and submit pull requests!

## License

Apache-2.0
MIT

--------------------------------------------------------------------------------------------------

k8s-python-leader-election/
│
├── app.py                 # Python app with leader election logic
├── Dockerfile             # To build container image
├── requirements.txt       # Python dependencies
├── k8s/
│   ├── deployment.yaml    # Kubernetes Deployment and ServiceAccount manifests
│   ├── lease.yaml         # Lease resource for leader election lock
│   ├── rbac.yaml          # RBAC manifests granting lease access
│
├── README.md              # Project overview, usage, contribution
└── .github/
    └── workflows/
        └── ci-cd.yaml     # GitHub Actions workflow (optional)

@vivs-ty 
