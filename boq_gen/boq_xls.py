import math, json, os, re
from libXls import *
from copy import deepcopy

class BoQ_XLS(object):
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
    self.rowBgColorList = [None,'F0F0F0F0']
    self.thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    self.titleFgColor = 'FFFFFFFF'
    self.titleBgColor = '00000000'
    
  def loadWorkbook(self,filename=None,data_only=True):
    try:
      self.wb = openpyxl.load_workbook(filename, data_only=data_only)
    except:
      self.wb = None
    return self.wb
  
  def formatTitle(self,wsName,n=1):
    ws = self.wb[wsName]
    for col in range(1,ws.max_column+1):
      for r in range(1,n+1):
        cell = ws.cell(row=r,column=col)
        setCellBgColor(cell, self.titleBgColor)
        setCellFgColor(cell, self.titleFgColor)
        setCellAlignment(cell, horizontal='center', vertical='center')
  
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
  
  def save(self,fileName):
    try:
      assert self.wb is not None
      assert len(fileName) > 0
    except:
      return
    if len(self.wb.get_sheet_names()) > 0:
      try:
        os.makedirs(os.path.dirname(fileName))
      except:
        pass
      open(fileName,'w').close()
      self.wb.active = 0
      self.wb.save(fileName)
  
  @staticmethod
  def replaceSpecialChar(s,char='_'):
    p = re.compile('[^a-zA-Z\d]+')
    s = p.sub(char, s)
    s = s.strip(char)
    return s
  
    
class HW_XLS(BoQ_XLS):
  
  def __init__(self,filename=None,proj_name=None,data_only=True,margin=0.8):
    super(HW_XLS,self).__init__(filename,proj_name,data_only)
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
  
  def summarizeAdjComputeNodes(self):
    self.adjustedComputeNodes = {}
    for adjDev in self.adjustedDev['compute']:
      try:
        self.adjustedComputeNodes[adjDev['hyperthreading']]
      except:
        self.adjustedComputeNodes[adjDev['hyperthreading']] = {}
      try:
        self.adjustedComputeNodes[adjDev['hyperthreading']][adjDev['cpu_pinning']]
      except:
        self.adjustedComputeNodes[adjDev['hyperthreading']][adjDev['cpu_pinning']] = {}
      try:
        self.adjustedComputeNodes[adjDev['hyperthreading']][adjDev['cpu_pinning']][adjDev['dpdk'] or adjDev['sr_iov']]
      except:
        self.adjustedComputeNodes[adjDev['hyperthreading']][adjDev['cpu_pinning']][adjDev['dpdk'] or adjDev['sr_iov']] = []
      self.adjustedComputeNodes[adjDev['hyperthreading']][adjDev['cpu_pinning']][adjDev['dpdk'] or adjDev['sr_iov']].append(adjDev)

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
  
  def findComputeNodeByCond(self,cond=None):
    if cond is None:
      _cond = {}
    else:
      cond = deepcopy(cond)
    try:
      assert not _cond['hyperthreading']
    except:
      _cond['hyperthreading'] = True
    try:
      assert _cond['cpu_pinning']
    except:    # hyperthreading is a strict requirement
    # while cpu_pinning and sriov_dpdk is 'required' vs 'supported',
    # i.e. there two features, when not required, can be run on 'supported' node.
    # The only unmatch condition is 'required' with 'not supported'
    # We will give priority to those supported nodes

      _cond['cpu_pinning'] = False
    try:
      assert _cond['sriov_dpdk']
    except:
      _cond['sriov_dpdk'] = False
    for adjDev in self.adjustedDev['compute']:
      bMatch = True
      try:
        for k in ['hyperthreading','cpu_pinning','sriov_dpdk']:
          assert _cond[k] == adjDev[k]
      except:
        bMatch = False
      if bMatch:
        
        break

  @staticmethod
  def _getNodeBandwidth(dev):
    node_bandwidth = 0
    for ports in dev['network']:
      node_bandwidth += ports['capacity']*ports['quantity']
    return node_bandwidth
  @staticmethod
  def _getNodeStorage(dev):
    node_storage = 0
    for k in ['storage','ssd_storage']:
      try:
        node_storage += dev[k]
      except:
        pass
    return node_storage
                
    
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

