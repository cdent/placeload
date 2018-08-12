
import sys
import itertools
from urllib.parse import urljoin, urlsplit
import uuid

import aiohttp
import asyncio


DEFAULT_HEADERS = {
        # Using latest is usually dangerous but we want it here.
        'openstack-api-version': 'placement latest',
        'accept': 'application/json',
        'content-type': 'application/json',
        # fulfill noauth strategies expectations
        'x-auth-token': 'admin',
}


AGGREGATES = [
    '14a5c8a3-5a99-4e8f-88be-00d85fcb1c17',
    '66d98e7c-3c25-485d-a0dc-1cea651884de',
    'a59dbb28-fd98-4c6e-9ec5-ae5f3d04b0aa',
]
AGG_CHUNKS = [
    AGGREGATES[0:1],
    AGGREGATES[0:2],
    AGGREGATES[0:3],
]
AGG_CYCLE = itertools.cycle(AGG_CHUNKS)


# For now we default to allocation_ratio always being 1 because
# we don't want to think.
# Simple homogeneous topology for now.
INVENTORY_DICT = {
        'MEMORY_MB': {
            'total': 8192,
            'min_unit': 128,
            'max_unit': 8192,
        },
        'DISK_GB': {
            'total': 8192,
            'min_unit': 5,
            'max_unit': 8192,
        },
        'VCPU': {
            'total': 32,
            'min_unit': 1,
            'max_unit': 16,
        },
}


class LoaderException(Exception):
    """Base exception for bad things."""
    pass


async def version(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            raise LoaderException(
                'Unable to reach %s: %d' % (url, resp.status))
        data = await resp.json()
        version = data['versions'][0]['max_version']
        print(f'Placement is {version}')


async def verify(service):
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        await version(session, service)


async def _set_agg(session, url):
    """Set aggregates.

    Each resource provider is a member of one, two or three
    aggregates.
    """
    # you can call __next__ on a cycle, but not next(). *shrug*
    aggregates = AGG_CYCLE.__next__()
    data = {
            'resource_provider_generation': 1,
            'aggregates': aggregates,
    }
    try:
        async with session.put(url, json=data) as resp:
            if resp.status == 200:
                print('a', end='', flush=True)
            else:
                uu = urlsplit(url).path.rsplit('/')[-2]
                print(f'X{resp.status}, {uu}', flush=True)
    except aiohttp.client_exceptions.ClientError as exc:
        print(f'C{url}...{exc}')


async def _set_inv(session, url):
    """Set inventory.

    Everybody gets the same inventory.
    """
    data = {
            'resource_provider_generation': 0,
            'inventories': INVENTORY_DICT,
    }
    try:
        async with session.put(url, json=data) as resp:
            if resp.status == 200:
                print('i', end='', flush=True)
                agg_url = url.replace('inventories', 'aggregates')
                async with aiohttp.ClientSession(
                        headers=DEFAULT_HEADERS) as isession:
                    await _set_agg(isession, agg_url)
            else:
                uu = urlsplit(url).path.rsplit('/')[-2]
                print(f'X{resp.status}, {uu}', flush=True)
    except aiohttp.client_exceptions.ClientError as exc:
        print(f'C{url}...{exc}')


async def _create_rp(session, url, uu):
    """The guts of creating one resource provider.

    If the resource provider is successfully created, set its inventory.
    """
    data = {
            'uuid': uu,
            'name': uu,
    }
    try:
        async with session.post(url, json=data) as resp:
            if resp.status == 200:
                print('r', end='', flush=True)
                inv_url = urljoin(f'{url}/', f'{uu}/inventories')
                # we need a different session otherwise the one we had closes
                async with aiohttp.ClientSession(
                        headers=DEFAULT_HEADERS) as isession:
                    await _set_inv(isession, inv_url)
            else:
                print(f'X{resp.status}, {uu}', end='', flush=True)
    except aiohttp.client_exceptions.ClientError as exc:
        print(f'{url}...{exc}')


async def create_rp(service, uu, semaphore):
    """Create one resource provider named and identified by the uuid in uu."""
    # We need a semaphore outside the session, otherwise when talking
    # through the Docker for Mac proxy things go terribly wrong because
    # sockets are unavailable.
    url = urljoin(service, 'resource_providers')
    async with semaphore:
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            await _create_rp(session, url, uu)


async def create(service, count):
    """Create 500 separate resource providers with inventory."""
    tasks = []
    uuids = []
    semaphore = asyncio.Semaphore(count//min(5, count))
    while count:
        uuids.append(str(uuid.uuid4()))
        count -= 1
    for uu in uuids:
        tasks.append(create_rp(service, uu, semaphore))
    await asyncio.gather(*tasks)


def start(service, count):
    loop = asyncio.get_event_loop()

    # Confirm the presence of a working placement service at the URL
    # in `service`.
    try:
        loop.run_until_complete(verify(service))
    except LoaderException as exc:
        sys.stderr.write('STARTUP FAIL: %s\n' % str(exc))
        sys.exit(1)

    # Create some resource providers with inventory described in
    # INVENTORY_DICT and aggregates from AGGREGATES.
    loop.run_until_complete(create(service, count))
    # output the aggregates so we can query for them easily
    print()
    print('\n'.join(AGGREGATES))


def run():
    service = sys.argv[1]
    count = 500
    if len(sys.argv) == 3:
        count = int(sys.argv[2])
    start(service, count)


if __name__ == '__main__':
    run()
