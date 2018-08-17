import os, glob,math
from boq_xls import *

class BoQ_GEN(object):
  def __init__(self,fileDir=None,projName=None,margin=0.9):
    
    if fileDir is not None:
      if fileDir.endswith(('\\','/')):
        fileDir = fileDir[:-1]

    self.inputFileDir = fileDir
    
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
    self.hwWb = HW_XLS(self.hwXls,proj_name=self.projName,margin=margin)
    
    try:
      self.vnfXls = glob.glob(os.path.join(fileDir,'vnf','*.xlsx'))[0]
    except:
      try:
        self.vnfXls = glob.glob(os.path.join(fileDir,'vnf','*.xls'))[0]
      except:
        self.vnfXls = None
        print('Warning: VNF/VDU excel file is not defined. Please define it if needs to generate VNF module')
    self.vnfWb = VNF_XLS(self.vnfXls,proj_name=self.projName)
    
    assert self.hwWb is not None
    assert self.vnfWb is not None
    
    self.infraDevIds = {'compute':[],'storage':[],'network':[],'rack':[]}
  
  def loadData(self,bAccumulatedVdu=False,bIgnoreCpupinning=True,bIgnoreSriovDpdk=True):
    self.hwWb.parse()
    self.vnfWb.parse()
    d = {'bAccumulatedVdu': bAccumulatedVdu,'bIgnoreCpupinning': bIgnoreCpupinning,'bIgnoreSriovDpdk':bIgnoreSriovDpdk}
    self.vnfWb.adjustInput(d)
    #assert self.hwWb.parsed
    #assert self.vnfWb.parsed
    vnfReq = self.vnfWb.computeReqSummary()
    self.hwWb.genAdjDev(vnfReq)
    self.hwWb.summarizeAdjComputeNodes()
  
  
  def getVnfResourceSummary(self):
    self.summary = {}
    self.storageSummary = {}
    for site in self.vnfWb.vduSummary:
      self.summary[site] = {}
      self.storageSummary[site] = {}
      for scn in self.vnfWb.vduSummary[site]:
        self.summary[site][scn] = {}
        self.storageSummary[site][scn] = {'storage':0}
        for hyperthreading in self.vnfWb.vduSummary[site][scn]:
          self.summary[site][scn][hyperthreading] = {}
          for cpu_pinning in self.vnfWb.vduSummary[site][scn][hyperthreading]:
            self.summary[site][scn][hyperthreading][cpu_pinning] = {}
            for sriov_dpdk in self.vnfWb.vduSummary[site][scn][hyperthreading][cpu_pinning]:
              self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk] = {'vcpu':0,'memory':0,'storage':0,'east_west_bandwidth':0,'north_south_bandwidth':0}
              d = self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              for vduDict in self.vnfWb.vduSummary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]:
                for k in ['vcpu','memory','storage','east_west_bandwidth','north_south_bandwidth']: d[k] += vduDict[k]
              self.storageSummary[site][scn]['storage'] += d['storage']
  
  def allocateNodes(self):
    storageDev = None
    try:
      storageDev = self.hwWb.adjustedDev['storage'][0]
    except:
      pass
    for site in self.summary:
      for scn in self.summary[site]:
        if storageDev is not None:
          s = self.storageSummary[site][scn]
          s['storage_nodes'] = []
        for hyperthreading in self.summary[site][scn]:
          for cpu_pinning in self.summary[site][scn][hyperthreading]:
            for sriov_dpdk in self.summary[site][scn][hyperthreading][cpu_pinning]:
              d = self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              vduList = self.vnfWb.vduSummary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              # just use the 1st one in the list
              dev = self.hwWb.adjustedComputeNodes[hyperthreading][cpu_pinning][sriov_dpdk][0]
              # calculate the total bandwidth and storage available on the node
              node_bandwidth = HW_XLS._getNodeBandwidth(dev)
              node_storage = HW_XLS._getNodeStorage(dev)
              # Estimate how many nodes required, as if no affinity/anti-affinity requirement 
              c = []
              for k in ['vcpu','memory']:
                c.append(math.ceil(d[k]/dev[k]))
              c.append(math.ceil( (d['east_west_bandwidth']+d['north_south_bandwidth'])/node_bandwidth))
              # Record the adjusted node capacity and bare metal capacity
              d['adj_dev'] = dev
              d['bm_dev'] = self.hwWb.findInfraDevByPn(dev['part_number'])
              # Create the estimated compute nodes
              d['compute_nodes'] = []
              for i in range(max(c)):
                node = {'available':{},'vdus':[]}
                for k in ['vcpu','memory']: node['available'][k] = dev[k]
                node['available']['storage'] = node_storage
                node['available']['bandwidth'] = node_bandwidth
                d['compute_nodes'].append(node)
              # Now we start to allocate each VDU to compute nodes
              # Sanity check first: a empty node shall be able to contain at least 1 VDU, otherwise we bail out
              try:
                for vdu in vduList:
                  for k in ['vcpu','memory']:
                    assert dev[k] >= vdu[k]
                  assert node_bandwidth >= vdu['east_west_bandwidth'] + vdu['north_south_bandwidth']
                  if storageDev is not None:
                    assert HW_XLS._getNodeStorage(storageDev) >= vdu['storage']
              except:
                print(site,scn,vdu['vnf_name'],vdu['vdu_name'],' is too big to fit one node.')
                raise
              
              # category vdus
              affinityVduList = []
              antiaffinityVduList = []
              regularVduList = []
              for vdu in vduList:
                if vdu['affinity']:
                  affinityVduList.append(vdu)
                elif vdu['anti_affinity']:
                  antiaffinityVduList.append(vdu)
                else:
                  regularVduList.append(vdu)
              affinityVduList.sort(key=lambda vdu: vdu['vnf_num']*vdu['quantity']*vdu['vcpu'], reverse=True)
              antiaffinityVduList.sort(key=lambda vdu: vdu['vnf_num']*vdu['quantity'], reverse=True)
              regularVduList.sort(key=lambda vdu: vdu['vnf_num']*vdu['quantity']*vdu['vcpu'], reverse=True)
              
              # Firstly, allocate VDUs requiring Affinity
              # We will try to squeeze them on the same node, or as much as possible
              for vdu in affinityVduList:
                while True:
                  allocated_results = BoQ_GEN._allocateVduCompute(vdu, d['compute_nodes'])
                  if allocated_results is not None: break
                  d['compute_nodes'].append(BoQ_GEN._createAllocatedComputeNode(dev))
                if len(allocated_results) > 1:
                  tmp_node = BoQ_GEN._createAllocatedComputeNode(dev)
                  tmp_results = BoQ_GEN._allocateVduCompute(vdu, [tmp_node])
                  if tmp_results is None:
                    # seems one node is not enough for all the VDUs
                    # report a warning
                    print('Warning: Affinity requirement of '+'.'.join([site,scn,vdu['vnf_name'],vdu['vdu_name']])+' cannot be met')
                  else:
                    allocated_results = tmp_results
                    allocated_results[0]['node_seq'] = len(d['compute_nodes'])
                    d['compute_nodes'].append(tmp_node)
                # If there is storage node, give them priority
                if storageDev is None:
                  BoQ_GEN._recordVduCompute(vdu,d,allocated_results,ignoreStorage=False)
                else:
                  BoQ_GEN._recordVduCompute(vdu,d,allocated_results)
                  while True:
                    storage_allocated_results = BoQ_GEN._allocateVduStorage(vdu, s['storage_nodes'])
                    if storage_allocated_results is not None: break
                    s['storage_nodes'].append(BoQ_GEN._createAllocatedStorageNode(storageDev))
                  BoQ_GEN._recordVduStorage(vdu, s, storage_allocated_results)
              
              # Then we allocate VDUs requires anti-affinity
              for vdu in antiaffinityVduList:
                _vdu = deepcopy(vdu)
                _vdu['vnf_num'] = 1
                _vdu['quantity'] = 1
                startIdx = 0
                lastAllocatedIdx = -1
                allocatedNumber = 0
                limit = vdu['anti_affinity_limit']
                # allocate 1 VDU at a time
                for vnf_seq in range(vdu['vnf_num']):
                  for vdu_seq in range(vdu['quantity']):
                    while True:
                      allocated_results = BoQ_GEN._allocateVduCompute(_vdu, d['compute_nodes'][startIdx:])
                      if allocated_results is not None: break
                      d['compute_nodes'].append(BoQ_GEN._createAllocatedComputeNode(dev))
                    #print(startIdx,vdu['vnf_name'],vnf_seq,vdu['vdu_name'],vdu_seq,allocated_results)
                    allocated_results[0]['node_seq'] += startIdx
                    if allocated_results[0]['node_seq'] == lastAllocatedIdx:
                      # node didn't change, check the anti-affinity limit
                      allocatedNumber += 1
                    else:
                      lastAllocatedIdx = allocated_results[0]['node_seq']
                      allocatedNumber = 1
                    if allocatedNumber >= limit:
                      startIdx = allocated_results[0]['node_seq'] + 1
                    
                    # If there is storage node, give them priority
                    if storageDev is None:
                      allocatedVdu = BoQ_GEN._recordVduCompute(_vdu,d,allocated_results,ignoreStorage=False)[0]
                      # We need to adjust the vnf and vdu sequence number
                      allocatedVdu['vnf_seq'] = vnf_seq
                      allocatedVdu['vdu_seq'] = vdu_seq
                    else:
                      allocatedVdu = BoQ_GEN._recordVduCompute(_vdu,d,allocated_results)[0]
                      allocatedVdu['vnf_seq'] = vnf_seq
                      allocatedVdu['vdu_seq'] = vdu_seq
                      while True:
                        storage_allocated_results = BoQ_GEN._allocateVduStorage(_vdu, s['storage_nodes'])
                        if storage_allocated_results is not None: break
                        s['storage_nodes'].append(BoQ_GEN._createAllocatedStorageNode(storageDev))
                      allocatedVdu = BoQ_GEN._recordVduStorage(vdu, s, storage_allocated_results)[0]
                      allocatedVdu['vnf_seq'] = vnf_seq
                      allocatedVdu['vdu_seq'] = vdu_seq
                #print(site,scn,len(s['storage_nodes']))
                    
              # Then to allocate VDUs doesn't have special requirements
              for vdu in vduList:
                if vdu['affinity'] or vdu['anti_affinity']: continue
                while True:
                  allocated_results = BoQ_GEN._allocateVduCompute(vdu, d['compute_nodes'])
                  if allocated_results is not None: break
                  d['compute_nodes'].append(BoQ_GEN._createAllocatedComputeNode(dev))
                # If there is storage node, give them priority
                if storageDev is None:
                  BoQ_GEN._recordVduCompute(vdu,d,allocated_results,ignoreStorage=False)
                else:
                  BoQ_GEN._recordVduCompute(vdu,d,allocated_results)
                  while True:
                    storage_allocated_results = BoQ_GEN._allocateVduStorage(vdu, s['storage_nodes'])
                    if storage_allocated_results is not None: break
                    s['storage_nodes'].append(BoQ_GEN._createAllocatedStorageNode(storageDev))
                    #print(len(s['storage_nodes']))
                  BoQ_GEN._recordVduStorage(vdu, s, storage_allocated_results)
                #print(site,scn,len(s['storage_nodes']))
    # Format of allocated vdu:
    # vcpu:
    # memory:
    # storage:
    # east_west_bandwidth:
    # north_south_bandwidth:
    # vnf_name:
    # vnf_seq: (start from 0, name scope is within site/year)
    # vdu_name:
    # vdu_seq: (start from 0, name scope is within site/year/vnf)

  def getBoq(self):
    self.boq = {}
    for site in self.summary:
      self.boq[site] = {}
      for scn in self.summary[site]:
        self.boq[site][scn] = {'total':{'compute':0,'storage':0},'detail':{'compute':[],'storage':{}}}
        try:
          self.boq[site][scn]['total']['storage'] += len(self.storageSummary[site][scn]['storage_nodes'])
        except:
          pass
        #print(site,scn,self.storageSummary[site][scn]['storage_nodes'])
        for hyperthreading in self.summary[site][scn]:
          for cpu_pinning in self.summary[site][scn][hyperthreading]:
            for sriov_dpdk in self.summary[site][scn][hyperthreading][cpu_pinning]:
              d = self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              self.boq[site][scn]['total']['compute'] += len(d['compute_nodes'])
              compute = {}
              compute['hyperthreading'] = hyperthreading
              compute['cpu_pinning'] = cpu_pinning
              compute['sriov_dpdk'] = sriov_dpdk
              compute['quantity'] = len(d['compute_nodes'])
              for k in ['vcpu','memory','storage','bandwidth']: compute[k] = {'available':0,'used':0}
              compute['power'] = {}
              for k in ['max','average','idle']: compute['power'][k] = compute['quantity'] * d['bm_dev']['power'][k]
              for k in ['vcpu','memory']: compute[k]['total'] = compute['quantity'] * d['bm_dev'][k]
              if d['bm_dev']['hyperthreading'] and (not hyperthreading): compute['vcpu']['total'] /= 2
              compute['storage']['total'] = compute['quantity'] * HW_XLS._getNodeStorage(d['bm_dev'])
              adjusted_compute_storage = HW_XLS._getNodeStorage(d['adj_dev'])
              compute['bandwidth']['total'] = compute['quantity'] * HW_XLS._getNodeBandwidth(d['bm_dev'])
              for node in d['compute_nodes']:
                for k in ['vcpu','memory']:
                  compute[k]['available'] += node['available'][k]
                  compute[k]['used'] += d['adj_dev'][k] - node['available'][k]
                compute['bandwidth']['available'] += node['available']['bandwidth']
                compute['bandwidth']['used'] += HW_XLS._getNodeBandwidth(d['adj_dev']) - node['available']['bandwidth']
                compute['storage']['used'] += adjusted_compute_storage - node['available']['storage']