class VNF_XLS(BoQ_XLS):
  def __init__(self,filename=None,proj_name=None,data_only=True):
    super(VNF_XLS,self).__init__(filename,proj_name,data_only)
    self.parsed = False
    
  def parse(self):
    self.parsed = True
    self.site = {}
    # Read site information
    for wsName in self.wb.get_sheet_names():
      if wsName == 'data' or wsName == 'guide': continue
      siteName = wsName
      self.site[siteName] = {}
      self.readTitle(siteName,n=2)
      row = 3
      while row <= self.wb[siteName].max_row:
        w = getRowSpan(self.wb[siteName]['A'+str(row)])
        for n in range(row,row+w):
          # Read VNF/VDU
          d = self.readRow(siteName,n)
          try:
            assert d['vnf_name'] != 'Total'
            d['vnf_name'] = BoQ_XLS.replaceSpecialChar(d['vnf_name'])
            d['vdu_name'] = BoQ_XLS.replaceSpecialChar(d['vdu_name'])
            assert len(d['vnf_name']) > 0
            assert len(d['vdu_name']) > 0
          except:
            continue
          
          # check scenarios
          dataBlk = {}
          for k in d:
            m = re.search('^(.+)-vnf_num$',k)
            if m is not None:
              scnName = m.group(1)
              dataBlk[scnName]= {'vnf_num':d[scnName+'-vnf_num'], 'vdu_num':d[scnName+'-vdu_num']}
          
          # record scenarios
          for scnName in dataBlk:
            try:
              self.site[siteName][scnName]
            except:
              self.site[siteName][scnName] = {}
            try:
              self.site[siteName][scnName][d['vnf_name']]
            except:
              try:
                vnf_num = int(dataBlk[scnName]['vnf_num'])
                assert vnf_num > 0
                self.site[siteName][scnName][d['vnf_name']] = {}
                self.site[siteName][scnName][d['vnf_name']]['quantity'] = vnf_num
                self.site[siteName][scnName][d['vnf_name']]['vdus'] = {}
              except:
                pass
            try:
              assert self.site[siteName][scnName][d['vnf_name']]['vdus'][d['vdu_name']]['quantity'] > 0
              self.parsed = False
              print('Error: Duplicated VDU definition in ',siteName,scnName,d['vdu_name'])
            except:
              try:
                vdu_num = int(dataBlk[scnName]['vdu_num'])
                assert vdu_num > 0
                self.site[siteName][scnName][d['vnf_name']]['vdus'][d['vdu_name']] = {}
                vduDict = self.site[siteName][scnName][d['vnf_name']]['vdus'][d['vdu_name']]
                vduDict['quantity'] = vdu_num
                # record VDU
                for k in ['vcpu','anti_affinity_limit']:
                  try:
                    vduDict[k] = int(d[k])
                    assert vduDict[k] > 0
                  except:
                    vduDict[k] = 1
                for k in ['memory','storage']:
                  try:
                    vduDict[k] = round(float(d[k]))
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
              except:
                pass 

        row += w
  def adjustInput(self,adjustDict):
    for siteName in self.site:
      for scnName in self.site[siteName]:
        for vnfName in self.site[siteName][scnName]:
          if adjustDict['bAccumulatedVdu']:
            try:
              assert self.site[siteName][scnName][vnfName]['quantity'] > 1
              self.site[siteName][scnName][vnfName]['quantity'] = 1
            except:
              pass
          for vduName in self.site[siteName][scnName][vnfName]['vdus']:
            vduDict = self.site[siteName][scnName][vnfName]['vdus'][vduName]
            if adjustDict['bIgnoreCpupinning']:
              vduDict['cpu_pinning'] = True
            if adjustDict['bIgnoreSriovDpdk']:
              vduDict['sriov_dpdk'] = True

  def computeReqSummary(self):
    req = {}
    self.vduSummary = {}
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']: req[k] = {}
    for site in self.site:
      self.vduSummary[site] = {}
      for scn in self.site[site]:
        self.vduSummary[site][scn] = {}
        for vnf in self.site[site][scn]:
          for vdu in self.site[site][scn][vnf]['vdus']:
            vduDict = self.site[site][scn][vnf]['vdus'][vdu]
            for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
              req[k][vduDict[k]] = 1
            try:
              self.vduSummary[site][scn][vduDict['hyperthreading']]
            except:
              self.vduSummary[site][scn][vduDict['hyperthreading']] = {}
            try:
              self.vduSummary[site][scn][vduDict['hyperthreading']][vduDict['cpu_pinning']]
            except:
              self.vduSummary[site][scn][vduDict['hyperthreading']][vduDict['cpu_pinning']] = {}
            try:
              self.vduSummary[site][scn][vduDict['hyperthreading']][vduDict['cpu_pinning']][vduDict['sriov_dpdk']]
            except:
              self.vduSummary[site][scn][vduDict['hyperthreading']][vduDict['cpu_pinning']][vduDict['sriov_dpdk']] = []
            _vduDict = deepcopy(vduDict)
            _vduDict['vdu_name'] = vdu
            _vduDict['vnf_name'] = vnf
            _vduDict['vnf_num'] = self.site[site][scn][vnf]['quantity']
            self.vduSummary[site][scn][vduDict['hyperthreading']][vduDict['cpu_pinning']][vduDict['sriov_dpdk']].append(_vduDict)
    ret = {}
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']: ret[k] = []
    for k in ['hyperthreading', 'cpu_pinning','sriov_dpdk']:
      for i in req[k]:
        ret[k].append(i)
    return ret
  
  def printSummary(self):
    print(json.dumps(self.site,indent=4))
    
