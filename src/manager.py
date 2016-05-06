from vboxapi import *
import copy
import argparse
import os
from os import path
import sys
import shlex
import re
import time
import traceback
#TODO: command for setting env. variable
#      performance collector
#      set cpus/ram/gram

sys.path.append(path.dirname(path.dirname(path.realpath(sys.argv[0]))))
from modules.errors import *
from modules.globals import *

class Group():
    def __init__(self, name):
        self.name = name
        self.machines = {}
        return
    
    def addMachine(self, host, machname, user=None, password=None):
        if ((user is None and password is not None) or 
            (user is not None and password is None)):
            print "Must user or password"
            return
        credentials = {'user': user, 'password': password}
        
        if host not in self.machines.keys():
            self.machines[host] = {machname: credentials}
        else:
            self.machines[host][machname] = credentials
        return
    
    def removeMachine(self, host, machname):
        if host in self.machines.keys() and machname in self.machines[host].key():       
            del self.machines[host][machname]
            if not len(self.machines[host]):
                del self.machines[host]
        return
    
    def getName(self):
        return self.name
    
    def getMachines(self):
        return self.machines

class Environment():
    def __init__(self, values):
        if values is None:
            values = {}
        elif not isinstance(values, dict):
            raise EnvironmentException("Given values are not a dictionary object")

        self.hostname = values.get('hostname', 'localhost')
        self.port = values.get('port', 18083)
        self.username = values.get('username', "")
        self.password = values.get('password', "")
        self.name = values.get('name') if (values.get('name') and len(values.get('name'))) else self.hostname
        self.style = values.get('style')
        self.remote = (self.style == 'WEBSERVICE')
        if self.username:
            self.prompt = self.username + '@' + self.name + '>'
        else:
            self.prompt = self.name + '>'
        
        self.mgr = None
        self.vbox = None
        self.const = None
        params = None
        if self.remote:
            self.url = 'http://' + self.hostname + ':' + str(self.port)        
            params = {'url': self.url,
                      'user': self.username,
                      'password': self.password,
                      }

        mgr = VirtualBoxManager(self.style, params)
        self.mgr = mgr
        self.vbox = mgr.vbox
        self.const = mgr.constants
        self.remote = mgr.remote
        
        self.machines = {}
    
    def addMachine(self, machname, user=None, password=None):
        if ((user is None and password is not None) or 
            (user is not None and password is None)):
            print "Must user or password"
            return
        self.machines[machname] = {'user': user, 'password': password}
    
    def removeMachine(self, machname):
        if machname in self.machines.keys():
            del self.machines[machname]
    def getMachines(self):
        return self.machines
        
