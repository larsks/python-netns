import os
import socket as socket_module

# Python doesn't expose the `setns()` function manually, so
# we'll use the `ctypes` module to make it available.
from ctypes import cdll
libc = cdll.LoadLibrary('libc.so.6')
_setns = libc.setns

CLONE_NEWIPC = 0x08000000
CLONE_NEWNET = 0x40000000
CLONE_NEWUTS = 0x04000000


def setns(fd, nstype):
    '''Given a file descriptor referring to a namespace, reassociate the
    calling thread with that namespace.  The fd argument may be either a
    numeric file  descriptor or a Python object with a fileno() method.'''

    if hasattr(fd, 'fileno'):
        fd = fd.fileno()

    _setns(fd, nstype)


def socket(nspath, *args):
    '''This is a wrapper for socket.socket() that will return a socket
    inside the namespace specified by the nspath argument, which should be
    a filesystem path to an appropriate namespace file.  You can use the
    get_ns_path() function to generate an appropriate filesystem path if
    you know a namespace name or pid.'''

    with NetNS(nspath=nspath):
        return socket_module.socket(*args)


def get_ns_path(nspath=None, nsname=None, nspid=None):
    '''Generate a filesystem path from a namespace name or pid, and return
    a filesystem path to the appropriate file.  Returns the nspath argument
    if both nsname and nspid are None.'''

    if nsname:
        nspath = '/var/run/netns/%s' % nsname
    elif nspid:
        nspath = '/proc/%d/ns/net' % nspid

    return nspath


class NetNS (object):
    '''This is a context manager that on enter assigns the current process
    to an alternate network namespace (specified by name, filesystem path,
    or pid) and then re-assigns the process to its original network
    namespace on exit.'''

    def __init__(self, nsname=None, nspath=None, nspid=None):
        self.mypath = get_ns_path(nspid=os.getpid())
        self.targetpath = get_ns_path(nspath,
                                  nsname=nsname,
                                  nspid=nspid)

        if not self.targetpath:
            raise ValueError('invalid namespace')

    def __enter__(self):
        # before entering a new namespace, we open a file descriptor
        # in the current namespace that we will use to restore
        # our namespace on exit.
        self.myns = open(self.mypath)
        with open(self.targetpath) as fd:
            setns(fd, CLONE_NEWNET)

    def __exit__(self, *args):
        setns(self.myns, CLONE_NEWNET)
        self.myns.close()
