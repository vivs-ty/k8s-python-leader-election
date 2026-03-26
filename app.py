import logging
import os
import signal
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from datetime import datetime, timezone, timedelta

# Configurable via environment variables with defaults
LEASE_NAME = os.getenv("LEASE_NAME", "leader-election-lease")
NAMESPACE = os.getenv("NAMESPACE", "default")
LEASE_DURATION_SECONDS = int(os.getenv("LEASE_DURATION_SECONDS", "15"))
RENEW_INTERVAL_SECONDS = int(os.getenv("RENEW_INTERVAL_SECONDS", "5"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Kubernetes liveness and readiness probes."""
    def do_GET(self):
        if self.path in ('/healthz', '/ready'):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress per-request access logs


def start_health_server(port: int = 8080):
    server = HTTPServer(('', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check server listening on port {port}")


_shutdown = threading.Event()


def _handle_signal(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully…")
    _shutdown.set()


def release_lease(api, identity):
    """Clear holder_identity so another pod can immediately acquire leadership."""
    try:
        lease = get_lease(api)
        if lease and lease.spec.holder_identity == identity:
            lease.spec.holder_identity = None
            lease.spec.renew_time = None
            api.replace_namespaced_lease(name=LEASE_NAME, namespace=NAMESPACE, body=lease)
            logger.info(f"{identity} released the lease")
    except Exception as e:
        logger.warning(f"Failed to release lease on shutdown: {e}")

def create_lease_api_object():
    return client.CoordinationV1Api()

def get_lease(api):
    try:
        lease = api.read_namespaced_lease(LEASE_NAME, NAMESPACE)
        return lease
    except ApiException as e:
        if e.status == 404:
            return None
        else:
            logger.error(f"Exception getting lease: {e}")
            raise e

def create_lease(api):
    lease_body = client.V1Lease(
        metadata=client.V1ObjectMeta(name=LEASE_NAME, namespace=NAMESPACE),
        spec=client.V1LeaseSpec(
            holder_identity=None,
            lease_duration_seconds=LEASE_DURATION_SECONDS,
            acquire_time=None,
            renew_time=None,
            lease_transitions=0,
        )
    )
    try:
        api.create_namespaced_lease(namespace=NAMESPACE, body=lease_body)
        logger.info("Created lease object")
    except ApiException as e:
        if e.status == 409:  # Already exists
            logger.info("Lease object already exists")
        else:
            logger.error(f"Failed to create lease: {e}")
            raise e

def try_acquire_leader(api, identity):
    now = datetime.now(timezone.utc)

    lease = get_lease(api)
    if lease is None:
        create_lease(api)
        lease = get_lease(api)
        if lease is None:
            logger.error("Lease still not found after creation — skipping cycle")
            return False

    spec = lease.spec
    renew_time = spec.renew_time
    holder = spec.holder_identity
    lease_duration = timedelta(seconds=LEASE_DURATION_SECONDS)

    # Check if lease expired or no holder
    if holder is None or (renew_time is not None and (now - renew_time) > lease_duration):
        spec.holder_identity = identity
        spec.renew_time = now
        spec.acquire_time = now if spec.acquire_time is None else spec.acquire_time
        spec.lease_transitions = (spec.lease_transitions or 0) + 1
        lease.spec = spec

        try:
            api.replace_namespaced_lease(name=LEASE_NAME, namespace=NAMESPACE, body=lease)
            logger.info(f"{identity} acquired the leadership")
            return True
        except ApiException as e:
            logger.warning(f"Failed to acquire leadership: {e}")
            return False

    elif holder == identity:
        # Renew leadership before lease expires
        spec.renew_time = now
        lease.spec = spec
        try:
            api.replace_namespaced_lease(name=LEASE_NAME, namespace=NAMESPACE, body=lease)
            logger.info(f"{identity} renewed the leadership")
            return True
        except ApiException as e:
            logger.warning(f"Failed to renew leadership: {e}")
            return False

    else:
        logger.info(f"Leadership held by another pod: {holder}")
        return False

def main():
    # Config load either from cluster (in-cluster) or fallback for dev testing
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    start_health_server()

    api = create_lease_api_object()
    identity = os.getenv('POD_NAME', f"pod-{os.getpid()}")

    logger.info(f"Starting leader election with identity: {identity}")

    while not _shutdown.is_set():
        try:
            if try_acquire_leader(api, identity):
                logger.info(f"{identity} is the MASTER node")
                # Master-specific logic here
            else:
                logger.info(f"{identity} is a WORKER node")
                # Worker logic here
        except Exception as e:
            logger.error(f"Unexpected exception in leader election loop: {e}")
        _shutdown.wait(timeout=RENEW_INTERVAL_SECONDS)

    release_lease(api, identity)
    logger.info("Shutdown complete")

if __name__ == "__main__":
    main()
