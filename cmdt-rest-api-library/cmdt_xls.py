import math
from libXls import *
from copy import deepcopy

class CMDT_XLS(object):
  def __init__(self,filename=None,proj_name=None,data_only=True):
    if filename is None:
      self.wb = openpyxl.workbook.Workbook()
    else:
      try:
        self.wb = openpyxl.load_workbook(filename, data_only=data_only)
      except:
        self.wb = None
    if proj_name is None:
      self.proj_name = 'PROJ1'
    else:
      self.proj_name = proj_name
    self.title = {}
  
  def loadWorkbook(self,filename=None,data_only=True):
    try:
      self.wb = openpyxl.load_workbook(filename, data_only=data_only)
    except:
      self.wb = None
    return self.wb
  
  def readTitle(self,wsName,n=1):
    ret = []
    ws = self.wb[wsName]
    for col in range(1,ws.max_column+1):
      vd = []
      r = 1
      while r <= n:
        cell = ws.cell(row=r,column=col)
        v = getCellValueWithMergeLookup(cell)
        r += getRowSpan(cell)
        try:
          assert len(v) > 0
          vd.append(v)
        except:
          pass
      if len(vd) > 0:
        ret.append('-'.join(vd))
      else:
        break
    self.title[wsName] = ret
    return ret

  def readRow(self,wsName,rowNum):
    ret = {}
    title = self.title[wsName]
    for n,k in enumerate(title,1):
      try:
        ret[k] = getCellValueWithMergeLookup(self.wb[wsName].cell(row=rowNum,column=n))
        try:
          ret[k] = ret[k].strip()
        except:
          pass
        assert len(str(ret[k])) > 0
      except:
        ret[k] = None
    return ret
  
  @staticmethod
  def replaceSpecialChar(s,char='_'):
    p = re.compile('[^a-zA-Z\d]+')
    s = p.sub(char, s)
    s = s.strip(char)
    return s
  
    