#              for k in ['vcpu','memory','bandwidth']: compute[k]['used'] = compute[k]['total'] - compute[k]['available']
              self.boq[site][scn]['detail']['compute'].append(compute)
        # Calculate the power
        adjusted_dev = self.hwWb.adjustedDev['compute'][0]
        bm_dev = self.hwWb.findInfraDevByPn(adjusted_dev['part_number'])
        self.boq[site][scn]['detail']['power'] = {'max':0,'average':0,'idle':0}
        for k in ['max','average','idle']:
          self.boq[site][scn]['detail']['power'][k] += self.boq[site][scn]['total']['compute'] * bm_dev['power'][k] 
        try:
          adjusted_storage_dev = self.hwWb.adjustedDev['storage'][0]
          bm_storage_dev = self.hwWb.findInfraDevByPn(adjusted_storage_dev['part_number'])
          self.boq[site][scn]['detail']['storage']['total'] = self.boq[site][scn]['total']['storage'] * HW_XLS._getNodeStorage(bm_storage_dev)
          total_storage = self.boq[site][scn]['total']['storage'] * HW_XLS._getNodeStorage(adjusted_storage_dev)
          total_available_storage = 0
          for storage in self.storageSummary[site][scn]['storage_nodes']:
            total_available_storage += storage['available']['storage']
          self.boq[site][scn]['detail']['storage']['used'] = total_storage - total_available_storage
          for k in ['max','average','idle']:
            self.boq[site][scn]['detail']['power'][k] += self.boq[site][scn]['total']['storage'] * bm_storage_dev['power'][k]
        except:
          pass 
  
  def saveBoq(self):
    overviewXls = BOQ_SUMMARY_RESULT_XLS()
    overviewXls.writeBoq(self.boq)
    fileName = os.path.join(self.inputFileDir,'boq','boq_overview.xlsx')
    overviewXls.save(fileName)
    computeXls = BOQ_COMPUTE_RESULT_XLS()
    computeXls.writeDetail(self.summary)
    fileName = os.path.join(self.inputFileDir,'boq','boq_compute.xlsx')
    computeXls.save(fileName)
    
  def printBoq(self):
    print()
    for site in self.boq:
      print('******** '+site+' ********')
      for scn in self.boq[site]:
        print('  ======== scn: '+scn+' ========')
        print('  *Compute Nodes:',self.boq[site][scn]['total']['compute'],'*Storage Nodes: ',self.boq[site][scn]['total']['storage'])
        print('  |---> Compute Node Details:')
        for compute in self.boq[site][scn]['detail']['compute']:
          print('        *Quantity:',compute['quantity'],'*hyperthreading:',compute['hyperthreading'],'*cpu_pinning:',compute['cpu_pinning'],'*sriov_dpdk:',compute['sriov_dpdk'])

  # Try to allocate vcpu, memory, and bandwidth to the available nodes
  # This method will not change any content, just to find whether we can fit the VDU
  
  @ staticmethod
  def _allocateVduCompute(vdu,devList):
    #print('--------allocate vdu')
    #print('vdu=',vdu['vdu_name'],vdu['quantity'])
    #print('devList=',devList)
    #print()
    ret = None
    try:
      assert vdu is not None
      assert len(devList) > 0
    except:
      return ret
    
    # Firstly, try to put all the VDUs in the same node    
    meet = []
    candidate = []

    # Calculate the total required resources
    required = {}
    for k in ['vcpu','memory','storage']:
      required[k] = vdu['vnf_num'] * vdu['quantity'] * vdu[k]
    required['bandwidth'] = vdu['vnf_num'] * vdu['quantity'] * (vdu['east_west_bandwidth'] + vdu['north_south_bandwidth'])
    
    # Allocate vcpu and memory first
    # Try to put all of them on the same node, if possible
    for n,dev in enumerate(devList):
      # To see if we can put them in the same node
      #print('dev[available]=',dev['available'])
      try:
        for k in ['vcpu','memory','bandwidth']:
          assert dev['available'][k] >= required[k]
        # yes this node can hold all the VDUs, in terms of vcpu, memory and bandwidth
        meet.append({'node_seq':n,'vdu_num':vdu['vnf_num']*vdu['quantity']})
        # If the node can hold all the storage as well, that will be perfect, we don't need to search any more
        if dev['available']['storage'] >= required['storage']:
          meet = [{'node_seq':n,'vdu_num':vdu['vnf_num']*vdu['quantity']}]
          break
      except:
        # so this node does not have enough resources to hold all the VDUs
        # If we already have meet node, then don't bother to record this node
        if len(meet) > 0: continue
        c = []
        for k in ['vcpu','memory']:
          c.append(math.floor(dev['available'][k]/vdu[k]))
        c.append(math.floor(dev['available']['bandwidth']/(vdu['east_west_bandwidth']+vdu['north_south_bandwidth'])))
        if min(c) > 0:
          candidate.append({'node_seq':n,'vdu_num':min(c)})
      
    # If there is a node can fit all the VDUs, then we return one of the node
    #print('required=',required,'meet=',meet)
    if len(meet) > 0:
      ret = meet[:1]
    elif len(candidate) > 0:
      # We will try to allocate the VDUs to as few as possible nodes
      candidate.sort(key=lambda x: x['vdu_num'], reverse=True)
      vdu_num = vdu['vnf_num'] * vdu['quantity']
      ret = []
      for node in candidate:
        if vdu_num > node['vdu_num']:
          vdu_num -= node['vdu_num']
          ret.append(node)
        else:
          node['vdu_num'] = vdu_num
          ret.append(node)
          vdu_num = 0
          break
      if vdu_num > 0:
        # We cannot allocate the vdus
        ret = None
    # Debug
    #if ret is not None:
    #  print('********',ret,'********')
    #  for i in ret:
    #    if i['node_seq'] == 0:
    #      print(devList[i['node_seq']])
    return ret  

  @ staticmethod
  def _allocateVduStorage(vdu,devList):
    ret = None
    try:
      assert vdu is not None
      assert len(devList) > 0
    except:
      return ret
    candidate = []
    vdu_num = vdu['vnf_num']* vdu['quantity']
    for n,dev in enumerate(devList):
      x = math.floor(dev['available']['storage']/vdu['storage'])
      if x >= vdu_num:
        candidate.append({'node_seq':n,'vdu_num':vdu_num})
        vdu_num = 0
        break
      elif x > 0:
        candidate.append({'node_seq':n,'vdu_num':x})
        vdu_num -= x
    if vdu_num == 0:
      ret = candidate
    return ret
  
  @staticmethod
  def _recordVduCompute(vdu,devSummary,allocateList,ignoreStorage=True):
    ret = None
    allocateSeqList = []
    for vnf_seq in range(vdu['vnf_num']):
      for vdu_seq in range(vdu['quantity']):
        allocateSeqList.append({'vnf_seq':vnf_seq,'vdu_seq':vdu_seq})
    allocateIdx = 0
    for allocate in allocateList:
      for n in range(allocate['vdu_num']):
        allocatedVdu = {}
        d = devSummary['compute_nodes'][allocate['node_seq']]
        for k in ['vcpu','memory']:
          allocatedVdu[k] = vdu[k]
          d['available'][k] -= vdu[k]
        for k in ['east_west_bandwidth','north_south_bandwidth']:
          allocatedVdu[k] = vdu[k]
          d['available']['bandwidth'] -= vdu[k]
        for k in ['hyperthreading','cpu_pinning','sriov_dpdk','affinity','anti_affinity','anti_affinity_limit']: allocatedVdu[k] = vdu[k]
        for k in ['vnf_name','vdu_name']:
          allocatedVdu[k] = vdu[k]
        allocatedVdu['vnf_seq'] = allocateSeqList[allocateIdx]['vnf_seq']
        allocatedVdu['vdu_seq'] = allocateSeqList[allocateIdx]['vdu_seq']
        if not ignoreStorage:
          allocatedVdu['storage'] = vdu['storage']
          d['available']['storage'] -= vdu['storage']
          try:
            assert d['available']['storage'] >= 0
          except:
            print('Error: Not enough storage for ' + '.'.join([ allocatedVdu['vnf_name'],allocatedVdu['vnf_seq'],allocatedVdu['vdu_name'],allocatedVdu['vdu_seq'] ] ) )
            print('Consider to use storage nodes?')
            raise
        d['vdus'].append(allocatedVdu)
        try:
          ret.append(allocatedVdu)
        except:
          ret = [allocatedVdu]
        allocateIdx += 1
    return ret
  
  @staticmethod
  def _recordVduStorage(vdu,devSummary,allocateList):
    #print(vdu['vnf_name'],vdu['vdu_name'],allocateList)
    ret = None
    allocateSeqList = []
    for vnf_seq in range(vdu['vnf_num']):
      for vdu_seq in range(vdu['quantity']):
        allocateSeqList.append({'vnf_seq':vnf_seq,'vdu_seq':vdu_seq})
    allocateIdx = 0
    for allocate in allocateList:
      for n in range(allocate['vdu_num']):
        allocatedVdu = {}
        d = devSummary['storage_nodes'][allocate['node_seq']]
        allocatedVdu['storage'] = vdu['storage']
        d['available']['storage'] -= vdu['storage']
        #print(d['available']['storage'], vdu['storage'], allocate)
        for k in ['vnf_name','vdu_name']:
          allocatedVdu[k] = vdu[k]
        allocatedVdu['vnf_seq'] = allocateSeqList[allocateIdx]['vnf_seq']
        allocatedVdu['vdu_seq'] = allocateSeqList[allocateIdx]['vdu_seq']
        d['vdus'].append(allocatedVdu)
        try:
          ret.append(allocatedVdu)
        except:
          ret = [allocatedVdu]
        allocateIdx += 1
    return ret
  
  @staticmethod
  def _createAllocatedComputeNode(dev):
    node = {'available':{},'vdus':[]}
    for k in ['vcpu','memory']: node['available'][k] = dev[k]
    node['available']['storage'] = HW_XLS._getNodeStorage(dev)
    node['available']['bandwidth'] = HW_XLS._getNodeBandwidth(dev)
    return node
  
  @staticmethod
  def _createAllocatedStorageNode(dev):
    node = {'available':{},'vdus':[]}
    node['available']['storage'] = HW_XLS._getNodeStorage(dev)
    return node
  
  def printDimensionData(self):
    for site in self.summary:
      print('******** site: '+site+' ********')
      for scn in self.summary[site]:
        s = None
        try:
          s = self.storageSummary[site][scn]
        except:
          pass
        print('  ======== scn: '+scn+' ========')
        print('    -------- Compute Nodes --------')
        for hyperthreading in self.summary[site][scn]:
          for cpu_pinning in self.summary[site][scn][hyperthreading]:
            for sriov_dpdk in self.summary[site][scn][hyperthreading][cpu_pinning]:
              d = self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk]
              print('      -------- hyperthreading',hyperthreading,'cpu_pinning',cpu_pinning,'sriov_dpdk',sriov_dpdk,' --------')
              for node in d['compute_nodes']:
                print('      |------>Available: vcpu-',node['available']['vcpu'],'memory-',node['available']['memory'],'storage-',node['available']['storage'],'bandwidth-',node['available']['bandwidth'])
                for vdu in node['vdus']:
                  print('        |------>',vdu['vnf_name'],vdu['vnf_seq'],vdu['vdu_name'],vdu['vdu_seq'])
        if s is None: continue
        print('    -------- Storage Nodes --------')
        for node in s['storage_nodes']:
          print('      |------>Available:', 'storage-',node['available']['storage'])
          for vdu in node['vdus']:
            print('        |------>',vdu['vnf_name'],vdu['vnf_seq'],vdu['vdu_name'],vdu['vdu_seq'])
                
#    self.summary[site][scn][hyperthreading][cpu_pinning][sriov_dpdk] 
#    print(json.dumps(self.summary,indent=4))
#    print(json.dumps(self.storageSummary,indent=4))