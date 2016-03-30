from vboxapi import *
import argparse
import os
from os import path
import sys
import shlex
import traceback
#TODO: command for setting env. variable
#      performance collector
#      set cpus/ram/gram

sys.path.append(path.dirname(path.dirname(path.realpath(sys.argv[0]))))
from modules.exceptions import *
from modules.globals import *

class Environment():
    def __init__(self, info):
        self.info = info
        
class Interpret():
    def __init__(self, style):       
        self.envs = {}        
        self.isRemote = (style == 'WEBSERVICE')
        self.commands = self.createCommands()
        self.active = None
    
    def addEnv(self, env):
        if not isinstance(env, Environment):
            print "Environment object invalid"
            return
        if 'remoteinfo' in env.info.keys():
            url = env.info['remoteinfo'][0]
        else:
            url = "http://localhost:18083"
        self.envs[url] = env
    
    def setActiveEnv(self, url):
        if url not in self.envs.keys():
            print "Environment does not exist"
            return 0
        self.active = self.envs[url]
            
    def cmdRestartVM(self, args):
        if len(args) != 2:
            print "Wrong arguments for restart. Usage: restart <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        session.console.reset()
        return 0
    
    def cmdPause(self, args):
        if len(args) != 2:
            print "Wrong arguments for pause. Usage: pause <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        session.console.pause()
        return 0
                
    def cmdResume(self, args):
        if len(args) != 2:
            print "Wrong arguments for resume. Usage: resume <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        session.console.resume() 
        return 0
                
    def cmdPowerOff(self, args):
        if len(args) != 2:
            print "Wrong arguments for poweroff. Usage: poweroff <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        progress = session.console.powerDown() 
        self.progressBar(progress)               
        return 0
    
    def cmdPowerButton(self, args):
        if len(args) != 2:
            print "Wrong arguments for powerbutton. Usage: powerbutton <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        session.console.powerButton()
        return 0
            
    def cmdSleepButton(self, args):
        if len(args) != 2:
            print "Wrong arguments for sleepbutton. Usage: sleepbutton <machine_name|machine uuid>"
            return 0
        machname = args[1]
        machine, session = self.lockSession(machname)
        session.console.sleepButton()
        return 0
    
    def cmdSleep(self, args):
        if len(args) != 2:
            print "Wrong arguments for sleep. Usage: sleep <time>"
            return 0
        from time import sleep
        sleep(args[1])
        return 0
                
    def lockSession(self, machname):
        vbox = self.active.info['vbox']
        const = self.active.info['const']
        machine = vbox.findMachine(machname)
        session = self.active.info['mgr'].getSessionObject(vbox)
        machine.lockMachine(session, const.LockType_Shared)
        return machine, session
        
    def createCommands(self):
        commands = {"help": ("Prints this help", self.cmdHelp),
                    "createvm": ("Create a virtual machine", self.cmdCreateVM),
                    "removevm": ("Create a virtual machine", self.cmdRemoveVM),
                    "startvm": ("Start virtual machine", self.cmdStartVM),
                    "reset": ("Restart virtual machine", self.cmdRestartVM),
                    "pause": ("Pause virtual machine", self.cmdPause),            
                    "resume": ("Resume virtual machine", self.cmdResume),
                    "poweroff": ("Power off a virtual machine", self.cmdPowerOff),
                    "powerbutton": ("Power off a virtual machine", self.cmdPowerButton),
                    "sleepbutton": ("Sleep a virtual machine", self.cmdSleepButton),                            
                    "exportvm": ("Export virtual machine", self.cmdExportVM),
                    "importvm": ("Import virtual machine", self.cmdImportVM),
                    "host": ("Show info about host", self.cmdHost),
                    "guest": ("Execute a command on guest", self.cmdGuest),
                    "sleep": ("Sleep for a period of time", self.cmdSleep),
                    "exit": ("Quit program", self.cmdExit),
                   }
        if self.isRemote:
            commands["addhost"] = ("Add a new host", self.cmdAddHost)
            commands["removehost"] = ("Remove host", self.cmdRemoveHost)
            commands['switchhost'] = ('Switch to another host', self.cmdSwitchHost)
            commands['connect'] = ('Connect to remote Virtual Box', self.cmdConnect)
            commands['disconnect'] = ('Disconnect from remote Virtual Box', self.cmdDisconnect)
            commands['reconnect'] = ('Reconnects to a remote Virtual Box', self.cmdReconnect)
        return commands  
     
    def run(self):
        if self.active is None:
            print "No VBoxWebServer to connect to."
            return 
        while True:
            try:
                cmd = raw_input(g_prompt)
                ret = self.runCmd(cmd)
                if ret != 0:
                    break
            except KeyboardInterrupt:
                print "Type quit to exit application"
                         
    def progressBar(self, progress, update_time=1000):
        try:
            while not progress.completed:
                percent = progress.percent
                string = "[" + int(percent)/2 * "=" + ">]"
                print string + (60 - len(string) - 3) * " " + str(percent) + "%\r",
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
    
    def cmdConnect(self, args):
        if len(args) < 2 or len(args > 4):
            print "Wrong arguments for connect. Usage: connect <hostname|ip> [port] [user] [password]"
            return 0
        
        if self.active.info['vbox'] is not None:
            print "Already connected"
            return 0
        host = args[1]
        port = args[2] if len(args) > 2 else 18083
        user = args[3] if len(args) > 3 else ""
        password = args[4] if len(args) > 4 else ""
        url = "http://" + host + ":" + port
        self.active.info['remoteinfo'] = [url, user, password]
        
        self.active.info['mgr'].platform.connect(url, user, password)
        self.active.info['vbox'] = self.active.info['mgr'].vbox  
        return 0
    
    def cmdReconnect(self, args):
        if len(args) != 1:
            print "Too many arguments for disconnect"
            return 0
        try:
            [url, user, password] = self.active.info['remoteinfo'] 
        except KeyError:
            print "Trying to recconect to the unknown host machine"
            return 0
        try:
            self.active.info['mgr'].platform.disconnect()
        except: # Do nothing if already disconnected
            pass 
        vbox = self.active.info['mgr'].platform.connect(url, user, password)
        self.active.info['vbox'] = vbox
        return 0
    
    def cmdDisconnect(self, args):
        if len(args) != 2:
            print "Too many arguments for disconnect"
            return 0
        try:
            self.active.info['mgr'].platform.disconnect()
        except:
            pass
        return 0
    
    def cmdHelp(self, args):
        print "This is help"
        return 0

    def cmdCreateVM(self, args):
        if len(args) < 2 or len(args) > 2:
            print "Wrong arguments for startvm"
        name = args[1]
        
        mach = self.active.info['vbox'].createMachine("", name, None, "Ubuntu_64", 1)
        mach.saveSettings()
        self.active.info['vbox'].registerMachine(mach)
        return 0

    def cmdRemoveVM(self, args):
        if len(args) < 2 or len(args) > 2:
            print "Wrong arguments for removevm"
        name = args[1]
        machine = self.active.info['vbox'].findMachine(name)
        flag = 3
        medias = machine.unregister(flag)
        progress = machine.deleteConfig(medias)
        self.progressBar(progress, 100)
        return 0            
    
    def cmdExit(self, args):
        return 1
   
    def cmdGuest(self, args):
        if len(args) < 3:
            print "Wrong arguments for guest"
            return 0
        machname = args[1]
        executable = args[2]
        guestargs = args[2:]
        
        vbox = self.active.info['vbox']
        mach = vbox.findMachine(machname)
        const = self.active.info['const']
        session = self.active.info['mgr'].getSessionObject(vbox)
        mach.lockMachine(session, self.active.info['const'].LockType_Shared)
        
        user = raw_input("User: ")
        password = raw_input("Password: ")
        guestSession = session.console.guest.createSession(user, password, '', '')
        guestSession.waitFor(1, 10000)
        print "Starting process %s with args %s"%(executable, str(guestargs))
        proc = guestSession.processCreate(executable, guestargs, None, None, 0)
        proc.waitFor(1, 10000)
        print "Process started with PID " + str(proc.PID)
        proc.waitFor(2, 10000)
        print "Process ended with exit code " + str(proc.exitCode)
        return 0
        
    def cmdAddHost(self, args):
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
        self.envs[url] = Environment({'mgr': vboxMgr,
                       'vbox': vboxMgr.vbox,
                       'const': vboxMgr.constants,
                       'remote': vboxMgr.remote,
                       'remoteinfo': [url, user, password]
                       })
        return 0
    
    def cmdRemoveHost(self, args):
        if len(args) < 2 or len(args) > 3:
            print "Wrong arguments for removehost"
            return 0
        host = args[1]
        port = args[2] if len(args) > 2 else 18083
        url = "http://" + host + ":" + str(port)
        print url
        try:
            print "Host successfully removed"
        except KeyError:
            print "Host is not registrered, it can't be removed"
        return 0
    
    def cmdSwitchHost(self, args):
        if len(args) != 2:
            print "Wrong arguments for switchhost"
            return 0
        url = args[1]
        try:
            self.active = self.envs[url]
        except KeyError:
            print "Host does not exist"
        else:
            self.cmdReconnect([""])
        return 0
    
    def cmdStartVM(self, args):
        if len(args) < 1 or len(args) > 2:
            print "Wrong arguments for startvm"
            return 0
        name = args[1]
        machine = self.active.info['vbox'].findMachine(name)
        session = self.active.info['mgr'].getSessionObject(self.active.info['vbox'])
        progress = machine.launchVMProcess(session, "gui", "")
        self.progressBar(progress, 100)
        
        return 0
    
    def cmdExportVM(self,args):
        if len(args) < 3 or len(args) > 4:
            print "Wrong arguments for exportvm"
            return 0
        machine_name = args[1]
        expPath = args[2]
        print expPath
        if len(args) > 3:
            format = args[3]
        else:
            format = "ovf-1.0"
        vbox = self.active.info['vbox']
        appliance = vbox.createAppliance()
        machine = vbox.findMachine(machine_name)
        desc = machine.exportTo(appliance, '')
        progress = appliance.write(format, None, expPath)
        self.progressBar(progress)
        print "Export completed"
        return 0
    
    def cmdImportVM(self, args):
        if len(args) != 2:
            print "Wrong arguments for importvm"
            return 0
        vbox = self.active.info['vbox']
        import_file = args[1]
        appliance = vbox.createAppliance()
        progress = appliance.read(import_file)
        self.progressBar(progress, 1000)
        print "Read completed"
        appliance.interpret()
        progress = appliance.importMachines(None)
        self.progressBar(progress, 1000)
        print "Import completed"
    
        return 0
    
    def cmdHost(self, args):
        if len(args) > 1:
            print "Wrong arguments for host"
            return 0
        for key, value in self.active.info.items():
            print key + ": " + str(value)
        return 0
            
    def runCommandWithArgs(self, args):
        cmd = args[0]
        try:
            ci = self.commands[cmd]
        except KeyError:
            ci = None
        if ci is None:
            print "Unknown command %s. Use 'help' to get commands"%cmd
            return 0
        return ci[1](args)
        
    def runCmd(self, cmd):
        if len(cmd) == 0:
            return 0
        args = shlex.split(cmd)
        print args
        if len(args) == 0:
            return 0
        return self.runCommandWithArgs(args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--webservice", dest="style", action="store_const", const="WEBSERVICE", help = "Use webservice")
    args = parser.parse_args(sys.argv[1:])
    
    params = None
    #for arg1, option in vars(args).items():
    #    print arg1 + ": " + str(option)
    #    opts = option.split(',')
    #    for opt_line in opts:
    #        opt, arg = opt_line.split('=')
            
    params = None
    try:
        vboxMgr = VirtualBoxManager(args.style, params)
    except:
        print "Vbox not running, exiting."
        exit(0)
    url = "http://localhost:18083"
    env = Environment({'mgr' : vboxMgr,
                       'vbox': vboxMgr.vbox,
                       'const': vboxMgr.constants,
                       'remote': vboxMgr.remote
                       })
    if env.info['remote']:
        env.info['remoteinfo'] = [url, "", ""]
    interpret = Interpret(args.style)
    interpret.addEnv(env)
    interpret.setActiveEnv(url)
    interpret.run()
    # Run ended
    for env in interpret.envs.values():
        del env.info['mgr']