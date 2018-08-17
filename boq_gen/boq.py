#!/usr/bin/pypy3
import os, sys
from time import gmtime, strftime
from boq_gen import BoQ_GEN

progArgs = sys.argv[1:len(sys.argv)]
try:
  argDict = dict(zip(*[iter(progArgs)]*2))
  fileDir = argDict['-dir']
except:
#  print(sys.exc_info()[0])
  print('Usage: ' + os.path.basename(__file__) + ' -dir <directory of excel files> -margin <0..100>') 
  print('Mandatory parameters:')
  print('\t-dir:\tThe directory contains hardware and vnf definition excel files.')
  print('\t\thardware excel should be put in "hw" subfolder,')
  print('\t\tvnf excel should be put in "vnf" subfolder,')
  print('Optional parameters:')
  print('\t-margin: The margin of dimension results in percentage.')
  print('\t\tThe value should be in the range of (0,100].')
  print('\t\tE.g. 90 means the 90% of dimension results will fullfill the VNF requirement.')
  print('\t\tdefault: 100')
  print('\t-accumulatedVdu: Whether the vdu count in vnf input file is accumulated number.')
  print('\t\tTrue - The total number of a VDU is not multiplied by the vnf_num')
  print('\t\tFalse - The total VDU number = vdu_num * vnf_num.')
  print('\t\tdefault: False')
  print('\t-ignore_cpupinning: Whether to ignore the value of cpupinning column of vnf input file')
  print('\t\tTrue - Ignored, i.e.regardless the input file, always treate it as True(the default value)')
  print('\t\tFalse - Interpret the value of this column')
  print('\t\tdefault: True. Since most of the HW supports CPU Pinning, and most of the VDU can run on CPU pinning enabled hardware, regardless if the VDU requires it or not')
  print('\t-ignore_sriov_dpdk: Whether to ignore the value of sriov_dpdk column of vnf input file')
  print('\t\tTrue - Ignored, i.e.regardless the input file, always treate it as True(the default value)')
  print('\t\tFalse - Interpret the value of this column')
  print('\t\tdefault: True. Since most of the HW supports either SR-IOV or DPDK, and most of the VDU can run on hardware with these feature enabled, regardless if the VDU requires it or not')  
  exit()

try:
  projName = argDict['-projName']
except:
  projName = None

try:
  bAccumulatedVdu = bool(argDict['-accumulatedVdu'])
except:
  bAccumulatedVdu = False

try:
  bIgnoreCpupinning = bool(argDict['-ignore_cpupinning'])
except:
  bIgnoreCpupinning = True

try:
  bIgnoreSriovDpdk = bool(argDict['-ignore_sriov_dpdk'])
except:
  bIgnoreSriovDpdk = True
  
try:
  margin = int(argDict['-margin'])/100
except:
  margin = 1

print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Loading excel files ...')
im = BoQ_GEN(fileDir,margin=margin)
im.loadData(bAccumulatedVdu=bAccumulatedVdu,bIgnoreCpupinning=bIgnoreCpupinning,bIgnoreSriovDpdk=bIgnoreSriovDpdk)
print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Calculating BoQ ...')
im.getVnfResourceSummary()
im.allocateNodes()
im.getBoq()
print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Saving BoQ ...')
im.saveBoq()
print('['+strftime("%Y-%m-%d %H:%M:%S", gmtime())+']'+' Completed.')
