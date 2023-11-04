import os
import socket as socket_module

# Python doesn't expose the `setns()` or `unshare()` function manually, so
# we'll use the `ctypes` module to make it available.
import ctypes
from ctypes import util
import errno

# items for c library direct calls - from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
# //include/linux/fs.h
MNT_FORCE = 1  # Attempt to forcibly umount
MNT_DETACH = 2  # Just detach from the tree
MNT_EXPIRE = 4  # Mark for expiry
UMOUNT_NOFOLLOW = 8  # Don't follow symlink on umount
# //include/uapi/linux/fs.h
MS_RDONLY = 1  # Mount read-only
MS_NOSUID = 2  # Ignore suid and sgid bits
MS_NODEV = 4  # Disallow access to device special files
MS_NOEXEC = 8  # Disallow program execution
MS_SYNCHRONOUS = 16  # Writes are synced at once
MS_REMOUNT = 32  # Alter flags of a mounted FS
MS_MANDLOCK = 64  # Allow mandatory locks on an FS
MS_DIRSYNC = 128  # Directory modifications are synchronous
MS_NOATIME = 1024  # Do not update access times.
MS_NODIRATIME = 2048  # Do not update directory access times
MS_BIND = 4096  #
MS_MOVE = 8192  #
MS_REC = 16384  #
MS_SILENT = 32768  #
MS_POSIXACL = (1 << 16)  # VFS does not apply the umask
MS_UNBINDABLE = (1 << 17)  # change to unbindable
MS_PRIVATE = (1 << 18)  # change to private
MS_SLAVE = (1 << 19)  # change to slave
MS_SHARED = (1 << 20)  # change to shared
MS_RELATIME = (1 << 21)  # Update atime relative to mtime/ctime.
MS_STRICTATIME = (1 << 24)  # Always perform atime updates
MS_LAZYTIME = (1 << 25)  # Update the on-disk [acm]times lazily
# //include/uapi/linux/sched.h
CLONE_NEWNS = 0x00020000  # New mount namespace group
CLONE_NEWCGROUP = 0x02000000  # New cgroup namespace
CLONE_NEWUTS = 0x04000000  # New utsname namespace
CLONE_NEWIPC = 0x08000000  # New ipc namespace
CLONE_NEWUSER = 0x10000000  # New user namespace
CLONE_NEWPID = 0x20000000  # New pid namespace
CLONE_NEWNET = 0x40000000  # New network namespace

NETNS_RUN_DIR = '/var/run/netns'
NETNS_ETC_DIR = '/etc/netns'

def errcheck(ret, func, args):
    if ret == -1:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))

# less specific C lib finding - not sure if necessary, but this seems to be more forgiving.
# again - from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
libc = ctypes.CDLL(util.find_library('c'), use_errno=True)
libc.setns.errcheck = errcheck

# See the relevant system call's man pages and: https://docs.python.org/3/library/ctypes.html#fundamental-data-types
# also from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                       ctypes.c_ulong, ctypes.c_void_p)
libc.sethostname.argtypes = (ctypes.c_char_p, ctypes.c_size_t)
libc.umount2.argtypes = (ctypes.c_char_p, ctypes.c_int)
libc.unshare.argtypes = (ctypes.c_int,)

def setns(fd, nstype):
    '''Change the network namespace of the calling thread.

    Given a file descriptor referring to a namespace, reassociate the
    calling thread with that namespace.  The fd argument may be either a
    numeric file  descriptor or a Python object with a fileno() method.
    '''

    if hasattr(fd, 'fileno'):
        fd = fd.fileno()

    return libc.setns(fd, nstype)


def socket(nspath, *args, bind_mount=False, prevent_unshare=False, **kwargs):
    '''Return a socket from a network namespace.

    This is a wrapper for socket.socket() that will return a socket
    inside the namespace specified by the nspath argument, which should be
    a filesystem path to an appropriate namespace file.  You can use the
    get_ns_path() function to generate an appropriate filesystem path if
    you know a namespace name or pid.
    '''

    with NetNS(nspath=nspath, bind_mount=bind_mount, prevent_unshare=prevent_unshare):
        return socket_module.socket(*args, **kwargs)


