from vboxapi import *
import argparse
import os
from os import path
import sys
sys.path.append(os.getcwd())
print sys.path
from modules.exceptions import *
from modules.globals import *

def cmdConnect(args, env):
    if len(args > 4):
        print "Too many arguments for connect"
        return 0
    
    if env['vbox'] is not None:
        print "Already connected"
        return 0
    url = args[0] if len(args) > 1 else None
    user = args[1] if len(args) > 2 else ""
    password = args[2] if len(args) > 3 else ""
    env['remoteinfo'] = [url, user, password]
    
    env['mgr'].platform.connect(url, user, password)
    env['vbox'] = env['mgr'].vbox  
    return 0

def cmdDisconnect(args, env):
    if len(args > 1):
        print "Too many arguments for disconnect"
        return 0
    
    env['mgr'].platform.disconnect()
    return

def cmdHelp(args, env):
    print "This is help"
    return 0

def cmdQuit(args, env):
    return 1

def cmdStartVM(args, env):
    if len(args) < 1 or len(args) > 2:
        print "Wrong arguments for startvm"
    name = args[1]
    machine = env['vbox'].findMachine(name)
    session = env['mgr'].getSessionObject(env['vbox'])
    progress = machine.launchVMProcess(session, "gui", "")
    progress.waitForCompletion(-1)
    
    return 0

def runCommandWithArgs(args, env):
    cmd = args[0]
    try:
        ci = commands[cmd]
    except KeyError:
        ci = None
    if ci is None:
        print "Unknown command %s. Use 'help' to get commands"%cmd
        return 0
    return ci[1](args, env)
    
def runCmd(cmd, env):
    if len(cmd) == 0:
        return 0
    args = cmd.split()
    if len(args) == 0:
        return 0
    return runCommandWithArgs(args, env)
    
def runShell(env):
    if env['remote']:
        commands['connect'] = ('Connect to remote Virtual Box', cmdConnect)
        commands['disconnect'] = (('Disconnect from remote Virtual Box', cmdDisconnect))
        env['remoteinfo'] = ["http://localhost:18083", "", ""]
        
    while True:
        try:
            cmd = raw_input(g_prompt)
            ret = runCmd(cmd, env)
            print "Cmd: %s"%cmd
            if ret != 0:
                break
        except KeyboardInterrupt:
            print "Type quit to exit application"
                

commands = {"help": ("Prints this help", cmdHelp),
            "startvm": ("Start virtual machine", cmdStartVM),
            "quit": ("Quit program", cmdQuit),
           }    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help = "Print more info")
    parser.add_argument("-w", "--webservice", dest="style", action="store_const", const="WEBSERVICE", help = "Use webservice")
    args = parser.parse_args(sys.argv[1:])
    
    print args
    params = None
    vboxMgr = VirtualBoxManager(args.style, params)
    print vboxMgr
    env = {'mgr' : vboxMgr,
           'vbox': vboxMgr.vbox,
           'const': vboxMgr.constants,
           'remote': vboxMgr.remote
           }
    
    runShell(env)
    vboxMgr.deinit()
    del vboxMgr
