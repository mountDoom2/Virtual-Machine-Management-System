"""
File: manager.py
Author: Milan Skala
Date: 2016-03-20
Brief: This program enables remote control of virtual machines using
       VirtualBox API. User is able to execute commands on standalone
       virtual machines or gather them into groups and execute commands
       for a set of virtual machines. Interactive and automatic modes 
       are supported for this purpose. 
"""

import argparse # Argument parser
from datetime import datetime
from collections import OrderedDict
import copy # Backup current configuration, see loadConfiguration method
import os # OS features
from os import path # Paths handling
import re # Regex matches
import shlex # shell-like parser
import sys # Basic system features handling
import time # Used for sleep
from vboxapi import * # VirtualBox API module

# Extend path for own modules
sys.path.append(path.dirname(path.dirname(path.realpath(sys.argv[0]))))
from modules.errors import *  # Custom exceptions
from modules.globals import * # Some global constants

try: # Modules for history and autocompletion support
    import readline   # GNU readline
    import rlcompleter # Auto completer module
    historySupport = True
    cmdCompleter = True
except:
    pass

class commandCompleter(rlcompleter.Completer):
        """
        Class for command autocompletion
        """
        def __init__(self, cmds):
            """ Initiate with supported commands """
            rlcompleter.Completer.__init__(self, cmds)

        def complete(self, text, state):
            """ Overload complete method """
            return rlcompleter.Completer.complete(self, text, state)

        def isCommand(self, text):
            """ 
            Check if passed text can be command -> it has to be
            the first word. 
            """
            try:
                hasSpace = text.index(" ") # Command must be the first element in text
                return False
            except ValueError:
                return True # No space found, it can be commands
            
        def global_matches(self, text):
            """
            Overload global_matches method. Return array 
            of possible matches.
            """
            matches = []
            inp = readline.get_line_buffer() # Get user's input
            length = len(inp)

            if self.isCommand(inp): # No space in input
                for cmds in [self.namespace]:
                    for cmd in cmds:
                        if cmd[:length] == text: # Match found
                            matches.append(cmd)
            return matches

class Group():
    """
    Gathers the machines into a single entity. Most of the interpreter
    commands can be applied to this entity. 
    """
    def __init__(self, name):
        self.name = name
        self.machines = {}
        return
    
    def addMachine(self, host, machname, user=None, password=None):
        """
        Add a new machine to this group.
        @param host: hostname or IP address of server, where the machine is located
        @param machname: Machine name
        @param user: Username, which will be used for commands if needed. Default value: None
        @param password: Password, which will be used for commands if needed. Default value: None   
        """
        if ((user is None and password is not None) or # None or both credentials must be passed
            (user is not None and password is None)):
            print "Missing user or password"
            return
        
        credentials = {'user': user, 'password': password}

        if host not in self.machines.keys(): # First machine on this host, create a key for it
            self.machines[host] = {machname: credentials}
        else:
            self.machines[host][machname] = credentials
        return
    
    def removeMachine(self, host, machname = None):
        """
        Remove machine from this group. If host or machine does not exist, the method does nothing
        @param host: Known hostname from which the machine will be removed
        @param machname: Machine, which will be removed. If None, then all machines from passed host
                         are removed. Default value: None.
          
        """
        if host in self.machines.keys(): # Host exists
            if machname is None: # Remove the whole host
                del self.machines[host]
            elif machname in self.machines[host].keys(): # Remove a single machine       
                del self.machines[host][machname]
        return
    
    def getName(self):
        return self.name
    
    def getMachines(self):
        return self.machines

class Environment():
    """
    A class representing a single host machine and stores all neccessary data
    """
    def __init__(self, values):
        """
        Constructor
        @param values: Values passed in dictionary. Supported values are:
                       host: hostname or port of the server. Obligatory
                       port: port of HTTP server on host. Default value 18083
                       user: User used to login on the server
                       password: Password used to login on the server
                       name: User friendly name of server. If not passed, hostname is used.
                       style: If the value is 'WEBSERVICE', then this communication
                              with HTTP server will be user, else COM model is used.
        """
        if values is None:
            values = {}
        elif not isinstance(values, dict):
            raise EnvironmentException("Given values are not a dictionary object")
        elif 'host' not in values.keys() or not len(values.get('host')):
            raise EnvironmentException("Missing hostname")
        
        # Store parameters
        self.host = values.get('host')
        self.port = values.get('port') if values.get('port') else 18083 
        self.user = values.get('user') if values.get('user') else ""
        self.password = values.get('password') if values.get('port') else ""
        self.name = values.get('name') if (values.get('name') and len(values.get('name'))) else self.host
        self.style = values.get('style')
        self.remote = (self.style == 'WEBSERVICE')
        # Define the prompt for user 
        if self.user:
            self.prompt = self.user + '@' + self.name + '>'
        else:
            self.prompt = self.name + '>'
        
        # VirtualBox objects
        self.mgr = None
        self.vbox = None
        self.const = None
        params = None
        if self.remote: # Connect via webservice?
            self.url = 'http://' + self.host + ':' + str(self.port)        
            params = {'url': self.url,
                      'user': self.user,
                      'password': self.password,
                      }
        # Try to connect to remote server (or create local manager via COM)
        mgr = VirtualBoxManager(self.style, params)
        self.mgr = mgr
        self.vbox = mgr.vbox
        self.const = mgr.constants
        # Something went wrong during initialization
        if not any([self.mgr, self.vbox, self.const]):
            raise EnvironmentException("Failed to initialize environment")
        self.machines = {} # Dictionary to store machines credentials
    
    def addMachine(self, machname, user=None, password=None):
        """
        Add a new machine to this environment. Serves to store credentials to machine.
        """
        if ((user is None and password is not None) or # None or both credentials must be passed
            (user is not None and password is None)):
            print "Missing user or password"
            return
        if machname not in self.machines.keys():
            self.machines[machname] = {'user': user, 'password': password}
    
    def removeMachine(self, machname):
        """
        Remove machine if exists
        @param machname: machine to remove
        """
        if machname in self.machines.keys():
            del self.machines[machname]
                          
    def getName(self):
        return self.name
    
    def getMachines(self):
        return self.machines
        
