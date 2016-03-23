from vboxapi import *
import argparse
import os
from os import path
import sys
sys.path.append(os.getcwd())
from modules.exceptions import *
from modules.globals import *
import traceback

def progressBar(progress, update_time=1000):
    try:
        while not progress.completed:
            print "[" + int(progress.percent)/2 * "=" + ">]\r",
            sys.stdout.flush()
            progress.waitForCompletion(update_time)
        
        if int(progress.resultCode) != 0:
            print "Error while performing command"
            print str(progress.errorInfo.text)
    except KeyboardInterrupt:
        if progress.cancelable:
            print "Canceling..."
            progress.cancel()
    return 0

def cmdConnect(args, env):
    if len(args) < 2 or len(args > 4):
        print "Wrong arguments for startvm"
        return 0
    
    if env['vbox'] is not None:
        print "Already connected"
        return 0
    host = args[1]
    port = args[2] if len(args) > 2 else 18083
    user = args[3] if len(args) > 3 else ""
    password = args[4] if len(args) > 4 else ""
    url = "http://" + host + ":" + port
    env['remoteinfo'] = [url, user, password]
    
    env['mgr'].platform.connect(url, user, password)
    env['vbox'] = env['mgr'].vbox  
    return 0

def cmdDisconnect(args, env):
    if len(args) > 1:
        print "Too many arguments for disconnect"
        return 0
    
    env['mgr'].platform.disconnect()
    return

def cmdHelp(args, env):
    print "This is help"
    return 0

def cmdExit(args, env):
    return 1

def cmdAddHost(args, env):
    if len(args) < 2 or len(args) > 4:
        print "Wrong arguments for addhost"
        return 0
    host = args[1]
    port = args[2] if len(args) > 2 else 18083
    user = args[3] if len(args) > 3 else ""
    password = args[4] if len(args) > 4 else ""
    url = "http://" + host + ":" + str(port)
    params = {'url': url,
              'user': user,
              'password': password}
    
    vboxMgr = VirtualBoxManager('WEBSERVICE', params)
    g_envs[url] = {'mgr': vboxMgr,
                   'vbox': vboxMgr.vbox,
                   'const': vboxMgr.constants,
                   'remote': vboxMgr.remote,
                   'remoteinfo': [url, user, password]
                   }
    return 0

def cmdRemoveHost(args, env):
    if len(args) < 2 or len(args) > 3:
        print "Wrong arguments for removehost"
        return 0
    host = args[1]
    port = args[2] if len(args) > 2 else 18083
    url = "http://" + host + ":" + str(port)
    print url
    print g_envs
    try:
        del g_envs[url]
        print "Host successfully removed"
    except KeyError:
        print "Host is not registrered, it can't be removed"
    return 0

def cmdSwitchHost(args, env):
    if len(args) != 2:
        print "Wrong arguments for switchhost"
        return 0
    global g_envs
    env = g_envs[url]
    return 0

def cmdStartVM(args, env):
    if len(args) < 1 or len(args) > 2:
        print "Wrong arguments for startvm"
        return 0
    name = args[1]
    machine = env['vbox'].findMachine(name)
    session = env['mgr'].getSessionObject(env['vbox'])
    progress = machine.launchVMProcess(session, "gui", "")
    progressBar(progress, 100)
    
    return 0

def cmdExportVM(args, env):
    if len(args) < 3 or len(args) > 4:
        print "Wrong arguments for exportvm"
        return 0
    machine_name = args[1]
    expPath = args[2]
    print expPath
    print os.path.exists(os.path.dirname(expPath))
    print os.access((os.path.dirname(expPath)), os.R_OK)
    if len(args) > 3:
        format = args[3]
    else:
        format = "ovf-1.0"
    vbox = env['vbox']
    print args
    appliance = vbox.createAppliance()
    machine = vbox.findMachine(machine_name)
    desc = machine.exportTo(appliance, '')
    progress = appliance.write(format, None, expPath)
    progressBar(progress)
    print "Export completed"
    return 0

def cmdImportVM(args, env):
    if len(args) != 2:
        print "Wrong arguments for importvm"
        return 0
    vbox = env['vbox']
    import_file = args[1]
    appliance = vbox.createAppliance()
    progress = appliance.read(import_file)
    progressBar(progress, 1000)
    print "Read completed"
    appliance.interpret()
    progress = appliance.importMachines(None)
    progressBar(progress, 1000)
    print "Import completed"

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
    print args
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
        url = "http://localhost:18083"
        commands["addhost"] = ("Add a new host", cmdAddHost)
        commands["removehost"] = ("Remove host", cmdRemoveHost)
        commands['switchhost'] = ('Switch to another host', cmdSwitchHost)
        commands['connect'] = ('Connect to remote Virtual Box', cmdConnect)
        commands['disconnect'] = ('Disconnect from remote Virtual Box', cmdDisconnect)
        
        env['remoteinfo'] = [url, "", ""]
        g_envs[url] = env
        
    while True:
        try:
            cmd = raw_input(g_prompt)
            ret = runCmd(cmd, env)
            if ret != 0:
                break
        except KeyboardInterrupt:
            print "Type quit to exit application"
                
commands = {"help": ("Prints this help", cmdHelp),
            "startvm": ("Start virtual machine", cmdStartVM),
            "exportvm": ("Export virtual machine", cmdExportVM),
            "importvm": ("Import virtual machine", cmdImportVM),
            "exit": ("Quit program", cmdExit),
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
    try:
        vboxMgr.deinit()
    except:
        pass
    finally:
        del vboxMgr
