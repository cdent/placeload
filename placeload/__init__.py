
import sys
import json
from urllib.parse import urljoin
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


class LoaderException(Exception):
    """Base exception for bad things."""
    pass


async def fetch(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            raise LoaderException('Unable to reach %s: %d' % (url, resp.status))
        data = await resp.json()
        version = data['versions'][0]['max_version']
        print(f'Placement is {version}')


async def verify(service):
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        await fetch(session, service)


async def _create_rp(session, url, uu):
    data = {
            'uuid': uu,
            'name': uu,
    }
    try:
        async with session.post(url, json=data) as resp:
            if resp.status == 200:
                print('.', end='', flush=True)
            else:
                print(f'X{resp.status}', end='', flush=True)
    except aiohttp.client_exceptions.ClientOSError as exc:
        print(f'{url}...{exc}')
    except aiohttp.client_exceptions.ServerDisconnectedError as exc:
        print(f'{url}...{exc}')


async def create_rp(service, uu, semaphore):
    # We need a semaphore to make sure that we outside the session,
    # otherwise when talking through the Docker for Mac proxy things
    # go terribly wrong.
    async with semaphore:
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            url = urljoin(service, 'resource_providers')
            await _create_rp(session, url, uu)


async def create(service, count=500):
    tasks = []
    uuids = []
    semaphore = asyncio.Semaphore(count//20)
    while count:
        uuids.append(str(uuid.uuid4()))
        count -= 1
    for uu in uuids:
        tasks.append(create_rp(service, uu, semaphore))
    await asyncio.gather(*tasks)


def start(service):
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(verify(service))
    except LoaderException as exc:
        sys.stderr.write('STARTUP FAIL: %s\n' % str(exc))
        sys.exit(1)

    loop.run_until_complete(create(service))


if __name__ == '__main__':
    service = sys.argv[1]
    start(service)