class CMDT_HW_XLS(CMDT_XLS):
  
  def __init__(self,filename=None,proj_name=None,data_only=True,margin=0.8):
    super(CMDT_HW_XLS,self).__init__(filename,proj_name,data_only)
    self.margin = margin
    self.marginStr = 'margin'+"{0:.0f}%".format(margin * 100)
    self.parsed=False
  
  def parse(self):
    self.parsed=True
    self.infra_devices = {}
    self.adjust = {}
    # Read Infrastructure devices
    for wsName in ['compute','storage','network','rack']: self.infra_devices[wsName] = []
    for wsName in ['compute','storage','network','rack']:
      self.readTitle(wsName,n=2)
      for n in range(3,self.wb[wsName].max_row+1):
        d = self.readRow(wsName,n)
        if d['part_number'] is None: break
        self.infra_devices[wsName].append(d)
    # re-format the data of network/mgmt network, power and physical_dimensions
    for devs in self.infra_devices:
      for dev in self.infra_devices[devs]:
        keyToDel = []
        dNetwork = {'network':[],'mgmt_network':[]}
        dPower = {}
        dPhyDim = {}
        for k in dev:
          m = re.search('^(network|mgmt_network)-(\d+)gbps$',k)
          if m is not None:
            try:
              assert int(dev[k]) > 0
              dNetwork[m.group(1)].append({'capacity':int(m.group(2)),'quantity':int(dev[k])})
            except:
              pass
            keyToDel.append(k)
          else:
            m = re.search('^power-(\w+)$',k)
            if m is not None:
              dPower[m.group(1)] = dev[k]
              keyToDel.append(k)
            else:
              m = re.search('^physical_dimensions-(\w+)$',k)
              if m is not None:
                dPhyDim[m.group(1)] = dev[k]
                keyToDel.append(k)
        for k in dNetwork:
          if len(dNetwork[k]) > 0: dev[k] = dNetwork[k]
        if len(dPower) > 0: dev['power'] = dPower
        if len(dPhyDim) > 0: dev['physical_dimensions'] = dPhyDim
        for k in keyToDel: dev.pop(k,None)
    # re-format/sanity check the boolean value
    for dev in self.infra_devices['compute']:
      for k in ['cpu_pinning','sr_iov','dpdk','use_as_storage']:
        try:
          assert dev[k] == 'Y' or dev[k] == 'y'
          dev[k] = True
        except:
          dev[k] = False
      for k in ['hyperthreading',]:
        try:
          assert dev[k] == 'N' or dev[k] == 'n'
          dev[k] = False
        except:
          dev[k] = True
        
    # sanity check of compute/storage resources
    for devs in ['compute','storage']:
      for dev in self.infra_devices[devs]:
        for k in ['vcpu', 'memory', 'ssd_storage', 'storage']:
          try:
            assert dev[k] > 0
          except:
            dev[k] = 0
    # Read adjustment data
    for wsName in ['adj_compute','adj_storage']: self.adjust[wsName.strip('adj_')] = []
    for wsName in ['adj_compute','adj_storage']:
      self.readTitle(wsName,n=1)
      for n in range(2,self.wb[wsName].max_row+1):
        d = self.readRow(wsName,n)
        if d['part_number'] is None: break
        self.adjust[wsName.strip('adj_')].append(d)
  
  def genAdjDev(self,vnfComputeReq=None):
    # varDict shall specify the summary of compute node requirement from the vnf, i.e. hyperthreading, cpu pinning, sriov/dpdk
    self.adjustedDev = {'compute':[],'storage':[]}
    # if vnfComputeReq is None, just return as it is
    if vnfComputeReq is None:
      self.adjustedDev['storage'] = deepcopy(self.infra_devices['storage'])
      self.adjustedDev['compute'] = deepcopy(self.infra_devices['compute'])
      return
    # generate adjusted storage devs
    for dev in self.infra_devices['storage']:
      adjDev = deepcopy(dev)
      adj = self.findAdjByPn('storage',dev['part_number'])
      if adj is None:
        adj = self.findAdjByPn('storage','DEFAULT')
      if adj is None: continue
      self.adjustStorageOverhead(adjDev,ratio=adj['storage_factor']*self.margin)
      if adj['storage_type'] != 'DEFAULT':
        adjDev['side_names'] = [adj['storage_type'],]
      if self.margin != 1:
        adjDev['side_names'].append(self.marginStr)
      self.adjustedDev['storage'].append(adjDev)
    # generate compute devs
    for dev in self.infra_devices['compute']:
      adj = self.findAdjByPn('compute',dev['part_number'])
      if adj is None:
        adj = self.findAdjByPn('compute','DEFAULT')
      if adj is None: continue
      devVar = {'hyperthreading':[], 'cpu_pinning':[],'sriov_dpdk':[]}
      for kVnfReq in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
        for req in vnfComputeReq[kVnfReq]:
          if kVnfReq == 'hyperthreading':
            if req and not dev['hyperthreading']:
              continue
            else:
              devVar[kVnfReq].append(req)
          elif kVnfReq == 'cpu_pinning':
            if req and not dev['cpu_pinning']:
              continue
            else:
              devVar[kVnfReq].append(req)
          elif kVnfReq == 'sriov_dpdk':
            if req and not (dev['sr_iov'] or dev['dpdk']):
              continue
            else:
              if req:
                devVar[kVnfReq].append((dev['sr_iov'],dev['dpdk']))
              else:
                devVar[kVnfReq].append((False,False))
      for ht in devVar['hyperthreading']:
        for cpup in devVar['cpu_pinning']:
          for vio in devVar['sriov_dpdk']:
            adjDev = deepcopy(dev)
            adjDev['side_names'] = []
            if adj['cloud_type'] != 'DEFAULT':
              adjDev['side_names'].append(adj['cloud_type'])
            adjDev['hyperthreading'] = ht
            if dev['hyperthreading'] and not adjDev['hyperthreading']: adjDev['vcpu'] /= 2
            adjDev['cpu_pinning'] = cpup
            adjDev['sr_iov'] = vio[0]
            adjDev['dpdk'] = vio[1]
            if len(devVar['hyperthreading']) > 1 or ht != dev['hyperthreading']:
              adjDev['side_names'].append('HT' if ht else 'noHT')
            if len(devVar['cpu_pinning']) > 1 or cpup != dev['cpu_pinning']:
              adjDev['side_names'].append('CPUPIN' if cpup else 'noCPUPIN')
            if len(devVar['sriov_dpdk']) > 1 or vio[0] != dev['sr_iov'] or vio[1] != dev['dpdk']:
              adjDev['side_names'].append('SRIOVDPDK' if vio[0] or vio[1] else 'noSRIOVDPDK')
            adjDev['vcpu'] -= adj['vcpu']
            adjDev['memory'] -= adj['memory']
            self.adjustStorageOverhead(adjDev,adj['storage'])
            # adjust for storage
            if dev['use_as_storage']:
              adjStorage = self.findAdjByPn('storage',dev['part_number'])
              if adjStorage is None:
                adjStorage = self.findAdjByPn('storage','DEFAULT')
              if adjStorage is not None:
                self.adjustStorageOverhead(adjDev,ratio=adjStorage['storage_factor'])
                if adjStorage['storage_type'] != 'DEFAULT':
                  adjDev['side_names'].append(adjStorage['storage_type'])
            adjDev['vcpu'] = int(round(math.ceil(adjDev['vcpu']*self.margin)))
            adjDev['memory'] = int(round(math.ceil(adjDev['memory']*self.margin)))
            self.adjustStorageOverhead(adjDev,ratio=self.margin)
            if self.margin != 1:
              adjDev['side_names'].append(self.marginStr)
            self.adjustedDev['compute'].append(adjDev)
  
  def findInfraDevByPn(self,part_number):
    for devs in self.infra_devices:
      for dev in self.infra_devices[devs]:
        if dev['part_number'] == part_number:
          return dev
    return None
  
  def findAdjByPn(self,dev_type,part_number):
    for adj in self.adjust[dev_type]:
      if adj['part_number'] == part_number:
        return adj
    return None
    
  def adjustStorageOverhead(self, devDict, overhead=0, ratio=1):
    totalStorage = devDict['storage'] + devDict['ssd_storage']
    adjustedStorage = totalStorage - overhead
    if adjustedStorage > 0:
      r = 1.0*ratio*adjustedStorage/totalStorage
      for k in ('storage', 'ssd_storage'):
          devDict[k] = int(round(math.ceil(r * devDict[k])))
  
  def printSummary(self):
    # for debugging purpose
    print('--------adjusted devices--------')
    for i in self.adjustedDev:
      for dev in self.adjustedDev[i]:
        try:
          side_names = dev['side_names']
        except:
          side_names = None
        print(i, dev['part_number'],side_names, dev)

    print('--------baremetal devices--------')
    for i in self.infra_devices:
      for dev in self.infra_devices[i]:
          print(i, dev['part_number'], dev)

