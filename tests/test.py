from vboxapi import *

mgr = VirtualBoxManager("WEBSERVICE", {'url':'http://127.0.0.1:18083', 'user':'myServerLogin', 'password':'myPassThere'})
vbox = mgr.vbox
constants = mgr.constants
mach1 = vbox.findMachine("centos")
session = mgr.getSessionObject(vbox)
mach1.lockMachine(session, constants.LockType_Shared)

console = session.console
guest = console.guest
#guestSession = guest.createSession('user', '123456', '', '')
guestSession = guest.createSession('milan', 'arnold', '', '')
print guestSession.waitFor(1, 10000)

#proc = guestSession.processCreate('C:\\Windows\\System32\\cmd.exe', ['cmd', '/c', 'mkdir', 'C:\\Users\\user\\testdir'], None, None, 0)
proc = guestSession.processCreate('/bin/sh', ['-c a.sh'], None, None, 0)
print proc.waitFor(1, 10000) # Wait for start
print proc.PID
print proc.waitFor(2, 10000) # Wait for terminate
print proc.status
print proc.exitCode