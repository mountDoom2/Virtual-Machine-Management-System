import os
from os import path
import sys
sys.path.append('..')

import time
from vboxapi import *
from Tkinter import *
from win32gui import *
from modules.constants import *

mgr = VirtualBoxManager("WEBSERVICE", {'url':'http://127.0.0.1:18083', 'user':'myServerLogin', 'password':'myPassthere'})
vbox = mgr.vbox

mach1 = vbox.findMachine("win")
print mach1.logFolder
mach2 = vbox.findMachine("new")
session = mgr.getSessionObject(vbox)
#session = mgr.openMachineSession(mach1, True)
#session2 = mgr.openMachineSession(mach2, True)
try:
    session.unlockMachine()
except:
    pass
progress1 = mach1.launchVMProcess(session, "gui", "")
progress1.waitForCompletion(-1)
time.sleep(15)
console = session.console

ocollector = mgr.getPerfCollector(vbox)
ocollector.setup(["*"], [mach1], 2, 10)
time.sleep(30)
val = ocollector.query(["*"], [mach1])
print "Done"
print val


#guest = console.guest
#print guest.OSTypeId
#
#guestSession = guest.createSession('user', '123456', '', '')
#print guestSession.waitFor(1, 10000)
#time.sleep(2)
#print "Starting process"
#proc = guestSession.processCreate('C:\\Windows\\System32\\cmd.exe', ['/c', 'mkdir', 'a'], None, None, 0)
#proc.waitFor(1,10000)
#time.sleep(2)
#print proc.executablePath
#print proc.exitCode

#guestSession.close()
#prog = console.teleport('localhost', 6000, '', 250)
#prog.waitForCompletion(-1)
#expPath = path.join(path.expanduser('~'), 'git')
#expPathFile = path.join(expPath, 'exp.ova')
#print expPath
#exp = vbox.createAppliance()

#print exp.path
#desc = mach1.exportTo(exp, '')
#prog = exp.write("ovf-1.0", None, expPathFile)
#while not prog.completed:
#    print "Exporting: %d\%"%(prog.percent)
#    time.sleep(1)
#print "Export completed"

#imp = vbox.createAppliance()
#prog = imp.read(expPathFile)
#while not prog.completed:
#    print "Reading: %d\%"%(prog.percent)
#    time.sleep(1)
#print "Read completed"
#imp.interpret()
#print "Interpreting"
#prog = imp.importMachines(None)
#while not prog.completed:
#    print (prog.percent)
#    time.sleep(1)
#print "Import completed"

"""
progress1 = mach1.launchVMProcess(session, "gui", "")
progress1.waitForCompletion(-1)
time.sleep(10)
session.unlockMachine()
progress2 = mach2.launchVMProcess(session, "gui", "")
progress2.waitForCompletion(-1)
time.sleep(10)
console = session.console
progress = console.powerDown()
progress.waitForCompletion(-1)
session.unlockMachine()
time.sleep(1)
mach1.lockMachine(session, 1)
time.sleep(1)
console = session.console
progress = console.powerDown()
"""
#session.unlockMachine()
#progress2 = mach2.launchVMProcess(session, "gui", "")
#progress2.waitForCompletion(-1)
#progress2 = mach2.launchVMProcess(session2, "gui", "")
#session = mgr.getSessionObject(vbox)
#progress = mach1.launchVMProcess(session, "gui", "")

for i in range(5):
    print 10 * "="
    print session.state
    print mach1.getState()
    print 10 * "="
    time.sleep(1)
#console = session.console
#mgr.closeMachineSession(session)     
"""
progress = mach.launchVMProcess(session, "", "")
progress.waitForCompletion(-1)
console = session.console
#session.lockMachine()
print SCANCODES
time.sleep(40)
stats = console.guest.internalGetStatistics()
print stats
"""
"""
if (mach.canShowConsoleWindow()):
    print "Can show"
    wid = mach.showConsoleWindow()
    print "win id: " + str(wid)
    ShowWindow(wid, 3) # 3 = maximize window
"""
"""
string = "testing string"
for char in string:
    key_press_code = SCANCODES[char][0]
    key_release_code = SCANCODES[char][1]
    key_codes = key_press_code + key_release_code
    print char + " " + str(key_codes) +  " " + str(console.keyboard.putScanCodes(key_codes))
    #time.sleep(0.5)
    #print console.keyboard.putScanCodes(SCANCODES[char])
"""
#stored = console.keyboard.putScancodes([0xe0,0x5b])
#print stored
#session.unlockMachine()

#for attr in dir(session.console):
#    print "obj.%s = %s"%(attr, getattr(session, attr))
#print session.console
#print mach.monitorCount



#for machine in mgr.getArray(vbox, 'machines'):
#    print machine
#print 