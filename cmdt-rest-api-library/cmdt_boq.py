#!/usr/bin/pypy3
import sys
from time import gmtime, strftime
from cmdt_import import *

progArgs = sys.argv[1:len(sys.argv)]
try:
  argDict = dict(zip(*[iter(progArgs)]*2))
  fileDir = argDict['-dir']
except:
#  print(sys.exc_info()[0])
  print('Usage: ' + os.path.basename(__file__) + ' -dir <directory of excel files> -projName <string> -margin <0..1>') 
  print('\t-cmdtServer <ip> -cmdtUser <username> -cmdtPassword <password>')
  print('\t-validate <True or False>')
  print('Mandatory parameters:')
  print('\t-dir:\tThe directory contains hardware and vnf definition excel files.')
  print('\t\thardware excel should be put in "hw" subfolder,')
  print('\t\tvnf excel should be put in "vnf" subfolder,')
  print('Optional parameters:')
  print('\t-projName: The name of the project which will be created in CMDT')
  print('\t\tdefault: the folder name of "-dir" parameter')
  print('\t-margin: The margin of dimension results in percentage.')
  print('\t\tThe value should be in the range of (0,100].')
  print('\t\tE.g. 91 means the 91% of dimension results will fullfill the VNF requirement.')
  print('\t\tdefault: 100')
  print('\t-cmdtServer, -cmdtUser, -cmdtPassword: login credential of CMDT Server.')
  print('\t\tdefault: cmdtServer="10.6.138.20", cmdtUsername="automation", cmdtPassword="automation"')
  print('\t-validate: If this value is set to True, then this tool will just check the excel files and')
  print('\t\tprint Error/Warning messages if applicable')
  print('\t\tdefault: False')
  exit()

try:
  projName = argDict['-projName']
except:
  projName = None
  
try:
  margin = int(argDict['-margin'])/100
except:
  margin = 1.0

try:
  cmdtServer = argDict['-cmdtServer']
except:
  cmdtServer = '10.6.138.20'

try:
  cmdtUser = argDict['-cmdtUser']
except:
  cmdtUser = 'automation'

try:
  cmdtPassword = argDict['-cmdtPassword']
except:
  cmdtPassword = 'automation'

try:
  validateOnly = bool(argDict['-validate'])
except:
  validateOnly = False

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Loading excel files...')
im = CMDT_IMPORT(fileDir,cmdtServer=cmdtServer,cmdtUser=cmdtUser,cmdtPassword=cmdtPassword,projName=projName,margin=margin)
im.loadData()

if validateOnly:
  print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Validating Completed.')
  exit()

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Creating HW models on CMDT Server ...')
im.cmdt.infraDevDelAll()
im.createInfraDevs()

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Creating VNF/VDU models on CMDT Server ...')
im.createVnfs()

time.sleep(2)

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Creating Sites on CMDT Server ...')
im.createSites()

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Completed.')