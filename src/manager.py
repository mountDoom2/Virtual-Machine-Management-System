from vboxapi import *
import argparse
import os
from os import path
import sys
sys.path.append(os.getcwd())
from modules.exceptions import *
from modules.globals import *
import traceback

class Environment():
    def __init__(self, info):
        self.info = info
        
class Interpret():
    def __init__(self, args):
        
        self.envs = {}
        self.active = None
        self.isRemote = args.style == 'WEBSERVICE'
        self.commands = self.createCommands()
        
        params = None
        vboxMgr = VirtualBoxManager(args.style, params)
        env = Environment({'mgr' : vboxMgr,
                           'vbox': vboxMgr.vbox,
                           'const': vboxMgr.constants,
                           'remote': vboxMgr.remote
                           })
        if self.isRemote:
            url = "http://localhost:18083"
            env.info['remoteinfo'] = [url, "", ""]
            self.envs[url] = env
        self.active = env

    def createCommands(self):
        commands = {"help": ("Prints this help", self.cmdHelp),
                    "startvm": ("Start virtual machine", self.cmdStartVM),
                    "exportvm": ("Export virtual machine", self.cmdExportVM),
                    "importvm": ("Import virtual machine", self.cmdImportVM),
                    "exit": ("Quit program", self.cmdExit),
                   }
        if self.isRemote:
            commands["addhost"] = ("Add a new host", self.cmdAddHost)
            commands["removehost"] = ("Remove host", self.cmdRemoveHost)
            commands['switchhost'] = ('Switch to another host', self.cmdSwitchHost)
            commands['connect'] = ('Connect to remote Virtual Box', self.cmdConnect)
            commands['disconnect'] = ('Disconnect from remote Virtual Box', self.cmdDisconnect)
        return commands  
     
    def run(self):
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
    
    def cmdConnect(self, args):
        if len(args) < 2 or len(args > 4):
            print "Wrong arguments for startvm"
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
        self.active.info['vbox'] = env['mgr'].vbox  
        return 0
    
    def cmdDisconnect(self, args):
        if len(args) > 1:
            print "Too many arguments for disconnect"
            return 0
        
        self.active.info['mgr'].platform.disconnect()
        return
    
    def cmdHelp(self, args):
        print "This is help"
        return 0
    
    def cmdExit(self, args):
        return 1
    
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
        global g_envs
        self.active = self.envs[url]
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
    
    def runCommandWithArgs(self, args):
        cmd = args[0]
        try:
            ci = self.commands[cmd]
        except KeyError:
            ci = None
        if ci is None:
            print "Unknown command %s. Use 'help' to get commands"%cmd
            return 0
        print args
        return ci[1](args)
        
    def runCmd(self, cmd):
        if len(cmd) == 0:
            return 0
        args = cmd.split()
        if len(args) == 0:
            return 0
        return self.runCommandWithArgs(args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False, help = "Print more info")
    parser.add_argument("-w", "--webservice", dest="style", action="store_const", const="WEBSERVICE", help = "Use webservice")
    args = parser.parse_args(sys.argv[1:])
    interpret = Interpret(args)
    interpret.run()