class Interpreter():
    """
    Class which executes all comands
    """
    def __init__(self, style):
        self.envs = {} # Existing environments
        self.groups = {} # Existing groups
        
        self.isRemote = (style == 'WEBSERVICE')
        self.commands = self.createCommands()

        self.autoMode = False
        self.active = None # There is no active host now
    
    def setCmdAutoCompletion(self): 
        """
        Create and set auto completer
        """
        cmdDict = dict((key, None) for key in self.commands.keys())
        completer = commandCompleter(cmdDict)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")
    
    def getGroup(self, name):
        return self.groups.get(name)
        
    def addEnv(self, env):
        if not isinstance(env, Environment):
            print "Environment object invalid"
            return
        
        self.envs[env.name] = env
    
    def getCredentials(self, machname):
        """
        Try to find machine credentials in known machines. If not found,
        prompt user to insert them
        """
        # Search the machines of current environment
        if machname in self.active.getMachines().keys():
            user = self.active.getMachines()[machname]['user']
            password = self.active.getMachines()[machname]['password']
            if len(user) and len(password):
                return user, password
        # Search for the machine in groups
        for group in self.groups.values():
            for host, machines in group.getMachines().items():
                if host != self.active.name:
                    continue                            
                for mname, credentials in machines.items():
                    if machname == mname:
                        user = credentials['user']
                        password = credentials['password']
                        if len(user) and len(password):
                            return user, password
        # Nothing found, prompt user
        if self.autoMode:
            user = ""
            password = ""
        else:
            user = raw_input("User: ")
            password = raw_input("Password: ")
        return user, password
    
    def groupCommand(self, groupname, cmd, args):
        """
        Execute a command for group of machines
        @param groupname: Group whose machines will be used
        @param cmd: Command to be executed
        @param args: Command arguments  
        """
        machines = self.groups.get(groupname).getMachines()
        origHost = self.active.name
        for host in machines.keys():
            if host not in self.envs:
                print "Unexisting host " + host
                continue
            if self.active is not self.envs[host]: # Other host then actual -> switch
                self.cmdSwitchHost([host])
            for machname in machines[host].keys():
                args[0] = machname
                try:
                    cmd(args) # Execute a command with arguments
                except Exception as e:
                    if self.autoMode:
                        self.log("ERROR: Error while executing '%s' command with arguments '%s'"%(cmd.__name, args))
                    print str(e)
                    
        self.active = self.envs[origHost] # Switch back to original host
        return 0 
        
    def runCommandWithArgs(self, args):
        cmd = args[0] # Command name
        args = args[1:] if len(args) > 1 else [] # Command arguments
        try:
            ci = self.commands[cmd]
        except KeyError:
            print "Unknown command %s. Use 'help' to get commands"%cmd
            
            if self.autoMode:
                self.log("Using unknown command %s."%cmd)
                
            return 0
        if self.active.remote and ci[1] == "network": # Command uses server, make sure it stays connected
            self.cmdReconnect([])
        if len(args) and ci[1] == "network" and args[0] in self.groups.keys():
            # Group command
            retval = self.groupCommand(args[0], ci[2], args)
        else:
            retval = ci[2](args) # Execute command for a single machine
        return retval
        
    def runCmd(self, cmd):
        if len(cmd) == 0:
            return 0
        args = shlex.split(cmd)
        if len(args) == 0:
            return 0
        if self.active is None and args[0] != 'addhost':
            print "Program is not connected to any host, please add some with 'addhost' command"
            return 0
        return self.runCommandWithArgs(args)

    def run(self, batch_file=None):
        """
        Main method of interpreter. 
        @param batch_file: Batch file to process. If None, then interactive mode is used. 
        """
        global historySupport, cmdCompleter, maxHistoryLen
        if batch_file:
            # Run in auto mode
            self.autoMode = True
            self.logfile = open('manager_log.txt', 'w')
            self.cmdBatch([batch_file])
            return
        if self.active is None:
            print "Program is not connected to any host, please add some with 'addhost' command"
        
        # Set autocompleter and history if supported
        hist_file = os.path.join(os.path.expanduser("~"), ".managerhistory")
        if cmdCompleter:
            self.setCmdAutoCompletion()
        if historySupport:
            readline.set_history_length(maxHistoryLen)
            if os.path.exists(hist_file): # Load old history if any
                readline.read_history_file(hist_file)
        import traceback
        while True: # Interactive mode
            try:
                prompt = self.active.prompt if self.active else ">" 
                cmd = raw_input(prompt)
                retval = self.runCmd(cmd)
                if retval != 0:
                    break
            except KeyboardInterrupt: # SIGINT catch
                print "Type quit to exit application"
            except EOFError:
                print "Violently killed, exiting"
                break
            except Exception as e: # Something went wrong during the command execution
                traceback.print_exc()
                #print str(e) # Print the error, but do not break the loop
                
        if historySupport: # Interpreter ended, store history
            readline.write_history_file(hist_file) 
              
    def lockSession(self, machname):
        """
        Creates a new session and lock the machine
        @param machname: Machine to lock 
        """
        vbox = self.active.vbox
        const = self.active.const
        machine = vbox.findMachine(machname)
        session = self.active.mgr.getSessionObject(vbox) # Create new session object
        machine.lockMachine(session, const.LockType_Shared) # Lock the machine
        return machine, session
        
    def createCommands(self):   
        """
        Create a dictionary with supported commands. Some of them are not supported
        when using COM model.
        """
        
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
                    "exportvm": ("Export virtual machine to given destination", "network",self.cmdExportVM),
                    "importvm": ("Import virtual machine from image", "network", self.cmdImportVM),
                    "listhostvms": ("List virtual machines on current host", "network", self.cmdListVms),
                    "listrunningvms": ("List running virtual machine on current host", "network", self.cmdListRunningVms),
                    "gcmd": ("Execute a command on guest", "network", self.cmdGcmd),
                    "gshell": ("Run an interactive shell on guest", "network", self.cmdGshell),
                    "copyto": ("Copy file from host to virtual machine", "network", self.cmdCopyToMachine),
                    "copyfrom": ("Copy file from virtual machine to host", "network", self.cmdCopyFromMachine),
                    "batch": ("Run a batch file", "local", self.cmdBatch),
                    "setram": ("Set RAM memory for virtual machine", "network", self.cmdSetRam),
                    "setcpus": ("Set CPU count for virtual machine", "network", self.cmdSetCPU),
                    "listknownvms": ("List known virtual machines", "local", self.cmdList),
                    "host": ("List information about current host", "network", self.cmdHost),
                    "sleep": ("Sleep for a period of time", "local", self.cmdSleep),
                    "groups": ("Print existing groups", "local", self.cmdGroups),
                    "creategroup": ("Create a new group", "local", self.cmdCreateGroup),
                    "removegroup": ("Remove group", "local", self.cmdRemoveGroup),
                    "addtogroup": ("Add machine to existing local", "network", self.cmdAddToGroup),
                    "removefromgroup": ("Remove machine existing group", "local", self.cmdRemoveFromGroup),
                    "load": ("Load configuration from file", "local", self.cmdLoad),
                    "save": ("Save current configuration to the file", "local", self.cmdSave),
                    "exit": ("Exit program", "local", self.cmdExit),
                    "quit": ("Quit program", "local", self.cmdExit),
                   }
        if self.isRemote: # Additional commands
            commands["addhost"] = ("Add a new host machine", "network", self.cmdAddHost)
            commands["removehost"] = ("Remove host from known hosts", "network", self.cmdRemoveHost)
            commands['switchhost'] = ('Switch to another host', "network", self.cmdSwitchHost)
            commands['connect'] = ('Connect to remote Virtual Box', "network", self.cmdConnect)
            commands['disconnect'] = ('Disconnect from remote Virtual Box', "network", self.cmdDisconnect)
            commands['reconnect'] = ('Reconnects to a remote Virtual Box', "network", self.cmdReconnect)

        return commands  
                                       
    def progressBar(self, progress, update_time=1000):
        """
        Display progress bar for some commands.
        @param progress: IProgress object (from VirtualBox API)
        @param update_time: Time interval of progress update in miliseconds. Default value: 1000  
        """
        try:
            while not progress.completed:
                percent = progress.percent
                string = "[" + int(percent)/2 * "=" + ">]"
                spaceCount = (60 - len(string) - 3) # Calculate spaces for correct indentation
                print string + spaceCount * " " + str(percent) + "%\r", 
                sys.stdout.flush()
                progress.waitForCompletion(update_time)
            
            if int(progress.resultCode) != 0:
                print "Error while performing command"
                print str(progress.errorInfo.text)
        except KeyboardInterrupt:
            if progress.cancelable:
                print "Canceling..."
                progress.cancel()
            else:
                print "Cannot cancel current task"
        return 0

    def loadConfiguration(self, filename):
        """
        Load and parse configuration from config file.
        @param filename: Path to file, where the configuration is stored 
        """
        try:
            # Backup current state in case of error
            backupEnvs = copy.copy(self.envs)
            backupGroups = copy.copy(self.groups)
            lineNum = 0
            with open(filename, 'r') as conf_file:
                for line in conf_file:
                    lineNum += 1
                    if len(line) < 3 or line.startswith('#'): # Empty line or comment
                        continue
                    split = line.split()
                    if not len(split):
                        continue
                    params = {'host': None,
                              'name': None,
                              'group': None,
                              'user': None,
                              'port': None,
                              'password': None
                              }
                    type = split[0]
                    if type not in ['host', 'machine']:
                        print "Syntax error, line %d must start with keyword 'host' or 'machine', exiting"%lineNum
                        raise ValueError
                    # Parse parameters
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
                    # Configuring host
                    if type == 'host':
                        if params.get('group') is not None:
                            print "Cannot assign host to group, ignoring this parameter, line %d"%lineNum
                            raise ValueError
                        if params.get('name') is None:
                            print "Missing host name, line %d"%lineNum
                            raise ValueError
                        self.cmdAddHost([params.get('name'), params.get('port'), params.get('user'), params.get('password')])
                    else: # Configuring machine
                        if params.get('port'):
                            print "Cannot assign port to virtual machine, line %d"%lineNum
                            raise ValueError
                        if not len(params.get('host', "")):
                            print "Missing machine hostname, line %d"%lineNum
                            raise ValueError
                        
                        if params['group'] is not None:
                            if self.getGroup(params['group']) is None:
                                group = Group(params['group'])
                                self.groups[params['group']] = group
                            self.groups[params['group']].addMachine(params.get('host'), params.get('name'), params['user'], params['password'])
                        else:
                            try:
                                self.envs[params.get('host')].addMachine(params.get('name'), params.get('user'), params.get('password'))
                            except KeyError:
                                print "Host undefined, define it before registering a machine to it, line %d"%lineNum
                                raise ValueError                
        except IOError:
            print "Could not open or read configuration file"
        except (IndexError, ValueError): # Missing host or machine name
            print "Error while loading configuration on line %d, restoring the state before loading configuration file"%lineNum
            # Restore the original configuration
            self.clearConfiguration()
            self.envs = backupEnvs
            self.groups = backupGroups
        return

    def saveConfiguration(self, dest):
        """
        Save current configuration to destination file. If the file already exists
        it is overwritten.
        @param dest: Path to file, where the configuration will be stored 
        """        
        try:
            fp = open(dest, 'w')
        except IOError:
            print "Could not open file to save configuration"
            return
        # Save environments
        for env in self.envs.values():
            host = env.host
            port = env.port
            userstr = ("user=" + env.user) if env.user else ""
            passstr = ("password=" + env.password)  if env.password else ""
            fp.write("host name=%s port=%d %s %s\n"%(host, port, userstr, passstr))
            for machname, credentials in env.getMachines().items():
                userstr = ("user=" + credentials['user']) if credentials['user'] else ""
                passstr = ("password=" + credentials['password'])  if credentials['password'] else ""
                strline = "machine host=%s name=%s user=%s password=%s\n"%(host, machname, userstr, passstr)
                fp.write(strline)
        
        # Save groups
        for group in self.groups.values():
            for host, machines in group.getMachines().items():
                for machname, credentials in machines.items():
                    userstr = ("user=" + credentials['user']) if credentials['user'] else ""
                    passstr = ("password=" + credentials['password']) if credentials['password'] else ""
                    strline = "machine host=%s name=%s group=%s %s %s\n"%(host, machname, group.getName(), userstr, passstr)
                    fp.write(strline)
        fp.close()
        return
    
    def clearConfiguration(self):
        """
        Wipe out the current configuration.
        """
        self.envs = {}
        self.groups = {}
        return    
    
    def setActiveEnv(self, url):
        if url not in self.envs.keys():
            print "Environment does not exist"
            return 0
        self.active = self.envs[url]
    
    def log(self, message, close = False):
        self.logfile.write(datetime.now().strftime("%H:%M:%S") + " " + message + '\n')
        self.logfile.flush()
        if close:
            self.logfile.close()
                   
    """
    ############################################
    ############ Command section ###############
    ############################################
    """     
       
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
        """Print all existing groups and its machines"""
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
                    print 8 * " " + machname + " (" + username + ", " + password + ")"
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
        """Add a machine to group"""
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
            print "Adding to group"
            group.addMachine(hostname, machname, username, password)
        else:
            print "Adding to unexisting group, create one with creategroup command"
        return 0
    
    def cmdRemoveFromGroup(self, args):
        """Remove machine from group"""
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
    
    def cmdConnect(self, args):
        """ Connect to HTTP server """
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
        """ Reconnect to HTTP server """
        if len(args) > 1:
            print "Wrong arguments for reconnect command. Usage: reconneect <hostname>"
            return 0

        env = self.envs.get(args[0]) if len(args) > 0 else self.active
        try:
            url, user, password = env.url, env.user, env.password 
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
        """ Disconnect from HTTP server """
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
        """Print help for all commands"""
        for cmd, helpmsg in self.commands.items():
            print cmd
            print 4 * " " + helpmsg[0] 
        return 0

    def cmdCreateVM(self, args):
        if len(args) > 5:
            print "Wrong arguments for createvm. Usage: createvm [name] [ostype] [CPUs] [RAM] [DISK_SIZE]"
            return 0
        try:
            values = OrderedDict([('name', [args[0] if len(args) > 0 and len(args[0]) else None,'Name']),
                                  ('ostype', [args[1] if len(args) > 1 and len(args[1]) else None , 'OS Type']),
                                 ('cpus', [int(args[2]) if len(args) > 2 and len(args[2]) else None, 'CPU Count']),
                                 ('ram', [int(args[3]) if len(args) > 3 and len(args[3]) else None, 'RAM Size [MB]']),
                                 ('disksize', [int(args[4]) if len(args) > 4 and len(args[4]) else None, 'Disk Size [MB]'])
                                 ])
        except:
            print "Some of the arguments could not be properly converted"
            return 0

        if values.get('name')[0]:
            try:
                self.active.vbox.findMachine(values.get('name')[0])
            except Exception as e:
                pass # Machine does not exist -> OK
            else:
                print "Machine with given name already exists, please choose another name"
                return 0
        # Load parameters
        if self.autoMode:
            # Use some default values if not defined
            values['name'][0] = values['name'][0] if values['name'][0] else "VirtualMachine"
            values['ostype'][0] = values['name'][0] if values['ostype'][0] else "Ubuntu_64"
            values['cpus'][0] = values['name'][0] if values['cpus'][0] else 2
            values['ram'][0] = values['name'][0] if values['ram'][0] else 2048
            values['disksize'][0] = values['name'][0] if values['disksize'][0] else 32768
        
        else:
            for param, value in values.items():
                if value[0] is None:
                    while True:
                        if param == 'ostype':
                            inpstr = "Enter machine's %s, choose one of the following: RedHat RedHat_64 Ubuntu Ubuntu_64 Windows7 Windows7_64\nOSType: "%value[1]
                        else:
                            inpstr = "Enter machine's %s:"%value[1]
                        inp = raw_input(inpstr)
                        if not len(inp):
                            print "Missing value, if you wish to abort machine creation, enter Cancel or Quit"
                            continue
                        if inp.lower() in ['cancel', 'quit', 'exit', 'abort']:
                            print "Aborting VM creation"
                            return 0
                        
                        if param in ['cpus', 'ram', 'disksize']:
                            try:
                                values[param][0] = int(inp)
                                break
                            except:
                                print "Invalid value, must be a number"
                        elif (param == 'ostype' and inp not in ['RedHat', 'RedHat_64', 'Ubuntu',\
                                                            'Ubuntu_64', 'Windows7', 'Windows7_64']):
                            print "Invalid value, must be a valid OS Type"
                        else:
                            values[param][0] = inp
                            break
            
        mgr = self.active.mgr
        vbox = self.active.vbox
        const = self.active.const               
        print "Creating machine " + values.get('name')[0]
        mach = vbox.createMachine("", values.get('name')[0], [], values.get('ostype')[0], [1])    
        print "Creating hardrive"
        medium = vbox.createMedium('vmdk', r"C:\Users\mount_000\%s.vmdk"%values.get('name')[0], const.AccessMode_ReadWrite, const.DeviceType_HardDisk)
        print "Creating base storage"
        self.progressBar(medium.createBaseStorage(values.get('disksize')[0]*1024*1024, [const.MediumVariant_VmdkRawDisk]))
        print "Creating storage controller"
        #vbox.openMachine(values.get('name'))
        controller = mach.addStorageController('sata1', const.StorageBus_SATA)
        print "Registering machine"
        mach.saveSettings()
        vbox.registerMachine(mach)
        
        # Session is needed for modification of existing machine
        session = mgr.getSessionObject(vbox)
        try:
            mach.lockMachine(session, const.LockType_Write)
            mutable = session.machine # Get mutable instance of machine
            print "Setting RAM memory"
            mutable.setMemorySize(values.get('ram')[0])
            print "Setting CPUs"
            mutable.setCPUCount(values.get('cpus')[0])
            print "Attaching harddrive"
            mutable.attachDevice('sata1', 0, 0, const.DeviceType_HardDisk, medium)
            print "Finishing"
            mutable.saveSettings()            
        finally:
            session.unlockMachine()
        return 0

    def cmdRemoveVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for removevm. Usage: removevm <name>"
            return 0
        name = args[0]
        mgr = self.active.mgr
        vbox = self.active.vbox
        const = self.active.const
        
        machine = vbox.findMachine(name)
        session = mgr.getSessionObject(vbox)
        try:
            machine.lockMachine(session, const.LockType_Write)
            mutable = session.machine
            attachments = mgr.getArray(mutable, 'mediumAttachments')
            for attachment in attachments:
                mutable.detachDevice(attachment.controller, attachment.port, attachment.device)
            attachments = mgr.getArray(mutable, 'mediumAttachments')
            mutable.saveSettings()
        except:
            pass
        finally:
            session.unlockMachine()

        harddrives = machine.unregister(const.CleanupMode_Full)
        harddrives = list(harddrives)
        if machine:
            progress = machine.deleteConfig(harddrives)
            self.progressBar(progress)
        return 0            
    
    def cmdExit(self, args):
        return 1

    def cmdGcmd(self, args):
        """ Execute a command on machine and wait for it to end """
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
        try:
            guestSession = session.console.guest.createSession(user, password, '', '')
            guestSession.waitFor(1, 10000) # Wait for session to start
            proc = guestSession.processCreate(executable, guestargs, None, [5,6], 0)
        except Exception as e:
            print str(e)
        else:
            proc.waitFor(1, 10000) # Wait for process to start
            data = proc.read(1, 4096, 10000)
            print str(data)
            data = proc.read(2, 4096, 10000)
            print str(data)        
            print proc.waitFor(2, 10000) # Wait for terminate
            print proc.exitCode
        finally:
            session.unlockMachine()
        return 0
   
    def cmdGshell(self, args):
        """ Start interactive shell or command line on the machine """
        if len(args) != 1:
            print "Wrong arguments for guest. Usage: <machine_name|uuid>"
            return 0
        if self.autoMode:
            print "This command is not supported in auto mode"
            self.log("ERROR: Command 'gshell' is not supported in automatic mode")
            return 0
        machname = args[0]
        guestargs = args[1:]

        try:
            vbox = self.active.vbox
            const = self.active.const
            mach, session = self.lockSession(machname)
            #mach = vbox.findMachine(machname)
            #session = self.active.mgr.getSessionObject(vbox)
            
            #mach.lockMachine(session, self.active.const.LockType_Shared)
            user, password = self.getCredentials(machname)
            guestSession = session.console.guest.createSession(user, password, '', '')
            guestSession.waitFor(1, 10000) # Wait for session to start
        except Exception as e:
            print str(e)
        else:  
            pathstyle = guestSession.pathStyle # Distinguish guest OS (Linux or Windows)
            executable = r'C:\Windows\System32\cmd.exe' if pathstyle == const.PathStyle_DOS else r'/bin/sh'
            proc = guestSession.processCreate(executable, guestargs, None, [5, 6], 0)
            proc.waitFor(1, 10000) # Wait for process to start
            while True:
                data = proc.read(1, 10000, 10000) # Get data from stdout
                print str(data)
                if proc.status not in [const.ProcessStatus_Starting, const.ProcessStatus_Started]:
                    print "Exit code: " + str(proc.exitCode)
                    break
                inp = raw_input("cmd>")
                written = proc.write(0, 0, inp + '\n', 10000)  # Pass user input to guest process          
                data = proc.read(2, 10000, 10000) # Get data from stderr
                print str(data)
            
            proc.waitFor(2, 10000) # Wait for terminate
            guestSession.close()
        finally:
            session.unlockMachine()
        return 0
    
    def cmdCopyToMachine(self, args):
        print "This command is bugged in VirtualBox SDK 5.0.16, Bug #14336"
        return 0
        if len(args) < 3:
            print "Wrong arguments for copyto. Usage: copyto <machine> <src> <dst>"
            return 0
        machname = args[0]
        src = args[1]
        dst = args[2]
        try:
            machine, session = self.lockSession(machname)
            user, password = self.getCredentials(machname)
            guestSession = session.console.guest.createSession(user, password, '', '')
            guestSession.waitFor(1, 10000) # Wait for session to start
            if path.isfile(src):
                progress = guestSession.fileCopyToGuest(src, dst, [0])
            elif path.isdir(src):
                progress = guestSession.directoryCopyToGuest(src, dst, [0])
            else:
                print "Source does not exist on host machine"            
            self.progressBar(progress)
        except Exception as e:
            print str(e)            
        finally:
            session.unlockMachine()
        return 0
    
    def cmdCopyFromMachine(self, args):
        print "This command is bugged in VirtualBox SDK 5.0.16, Bug #14336"
        return 0
        if len(args) < 3:
            print "Wrong arguments for copyfrom. Usage: copyfrom <machine> <src> <dst>"
            return 0
        machname = args[0]
        src = args[1]
        dst = args[2]
        try:
            machine, session = self.lockSession(machname)
            user, password = self.getCredentials(machname)
            guestSession = session.console.guest.createSession(user, password, '', '')
            guestSession.waitFor(1, 10000) # Wait for session to start
            if guestSession.fileExists(src, False):
                progress = guestSession.fileCopyFromGuest(src, dst, [0])
            elif guestSession.directoryExists(src, False):
                progress = guestSession.directoryCopyFromGuest(src, dst, [0])
            else:
                print "Source does not exist on host machine"            
            self.progressBar(progress)
        except Exception as e:
            print str(e)            
        finally:
            session.unlockMachine()
        return 0

    def cmdBatch(self, args):
        """
        Execute a batch file
        """
        if len(args) != 1:
            print "Wrong arguments for batch. Usage: batch <file>"
            return 0
        try:
            fp = open(args[0], 'r')
            
            for line in fp:
                if not len(line) or line.startswith('#'): # Skip empty lines and comments
                    continue
                split = line.split(';') # There might be more commands on one line
                for command in split:
                    try:
                        retval = self.runCmd(command)
                        if retval:
                            break
                    except (KeyboardInterrupt, EOFError):
                        if self.autoMode:
                            self.log("INTERRUPT: Interrupted batch file while exucuting '%s' command"%command)                        
                    except Exception as e:
                        print ":'("
                        if self.autoMode:
                            self.log("ERROR: Error while executing '%s' command. Details: "%command + str(e))                        
                        print str(e)
        except IOError:
            print "Could not open batch file"
        finally:
            self.log("Batch %s finished"%args[0], True)
        print "Finishing batch"
        return 0
    
    def cmdSetRam(self, args):
        if len(args) != 2:
            print "Wrong arguments for setram. Usage: setram <machine> <memory_size_mb>"
            return 0
        
        machname = args[0]
        
        try:
            newsize = int(args[1])
            if newsize < 4 or newsize > 2097152: # Limits by VirtualBox
                print "Memory size must be in range <4; 2097152> MB" 
                return 0
        except ValueError:
            print "Memory size must be a number"
            return 0
        
        mgr = self.active.mgr
        vbox = self.active.vbox
        const = self.active.const
        
        mach = vbox.findMachine(machname)
        # Session is needed for modification of existing machine
        session = mgr.getSessionObject(vbox)
        try:
            print "Setting Memory size to " + str(newsize)
            mach.lockMachine(session, const.LockType_Write)
            mutable = session.machine # Get mutable instance of machine
            mutable.setMemorySize(newsize)
            mutable.saveSettings()            
        finally:
            session.unlockMachine()
        return 0
    
    def cmdSetCPU(self, args):
        if len(args) != 2:
            print "Wrong arguments for setcpus. Usage: setcpus <machine> <cpu_count>"
            return 0
        
        machname = args[0]
        
        try:
            newsize = int(args[1])
            if newsize < 1 or newsize > 32: # Limits byt VirtualBox
                print "CPU count size must be in range <1; 32>" 
                return 0
        except ValueError:
            print "CPU count must be a number"
            return 0
        
        mgr = self.active.mgr
        vbox = self.active.vbox
        const = self.active.const
        
        mach = vbox.findMachine(machname)
        # Session is needed for modification of existing machine
        session = mgr.getSessionObject(vbox)
        try:
            print "Setting CPU count to " + str(newsize)
            mach.lockMachine(session, const.LockType_Write)
            mutable = session.machine # Get mutable instance of machine
            mutable.setCPUCount(newsize)
            mutable.saveSettings()
        finally:
            session.unlockMachine()
        return 0
    
    def cmdLoad(self, args):
        if len(args) < 1:
            print "Wrong arguments for load. Usage: load <config_file>"
            return 0
        self.loadConfiguration(args[0])
        return 0

    def cmdSave(self, args):
        if len(args) < 1:
            print "Wrong arguments for save. Usage: save <config_file>"
            return 0
        self.saveConfiguration(args[0])
        return 0
    
    def cmdAddHost(self, args):
        if len(args) < 1 or len(args) > 5:
            print "Wrong arguments for addhost. Usage: addhost <hostname/ip> [port] [user] [password] [displayname]"
            return 0

        host = args[0]
        port = int(args[1]) if (len(args) > 1 and args[1] and len(args[1]) > 0) else 18083
        user = args[2] if len(args) > 2 else ""
        password = args[3] if len(args) > 3 else ""
        displayname = args[4] if (len(args) > 4 and args[4] and len(args[4]) > 0) else host
        url = "http://" + host + ":" + str(port) + '/'
        params = {'url': url,
                  'user': user,
                  'password': password}
        
        if host in self.envs.keys():
            print "Host already exists"
            return 0
                
        values = {'host': host,
                  'port': port,
                  'user': user,
                  'password': password,
                  'name': displayname,
                  'style': 'WEBSERVICE'
                  }
        try:
            self.envs[displayname] = Environment(values) # Create a new manager via webservice
        except:
            print "Could not connect to host " + host
        else:
            if self.active is None:
                print "This is the first known host (%s), setting it as active"%self.envs[host].getName()
                self.active = self.envs[host]
        print "Environments: %s"%str(self.envs.keys())
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
        print host
        print self.envs.keys()
        try:
            self.active = self.envs[host]
            self.cmdReconnect([host])
        except KeyError:
            print "Host does not exist"
        except:
            print "Could not switch to host, unable to connect"
        else:
            print "Host successfully switched to " + host
        return 0
    
    def cmdStartVM(self, args):
        if len(args) != 1:
            print "Wrong arguments for start. Usage: start <machine_name>"
            return 0
        name = args[0]
        mgr = self.active.mgr
        vbox = self.active.vbox
        
        machine = vbox.findMachine(name)
        session = mgr.getSessionObject(self.active.vbox)
        progress = machine.launchVMProcess(session, "gui", "")
        self.progressBar(progress, 1000)
        
        return 0
    
    def cmdExportVM(self,args):
        if len(args) < 2 or len(args) > 3:
            print "Wrong arguments for exportvm. Usage: exportvm <machine_name> <output_dir> [format]"
            return 0
        machname = args[0]
        expDir = args[1] 
        if len(args) == 3:
            format = args[2]
        else:
            format = "ovf-1.0"
        ext = "ova" if "ova" in format else "ovf"
        expPath = path.join(expDir, machname + "." + ext)  
        if not path.isdir(expDir):
            os.mkdir(expDir)
        vbox = self.active.vbox
        appliance = vbox.createAppliance()
        machine = vbox.findMachine(machname)
        desc = machine.exportTo(appliance, '')
        progress = appliance.write(format, None, expPath)
        self.progressBar(progress)
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
        appliance.interpret()
        progress = appliance.importMachines(None)
        self.progressBar(progress, 1000) 
        return 0
    
    def cmdList(self, args):
        for hostname, env in self.envs.items():
            for machname, credentials in env.getMachines().items():
                print 4*" " + "Machine: %s, User: %s, Password: %s"%(machname, credentials.get('user'), credentials.get('password'))
        return 0
    
    def cmdHost(self, args):
        if len(args) > 0:
            print "Wrong arguments for host. Usage: host"
            return 0
        vbox = self.active.vbox
        host = vbox.host
        print "VBoxWebSrv host:    " + str(self.active.host)
        print "VBoxWebSrv port:    " + str(self.active.port)
        print "VBoxWebSrv user:    " + (str(self.active.user) if len(self.active.user) else "No user")
        print "nameservers:        " + ("; ".join(str(ns) for ns in host.nameServers)) 
        print "CPU family:         " + str(host.getProcessorDescription(0))
        print "CPU physical cores: " + str(host.processorCoreCount)
        print "CPU logical cores:  " + str(host.processorCount)
        print "Operating system:   " + str(host.operatingSystem)
        print "OS version:         " + str(host.OSVersion)
        print "Memory size:        " + str(host.memorySize) + " MB"
        return 0
        
    def cmdListVms(self, args):
        if len(args) != 0:
            print "Wrong arguments for listvms. Usage: host"
            return 0
        vbox = self.active.vbox
        machines = self.active.mgr.getArray(vbox, 'machines')
        for mach in machines:
            print str(mach.name) + ", " + str(mach.OSTypeId)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--batch-file", dest="batch_file", help = "Batch file")
    parser.add_argument("-c", "--config-file", dest="config_file", help = "Configuration file")
    parser.add_argument("-w", "--webservice", dest="style", action="store_const", const="WEBSERVICE", help = "Use webservice")
    parser.add_argument("-o", "--opts", dest="opts", help="Additional command line parameters")
    args = parser.parse_args(sys.argv[1:])
    
    params = {'style' : args.style}
    if args.opts is not None:
        # Read optional arguments from cmdline
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
            params['host'] = params.get('host')
            params['port'] = params.get('port', 18083)
            params['user'] = params.get('user', "")
            params['password'] = params.get('password', "")
        else: 
            params['host'] = 'localhost'
        env = Environment(params)
    except EnvironmentError as e:
        print str(e) # print error
        sys.exit(1)
    
    interpreter = Interpreter(args.style)
    if (args.config_file):
        interpreter.loadConfiguration(args.config_file)
    if not interpreter.active and 'env' in locals():
        interpreter.addEnv(env)
        interpreter.setActiveEnv(env.getName())
    interpreter.run(args.batch_file)
    
    # Interpret finished
    for env in interpreter.envs.values():
        del env.mgr