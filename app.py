import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from datetime import datetime, timezone

LEASE_NAME = "leader-election-lease"
NAMESPACE = "default"
LEASE_DURATION_SECONDS = 15

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
        print("Created lease object")
    except ApiException as e:
        if e.status == 409:
            print("Lease already exists")
        else:
            raise e

def try_acquire_leader(api, identity):
    lease = get_lease(api)
    now = datetime.now(timezone.utc)

    if lease is None:
        create_lease(api)
        lease = get_lease(api)

    spec = lease.spec
    renew_time = spec.renew_time
    holder = spec.holder_identity

    if holder is None or (renew_time is not None and (now - renew_time).total_seconds() > LEASE_DURATION_SECONDS):
        # Acquire lease
        spec.holder_identity = identity
        spec.renew_time = now
        spec.acquire_time = now if spec.acquire_time is None else spec.acquire_time
        spec.lease_transitions = (spec.lease_transitions or 0) + 1

        lease.spec = spec

        try:
            api.replace_namespaced_lease(name=LEASE_NAME, namespace=NAMESPACE, body=lease)
            print(f"{identity} acquired the leadership")
            return True
        except ApiException as e:
            print(f"Failed to acquire leadership: {e}")
            return False

    elif holder == identity:
        # Renew lease
        spec.renew_time = now
        lease.spec = spec
        try:
            api.replace_namespaced_lease(name=LEASE_NAME, namespace=NAMESPACE, body=lease)
            print(f"{identity} renewed the leadership")
            return True
        except ApiException as e:
            print(f"Failed to renew leadership: {e}")
            return False
    else:
        print(f"Leadership held by {holder}")
        return False

def main():
    config.load_incluster_config()
    api = create_lease_api_object()

    # Pod identity can be hostname or pod name from the ENV var
    import os
    identity = os.getenv('POD_NAME', 'unknown-pod')

    while True:
        if try_acquire_leader(api, identity):
            print(f"{identity} is the master node")
            # Master node logic here
        else:
            print(f"{identity} is a worker node")
            # Worker node logic here
        time.sleep(5)

if __name__ == "__main__":
    main()
