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
import time
#proc = guestSession.processCreate('C:\\Windows\\System32\\cmd.exe', ['cmd', '/c', 'mkdir', 'C:\\Users\\user\\testdir'], None, None, 0)
proc = guestSession.processCreate('/bin/sh', None, None, [5], 0)
print proc.waitFor(1, 10000) # Wait for start
print proc.PID
#written = proc.write(0, 0, "ls", 10000)
#proc.write(0, 1, " ", 10000)
#print written
data = proc.read(1, 4096, 10000)
print "Data: " + str(data)
#written = proc.write(0, 0, "ls /home/milan", 10000)
#proc.write(0, 1, " ", 10000)
#print written
data = proc.read(1, 4096, 10000)

print "Data2: " + str(data)
print proc.waitFor(2, 10000) # Wait for terminate
print proc.status
print proc.exitCode