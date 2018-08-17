#!/usr/bin/pypy3
import sys
from cmdt_import import *

progArgs = sys.argv[1:len(sys.argv)]
try:
  argDict = dict(zip(*[iter(progArgs)]*2))
  projName = argDict['-projName']
except:
#  print(sys.exc_info()[0])
  print('Usage: ' + os.path.basename(__file__) + ' -projName <string> -cmdtServer <ip> -cmdtUser <username> -cmdtPassword <password>')
  print('Mandatory parameters:')
  print('\t-projName: The name of the project need to be removed from CMDT')
  print('Optional parameters:')
  print('\t-cmdtServer, -cmdtUser, -cmdtPassword: login credential of CMDT Server.')
  print('\t\tdefault: cmdtServer="10.6.138.20", cmdtUsername="automation", cmdtPassword="automation"')
  exit()

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

cmdt = CMDT(server=cmdtServer,username=cmdtUser,password=cmdtPassword)
cmdt.connect()
projId = cmdt.projGetByName(projName)
cmdt.projDel(projId)
cmdt.vnfDelBySubCategory(projName)
cmdt.boqDelByProjName(projName)
