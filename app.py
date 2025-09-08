import time
import logging
import os
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

    api = create_lease_api_object()
    identity = os.getenv('POD_NAME', f"pod-{os.getpid()}")

    logger.info(f"Starting leader election with identity: {identity}")

    while True:
        try:
            if try_acquire_leader(api, identity):
                logger.info(f"{identity} is the MASTER node")
                # Master-specific logic here
            else:
                logger.info(f"{identity} is a WORKER node")
                # Worker logic here
        except Exception as e:
            logger.error(f"Unexpected exception in leader election loop: {e}")
        time.sleep(RENEW_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
