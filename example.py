# This script sets up a network namespace, veth interfaces, routing,
# and iptables rules permitting outbound access, and then opens a
# socket inside the namespace and makes a web request.
#
# The script must be run as root.  E.g:
#
#     sudo python example.py
#
# Also if cat /proc/net/ipv4/ip_forward returns 0, this script will hang after setup (as traffic won't NAT.)
# Be sure to ensure it's 1 (as root, echo 1 > /proc/sys/net/ipv4/ip_forward)

import netns
import subprocess
import requests
import time

setup = [
    # create a network namespace named "sandbox"
    'ip netns add sandbox',

    # create a pair of veth interfaces named
    # "inside" and "outside"
    'ip link add outside type veth peer name inside',

    # Assign the "inside" interface to the network namespace
    'ip link set netns sandbox inside',

    # Assign an address to the "outside" interface
    'ip addr add 172.16.16.1/24 dev outside',
    'ip link set outside up',

    # Assign an address to the "inside" interface
    'ip netns exec sandbox ip addr add 172.16.16.2/24 dev inside',
    'ip netns exec sandbox ip link set inside up',

    # Set up a default route for the network namespace
    'ip netns exec sandbox ip route add default via 172.16.16.1',

    # Arrange to masquerade outbound packets from the network
    # namespace.
    'iptables -t nat -A POSTROUTING -s 172.16.16.0/24 -j MASQUERADE',

    # set up alternate DNS servers for the namespace.
    # if these lines are removed, Requests test will fail on ubuntu 22.04
    # with default dnsproxy /etc/resolv.conf
    'mkdir -p /etc/netns/sandbox',
    'echo "nameserver 1.1.1.1" > /etc/netns/sandbox/resolv.conf'
]

teardown = [
    'sleep 5',
    'ip link del outside',
    'ip netns del sandbox',
    'iptables -t nat -D POSTROUTING -s 172.16.16.0/24 -j MASQUERADE',
    'rm -f /etc/netns/sandbox/resolv.conf',
    'rmdir /etc/netns/sandbox',
]


def run_steps(steps, ignore_errors=False):
    for step in steps:
        try:
            print('+ {}'.format(step))
            subprocess.check_call(step, shell=True)
        except subprocess.CalledProcessError:
            if ignore_errors:
                pass
            else:
                raise

try:
    # socket test
    run_steps(setup)

    print("Socket Test:")
    s = netns.socket(netns.get_ns_path(nsname='sandbox'))
    s.connect((b'loripsum.net', 80))
    s.send(b'GET /api/3/short HTTP/1.1\r\n')
    s.send(b'Host: loripsum.net\r\n')
    s.send(b'\r\n')
    d = s.recv(1024)
    print(d)


    # more complex op using requests python library
    # if using ubuntu 22.04, or other distro using dns proxy, these will fail unless the process
    # is bind mounted with non 127.0.0.1 DNS servers, as the 127.0.0.1 servers are not reachable in the namespace.
    print("\n/etc/resolv.conf nameservers default namespace:")
    subprocess.check_call('cat /etc/resolv.conf | grep nameserver', shell=True)
    with netns.NetNS(nsname='sandbox', bind_mount=True):
        print("/etc/resolv.conf nameservers inside network namespace:")
        subprocess.check_call('cat /etc/resolv.conf | grep nameserver', shell=True)
        req_session = requests.Session()
        response = req_session.get("http://loripsum.net/api/3/short", timeout=4)
    print("/etc/resolv.conf nameservers after leaving namespace:")
    subprocess.check_call('cat /etc/resolv.conf | grep nameserver', shell=True)
    print("\nRequests Test response:")
    print(response.text)

finally:
    run_steps(teardown, ignore_errors=True)