class Interpret():
    def __init__(self, style):       
        self.envs = {}
        self.isRemote = (style == 'WEBSERVICE')
        self.commands = self.createCommands()

        self.active = None
        self.groups = {}
    
    def getGroup(self, name):
        return self.groups.get(name)
        
    def addEnv(self, env):
        if not isinstance(env, Environment):
            print "Environment object invalid"
            return
        
        self.envs[env.name] = env
    
    def getCredentials(self, machname):
        if machname in self.active.getMachines().keys():
            user = self.active.getMachines()[machname]['username']
            password = self.active.getMachines()[machname]['password']
            if len(user) and len(password):
                return user, password

        for group in self.groups.values():
            for host, machines in group.getMachines().items():
                if host != self.active.name:
                    continue                            
                for mname, credentials in machines.items():
                    print credentials
                    if machname == mname:
                        user = credentials['user']
                        password = credentials['password']
                        if len(user) and len(password):
                            return user, password
        user = raw_input("User: ")
        password = raw_input("Password: ")
        return user, password

    def loadConfiguration(self, filename):
        try:
            backupEnvs = copy.copy(self.envs) # Backup current state in case of error
            backupGroups = copy.copy(self.groups)
            lineNum = 0
            with open(filename, 'r') as conf_file:
        
                for line in conf_file:
                    lineNum += 1
                    if len(line) < 3: # Empty line, do not count newline chars (\r\n)
                        continue
                    split = line.split()
                    if not len(split):
                        continue
                    params = {'group': None,
                              'user': None,
                              'password': None
                              }
                    host, machname = split[0].split('/')
                    for element in split[1:]:
                        paramName, paramVal = element.split('=')
                        # Accept only first occurence of parameter
                        if paramName in params.keys():
                            if params[paramName] is None:
                                params[paramName] = paramVal
                            else:
                                print "Parameter '%s' already set, ignoring this one. (line %d)"%(paramName, lineNum)
                        else:
                            print "Undefined parameter '%s' on line %d"%(paramName, lineNum)
                            continue
                    if params['group'] is not None:
                        if self.getGroup(params['group']) is None:
                            group = Group(params['group'])
                            self.groups[params['group']] = group
                        self.groups[params['group']].addMachine(host, machname, params['user'], params['password'])               
        except IOError:
            print "Could not open or read configuration file"
        except (IndexError, ValueError): # Missing host or machine name
            print "Error while loading configuration on line %d, restoring the state before loading configuration file"%lineNum
            self.clearConfiguration()
            self.envs = backupEnvs
            self.groups = backupGroups
        return

    def saveConfiguration(self, dest):
        try:
            fp = open(dest, 'w')
        except IOError:
            print "Could not open file to save configuration"
            return
        # Save environments
        for env in self.envs.values():
            host = env.hostname
            user = env.username
            password = env.password
            
            for machname, credentials in env.machines:
                print machname, credentials
        
        # Save groups
        for group in self.groups.values():   
            for host, machines in group.getMachines().items():
                for machname, credentials in machines.items():
                    userstr = ("user=" + credentials['user'])
                    passstr = ("password=" + credentials['password'])
                    strline = "%s/%s group=%s %s %s\n"%(host, machname, group.getName(), userstr, passstr)
                    fp.write(strline)
        fp.close()
        return
    
    def clearConfiguration(self):
        self.envs = {}
        self.groups = {}
        return    
    
    def setActiveEnv(self, url):
        if url not in self.envs.keys():
            print "Environment does not exist"
            return 0
        self.active = self.envs[url]
            
    def cmdRestartVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for restart. Usage: restart <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        session.console.reset()
        return 0
    
    def cmdPause(self, args):
        if len(args) != 1:
            print "Wrong arguments for pause. Usage: pause <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        session.console.pause()
        return 0
                
    def cmdResume(self, args):
        if len(args) != 1:
            print "Wrong arguments for resume. Usage: resume <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        session.console.resume() 
        return 0
                
    def cmdPowerOff(self, args):
        if len(args) != 1:
            print "Wrong arguments for poweroff. Usage: poweroff <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        progress = session.console.powerDown() 
        self.progressBar(progress)               
        return 0
    
    def cmdPowerButton(self, args):
        if len(args) != 1:
            print "Wrong arguments for powerbutton. Usage: powerbutton <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        session.console.powerButton()
        return 0
            
    def cmdSleepButton(self, args):
        if len(args) != 1:
            print "Wrong arguments for sleepbutton. Usage: sleepbutton <machine_name|machine uuid>"
            return 0
        machname = args[0]
        machine, session = self.lockSession(machname)
        session.console.sleepButton()
        return 0
    
    def cmdGroups(self, args):
        if len(args) > 0:
            print "Too much arguments for groups"
            return 0
        if not len(self.groups):
            print "No existing groups found. Use command 'creategroup' to create one"
        for groupName, group in self.groups.items():
            print groupName
            machines = group.getMachines()
            if not len(machines):
                print 4*" " + "<empty>"
                continue
            for host, machines in machines.items():
                print 4 * " " + host
                for machname, credentials in machines.items():
                    username = str(credentials.get('user', '<empty>'))
                    password = str(credentials.get('password', '<empty>'))
                    print 8 * " " + machname + " (" + username + ", " + password + ')'

        return 0
    
    def cmdCreateGroup(self, args):
        if len(args) != 1:
            print "Wrong arguments for creategroup command. Usage: creategroup <groupname>"
            return 0
        groupname = args[0] 
        group = Group(groupname)
        if groupname not in self.groups.keys():
            self.groups[groupname] = group
        else:
            print "Group already exists"
        return 0
    
    def cmdRemoveGroup(self, args):
        if len(args) != 1:
            print "Wrong arguments for creategroup command. Usage: removegroup <groupname>"
            return 0
        groupname = args[0] 
        group = Group(groupname)
        if group:
            del self.groups[groupname]
        return 0
        
    def cmdAddToGroup(self, args):
        if len(args) < 3 or len(args) > 5:
            print "Wrong arguments for addtogroup command. Usage: addtogroup <groupname> <hostname> <machine> [username] [password]"
            return 0
        groupname = args[0]
        hostname = args[1]
        machname = args[2]
        username = args[3] if len(args) > 3 else None
        password = args[4] if len(args) > 4 else None
        
        if hostname not in self.envs.keys():
            print "Unknown host"
            return 0
        
        if groupname not in self.groups.keys():
            print "Creating a new group"
            self.cmdCreateGroup([groupname])
            
        group = self.groups.get(groupname)
        if group:
            group.addMachine(hostname, machname, username, password)
        else:
            print "Adding to unexisting group, create one with creategroup command"
        return 0
    
    def cmdRemoveFromGroup(self, args):
        if len(args) < 2 or len(args) > 3:
            print "Wrong arguments for removefromgroup. Usage: removefromgroup <host> <group> [machine]"
            return 0
        
        groupname = args[0]
        hostarg = args[1]
        macharg = args[2] if len(args) > 2 else None
        
        group = self.getGroup(groupname)
        if group is None:
            print "Group '%s' not found"%groupname
            return 0
        
        for hostname, machines in group.getMachines().items():
            if hostname == hostarg:
                if macharg is None:
                    del group.getMachines()[hostname]
                    break
                for machname in machines:
                    if machname == macharg:
                        del group[group][machname]
                        return 0
        return 0
    
    def cmdSleep(self, args):
        if len(args) != 1:
            print "Wrong arguments for sleep. Usage: sleep <time>"
            return 0
        time.sleep(float(args[0]))
        return 0
                
    def lockSession(self, machname):
        vbox = self.active.vbox
        const = self.active.const
        machine = vbox.findMachine(machname)
        session = self.active.mgr.getSessionObject(vbox)
        machine.lockMachine(session, const.LockType_Shared)
        return machine, session
        
    def createCommands(self):
        commands = {"help": ("Prints this help", "local", self.cmdHelp),
                    "createvm": ("Create a virtual machine", "network", self.cmdCreateVM),
                    "removevm": ("Remove a virtual machine", "network",self.cmdRemoveVM),
                    "start": ("Start virtual machine", "network",self.cmdStartVM),
                    "restart": ("Restart virtual machine", "network",self.cmdRestartVM),
                    "pause": ("Pause virtual machine", "network",self.cmdPause),            
                    "resume": ("Resume virtual machine", "network",self.cmdResume),
                    "poweroff": ("Power off a virtual machine", "network",self.cmdPowerOff),
                    "powerbutton": ("Power off a virtual machine", "network",self.cmdPowerButton),
                    "sleepbutton": ("Sleep a virtual machine", "network",self.cmdSleepButton),                  
                    "exportvm": ("Export virtual machine", "network",self.cmdExportVM),
                    "importvm": ("Import virtual machine", "network", self.cmdImportVM),
                    "listvms": ("List virtual machines on current host", "network", self.cmdListVms),
                    "listrunningvms": ("List running virtual machine on current host", "network", self.cmdListRunningVms),
                    "host": ("Show info about host", "local", self.cmdHost),
                    "gcmd": ("Execute a command on guest", "network", self.cmdGcmd),
                    "gshell": ("Run an interactive shell on guest", "network", self.cmdGshell),
                    "batch": ("Run a batch file", "local", self.cmdBatch),
                    "sleep": ("Sleep for a period of time", "local", self.cmdSleep),
                    "groups": ("Print existing groups", "local", self.cmdGroups),
                    "creategroup": ("Create a new group", "local", self.cmdCreateGroup),
                    "removegroup": ("Remove group", "local", self.cmdRemoveGroup),
                    "addtogroup": ("Add machine to existing local", "network", self.cmdAddToGroup),
                    "removefromgroup": ("Remove machine existing group", "local", self.cmdRemoveFromGroup),
                    "load": ("Load configuration from file", "local", self.cmdLoad),
                    "save": ("Save current configuration to the file", "local", self.cmdSave),
                    "exit": ("Quit program", "local", self.cmdExit),
                   }
        if self.isRemote:
            commands["addhost"] = ("Add a new host", "network", self.cmdAddHost)
            commands["removehost"] = ("Remove host", "network", self.cmdRemoveHost)
            commands['switchhost'] = ('Switch to another host', "network", self.cmdSwitchHost)
            commands['connect'] = ('Connect to remote Virtual Box', "network", self.cmdConnect)
            commands['disconnect'] = ('Disconnect from remote Virtual Box', "network", self.cmdDisconnect)
            commands['reconnect'] = ('Reconnects to a remote Virtual Box', "network", self.cmdReconnect)
        return commands  
     
    def run(self):
        if self.active is None:
            print "Program is not connected to any host, please add some with 'addhost' command"
        while True:
            try:
                cmd = raw_input(self.active.prompt)
                retval = self.runCmd(cmd)
                if retval != 0:
                    break
            except KeyboardInterrupt:
                print "Type quit to exit application"
                break
            except EOFError:
                print "Violently killed, exiting"
                break
            except Exception:
                traceback.print_exc()
                #break
                
                         
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
        if len(args) != 1:
            print "Wrong arguments for connect. Usage: connect <hostname>"
            return 0
        
        host = args[0]

        env = self.envs.get(host)
        if not env:
            print "Unknown host"
            return 0
        
        url, user, password = env.url, env.username, env.password
        vbox = env.mgr.platform.connect(url, user, password)
        env.vbox = vbox  
        return 0
    
    def cmdReconnect(self, args):
        if len(args) > 1:
            print "Wrong arguments for reconnect command. Usage: reconneect <hostname>"
            return 0


        env = self.envs.get(args[0]) if len(args) > 0 else self.active
        
        try:
            url, user, password = env.url, env.username, env.password 
        except AttributeError, KeyError:
            print "Trying to reconnect to the unknown host machine"
            return 0
        try:
            env.mgr.platform.disconnect()
        except: # Do nothing if already disconnected
            pass 
        vbox = env.mgr.platform.connect(url, user, password)
        env.vbox = vbox
        return 0
    
    def cmdDisconnect(self, args):
        if len(args) > 1:
            print "Wrong arguments for disconnect. Usage: disconnect [hostname]"
            return 0
        env = self.envs.get(args[0]) if len(args) > 0 else self.active
        try:
            env.mgr.platform.disconnect()
        except:
            pass
        return 0
    
    def cmdHelp(self, args):
        print "This is help"
        return 0

    def cmdCreateVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for createvm. Usage: createvm <name>"
        name = args[0]
        
        mach = self.active.vbox.createMachine("", name, None, "Ubuntu_64", 1)
        mach.saveSettings()
        self.active.vbox.registerMachine(mach)
        return 0

    def cmdRemoveVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for removevm. Usage: removevm <name>"
        name = args[0]
        machine = self.active.vbox.findMachine(name)
        flag = 3
        medias = machine.unregister(flag)
        progress = machine.deleteConfig(medias)
        self.progressBar(progress, 100)
        return 0            
    
    def cmdExit(self, args):
        return 1

    def cmdGcmd(self, args):
        if len(args) < 2:
            print "Wrong arguments for gcmd. Usage: <machine_name|uuid> <path_to_executable> <args>"
            return 0
        machname = args[0]
        executable = args[1]
        guestargs = args[1:]
        
        vbox = self.active.vbox
        mach = vbox.findMachine(machname)
        session = self.active.mgr.getSessionObject(vbox)
        mach.lockMachine(session, self.active.const.LockType_Shared)
        
        user, password = self.getCredentials(machname)

        guestSession = session.console.guest.createSession(user, password, '', '')
        guestSession.waitFor(1, 10000) # Wait for session to start
        proc = guestSession.processCreate(executable, guestargs, None, [5,6], 0)
        print proc.waitFor(1, 10000) # Wait for process to start
        print proc.PID
        data = proc.read(1, 4096, 10000)
        print "stdout: " + str(data)
        
        data = proc.read(2, 4096, 10000)
        print "sterr: " + str(data)
        print proc.status
    
        print proc.waitFor(2, 10000) # Wait for terminate
        print proc.exitCode
        session.unlockMachine()
        return 0
   
    def cmdGshell(self, args):
        if len(args) != 1:
            print "Wrong arguments for guest. Usage: <machine_name|uuid>"
            return 0
        machname = args[0]
        #executable = r'C:\Codasip\MinGW\bin\sh.exe'#
        executable = r'C:\Windows\System32\cmd.exe'
        #executable = r'/bin/sh'
        guestargs = args[1:]

        vbox = self.active.vbox
        mach = vbox.findMachine(machname)
        session = self.active.mgr.getSessionObject(vbox)
        mach.lockMachine(session, self.active.const.LockType_Shared)
        
        user, password = self.getCredentials(machname)
        guestSession = session.console.guest.createSession(user, password, '', '')
        guestSession.waitFor(1, 10000) # Wait for session to start
        
        pathstyle = guestSession.pathStyle
        executable = r'C:\Windows\System32\cmd.exe' if pathstyle == 'DOS' else r'/bin/sh'
        
        proc = guestSession.processCreate(executable, guestargs, None, [5, 6], 0)
        print proc.waitFor(1, 10000) # Wait for process to start
        print proc.PID
        while True:
            data = proc.read(1, 8192, 10000)
            print "stdout: " + str(data)
            if proc.status == self.active.const.ProcessStatus_TerminatedNormally:
                print "Exit code: " + str(proc.exitCode)
                break
            inp = raw_input("cmd>")
            written = proc.write(0, 0, inp + '\n', 10000)            
            data = proc.read(2, 8192, 10000)
            print "sterr: " + str(data)
        
        proc.waitFor(2, 10000) # Wait for terminate
        guestSession.close()
        session.unlockMachine()
        return 0
    
    def cmdBatch(self, args):
        if len(args) != 1:
            print "Wrong arguments for batch. Usage: batch <file>"
            return 0
        
        try:
            fp = open(args[0], 'r')
            
            for line in fp:
                split = line.split(';') # There might be more commands on one line
                for command in split:
                    retval = self.runCmd(command)
                    if retval:
                        break
        except IOError:
            print "Could not open batch file"
        except KeyboardInterrupt:
            print "Type quit to exit application"
        except EOFError:
            print "Violently killed, exiting"
        except Exception:
            traceback.print_exc()
        return 0
    
    def cmdLoad(self, args):
        if len(args) < 1:
            print "Wrong arguments for loadconfig. Usage: loadconfig <file>"
        self.loadConfiguration(args[0])
        return 0

    def cmdSave(self, args):
        if len(args) < 1:
            print "Wrong arguments for saveconfig. Usage: saveconfig <file>"
        self.saveConfiguration(args[0])
        return 0
    
      
    def cmdAddHost(self, args):
        if len(args) < 1 or len(args) > 4:
            print "Wrong arguments for addhost. Usage: addhost <hostname/ip> [port] [user] [password] [displayname]"
            return 0
        host = args[0]
        port = int(args[1]) if (len(args) > 2 and len(args[1]) > 0) else 18083
        user = args[2] if len(args) > 3 else ""
        password = args[3] if len(args) > 4 else ""
        displayname = args[4] if (len(args) > 4 and len(args[4]) > 0) else None
        url = "http://" + host + ":" + str(port)
        params = {'url': url,
                  'user': user,
                  'password': password}
        try:
            if host in self.envs.keys():
                print "Host already exists"
                return 0
            vboxMgr = VirtualBoxManager('WEBSERVICE', params)
            self.envs[host] = Environment({'mgr': vboxMgr,
                                          'vbox': vboxMgr.vbox,
                                          'const': vboxMgr.constants,
                                          'remote': vboxMgr.remote,
                                          'remoteinfo': [url, user, password]
                                          })
        except:
            print "Could not connect to host " + host
        else:
            if self.active is None:
                print "This is the first known host, setting it as active"
                self.active = self.envs[host]
        return 0
    
    def cmdRemoveHost(self, args):
        if len(args) != 1:
            print "Wrong arguments for removehost. Usage: removehost <hostname>"
            return 0
        host = args[0]
        try:
            del self.envs[host]
            print "Host successfully removed"
        except KeyError:
            print "Uknown host, could not be deleted"
        return 0
    
    def cmdSwitchHost(self, args):
        if len(args) != 1:
            print "Wrong arguments for switchhost. Usage: switchhost <hostname>"
            return 0
        host = args[0]
        try:
            self.active = self.envs[host]
            self.cmdReconnect([])
        except KeyError:
            print "Host does not exist"
        except:
            print "Could not switch to host, unable to connect"
        else:
            print "Host successfully switched"
        return 0
    
    def cmdStartVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for startvm. Usage: startvm <machine_name>"
            return 0
        name = args[0]
        machine = self.active.vbox.findMachine(name)
        session = self.active.mgr.getSessionObject(self.active.vbox)
        progress = machine.launchVMProcess(session, "gui", "")
        self.progressBar(progress, 100)
        
        return 0
    
    def cmdExportVM(self,args):
        if len(args) < 2 or len(args) > 3:
            print "Wrong arguments for exportvm. Usage: exportvm <machine_name> <output_path>"
            return 0
        machine_name = args[0]
        expPath = args[1]
        print expPath
        if len(args) > 3:
            format = args[2]
        else:
            format = "ovf-1.0"
        vbox = self.active.vbox
        appliance = vbox.createAppliance()
        machine = vbox.findMachine(machine_name)
        desc = machine.exportTo(appliance, '')
        progress = appliance.write(format, None, expPath)
        self.progressBar(progress)
        print "Export completed"
        return 0
    
    def cmdImportVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for importvm. Usage: importvm <path_to_image>"
            return 0
        vbox = self.active.vbox
        import_file = args[0]
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
        if len(args) != 0:
            print "Wrong arguments for host"
            return 0
        return 0
    
    def cmdListVms(self, args):
        if len(args) != 0:
            print "Wrong arguments for listvms"
            return 0
        vbox = self.active.vbox
        machines = self.active.mgr.getArray(vbox, 'machines')
        for mach in machines:
            print str(mach.name) + " " + str(mach.state) + " " + str(mach.OSTypeId)
        return 0
    
    def cmdListRunningVms(self, args):
        if len(args) != 0:
            print "Wrong arguments for listrunningvms"
            return 0
        vbox = self.active.vbox
        machines = self.active.mgr.getArray(vbox, 'machines')
        for mach in machines:
            state = mach.state
            if state in ['FirstOnline', 'LastOnline']:
                print str(mach.name) + " " + str(mach.OSTypeId)        
        return 0
    
    def groupCommand(self, groupname, cmd, args):
        machines = self.groups.get(groupname).getMachines()
        for host in machines.keys():
            if host not in self.envs:
                print "Unexisting host " + host
                continue
            if self.active is not self.envs[host]:
                self.cmdSwitchHost([host])
            for machname in machines[host].keys():
                args[0] = machname
                try:
                    cmd(args)
                except:
                    traceback.print_exc()
        return 0 
        
    def runCommandWithArgs(self, args):
        cmd = args[0]
        args = args[1:] if len(args) > 1 else []
        try:
            ci = self.commands[cmd]
        except KeyError:
            print "Unknown command %s. Use 'help' to get commands"%cmd
            return 0
        if ci[1] == "network":
            self.cmdReconnect([]) # Do not lose connection
        if len(args) and ci[1] == "network" and args[0] in self.groups.keys():
            self.groupCommand(args[0], ci[2], args)
            retval = 0
        else:
            retval = ci[2](args) 
        return retval
        
    def runCmd(self, cmd):
        if len(cmd) == 0:
            return 0
        args = shlex.split(cmd)
        print args
        if len(args) == 0:
            return 0
        if self.active is None and args[0] != 'addhost':
            print "Program is not connected to any host, please add some with 'addhost' command"
            return 0
        return self.runCommandWithArgs(args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config-file", dest="config_file", help = "Configuration file")
    parser.add_argument("-w", "--webservice", dest="style", action="store_const", const="WEBSERVICE", help = "Use webservice")
    parser.add_argument("-o", "--opts", dest="opts", help = "Additional command line parameters")
    args = parser.parse_args(sys.argv[1:])
    
    params = {'style' : args.style}
    if args.opts is not None:
        try:
            for opt in args.opts.split(','):
                paramName = opt.split('=')[0]
                paramVal = opt.split('=')[1]
                params[paramName] = paramVal
        except:
            print "Arguments in wrong format, exiting..."
            sys.exit(1)
    
    try:
        if args.opts:
            params['hostname'] = params.get('hostname')
            params['user'] = params.get('user', "")
            params['password'] = params.get('password', "")    
        env = Environment(params)
    except EnvironmentError as e:
        print str(e) # print error
        sys.exit(1)
    

    interpret = Interpret(args.style)
    if (args.config_file):
        interpret.loadConfiguration(args.config_file)
    if 'env' in locals():
        interpret.addEnv(env)
        interpret.setActiveEnv(env.name)
    interpret.run()
    
    # Interpret finished
    for env in interpret.envs.values():
        del env.mgr