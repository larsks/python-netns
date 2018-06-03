# This script sets up a network namespace, veth interfaces, routing,
# and iptables rules permitting outbound access, and then opens a 
# socket inside the namespace and makes a web request.
#
# The script must be run as root.  E.g:
#
#     sudo python example.py

import netns
import subprocess
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
]

teardown = [
    'ip link del outside',
    'ip netns del sandbox',
    'iptables -t nat -D POSTROUTING -s 172.16.16.0/24 -j MASQUERADE',
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
    run_steps(setup)

    s = netns.socket(netns.get_ns_path(nsname='sandbox'))
    s.connect(('loripsum.net', 80))
    s.send('GET /api/3/short HTTP/1.1\r\n')
    s.send('Host: loripsum.net\r\n')
    s.send('\r\n')
    d = s.recv(1024)
    print(d)
finally:
    run_steps(teardown, ignore_errors=True)