def get_ns_path(nspath=None, nsname=None, nspid=None):
    '''Generate a filesystem path from a namespace name or pid.

    Generate a filesystem path from a namespace name or pid, and return
    a filesystem path to the appropriate file.  Returns the nspath argument
    if both nsname and nspid are None.
    '''

    if nsname:
        nspath = f'{NETNS_RUN_DIR}/{nsname}'
    elif nspid:
        nspath = f'/proc/{nspid}/ns/net'

    if not os.path.exists(nspath):
        raise ValueError(f'namespace path {nspath} does not exist')

    return nspath

def get_ns_name(nspath=None, nspid=None):
    '''Lookup a net namespace name from path or pid.

    This is needed if /etc bind_mounts are required, as it requires the name
    to create the bind mounts.

    identify logic using inode/dev taken from:
    https://github.com/iproute2/iproute2/blob/main/ip/ipnetns.c#L639C24-L639C24
    '''

    found_name = None

    # lookup stat of what we've got.
    if nspid:
        local_nspath = get_ns_path(nspid=nspid)
    elif nspath:
        local_nspath = nspath
    else:
        raise ValueError(f'need nspath or nspid.')

    if not os.path.exists(local_nspath):
        raise ValueError(f'namespace path {local_nspath} does not exist')

    # use os stat to lookup name.
    # We could look for last part of dir in nspath, but we need to do this for pid anyway.
    path_st = os.stat(local_nspath)
    for nsname in list_netns:
        ns_st = os.stat(f'{NETNS_RUN_DIR}/{nsname}')
        if path_st.st_dev == ns_st.st_dev and path_st.st_ino == ns_st.st_ino:
            found_name = nsname

    # did we get anything?
    if found_name is None:
        raise ValueError(f'no network namespace found for {nspath if not None else nspid}.')


def list_netns():
    try:
        return os.listdir(NETNS_RUN_DIR)
    except FileNotFoundError:
        return []

def mount(src, tgt, fs, flags=MS_NODEV | MS_NOEXEC | MS_NOSUID | MS_RELATIME):
    '''Generic mount function, with default mount values

    Taken from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
    '''
    ret = libc.mount(src.encode(), tgt.encode(), fs.encode() if fs else None,
                     flags, None)
    if ret < 0:
        l_errno = ctypes.get_errno()
        raise OSError(errno, f'{os.strerror(l_errno)} mounting {src} on {tgt} (fs={fs} flags={hex(flags)})')

def umount(tgt, flags=MNT_DETACH):
    '''Generic umount function, with default values

    Not taken from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py, but similar to mount()
    '''
    ret = libc.umount2(tgt.encode(), flags)
    if ret < 0:
        l_errno = ctypes.get_errno()
        raise OSError(errno, f'{os.strerror(l_errno)} unmounting {tgt} (flags={hex(flags)})')

def remount_proc():
    '''Function to remount proc when doing bind_mount for netns

    Taken from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
    '''
    # these may not be mounted - ignore failures.
    umount('/proc')
    mount('proc', '/proc', 'proc')


def remount_sys():
    '''Function to remount sys when doing bind_mount for netns

    Taken from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
    '''
    # these may not be mounted - ignore failures.
    umount('/sys/fs/cgroup')
    umount('/sys/fs/bpf')
    umount('/sys')
    mount('sysfs', '/sys', 'sysfs')
    mount('bpf', '/sys/fs/bpf', 'bpf')
    mount('cgroup2', '/sys/fs/cgroup', 'cgroup2')

