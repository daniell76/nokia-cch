import os, glob
from cmdt import *
from cmdt_xls import *

class CMDT_IMPORT(object):
  def __init__(self,fileDir=None,cmdtServer='192.168.122.127',cmdtUser='automation',cmdtPassword='automation',projName=None,margin=0.8,prepend_vnf=True):
    
    if fileDir is not None:
      if fileDir.endswith(('\\','/')):
        fileDir = fileDir[:-1]
    
    if projName is None:
      try:
        self.projName = os.path.basename(fileDir)
      except:
        self.projName = 'PROJ1'
    else:
      self.projName = projName
    
    try:
      self.hwXls = glob.glob(os.path.join(fileDir,'hw','*.xlsx'))[0]
    except:
      try:
        self.hwXls = glob.glob(os.path.join(fileDir,'hw','*.xls'))[0]
      except:
        self.hwXls = None
        print('Warning: hardware excel file is not defined. Please define it if needs to generate hardware module')
    self.hwWb = CMDT_HW_XLS(self.hwXls,proj_name=self.projName,margin=margin)
    
    try:
      self.vnfXls = glob.glob(os.path.join(fileDir,'vnf','*.xlsx'))[0]
    except:
      try:
        self.vnfXls = glob.glob(os.path.join(fileDir,'vnf','*.xls'))[0]
      except:
        self.vnfXls = None
        print('Warning: VNF/VDU excel file is not defined. Please define it if needs to generate VNF module')
    self.vnfWb = CMDT_VNF_XLS(self.vnfXls,proj_name=self.projName,prepend_vnf=prepend_vnf)
    
    self.cmdt = CMDT(server=cmdtServer,username=cmdtUser,password=cmdtPassword)
    self.cmdt.connect()
    
    try:
      assert self.cmdt.token is not None
    except:
      print('Warning: CMDT server is not connected. Please check the username/password, or network connectivity')
    
    assert self.hwWb is not None
    assert self.vnfWb is not None
    
    self.infraDevIds = {'compute':[],'storage':[],'network':[],'rack':[]}
  
  def loadData(self):
    self.hwWb.parse()
    self.vnfWb.parse()
    #assert self.hwWb.parsed
    #assert self.vnfWb.parsed
    vnfReq = self.vnfWb.computeReqSummary()
    self.hwWb.genAdjDev(vnfReq)
  
  def createInfraDevs(self):
    for k in ['compute','storage']:
      for dev in self.hwWb.adjustedDev[k]:
        devId = self.cmdt.infraDevImport(k,dev)
        if devId is not None:
          self.infraDevIds[k].append(devId)
    for k in ['network','rack']:
      for dev in self.hwWb.infra_devices[k]:
        devId = self.cmdt.infraDevImport(k,dev)
        if devId is not None:
          self.infraDevIds[k].append(devId)
        
  def createVnfs(self):
    for vnfName in self.vnfWb.vnf:        
      vduInfoList = []
      vduChanged = False
      for vduName in self.vnfWb.vnf[vnfName]:
        vduInfo = {}
        # Check if the VDU is already created
        vduFromCmdt = self.cmdt.devGetByName(display_name=vduName,devType='VDU')
        if vduFromCmdt is not None:
          vduId = vduFromCmdt['id']
          if self.cmdt.vduCompare(self.vnfWb.vnf[vnfName][vduName], vduFromCmdt):
            print('Warning: VDU '+vduName+' already exists, skipped')
          else:
            vduChanged = True
            print('Warning: VDU '+vduName+' already exists, update')
            newVduId = self.cmdt.vduCreate(vnfName,vduName,self.vnfWb.vnf[vnfName][vduName],isEdit=True)
            if newVduId is None:
              print('Warning: Failed to update VDU '+vduName)
            else:
              print('Information: VDU updated: '+vduName+'('+str(newVduId)+')')
              vduId = newVduId
        else:
          vduId = self.cmdt.vduCreate(vnfName,vduName,self.vnfWb.vnf[vnfName][vduName])
          if vduId is None:
            print('Warning: Failed to create VDU '+vduName)
            continue
          else:
            vduChanged = True
            print('Information: VDU created: '+vduName+'('+str(vduId)+')')
        vduInfo['id'] = vduId
        vduInfo['name'] = vduName
        for k in ['affinity','anti_affinity','anti_affinity_limit']:
          vduInfo[k] = self.vnfWb.vnf[vnfName][vduName][k]
        vduInfoList.append(vduInfo)
        sys.stdout.flush()
      
      # Check if the VNF already exists
      vnfFromCmdt = self.cmdt.devGetByName(display_name=vnfName,devType='VNF')
      if vnfFromCmdt is not None:
        vnfId = vnfFromCmdt['id']
        if self.cmdt.vnfCompare(self.vnfWb.vnf[vnfName], vnfFromCmdt) and (not vduChanged):
          print('Warning: VNF '+vnfName+' already exists, skipped')
          continue
        else:
          print('Warning: VNF '+vnfName+' already exists, update')
          vnfId = self.cmdt.vnfCreate(self.projName,vnfName,vduInfoList,isEdit=True)
      else:
        if len(vduInfoList) == 0:
          print('Warning: Failed to create VNF '+vnfName+'. No VDU defined')
          continue
        vnfId = self.cmdt.vnfCreate(self.projName,vnfName,vduInfoList)
      if vnfId is None:
        print('Warning: Failed to create/update VNF '+vnfName)
        continue
      else:
        print('Information: VNF created/updated: '+vnfName+'('+str(vnfId)+')')
        
      sys.stdout.flush()
  
  def createSites(self):
    # Create Project
    projId = self.cmdt.projGetByName(self.projName)
    if projId is None:
      projId = self.cmdt.projCreate(self.projName)
    else:
      print('Warning: Project '+self.projName+' already exists, adding sites to existing project')
    # Create sites and scenarios
    for siteName in self.vnfWb.site:
      # Check if the site already exists
      siteId = self.cmdt.siteIdGetByName(projId, siteName)
      if siteId is None:
        siteId = self.cmdt.siteCreate(projId, siteName)
      else:
        print('Warning: Site '+siteName+' already exists, resetting the site')
        self.cmdt.siteClear(siteId)
      # Add VNF to site
      vnfNameExist = {}
      for scnName in self.vnfWb.site[siteName]:
        for vnfName in self.vnfWb.site[siteName][scnName]:
          vnfNameExist[vnfName] = 1
      self.cmdt.siteVnfAdd(siteId, vnfNameExist.keys())
      if not self.cmdt.siteValidate(siteId):
        print('Error: Failed to validate site '+siteName)
        continue
      for scnName in self.vnfWb.site[siteName]:
        # Check if the scenario already exists
        scnId = self.cmdt.scnIdGetByName(siteId, scnName)
        if scnId is None:
          scnId = self.cmdt.scnCreate(siteId, scnName)
        else:
          print('Warning: Scenario '+scnName+' already exists, resetting the scenario')
          self.cmdt.scnClear(siteId, scnId)
        # Create racks
        res = self.cmdt.scnRackCreate(siteId, scnId, self.infraDevIds)
        #print json.dumps(res,indent=4)
        # set up scenario VDU info
        res = self.cmdt.scnVduLevelSet(siteId, scnId, self.vnfWb.site[siteName][scnName])
        #print json.dumps(res,indent=4)
        # Calculate results
        result = self.cmdt.scnResultCalc(siteId, scnId)
        #print json.dumps(result,indent=4)
        # Save BoQ
        self.cmdt.boqSave(siteId, scnId, result)
    
    