class BOQ_SUMMARY_RESULT_XLS(BoQ_XLS):
  
  def __init__(self,proj_name=None,data_only=True):
    scriptDir = os.path.dirname(os.path.realpath(__file__))
    fileName = os.path.join(scriptDir,'template','boq_overview.xlsx')
    super(BOQ_SUMMARY_RESULT_XLS,self).__init__(fileName,proj_name,data_only)
    # Read the title line
    self.title['overview'] = self.readTitle('overview', 2)
    self.title['compute'] = self.readTitle('compute', 1)
    # Format the title lines
    self.formatTitle('overview', 2)
    self.formatTitle('compute', 1)
    
  def writeBoq(self,boqData):
    # Write the overview sheet first
    rowStart = 3
    r = 0
    for nSite,site in enumerate(boqData):
      for nScn,scn in enumerate(boqData[site]):
        line = {}
        for k in self.title['overview']:line[k] = 0
        if nScn == 0:
          line['site'] = site
        else:
          line['site'] = None
        line['scn'] = scn
        line['compute node'] = boqData[site][scn]['total']['compute'] 
        line['storage node'] = boqData[site][scn]['total']['storage']
        for compute in boqData[site][scn]['detail']['compute']:
          for k1 in ['vcpu','memory','storage','bandwidth']:
            if k1 == 'storage':
              k1_name = 'storage<compute node>'
            else:
              k1_name = k1
            for k2 in ['total','used']:
              k = '-'.join([k1_name,k2])
              line[k] += compute[k1][k2]
        for k1 in ['vcpu','memory','storage<compute node>','bandwidth']:
          try:
            line[k1+'-percent'] = line[k1+'-used'] / line[k1+'-total']
          except:
            pass
        line['storage<storage node>-total'] = boqData[site][scn]['detail']['storage']['total']
        try:
          line['storage<storage node>-used'] = boqData[site][scn]['detail']['storage']['used']
        except:
          line['storage<storage node>-used'] = 0
        try:
          line['storage<storage node>-percent'] = line['storage<storage node>-used'] / line['storage<storage node>-total']
        except:
          pass
        for k in ['max','average','idle']:
          line['-'.join(['power',k])] = boqData[site][scn]['detail']['power'][k]
        
        colorCode = self.rowBgColorList[r%2]
        for c,k in enumerate(self.title['overview'],1):
          cell = self.wb['overview'].cell(row=r+rowStart,column=c)
          cell.value = line[k]
          if colorCode is not None:
            setCellBgColor(cell,colorCode)
          if re.search('storage<.+>-((?!percent).)+',k) is not None:
            cell.value /= 1000
            cell.number_format = '0.00'
          elif re.search('-percent$',k) is not None:
            cell.number_format = '0.00%'
        r += 1

    # Write the compute sheet
    rowStart = 2
    r = 0
    for nSite,site in enumerate(boqData):
      for nScn,scn in enumerate(boqData[site]):
        self.wb['compute']
        colorCode = self.rowBgColorList[nScn%2]
        for nCompute,compute in enumerate(boqData[site][scn]['detail']['compute']):
          line = {}
          for k in self.title['compute']:line[k] = None
          if nCompute == 0:
            line['scn'] = scn
            if nScn == 0:
              line['site'] = site
          for k in ['hyperthreading', 'cpu_pinning', 'sriov_dpdk']:
            line[k] = compute[k]
          line['compute node'] = compute['quantity']
          for c,k in enumerate(self.title['compute'],1):          
            cell = self.wb['compute'].cell(row=r+rowStart,column=c)
            cell.value = line[k]
            if colorCode is not None:
              setCellBgColor(cell,colorCode)
          r += 1
              
