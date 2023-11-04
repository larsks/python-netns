This is a Python wrapper for the `setns()` system call.

## Examples

Show interface configuration inside a named network namespace:

    import netns
    import subprocess

    with netns.NetNS(nsname='myns'):
        subprocess.call(['ip', 'a'])

Inspect the interface configuration inside a docker container
(assuming that you have retrieved the container pid via `docker
inspect` output or by using the Docker API):

    with netns.NetNS(nspid=29435):
        subprocess.call(['ip', 'a'])

Create a socket inside a network namespace:

    sock = netns.socket(netns.get_ns_path(nsname='myns'))

Also, the library can perform the same /etc/netns bind_mount operations done by `ip exec netns`. 
These allow fixing of a lot of common issues seen by namespace-unaware higher-level libraries 
(like DNS issues seen with [Requests](https://requests.readthedocs.io/en/latest/)).

    import netns
    import requests

    with open('/etc/netns/myns/resolv.conf', 'w') as ns_resolv_fd:
        ns_resolv_fd.write('nameserver 1.1.1.1\n')

    with netns.NetNS(nsname='myns', bind_mount=True):
        requests_ses = requests.Session()
        resp = requests_ses.get('http://www.google.com')
        print(resp.txt)