def unshare(flags):
    '''Function to unshare (detach from global namespace.)

    This function is key to netns bind_mount done by other tools (iproute2, etc.)
    This detaches the process namespaces and creates new ones. Can even do with Network Namespace.
    Taken from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
    '''
    ret = libc.unshare(flags)
    if ret < 0:
        l_errno = ctypes.get_errno()
        raise OSError(errno, f'{os.strerror(l_errno)} while unshare({hex(flags)})')

def dump_mounts():
    '''Debugging function to list mounts from within process.

    Useful for checking if bind_mounts are present.
    Taken partially from https://android.googlesource.com/kernel/tests/+/master/net/test/namespace.py
    '''
    with open('/proc/mounts', 'r') as mounts:
        return mounts.read()


class NetNS (object):
    '''A context manager for running code inside a network namespace.

    This is a context manager that on enter assigns the current process
    to an alternate network namespace (specified by name, filesystem path,
    or pid) and then re-assigns the process to its original network
    namespace on exit.
    '''

    mypath = None
    targetpath = None
    myns = None
    nsname = None
    nspath = None
    nspid = None
    # for bind_mount
    prevent_unshare = False
    bind_mount = False
    ns_etc_dir = None

    def __init__(self, nsname=None, nspath=None, nspid=None, bind_mount=False, prevent_unshare=False):
        self.mypath = get_ns_path(nspid=os.getpid())
        self.targetpath = get_ns_path(nspath,
                                      nsname=nsname,
                                      nspid=nspid)

        if not self.targetpath:
            raise ValueError('invalid namespace')

        # check for bind mount needed items
        if bind_mount:
            if nsname is None:
                self.nsname = get_ns_name(nspath=nspath, nspid=nspid)
            else:
                # we already have the nsname
               self.nsname = nsname

            self.ns_etc_dir = f'{NETNS_ETC_DIR}/{self.nsname}'

            # check to see if we should skip unshare on bind_mount.
            # this is useful to prevent unshare-ing on every bind_mount entry into a netns.
            # in most cases you only need to unshare the mount namespace once. It shouldn't hurt
            # to keep doing it - but nice to have the option.

            # it's also dangerous not to unshare() the mount space when bind_mount'ing as the temp mounts
            # will affect all processes! Bad for sure.

            # the unshare and bind logic were taken from a strace on iproute2 posted on stackexchange:
            # https://unix.stackexchange.com/questions/471122/namespace-management-with-ip-netns-iproute2/471214#471214

            if prevent_unshare is not True:
                # move this process into new mount namespace, with all the required components
                unshare(CLONE_NEWNS)
                # remount root as slave, so changes don't propagate to any other processes
                mount('none', '/', None, MS_REC | MS_SLAVE)
                # remount sys/proc to be safe.
                remount_proc()
                remount_sys()
        else:
            # ensure self netns is set
            self.nsname = nsname

        # finally, set any remaining self vars
        self.nspid = nspid
        self.nspath = nspath
        self.bind_mount = bind_mount
        self.prevent_unshare = prevent_unshare


    def __enter__(self):
        # before entering a new namespace, we open a file descriptor
        # in the current namespace that we will use to restore
        # our namespace on exit.
        self.myns = open(self.mypath)
        with open(self.targetpath) as fd:
            setns(fd, CLONE_NEWNET)
        if self.bind_mount is True and self.nsname is not None and self.ns_etc_dir is not None:
            if os.path.exists(self.ns_etc_dir):
                for entry in os.listdir(self.ns_etc_dir):
                    src = os.path.join(self.ns_etc_dir, entry)
                    dest = os.path.join("/etc", entry)
                    mount(src, dest, None, MS_BIND)


    def __exit__(self, *args):
        if self.bind_mount is True and self.nsname is not None and self.ns_etc_dir is not None:
            if os.path.exists(self.ns_etc_dir):
                for entry in os.listdir(self.ns_etc_dir):
                    dest = os.path.join("/etc", entry)
                    umount(dest)
        setns(self.myns, CLONE_NEWNET)
        self.myns.close()