class BOQ_COMPUTE_RESULT_XLS(BoQ_XLS):
  
  def __init__(self,proj_name=None,data_only=True):
    scriptDir = os.path.dirname(os.path.realpath(__file__))
    fileName = os.path.join(scriptDir,'template','boq_compute.xlsx')
    super(BOQ_COMPUTE_RESULT_XLS,self).__init__(fileName,proj_name,data_only)
    # Read the title line
    self.title['compute'] = self.readTitle('compute', 1)
    # Format the title lines
    self.formatTitle('compute', 1)
    self.FgColorCode = {'affinity':'00FF00','anti_affinity':'0000FF'}

  def writeDetail(self,summaryData):
    for nSite,site in enumerate(summaryData):
      for nScn,scn in enumerate(summaryData[site]):
        # make copies of the template sheet
        ws = self.wb.copy_worksheet(self.wb['compute'])
        ws.title = '-'.join([site,scn])
        # to record VNF allocation for each node
        rowStart = 2
        r = 0
        node_seq = 1
        for hyperthreading in summaryData[site][scn]:
          for cpu_pinning in summaryData[site][scn][hyperthreading]:
            for sriov_dpdk in summaryData[site][scn][hyperthreading][cpu_pinning]:
              d = summaryData[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              for node in d['compute_nodes']:
                node_sum = {}
                for k in self.title['compute']:node_sum[k] = None
                node_sum['vnf_name'] = 'Total'
                for k in ['vcpu','memory','storage','east_west_bandwidth','north_south_bandwidth']: node_sum[k] = 0
                for nVdu,vdu in enumerate(node['vdus']):
                  line = {}
                  for k in self.title['compute']:line[k] = None
                  for k in self.title['compute']:
                    try:
                      line[k] = vdu[k]
                    except:
                      pass
                  for k in ['vcpu','memory','storage','east_west_bandwidth','north_south_bandwidth']:
                    try:
                      node_sum[k] += line[k]
                    except:
                      pass
                  if nVdu == 0: line['node_seq'] = node_seq
                  BgColorCode = self.rowBgColorList[r%2]
                  if line['affinity']:
                    FgColorCode = self.FgColorCode['affinity']
                  elif line['anti_affinity']:
                    FgColorCode = self.FgColorCode['anti_affinity']
                  else:
                    FgColorCode = None
                  for c,k in enumerate(self.title['compute'],1):
                    cell = ws.cell(row=r+rowStart,column=c)
                    cell.value = line[k]
                    if BgColorCode is not None:
                      setCellBgColor(cell,BgColorCode)
                    if FgColorCode is not None:
                      setCellFgColor(cell, FgColorCode)
                  r += 1
                node_seq += 1
                BgColorCode = self.rowBgColorList[r%2]
                for c,k in enumerate(self.title['compute'],1):
                  cell = ws.cell(row=r+rowStart,column=c)
                  cell.value = node_sum[k]
                  if BgColorCode is not None:
                    setCellBgColor(cell,BgColorCode)
                  setCellFgColor(cell, '7F7F7F')
                r += 1
    self.wb.remove_sheet(self.wb['compute'])