class CMDT_VNF_XLS(CMDT_XLS):
  def __init__(self,filename=None,proj_name=None,data_only=True,prepend_vnf=True):
    super(CMDT_VNF_XLS,self).__init__(filename,proj_name,data_only)
    # ATM, the VNF/VDU name is still global, so we need to prepend VNF and VDU to differentiate them.
    # VNF name would be projName+vnfName, VDU name would be projName+vnfName+vduName
    self.prepend_vnf=prepend_vnf
    self.parsed=False
    
  def parse(self):
    self.parsed=True
    self.vnf = {}
    self.site = {}
    self.vduChecker = {}
    # Read site information
    for wsName in self.wb.get_sheet_names():
      if wsName == 'data'  or wsName == 'guide': continue
      self.site[wsName] = {}
      self.readTitle(wsName,n=2)
      row = 3
      while row <= self.wb[wsName].max_row:
        w = getRowSpan(self.wb[wsName]['A'+str(row)])
        for n in range(row,row+w):
          d = self.readRow(wsName,n)
          try:
            assert d['vnf_name'] != 'Total'
            d['vnf_name'] = CMDT_XLS.replaceSpecialChar(d['vnf_name'])
            d['vdu_name'] = CMDT_XLS.replaceSpecialChar(d['vdu_name'])
            assert len(d['vnf_name']) > 0
            assert len(d['vdu_name']) > 0
            # This piece of code needs to be removed once VDU names is not global
            __vnf_name = '-'.join([self.proj_name,d['vnf_name']])
            __vdu_name = '-'.join([self.proj_name,d['vnf_name'],d['vdu_name']])
            try:
              self.vduChecker[__vdu_name]
              #print('Warning: VDU named',__vdu_name,'already exists')
              #print('\tDuplicates found at', wsName)
              self.parsed=False
            except:
              self.vduChecker[__vdu_name] = 1
            if self.prepend_vnf:
              d['vnf_name'] = __vnf_name
              d['vdu_name'] = __vdu_name
          except:
            continue
          # check scenarios
          dataBlk = {}
          for k in d:
            m = re.search('^(.+)-vnf_num$',k)
            if m is not None:
              scn = m.group(1)
              dataBlk[scn]= {'vnf_num':d[scn+'-vnf_num'], 'vdu_num':d[scn+'-vdu_num']}
          # record VNF
          try:
            self.vnf[d['vnf_name']]
          except:
            self.vnf[d['vnf_name']] = {}
          # record VDU
          vduDict = {}
          for k in ['vcpu','memory','storage','anti_affinity_limit']:
            try:
              vduDict[k] = int(d[k])
              assert vduDict[k] > 0
            except:
              vduDict[k] = 1
          for k in ['east_west_bandwidth','north_south_bandwidth']:
            try:
              vduDict[k] = float(d[k])
              assert vduDict[k] > 0
            except:
              vduDict[k] = 0.001
          for k in ['physical', 'affinity', 'anti_affinity']:
            try:
              assert d[k] == 'Y' or d[k] == 'y'
              vduDict[k] = True
            except:
              vduDict[k] = False
          for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
            try:
              assert d[k] == 'N' or d[k] == 'n'
              vduDict[k] = False
            except:
              vduDict[k] = True
          for k in ['affinity_type']:
            try:
              assert d[k] in ['core_affinity','cpu_affinity','hyperthreaded_affinity']
              vduDict[k] = d[k]
            except:
              vduDict[k] = 'core_affinity'
          
          try:
            self.vnf[d['vnf_name']][d['vdu_name']]
            if  self.vnf[d['vnf_name']][d['vdu_name']] != vduDict:
              print('****Warning: VDU named',__vdu_name,'already exists')
              print('\tConflict VDU definition found at', wsName)
              print('\tPrevious:',self.vnf[d['vnf_name']][d['vdu_name']])
              print('\tCurrent:',vduDict)
          except:
            pass
          
          self.vnf[d['vnf_name']][d['vdu_name']] = deepcopy(vduDict)
            
          # record scenarios
          for scn in dataBlk:
            try:
              self.site[wsName][scn]
            except:
              self.site[wsName][scn] = {}
            try:
              self.site[wsName][scn][d['vnf_name']]
            except:
              self.site[wsName][scn][d['vnf_name']] = {}
              try:
                self.site[wsName][scn][d['vnf_name']]['quantity'] = int(dataBlk[scn]['vnf_num'])
              except:
                pass
              self.site[wsName][scn][d['vnf_name']]['vdus'] = {}
            try:
              self.site[wsName][scn][d['vnf_name']]['vdus'][d['vdu_name']] = int(dataBlk[scn]['vdu_num'])
            except:
              pass
        row += w

  def computeReqSummary(self):
    req = {}
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']: req[k] = {}
    for vnf in self.vnf:
      for vdu in self.vnf[vnf]:
        for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
          try:
            req[k][self.vnf[vnf][vdu][k]] = 1
          except:
            pass
    ret = {}
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']: ret[k] = []
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
      for i in req[k]:
        ret[k].append(i)
    return ret
    