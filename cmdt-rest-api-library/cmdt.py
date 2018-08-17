import requests, json, re, time, uuid, sys
#import base64
from copy import deepcopy

class CMDT(object):
  
  def __init__(self,server='192.168.122.127',username='automation',password='automation',domain='maestrorepo',debug=False):
    self.server = server
    self.username = username
    self.password = password
    self.domain = domain
    self.debug = debug
    self.token = None
    self.userid = None
  
  def request(self,cmd,data=None, method='GET'):
    ret = None
    try:
      assert cmd.split('/')[-1][0] == '?'
      url = 'http://'+self.server+'/api/'+cmd
    except:
      url = 'http://'+self.server+'/api/'+cmd+'/'
    h = {}
    h['Content-Type'] = 'application/json'
    if self.isConnected():
      h['Authorization'] = 'Token '+self.token
    method = str(method).upper()
    try:
      if data is not None:
        data=json.dumps(data)
      if method == 'GET':
        req_func = requests.get
      elif method == 'POST':
        req_func = requests.post
      elif method == 'PUT':
        req_func = requests.put
      elif method == 'PATCH':
        req_func = requests.patch
      elif method == 'DELETE':
        req_func = requests.delete
      res = req_func(url, headers=h, data=data)
      ret = res.json()
    except:
      if self.debug:
        print('CMDT RestAPI Error: url=',url)
        print('response=\n',res.text)
    return ret
  
  def connect(self):
    self.token = None
    cmd='keystone-login'
    d = {}
    d['domain'] = self.domain
    d['username'] = self.username
    d['password'] = self.password
    res = self.request(cmd=cmd,data=d,method='POST')
    try:
      self.token = res['token']
      self.__getUserId()
    except:
      if self.debug:
        print('CMDT Login Error. res = ',res)
      pass
    return self.isConnected()
  
  def isConnected(self):
    return self.token is not None
  
  def __getUserId(self):
    for u in self.request('admin/users')['users']:
      if u['username'] == self.username:
        self.userid = u['id']
        break
  
  def uuidGen(self):
    u = uuid.uuid4()
    return u.hex
    #return base64.urlsafe_b64encode(u.get_bytes()).lower().strip('==\n')
  
  #----------INFRASTRUCTURE DEVICE----------
  def infraDevGetAll(self,version='1.0'):
    method = 'GET'
    cmd = 'cmdt/'+version+'/infra_devices'
    res = self.request(cmd,method=method)
    devInfo = res['items']
    return devInfo
  
  def infraDevsGetByCategory(self,category,version='1.0'):
    ret = []
    method = 'GET'
    cmd = 'cmdt/'+version+'/infra_devices'
    res = self.request(cmd,method=method)
    devInfo = res['items']
    for dev in devInfo:
      if dev['category'] == category:
        ret.append(dev)
    if len(ret) > 0:
      return ret
    else:
      return None

  def infraDevGetCategoryByPn(self,allDevData,pn):
    ret = None
    for dev in allDevData:
      try:
        assert dev['part_number'] == pn
        ret = dev['category']
        break
      except:
        continue
    return ret
  
  def infraDevCreate(self,devDict,version='1.0'):
    ret = None
    method = 'POST'
    cmd = 'cmdt/'+version+'/infra_devices'
    try:
      devDict['price'] = float(devDict['price'])
      assert devDict['price'] >= 0
    except:
      devDict.pop('price',None)
    res = self.request(cmd,data=devDict,method=method)
    try:
      ret = res['id']
    except:
      print('CMDT failed to add device. response=\n',res)
      pass
    return ret
  
  def infraDevImport(self,category,devDict):
    try:
      devTemp = deepcopy(self.TEMPLATE_INFRA_DEV[category])
    except:
      return None
    for k in devDict:
      try:
        devTemp[k]
        devTemp[k] = devDict[k]
      except:
        pass
    for k in devDict:
      try:
        devTemp['dimensions'][k]
        devTemp['dimensions'][k] = devDict[k]
      except:
        pass
    for k in devDict:
      try:
        devTemp['physical_dimensions'][k]
        devTemp['physical_dimensions'][k] = devDict[k]
      except:
        pass
    try:
      assert len(devTemp['popular_name']) > 0
    except:
      devTemp['popular_name'] = devTemp['part_number']
    try:
      assert len(devDict['side_names']) > 0
      devTemp['popular_name'] += ('---ADJUSTED---' + '-'.join(devDict['side_names']))
    except:
      pass
    return self.infraDevCreate(devTemp)
  
  def infraDevDelAll(self,version='1.0'):
    method = 'DELETE'
    cmd = 'cmdt/'+version+'/infra_devices/all'
    res = self.request(cmd,method=method)
    return res

  def infraDevDel(self,devId,version='1.0'):
    method = 'DELETE'
    cmd = 'cmdt/'+version+'/infra_devices/'+devId
    res = self.request(cmd,method=method)
    return res

  #----------VNF/VDU----------

  def vduCreate(self,vnfName,vduName,devDict,vendor='',isEdit=False):
    devTemp = deepcopy(self.TEMPLATE_VDU)
    devTemp['is_edit'] = isEdit
        
#    vduDev['type_name'] = 'pensa.nodes.appliance.component.root'
    pDict = devTemp['device_settings']['properties']
    pDict['sub_category']['default'] = vnfName
    pDict['vendor']['default'] = vendor
    pDict['name']['default'] = vduName
  
    pDict['number_of_vCPU']['default'] = devDict['vcpu']
    pDict['memory_size']['default'] = devDict['memory']
    pDict['disk_size']['default'] = devDict['storage']
    
    pDict['hyperthreading_needed']['default'] = devDict['hyperthreading']
    pDict['cpu_pinning_needed']['default'] = devDict['cpu_pinning']
    pDict['sriov_dpdk_needed']['default'] = devDict['sriov_dpdk']
    pDict['east_west_bandwidth']['default'] = devDict['east_west_bandwidth']
    pDict['north_south_bandwidth']['default'] = devDict['north_south_bandwidth']
    pDict['cpu_affinity']['default'] = devDict['affinity_type']
    pDict['physical']['default'] = devDict['physical']
    
    pDict['description'].pop('default',None)
    #pDict['instance_description']['default'] = vnfName + ' - ' + vduName

    cmd = 'devices/create_device'
    while 1:
      res = self.request(cmd, devTemp, 'POST')
      try:
        assert res['errors'][0] == 'Device creation is already in progress, please try once it is completed'
        time.sleep(1)
      except:
        break
    for i in range(5):
      devId = self.devIdGetByName(display_name=vduName, retry=3, devType='VDU')
      if devId is not None:
        break
      time.sleep(1)
      i+=1
    if devId is not None:
      self.devWaitComplete([devId,])
    else:
      #print json.dumps(devTemp, indent = 4)
      print(json.dumps(res, indent = 4))
      pass
    return devId

  def vnfCreate(self,projName,vnfName,vduInfoList,description=None, cidr='192.168.1.0/24', isEdit=False):
    devTemp = deepcopy(self.TEMPLATE_VNF)
    devTemp['device_lifecycle'] = []
    devTemp['policies'] = []
    devTemp['component_links'] = []
    devTemp['is_edit'] = isEdit
    
    isPhysical = False
    
    pDict = devTemp['device_settings']['properties']
    pDict['sub_category']['default'] = projName
    pDict['name']['default'] = vnfName
    if description is None:
      pDict['description'].pop('default',None)
    else:
      pDict['description']['default'] = description
  
  # By default put all the vdu (label) in the same group 'GRP1'
    devTemp['groups'][0]['members'] = []
  
  # Generate Components and Internal Ports
  # By default each VDU is associated to 1 internal port
    devTemp['components'] = []
    xLocUnit = 1000 / (len(vduInfoList) + 1)
    componentVduKeys = []
    componentPortKeys = []
    for n,vduInfo in enumerate(vduInfoList,1):
      vduId = vduInfo['id']
      # Get the VDU info
      vduTemp = self.devGet(vduId)
      if bool(vduTemp['content']['properties']['physical']['default']):
        isPhysical = True
      vduDev = {}
      vduDev['category'] = 'VNF Component Device'
      vduDev['key'] = self.uuidGen()
      vduDev['loc'] = str(n*xLocUnit) + ' 200'
      vduDev['name'] = vduTemp['name']
      vduDev['sub_category'] = vnfName
      vduDev['properties'] = deepcopy(vduTemp['content']['properties'])
      vduLabel = vduDev['properties']['name']['default'] + '_' + str(n)
      vduDev['properties']['label']['default'] = vduLabel
      componentVduKeys.append(vduDev['key'])
      devTemp['components'].append(vduDev)
      devTemp['groups'][0]['members'].append(vduLabel)
      # Internal Ports
      port = deepcopy(self.TEMPLATE_PORT)
      port['key'] = self.uuidGen()
      port['loc'] = str(n*xLocUnit) + ' 300'
      port['properties']['label']['default'] = 'Port_' + str(n)
      componentPortKeys.append(port['key'])
      devTemp['components'].append(port)
      # create affinity policy to this VDU if required
      policyDict = None
      if vduInfo['affinity']:
        policyDict = deepcopy(self.TEMPLATE_VNF_POLICY_AFFINITY)
        policyDict['targets'].append(vduLabel)
      elif vduInfo['anti_affinity']:
        if vduInfo['anti_affinity_limit'] > 0:
          policyDict = deepcopy(self.TEMPLATE_VNF_POLICY_ANTI_AFFINITY_SCALE)
          policyDict['targets'].append(vduLabel)
          policyDict['properties']['no_of_instances']['default'] = vduInfo['anti_affinity_limit']
      if policyDict is not None:
        devTemp['policies'].append(policyDict)
    
    pDict['physical']['default'] = isPhysical
    
    # Generate 1 network, which will be used to connect all internal ports
    network = deepcopy(self.TEMPLATE_NETWORK)
    network['key'] = self.uuidGen()
    network['loc'] = '500 400'
    network['properties']['label']['default']  = 'Network_1'
    network['properties']['network_cidr']['default'] = cidr
    componentNetworkKey = network['key']
    devTemp['components'].append(network)
  
    # Generate 1 External Port
    exPort = deepcopy(self.TEMPLATE_EXPORT)
    exPort['key'] = self.uuidGen()
    exPort['loc'] = '100 100'
    exPort['properties']['label']['default'] = 'External_Port_1'
    componentExPortKey = exPort['key']
    devTemp['components'].append(exPort)
  
    # Generate links between components
    # Between VDU/Internal Ports, and Network/Internal Ports
    for (vduKey,portKey) in zip(componentVduKeys, componentPortKeys):
      devTemp['component_links'].append(deepcopy({'source':portKey, 'target':vduKey}))
      devTemp['component_links'].append(deepcopy({'source':portKey, 'target':componentNetworkKey}))
    # Connect the External Port to the 1st VDU
    devTemp['component_links'].append(deepcopy({'source':componentExPortKey, 'target':componentVduKeys[0]}))
  
    # Generate performance flavours
    # By default all the VDU initialised to 1, and the max scale is 5
    devTemp['performence_flavours'][0]['properties']['scaling_aspects']['default'][0]['properties']['max_scale_level'] = 5 * len(vduInfoList)
    devTemp['performence_flavours'][0]['properties']['instantiation_levels']['default'][0]['properties']['scale_info'][0]['properties']['scale_level'] = 1
    devTemp['performence_flavours'][0]['properties']['instantiation_levels']['default'][0]['properties']['vdu_level'] = []
    devTemp['performence_flavours'][0]['properties']['instantiation_levels']['entry_schema']['properties']['vdu_level']['entry_schema']['properties']['vdu_name']['constraints'][0]['valid_values'] = deepcopy(devTemp['groups'][0]['members'])
  
    for vduLabel in devTemp['groups'][0]['members']:
      initDict = {'type': 'pensa.datatypes.deployment.vdu_level'}
      initDict['properties'] = {'number_of_instances':1, 'vdu_name':vduLabel}
      devTemp['performence_flavours'][0]['properties']['instantiation_levels']['default'][0]['properties']['vdu_level'].append(initDict)
  
    cmd = 'devices/create_device'

    while 1:
      res = self.request(cmd, devTemp, 'POST')
      try:
        assert res['errors'][0] == 'Device creation is already in progress, please try once it is completed'
        time.sleep(1)
      except:
        break
      
    for i in range(5):
      time.sleep(1)
      devId = self.devIdGetByName(display_name=vnfName, retry=3, devType='VNF')
      if devId is not None:
        break
      i+=1
    if devId is not None:
      self.devWaitComplete([devId,])
#      print json.dumps(devTemp,indent=4)
    return devId
  
  @staticmethod
  def vduCompare(devFromXls,devFromCmdt):
    # Check all the parameters relevant to result calculation
    # All cosmetic parameters are ignored
    try:
      c = devFromCmdt['content']['properties']
    except:
      return False
    
    try:
      assert c['number_of_vCPU']['default'] == devFromXls['vcpu']
      assert c['memory_size']['default'] == devFromXls['memory']
      assert c['disk_size']['default'] == devFromXls['storage']
    
      assert c['hyperthreading_needed']['default'] == devFromXls['hyperthreading']
      assert c['cpu_pinning_needed']['default'] == devFromXls['cpu_pinning']
      assert c['sriov_dpdk_needed']['default'] == devFromXls['sriov_dpdk']
      assert c['east_west_bandwidth']['default'] == devFromXls['east_west_bandwidth']
      assert c['north_south_bandwidth']['default'] == devFromXls['north_south_bandwidth']
      assert c['cpu_affinity']['default'] == devFromXls['affinity_type']
      assert c['physical']['default'] == devFromXls['physical']
    
    except:
      return False
    
    return True
  
  @staticmethod
  def vnfCompare(devFromXls,devFromCmdt):
    # Just check VDU components
    # All cosmetic parameters are ignored
    c = devFromCmdt['content']['properties']
    try:
      assert len(devFromXls) == len(c['components']['default'])
      for d in c['components']['default']:
        found = False
        k = d.keys()[0]
        k = k.strip()
        for x in devFromXls:
          if re.match('^'+x+'_\d+$',k) is not None:
            found = True
            break
        assert found
    except:
      return False
    
    return True

# display name list only
  def devsGetByNameList(self,nameList,devType=None):
    res = self.devGetAll()
    if res is None: return None
    ret = []
    nameList = sorted(nameList)
    for name in nameList:
      for dev in sorted(res, key=lambda k: k['display_name']):
        if name == dev['display_name']:
          if devType is not None:
            if devType == 'VNF':
              if dev['category'] != 'VNF Device': continue
            elif devType == 'VDU':
              if dev['category'] != 'VNF Component Device': continue
            else:
              continue
          ret.append(self.devGet(dev['id']))
          break
    try:
      assert len(ret) > 0
      return ret
    except:
      return None

# get the VDU components of a VNF
  def vduGetByVnfName(self,vnfName=None):
    try:
      cmd = 'devices/?sub_category='+vnfName+'&category=VNF Component Device'
      ret = self.request(cmd)
    except:
      ret = None
    return ret
  
  def devGetByName(self, display_name=None, name=None, retry=0, retry_interval=1, devType=None, sub_category=None):
    try:
      assert retry > 0
      try:
        assert retry_interval > 0
      except:
        retry_interval = 1
      n = 0
      while n<= retry:
        dev = self.__devGetByName(display_name, name, devType, sub_category)
        try:
          assert dev['id'] > 0
          break
        except:
          time.sleep(retry_interval)
        n+=1 
    except:
      dev = self.__devGetByName(display_name, name, devType, sub_category)
    return dev
  
  def devIdGetByName(self, display_name=None, name=None, retry=0, retry_interval=1, devType=None, sub_category=None):
    try:
      return self.devGetByName(display_name, name, retry, retry_interval, devType, sub_category)['id']
    except:
      return None

  def __devGetByName(self, display_name=None, name=None, devType=None, sub_category=None):
    res = self.devGetAll()
    for dev in res:
      if dev['display_name'] != display_name and dev['name'] != name: continue 
      if devType is not None:
        if devType == 'VNF':
          if dev['category'] != 'VNF Device': continue
        elif devType == 'VDU':
          if dev['category'] != 'VNF Component Device': continue
        else:
          continue
      if sub_category is not None:
        if dev['sub_category'] != sub_category: continue
      return self.devGet(dev['id'])
    return None
  
  def devGet(self,devId):
    cmd = 'devices/' + str(devId)
    res = self.request(cmd)
    try:
      assert int(res['id']) == devId
      return res
    except:
      return None

  def devStatusGet(self, devId):
    ret = None
    cmd = 'devices/'+str(devId)+'/status'
    res = self.request(cmd)
    try: 
      ret = res["notes"]["status"]
    except:
      pass
    return ret
  
  def devWaitComplete(self, idList=None):
    ret = 'Completed'
    if idList is None:
      idList = []
      for dev in self.devGetAll():
        idList.append(dev['id'])
    for devId in idList:
      while 1:
        devStatus = self.devStatusGet(devId)
        if devStatus is None: break
        if devStatus == 'In-Progress' or devStatus == 'deletion_in_progress':
          time.sleep(1)
        else:
          if devStatus == 'Error':
            ret = 'Error'
          break
    return ret

  def devGetAll(self):
    cmd = 'devices'
    res = self.request(cmd)
    return res
  
  def vnfGetAll(self):
    cmd = 'devices/?global=true'
    res = self.request(cmd)
    return res
  
  def vnfDelBySubCategory(self,sub_category):
    for dev in self.vnfGetAll():
      try:
        assert dev['category'] == 'VNF Device' and dev['sub_category'] == sub_category
        cmd = 'user_types_files/delete'
        print('Information: Deleting VNF '+dev['display_name']+'('+str(dev['id'])+')')
        sys.stdout.flush()
        self.request(cmd, {'name':dev['name']}, method='POST')
        self.devWaitComplete([dev['id'],])
      except:
        pass
  
  def userVnfDelAll(self):
    for devBrief in self.devGetAll():
      try:
        assert devBrief['category'] == 'VNF Device'
        dev = self.devGet(devBrief['id'])
        assert bool(dev['content']['user_imported'])
        cmd = 'user_types_files/delete'
        print('Information: Deleting VNF '+dev['display_name']+'('+str(dev['id'])+')')
        sys.stdout.flush()
        self.request(cmd, {'name':dev['name']}, method='POST')
        self.devWaitComplete([dev['id'],])
      except:
        pass
    # delete any strand vdu if exists
    for devBrief in self.devGetAll():
      try:
        dev = self.devGet(devBrief['id'])
        assert bool(dev['content']['user_imported'])
        cmd = 'devices/'+str(dev['id'])
        print('Information: Deleting VDU '+dev['display_name']+'('+str(dev['id'])+')')
        sys.stdout.flush()
        self.request(cmd, method='DELETE')
        self.devWaitComplete([dev['id'],])
      except:
        pass

  def devDel(self,name):
    cmd = 'user_types_files/delete'
    devId = self.devIdGet(name=name)
    if devId is None: return
    self.request(cmd, {'name':name}, method='POST')
    self.devWaitComplete([devId,])
    
  #----------PROJECT----------
  def projCreate(self,projName,description=None):
    ret = None
    method = 'POST'
    cmd = 'projects'
    data = {'project_admin':['admin',self.username],'name':projName,"description":description}
    try:
      res = self.request(cmd,data,method=method)
      ret = res['id']
    except:
      pass
    return ret
  
  def projGetAll(self):
    try:
      cmd = 'projects/short_list'
      res = self.request(cmd)
      assert len(res['projects']) > 0
      return res['projects']
    except:
      return None
  
  def projGetByName(self, projName):
    try:
      for proj in self.projGetAll():
        if proj['name'] == projName:
          return proj['id']
    except:
      return None
  
  def projDel(self, projId):
    if projId is None: return
    method = 'DELETE'
    cmd = 'projects/'+str(projId)
    self.request(cmd,method=method)
  
  def projDelByName(self, projName):
    self.projDel(self.projGetByName(projName))

  def projDelAll(self):
    allProjs = self.projGetAll()
    if allProjs is None: return
    for proj in allProjs:
      self.projDel(proj['id'])
  
  #----------SITE----------
  def siteCreate(self,projId,siteName,description=None):
    ret = None
    method = 'POST'
    cmd = 'sites'
    site = deepcopy(self.TEMPLATE_SITE)
    site['name'] = siteName
    site['description'] = description
    site['project'] = projId
    try:
      res = self.request(cmd,site,method=method)
      ret = res['id']
    except:
      pass
    return ret

  def siteGetAll(self):
    cmd = 'sites'
    res = self.request(cmd)
    return res

  def siteGet(self,siteId):
    cmd = 'sites/'+str(siteId)
    res = self.request(cmd)
    return res

  def siteGetByName(self,projId,siteName):
    try:
      for site in self.siteGetAll():
        if site['name'] == siteName and site['project'] == projId:
          res = site
          break
      return res
    except:
      return None
  
  def siteIdGetByName(self,projId,siteName):
    try:
      for site in self.siteGetAll():
        if site['name'] == siteName and site['project'] == projId:
          res = site
          break
      return res['id']
    except:
      return None

  def siteGetAllByProj(self,projId):
    ret = []
    for site in self.siteGetAll():
      if site['project'] == projId:
        ret.append(site)
    try:
      assert len(ret) > 0
      return ret
    except:
      return None

  def siteDel(self, siteId):
    method = 'DELETE'
    cmd = 'sites/'+str(siteId)
    res = self.request(cmd,method=method)
    return res

  
  #----------SITE DESIGN----------

  # vnf name is the display name
  def siteVnfAdd(self,siteId,vnfNameList):
    method = 'PATCH'
    cmd = 'sites/'+str(siteId)
  
    patchData = {'validation_status':0}
  
    ########################################
    # Draft Data
    patchData['draft'] = [[deepcopy(self.TEMPLATE_SITE_DRAFT_CLOUD)],[]]
    # Devices (VNF / Network)
    devData = patchData['draft'][0]
  
    # Add an openstack cloud to the site
    draftCloud = devData[0]
  #  draftCloud['group'] = cmdtGenUuid()
    draftCloud['key'] = self.uuidGen()
    draftCloud['id'] = '_'.join([draftCloud['name'],draftCloud['key'],str(0)])
    # Get VNF repo info
    vnfRepoData =  self.devsGetByNameList(vnfNameList,devType='VNF')
    if vnfRepoData is None: return
    vnfList = []
    xLocUnit = 500 / (len(vnfRepoData)+1)
    # VNFs
    for n, vnfRepo in enumerate(vnfRepoData,1):
      vnf = deepcopy(self.TEMPLATE_SITE_DRAFT_VNF)
      vnf['sub_category'] = vnfRepo['sub_category']
      vnf['loc'] = str(250+xLocUnit*n) + ' 200'
      vnf['group'] = draftCloud['key']
      vnf['name'] = vnfRepo['name']
      vnf['key'] = self.uuidGen()
      vnf['id'] = '_'.join([vnf['name'],vnf['key'],str(0)])
      devData.append(vnf)
      vnfList.append(vnf)
    # Network
    draftNetwork = deepcopy(self.TEMPLATE_SITE_DRAFT_NETWORK)
    draftNetwork['loc'] = '500 300'
    draftNetwork['group'] = draftCloud['key']
    draftNetwork['key'] = self.uuidGen()
    draftNetwork['id'] = '_'.join([draftNetwork['name'],draftNetwork['key'],str(0)])
    devData.append(draftNetwork)
  
    # Links
    linkData = patchData['draft'][1]
    # Create 1 L3 link from each VNF and Network
    for vnf in vnfList:
      l3Link = deepcopy(self.TEMPLATE_SITE_DRAFT_L3_LINK)
      l3Link['key'] += self.uuidGen()
      l3Link['from'] = vnf['key']
      l3Link['to'] = draftNetwork['key']
      l3Link['fromPort'] = '_'.join([l3Link['fromPort'], l3Link['from'], str(0)])
      l3Link['toPort'] = '_'.join([l3Link['toPort'], l3Link['to'], str(0)])
      linkData.append(l3Link)
    ########################################
    # Design Data
    patchData['design_data'] = {'relationships':[],'nodes':[]}
    # add cloud tenant node
    tenantNode = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_TENANT)
    tenantNode['id'] = '_'.join([tenantNode['device_name'],draftCloud['key'],str(0)])
    tenantNode['properties']['label'] = '_'.join([tenantNode['properties']['name'],str(0)])
    patchData['design_data']['nodes'].append(tenantNode)
    # add vpc node
    vpcNode = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_VPC)
    vpcNode['group'] = draftCloud['key']
    vpcNode['id'] = '_'.join([vpcNode['device_name'],vpcNode['group'],str(0)])
    vpcNode['properties']['label'] = '_'.join([vpcNode['properties']['name'],str(0)])
    patchData['design_data']['nodes'].append(vpcNode)
    # add neutron sdn node
    sdnNode = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_NEUTRON)
    sdnNode['group'] = draftCloud['key']
    sdnNode['id'] = '_'.join([sdnNode['device_name'],sdnNode['group'],str(0)])
    sdnNode['properties']['label'] = '_'.join([sdnNode['properties']['name'],str(0)])
    patchData['design_data']['nodes'].append(sdnNode)
    # add VNF nodes
    for (vnfRepo,vnfDraft) in zip(vnfRepoData,vnfList):
      vnfDesign = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_VNF)
      vnfDesign['group'] = vnfDraft['group']
      vnfDesign['id'] = vnfDraft['id']
      vnfDesign['device_name'] = vnfDraft['name']
      vnfDesign['properties']['category'] = vnfDraft['category']
      vnfDesign['properties']['sub_category'] = vnfDraft['sub_category']
      vnfDesign['properties']['name'] = vnfRepo['display_name']
#      vnfDesign['properties']['description'] = vnfRepo['content']['properties']['description']['default']
      vnfDesign['properties']['description'] = ''
      vnfDesign['properties']['label'] = '_'.join([vnfDesign['properties']['name'],vnfDesign['id'].split('_')[-1]])
      vnfDesign['properties']['components'] = vnfRepo['content']['properties']['components']['default']
      patchData['design_data']['nodes'].append(vnfDesign)
      # and add the external ports to VNF
      exPortDesign = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_EXPORT)
      exPortDesign['group'] = vnfDraft['group']
      exPortDesign['id'] = '_'.join([exPortDesign['device_name'],vnfDraft['key'],str(0)])
      exPortDesign['properties']['label'] = '_'.join([exPortDesign['properties']['name'],str(0)])
      patchData['design_data']['nodes'].append(exPortDesign)
    # add Network
    networkNode = deepcopy(self.TEMPLATE_SITE_DESIGN_NODE_NETWORK)
    networkNode['group'] = draftCloud['key']
    networkNode['id'] = '_'.join([networkNode['device_name'],draftNetwork['key'],str(0)])
    networkNode['properties']['network_cidr'] = '192.168.1.0/24'
    networkNode['properties']['label'] = '_'.join([networkNode['properties']['name'],str(0)])
    networkNode['properties']['is_management'] = False
    patchData['design_data']['nodes'].append(networkNode)
  
    # add relations from vpc to cloud
    relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
    relData['type'] = 'pensa-relationships-network_hosted_on'
    relData['id'] = '_'.join([relData['type'],self.uuidGen()])
    relData['source'] = vpcNode['id']
    relData['target'] = tenantNode['id']
    relData['requirement_name'] = 'network_host'
    patchData['design_data']['relationships'].append(relData)
    # add relations from cloud to neutron
    relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
    relData['type'] = 'pensa-relationships-cloud_network_controller-openstack'
    relData['id'] = '_'.join([relData['type'],self.uuidGen()])
    relData['source'] = tenantNode['id']
    relData['target'] = sdnNode['id']
    relData['requirement_name'] = 'sdn_controller'
    patchData['design_data']['relationships'].append(relData)
    # add relations for each VNF
    for vnf in vnfList:
      # VNF to External Port
      relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
      relData['type'] = 'pensa-relationships-vm_hosted_on'
      relData['id'] = '_'.join([relData['type'],self.uuidGen()])
      relData['source'] = vnf['id']
      relData['target'] = '_'.join(['pensa-nodes-ExternalPort',vnf['key'],str(0)])
      relData['requirement_name'] = 'connection'
      patchData['design_data']['relationships'].append(relData)
      # External Port to VNF
      relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
      relData['type'] = 'pensa-relationships-network-binds_to'
      relData['id'] = '_'.join([relData['type'],self.uuidGen()])
      relData['source'] = '_'.join(['pensa-nodes-ExternalPort',vnf['key'],str(0)])
      relData['target'] = vnf['id']
      relData['requirement_name'] = 'binding'
      patchData['design_data']['relationships'].append(relData)
      # VNF to Tenant
      relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
      relData['id'] = 'pensa-relationships-vm_hosted_on_'+self.uuidGen()
      relData['source'] = vnf['id']
      relData['target'] = tenantNode['id']
      relData['type'] = 'pensa-relationships-vm_hosted_on'
      relData['requirement_name'] = 'host'
      patchData['design_data']['relationships'].append(relData)
      # VNF External Port to Network
      relData = deepcopy(self.TEMPLATE_SITE_DESIGN_REL)
      relData['type'] = 'pensa-relationships-network-connects_to'
      relData['id'] = '_'.join([relData['type'],self.uuidGen()])
      relData['source'] = '_'.join(['pensa-nodes-ExternalPort',vnf['key'],str(0)])
      relData['target'] = draftNetwork['id']
      relData['requirement_name'] = 'connection'
      patchData['design_data']['relationships'].append(relData)

    patchData['draft'] = json.dumps(patchData['draft']).replace('"', '\"')
    patchData['design_data'] = json.dumps(patchData['design_data']).replace('"', '\"')
    res = self.request(cmd,data=patchData,method=method)
    return res

  def siteValidate(self,siteId):
    ret = False
    method = 'POST'
    cmd = 'sites/'+str(siteId)+'/validate'
    data = {'network_snapshot':None}
    res = self.request(cmd,data=data,method=method)
    try:
      assert res['validation_status'] == 1
      ret = True
    except:
      try:
        err = res['validation_errors']
      except:
        err = 'Unknown Reason'
      print('Site Validation Failed:',err)
    return ret
  
  
  def siteCriteriaGet(self,siteId):
    cmd = 'sites/'+str(siteId)+'/criteria'
    return self.request(cmd)

  def siteClear(self,siteId):
    method = 'PATCH'
    cmd = 'sites/'+str(siteId)
    patchData = {'validation_status':0}
    patchData['draft'] = [[],[]]
    patchData['design_data'] = {'relationships':[],'nodes':[]}
    patchData['draft'] = json.dumps(patchData['draft']).replace('"', '\"')
    patchData['design_data'] = json.dumps(patchData['design_data']).replace('"', '\"')
    res = self.request(cmd,data=patchData,method=method)
    return res

  #----------SCENARIO----------
  
  def scnCreate(self,siteId,scnName,description=None,version='1.0'):
    method = 'POST'
    cmd = 'cmdt/'+str(version)+'/scenarios/?site_id='+str(siteId)
    if description is None: description = scnName
    data = {"user_id":5,"site_id":siteId,"name":scnName,"description":description}
    res = self.request(cmd,data=data,method=method)
    try:
      return res['id']
    except:
      return None

  def scnIdGetByName(self,siteId,scnName,version='1.0'):
    ret = None
    cmd = 'cmdt/'+str(version)+'/scenarios/?site_id='+str(siteId)
    res = self.request(cmd)
    try:
      assert len(res['items']) > 0
      for scn in res['items']:
        if scn['name'] == scnName:
          ret = scn['id']
          break
    except:
      pass
    return ret

  def scnGet(self,siteId,scnId,version='1.0'):
    cmd = 'cmdt/'+str(version)+'/scenarios/'+str(scnId)+'/?site_id='+str(siteId)
    res = self.request(cmd)
    return res
  
  def scnClear(self,siteId,scnId,version='1.0'):
    method = 'PATCH'
    cmd = 'cmdt/'+str(version)+'/scenarios/'+scnId+'/?site_id='+str(siteId)
    data = {'cloud_infrastructure':[]}
    res = self.request(cmd,data,method=method)
    return res

  def scnResultCalc(self,siteId,scnId,version='1.0'):
    method = 'POST'
    cmd = 'cmdt/'+str(version)+'/scenarios/'+scnId+'/calculate/?site_id='+str(siteId)
    data = {'scenarioId':scnId}
    res = self.request(cmd,data,method=method)
    return res

  #----------SCENARIO DESIN----------

  def scnRackCreate(self,siteId,scnId,infraDevIds,version=1.0):
    method = 'PATCH'
    cmd = 'cmdt/'+str(version)+'/scenarios/'+scnId+'/?site_id='+str(siteId)
    # infraDevIds = {'compute':[],'storage':[],'network':[],'rack':[]}
    allInfraDevInfo = self.infraDevGetAll()
    devInfo = {}
    for k in infraDevIds:
      devInfo[k] = []
      for devId in infraDevIds[k]:
        for dev in allInfraDevInfo:
          if dev['id'] == devId:
            devInfo[k].append(dev)
            break
    try:
      assert len(devInfo['compute']) > 0
      assert len(devInfo['network']) > 0
      assert len(devInfo['rack']) > 0
    except:
      print('scnRackCreate: Missing infrastructures, e.g. compute/network/rack')
      return
    # Find the least capable switch as the mgmt switch
    for dev in devInfo['network']:
      totalBw = 0
      totalPort = 0
      for net in dev['dimensions']['network']:
        totalBw += (net['capacity']*net['quantity'])
        totalPort += net['quantity']
      dev['TotalMetric'] = totalBw * 10000 + totalPort
    minMetric = -1
    mgmtDevIdx = -1
    for n,dev in enumerate(devInfo['network']):
      if minMetric < 0 or dev['TotalMetric'] < minMetric:
        minMetric = dev['TotalMetric']
        mgmtDevIdx = n
    devInfo['network'][mgmtDevIdx]['is_management_network'] = True
    for dev in devInfo['network']:
      dev.pop('TotalMetric',None)
  
    data = {'cloud_infrastructure':[]}
    rackU = 400
    for nRack,rackPart in enumerate(devInfo['rack'],1):
      #Frist add a rack
      rackPart.pop('id',None)
      rack = {'quantity':0}
      rack['rack_units'] = rackPart['rack_units']
      rack['parts'] = [rackPart,]
      rack['frontend_data'] = {'key':self.uuidGen()}
      rackBaseX = 2500*nRack
      rackBaseY = 3000
      rack['frontend_data']['loc'] =  str(rackBaseX)+' '+str(rackBaseY)
      rack['frontend_data']['size'] = '1891 6921'
      # add compute/storage/network nodes
      nRackU = 1
      for nodePart in devInfo['compute']+devInfo['storage']+devInfo['network']:
        nodePart['frontend_data'] = {'group':rack['frontend_data']['key'],'key':self.uuidGen()}
        nodePart['frontend_data']['loc'] = str(rackBaseX)+' '+str(rackBaseY*2 - rackU*nRackU)
        nodePart['quantity'] = 0
        nodePart.pop('id',None)
  #      print nodePart['frontend_data']['loc'],nodePart['category']
        rack['parts'].append(nodePart)
  #      try:
  #        nRackU += nodePart['rack_units']
  #      except:
  #        nRackU += 1
        nRackU += 1
      data['cloud_infrastructure'].append(rack)
    
#    print json.dumps(data,indent=4)
    res = self.request(cmd,data,method=method)
    return res

  def scnVduLevelSet(self,siteId,scnId,scnVnfInfo,version='1.0'):
    method = 'PATCH'
    cmd = 'cmdt/'+str(version)+'/scenarios/'+scnId+'/?site_id='+str(siteId)
    try:
      vduLevelInfo = self.siteCriteriaGet(siteId)['vdu_levels']
    except:
      return
    for vnfId in vduLevelInfo:
      vnfName = vduLevelInfo[vnfId]['name']
      for vnf in scnVnfInfo:
        if re.search('^'+vnf+'_\d+$', vnfName) is None: continue
        try:
          vnfCount = scnVnfInfo[vnf]['quantity']
        except:
          vnfCount = 0
        for vduId in vduLevelInfo[vnfId]['components']:
          vduName = vduLevelInfo[vnfId]['components'][vduId]['name']
          vduLevelInfo[vnfId]['components'][vduId]['count'] = 0
          for vdu in scnVnfInfo[vnf]['vdus']:
            if re.search('^'+vdu+'_\d+$', vduName) is None: continue
            vduLevelInfo[vnfId]['components'][vduId]['count'] = vnfCount * scnVnfInfo[vnf]['vdus'][vdu]
            break
        break
    scnInfo = self.scnGet(siteId, scnId)
    vduLevelPatch = deepcopy(self.TEMPLATE_SCN_VDULEVEL)
    for k in ['user_id', 'description','site_id','name']:
      vduLevelPatch[k] = scnInfo[k]
    vduLevelPatch['vdu_levels'] = vduLevelInfo
#    print json.dumps(vduLevelPatch,indent = 4)
    res = self.request(cmd, vduLevelPatch, method)
    return res
  
  #----------BoQ----------
  def boqSave(self,siteId,scnId,result,version='1.0'):
    if result is None:return
    method = 'POST'
    cmd = 'cmdt/'+str(version)+'/scenarios/'+scnId+'/save_boq/?site_id='+str(siteId)
    data = deepcopy(result['result']['boq'])
    for k in ['project_name','site_name','scenario_name']: data[k] = result[k]
    data['name'] = '-'.join([data['project_name'],data['site_name'],data['scenario_name']])
    data['user_name'] = self.username
    res = self.request(cmd,data,method=method)
    try:
      return res['boq_id']
    except:
      return None

  def boqDel(self, boqId,version='1.0'):
    method = 'DELETE'
    cmd = 'cmdt/'+str(version)+'/boqs/'+boqId
    self.request(cmd,method=method)
    return

  def boqGetAll(self, version='1.0'):
    cmd = 'cmdt/'+str(version)+'/boqs/short_list'
    res = self.request(cmd)
    try:
      assert len(res['items']) > 0
      return res['items']
    except:
      return None
  
  def boqGetByProjName(self,projName=None,version='1.0'):
    ret = []
    try:
      assert projName is not None
      for boq in self.boqGetAll(version):
        if boq['name'].startswith(projName+'-'):
          ret.append(boq)
    except:
      pass
    return ret
  
  def boqDelByProjName(self,projName=None,version='1.0'):
    try:
      for boq in self.boqGetByProjName(projName, version):
        self.boqDel(boq['id'],version)
    except:
      pass
  
  def boqDelAll(self,version='1.0'):
    try:
      for boq in self.boqGetAll(version):
        self.boqDel(boq['id'],version)
    except:
      pass
  
  #----------Misc Functions----------
  def printVnfSummary(self):
    allDevData = self.devGetAll()
    allVnfs = {}
    strandVdus = []
    for dev in allDevData:
      if not bool(dev['content']['user_imported']): continue
      if dev['category'] == 'VNF Device':
        allVnfs[dev['display_name']] = []
    for dev in allDevData:
      if not bool(dev['content']['user_imported']): continue
      if dev['category'] == 'VNF Component Device':
        vnfName = dev['sub_category']
        try:
          allVnfs[vnfName].append(dev['display_name'])
        except:
          strandVdus.append[dev['display_name']+'('+vnfName+')']
    for vnf in allVnfs:
      print('----------VNF: '+vnf+'----------')
      print(','.join(allVnfs[vnf]))
    if len(strandVdus) > 0:
      print('----------Strand VDUs----------')
      print(','.join(strandVdus))
        
  def printDevAll(self):
    allDevData = self.devGetAll()
    for dev in allDevData:
      print(dev['id'],dev['display_name'],dev['category'],dev['sub_category'])
      
  def testVnfDel(self):
    for dev in self.devGetAll():
      try:
        assert dev['category'] == 'VNF Device' and bool(dev['content']['user_imported'])
        assert re.search('^pensa-nodes-appliance-composite-root-TST_(VNF|VDU)_', dev['name']) is not None
        cmd = 'user_types_files/delete'
        self.request(cmd, {'name':dev['name']}, method='POST')
        self.devWaitComplete(self,[dev['id'],])
      except:
        pass
    for dev in self.devGetAll():
      try:
        assert bool(dev['content']['user_imported'])
        assert re.search('^pensa-nodes-appliance-composite-root-TST_(VNF|VDU)_', dev['name']) is not None
        cmd = 'devices/'+str(dev['id'])
        self.request(cmd, method='DELETE')
        self.devWaitComplete([dev['id'],])
      except:
        pass

  def clearAll(self):
#    cmdtDelAllSavedBoQ(cmdtServer,token)
    self.projDelAll()
    self.userVnfDelAll()
    self.infraDevDelAll()
  
  #----------VNFD/NSD----------
  def vnfdGet(self,name):
    cmd = 'user_types_files/?name='+name
    res = self.request(cmd)
    try:
      return res[0]['content']
    except:
      return None
    
  def nsdGet(self):
    pass
  
  #----------Rest API Data Templates----------
  
  # infrastructure devices
  TEMPLATE_INFRA_DEV = {}
  TEMPLATE_INFRA_DEV['compute'] =     {
        "category": "compute", 
        "rack_units": 1, 
        "vendor": "Nokia", 
        "dimensions": {
            "network": [
                {
                    "capacity": 10, 
                    "quantity": 1
                }
            ], 
            "power": {
                "max": 0, 
                "average": 0, 
                "idle": 0
            }, 
            "vcpu": 1, 
            "cpu_pinning": False, 
            "storage": 0, 
            "hyperthreading": True, 
            "sr_iov": False, 
            "memory_mts": 2133, 
            "memory": 0, 
            "mgmt_network": [
                {
                    "capacity": 1, 
                    "quantity": 1
                }
            ], 
            "dpdk": False
        },
        "price": 0,
        "part_number": "", 
        "popular_name": "", 
        "type": "HW"
  }
  
  TEMPLATE_INFRA_DEV['storage'] = {
        "category": "storage", 
        "rack_units": 1, 
        "vendor": "HP", 
        "dimensions": {
            "network": [
                {
                    "capacity": 10, 
                    "quantity": 1
                }
            ], 
            "power": {
                "max": 0, 
                "average": 0, 
                "idle": 0
            }, 
            "vcpu": 1, 
            "storage": 0, 
            "hyperthreading": True, 
            "memory_mts": 2133, 
            "memory": 0, 
            "ssd_storage": 0, 
            "mgmt_network": [
                {
                    "capacity": 1, 
                    "quantity": 1
                }
            ]
        },
        "price": 0,
        "part_number": "", 
        "popular_name": "", 
        "type": "HW"
  }
  TEMPLATE_INFRA_DEV['network'] = {
        "category": "network", 
        "rack_units": 1, 
        "vendor": "Nokia", 
        "dimensions": {
            "mgmt_network": [
                {
                    "capacity": 1, 
                    "quantity": 1
                }
            ], 
            "network": [
                {
                    "capacity": 10, 
                    "quantity": 1
                }
            ], 
            "power": {
                "max": 0, 
                "average": 0, 
                "idle": 0
            }
        },
        "price": 0,
        "part_number": "", 
        "popular_name": "", 
        "type": "HW"
  }
  
  TEMPLATE_INFRA_DEV['rack'] = {
        "category": "rack", 
        "rack_units": 42, 
        "vendor": "Nokia", 
        "part_number": "", 
        "popular_name": "", 
        "physical_dimensions": {
            "width": 600, 
            "depth": 3600, 
            "weight": 134, 
            "height": 1991
        },
        "price": 0
  }
  
  # VNF and VDU
  TEMPLATE_VDU = {
    "device_settings": {
        "properties": {
            "sub_category": {
                "constant": True, 
                "default": "VNF_TEST0001", 
                "display_order": "1.3", 
                "hidden": True, 
                "type": "string", 
                "order": 3
            }, 
            "north_south_bandwidth": {
                "description": "Maximum North South bandwidth in Gbps required by the application", 
                "default": 1, 
                "display_order": "2.4", 
                "type": "integer", 
                "order": 4, 
                "unit": "Gbps", 
                "gist": True
            }, 
            "memory_size": {
                "description": "Memory size in GigaBytes required by the VDU", 
                "default": 2, 
                "display_order": "2.2", 
                "type": "integer", 
                "order": 2, 
                "unit": "GB", 
                "gist": True
            },
            "physical": {
                "default": False, 
                "display_order": "1.0", 
                "type": "boolean"
            }, 
            "category": {
                "constant": True, 
                "default": "VNF Component Device", 
                "display_order": "1.2", 
                "hidden": True, 
                "type": "string", 
                "order": 2
            }, 
            "hyperthreading_needed": {
                "default": True, 
                "display_order": "2.7", 
                "type": "boolean", 
                "description": "Hyper Threading requirement of the VDU from the VIM. If the VIM does not support Hypher-threading, then this vm will not be placed in the VIM", 
                "order": 7
            }, 
            "version": {
                "display_order": "2.0", 
                "type": "string", 
                "hidden": True
            }, 
            "cpu_pinning_needed": {
                "default": False, 
                "display_order": "2.8", 
                "type": "boolean", 
                "description": "CPU Pinning requirement of the VDU from the VIM. If the VIM does not support CPU-Pinning, then this vm will not be placed in the VIM", 
                "order": 8
            },
            "vendor": {
                "default": "", 
                "display_order": "2.0", 
                "type": "string", 
                "hidden": True
            },
            "description": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "number_of_vCPU": {
                "description": "Number of logical CPUs required by the VDU", 
                "default": 1, 
                "display_order": "2.1", 
                "type": "integer", 
                "order": 1, 
                "gist": True
            },
            "sriov_dpdk_needed": {
                "default": False, 
                "display_order": "2.9", 
                "type": "boolean", 
                "description": "Accelaration support requirement of the VDU from the VIM. If the VIM does not support Accelaration, then this vm will not be placed in the VIM", 
                "order": 9
            }, 
            "name": {
                "constant": True, 
                "gist": True, 
                "default": "VDU_TEST0001", 
                "display_order": "1.1", 
                "hidden": True, 
                "type": "string", 
                "order": 1
            }, 
            "disk_size": {
                "description": "Root volume/disk size required in GigaBytes", 
                "default": 8, 
                "display_order": "2.3", 
                "type": "integer", 
                "order": 3, 
                "unit": "GB", 
                "gist": True
            }, 
            "east_west_bandwidth": {
                "description": "Maximum East West bandwidth in Gbps required by the application", 
                "default": 1, 
                "display_order": "2.5", 
                "type": "integer", 
                "order": 5, 
                "unit": "Gbps", 
                "gist": True
            }, 
            "cpu_affinity": {
                "description": "CPU affinity requirement. If it is core_affinity, always even number of vCPU will be allocated from VIM", 
                "default": "core_affinity", 
                "display_order": "2.9", 
                "type": "string", 
                "order": 9, 
                "constraints": [
                    {
                        "valid_values": [
                            "core_affinity", 
                            "cpu_affinity", 
                            "hyperthreaded_affinity"
                        ]
                    }
                ]
            }, 
        }
    }, 
    "device_lifecycle": [], 
    "deployment_settings": {
        "cloud-vmware-vsphere": {
            "image_type": "", 
            "artifact_url_list": [], 
            "artifact_url": "", 
            "name": "VMware vSphere Virtual Data Center", 
            "image_type_list": [
                "ZIP (OVF + VMDK)"
            ]
        }, 
        "cloud-aws-vpc": {
            "image_type": "", 
            "artifact_url_list": [], 
            "artifact_url": "", 
            "name": "Amazon Web Services VPC", 
            "image_type_list": []
        }, 
        "cloud-openstack-tenant": {
            "image_type": "", 
            "artifact_url_list": [], 
            "artifact_url": "", 
            "name": "OpenStack Private Cloud", 
            "image_type_list": [
                "ZIP (OVF + VMDK)", 
                "ZIP (QCOW2)"
            ]
        }
    }, 
    "type_name": "pensa.nodes.appliance.component.root", 
    "is_edit": False
}
  
  TEMPLATE_VNF = {
    "is_edit": False, 
    "device_lifecycle": [], 
    "deployment_settings": {
        "cloud-vmware-vsphere": {}, 
        "cloud-aws-vpc": {}, 
        "cloud-openstack-tenant": {}
    }, 
    "policies": [
        {
            "type": "pensa.policies.nfv.local_affinity", 
            "properties": {
                "scope": {
                    "default": "nfvi_node", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "constraints": [
                        {
                            "valid_values": [
                                "nfvi_node"
                            ]
                        }
                    ]
                }, 
                "name": {
                    "default": "Affinity Policy", 
                    "display_order": "2.0", 
                    "type": "string"
                }
            }, 
            "targets": [
                "GRP1"
            ]
        }
    ], 
    "groups": [
        {
            "type": "pensa.groups.nfv.ElementGroup", 
            "properties": {
                "name": {
                    "default": "GRP1", 
                    "display_order": "1.0", 
                    "type": "string"
                }
            }, 
            "members": [
                "VDU_1_1_0"
            ]
        }
    ], 
    "device_settings": {
        "attributes": {
            "instance_id": {
                "type": "string"
            }
        }, 
        "properties": {
            "category": {
                "constant": True, 
                "default": "VNF Device", 
                "display_order": "1.2", 
                "hidden": True, 
                "type": "string", 
                "order": 2
            }, 
            "descriptor_id": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "product_info_description": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "description": {
                "default": "DESC TST_VNF_001", 
                "display_order": "2.0", 
                "type": "string"
            }, 
            "software_version": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "default_localization_language": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "name": {
                "constant": True, 
                "gist": True, 
                "default": "TST_VNF_001", 
                "display_order": "1.1", 
                "hidden": True, 
                "type": "string", 
                "order": 1
            }, 
            "product_info_name": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "localization_languages": {
                "display_order": "2.0", 
                "type": "list", 
                "entry_schema": {
                    "type": "string"
                }
            }, 
            "label": {
                "display_order": "1.0", 
                "type": "string", 
                "gist": True, 
                "order": 0
            }, 
            "descriptor_version": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "instance_tag": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "provider": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "physical": {
                "default": False, 
                "display_order": "1.0", 
                "type": "boolean", 
                "hidden": True
            }, 
            "product_name": {
                "display_order": "2.0", 
                "type": "string"
            }, 
            "sub_category": {
                "constant": True, 
                "default": "PROJ1", 
                "display_order": "1.3", 
                "hidden": True, 
                "type": "string", 
                "order": 3
            }
        }
    }, 
    "type_name": "pensa.nodes.appliance.composite.root", 
    "component_links": [
        {
            "__gohashid": 17127, 
            "from": "vhcxtijt0scsvo6dbhroc9", 
            "to": "o3qy5gn2berszbu2kh995l"
        }
    ], 
    "components": [
        {
            "category": "VNF Component Device", 
            "loc": "254 114", 
            "name": "pensa-nodes-appliance-component-root-VDU_1_1", 
            "key": "o3qy5gn2berszbu2kh995l", 
            "__gohashid": 1457, 
            "properties": {
                "model_sku": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "instance_tag": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "vendor": {
                    "default": "", 
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "sub_category": {
                    "constant": True, 
                    "default": "TST_VNF_001", 
                    "display_order": "1.3", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 3
                }, 
                "initialization_settings": {
                    "default": {
                        "config_file": None, 
                        "configure_type": {
                            "type": "pensa.datatypes.host.configure_settings.ssh", 
                            "properties": {
                                "name": "ssh", 
                                "cli_prompt": "# "
                            }
                        }
                    }, 
                    "hidden": True, 
                    "type": "pensa.datatypes.host.configure_settings.VDU_1_1.initialization_settings", 
                    "display_order": "2.0", 
                    "properties": {
                        "config_file": {
                            "default": None, 
                            "display_order": "2.0", 
                            "type": "string"
                        }, 
                        "configure_type": {
                            "default": {
                                "type": "pensa.datatypes.host.configure_settings.ssh", 
                                "properties": {
                                    "cli_prompt": {
                                        "default": "# ", 
                                        "display_order": "2.0", 
                                        "type": "string"
                                    }, 
                                    "name": {
                                        "default": "ssh", 
                                        "display_order": "2.0", 
                                        "type": "string", 
                                        "primary_key": True
                                    }
                                }
                            }, 
                            "display_order": "2.0", 
                            "required": True, 
                            "type": "map", 
                            "copy_properties": True, 
                            "constraints": [
                                {
                                    "valid_values": [
                                        {
                                            "type": "pensa.datatypes.host.configure_settings.ssh", 
                                            "properties": {
                                                "cli_prompt": {
                                                    "default": "# ", 
                                                    "display_order": "2.0", 
                                                    "type": "string"
                                                }, 
                                                "name": {
                                                    "default": "ssh", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "primary_key": True
                                                }
                                            }
                                        }, 
                                        {
                                            "type": "pensa.datatypes.host.configure_settings.rest", 
                                            "properties": {
                                                "rest_authentication_method": {
                                                    "default": "Basic", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "constraints": [
                                                        {
                                                            "valid_values": [
                                                                "OAUTH", 
                                                                "OAUTH2", 
                                                                "XAUTH", 
                                                                "Basic"
                                                            ]
                                                        }
                                                    ]
                                                }, 
                                                "rest_endpoint_base_url": {
                                                    "display_order": "2.0", 
                                                    "required": True, 
                                                    "type": "string"
                                                }, 
                                                "rest_authentication_url": {
                                                    "display_order": "2.0", 
                                                    "type": "string"
                                                }, 
                                                "name": {
                                                    "default": "REST", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "primary_key": True
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }, 
                "model_subname": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "number_of_vCPU": {
                    "default": 1, 
                    "display_order": "2.1", 
                    "type": "integer", 
                    "gist": True, 
                    "order": 1
                }, 
                "product_url": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "bandwidth": {
                    "constant": True, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "description": "This is a Deprecated Property. This Property will be removed in Future Releases."
                }, 
                "north_south_bandwidth": {
                    "description": "Maximum North South bandwidth in Gbps required by the application", 
                    "default": 1, 
                    "display_order": "2.4", 
                    "type": "integer", 
                    "order": 4, 
                    "unit": "Gbps", 
                    "gist": True
                }, 
                "memory_size": {
                    "description": "Memory size in GigaBytes required by the VNF", 
                    "default": 2, 
                    "display_order": "2.2", 
                    "type": "integer", 
                    "order": 2, 
                    "unit": "GB", 
                    "gist": True
                }, 
                "credentials": {
                    "hidden": True, 
                    "type": "pensa.datatypes.host.credential.VDU_1_1.credentials", 
                    "display_order": "2.0", 
                    "properties": {
                        "username": {
                            "display_order": "2.0", 
                            "type": "string"
                        }, 
                        "ssh_tunnel_params": {
                            "display_order": "2.0", 
                            "type": "pensa.datatypes.ssh_tunnel_params.VDU_1_1.ssh_tunnel_params", 
                            "properties": {
                                "gateway_vm_prompt": {
                                    "default": "$ ", 
                                    "display_order": "2.0", 
                                    "type": "string"
                                }, 
                                "gateway_vm_key_path": {
                                    "hidden": True, 
                                    "type": "string", 
                                    "display_order": "2.0"
                                }, 
                                "localhost_key_path": {
                                    "display_order": "2.0", 
                                    "type": "string"
                                }, 
                                "remote_port": {
                                    "default": 22, 
                                    "display_order": "2.0", 
                                    "type": "integer"
                                }, 
                                "gateway_vm_login": {
                                    "display_order": "2.0", 
                                    "type": "string"
                                }, 
                                "gateway_vm_ip": {
                                    "display_order": "2.0", 
                                    "type": "ip_v4_address"
                                }, 
                                "gateway_vm_password": {
                                    "display_order": "2.0", 
                                    "type": "string"
                                }, 
                                "gate_vm_port": {
                                    "default": 22, 
                                    "display_order": "2.0", 
                                    "type": "integer"
                                }
                            }
                        }, 
                        "remote_port": {
                            "default": 22, 
                            "display_order": "2.0", 
                            "type": "integer"
                        }, 
                        "ssh_key_file": {
                            "display_order": "2.0", 
                            "type": "string"
                        }, 
                        "ssh_key_name": {
                            "display_order": "2.0", 
                            "type": "string"
                        }, 
                        "password": {
                            "display_order": "2.0", 
                            "type": "string"
                        }
                    }
                }, 
                "number_of_ports": {
                    "constant": True, 
                    "description": "This is a Deprecated Property. This Property will be removed in Future Releases.", 
                    "default": 1, 
                    "display_order": "2.6", 
                    "hidden": True, 
                    "type": "integer", 
                    "order": 6
                }, 
                "sriov_dpdk_needed": {
                    "default": False, 
                    "display_order": "2.9", 
                    "type": "boolean", 
                    "order": 9
                }, 
                "physical": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "1.0"
                }, 
                "category": {
                    "constant": True, 
                    "default": "VNF Component Device", 
                    "display_order": "1.2", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 2
                }, 
                "license": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "image_artifact": {
                    "hidden": True, 
                    "required": False, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "hyperthreading_needed": {
                    "default": False, 
                    "display_order": "2.7", 
                    "type": "boolean", 
                    "order": 7
                }, 
                "disk_size": {
                    "description": "Root volume/disk size required in GigaBytes", 
                    "default": 8, 
                    "display_order": "2.3", 
                    "type": "integer", 
                    "order": 3, 
                    "unit": "GB", 
                    "gist": True
                }, 
                "east_west_bandwidth": {
                    "description": "Maximum East West bandwidth in Gbps required by the application", 
                    "default": 1, 
                    "display_order": "2.5", 
                    "type": "integer", 
                    "order": 5, 
                    "unit": "Gbps", 
                    "gist": True
                }, 
                "instance_description": {
                    "default": "Virtual Network Function Mobility Component device", 
                    "display_order": "2.0", 
                    "type": "string"
                }, 
                "configure_settings": {
                    "default": {
                        "config_file": None, 
                        "configure_type": {
                            "type": "pensa.datatypes.host.configure_settings.ssh", 
                            "properties": {
                                "name": "ssh", 
                                "cli_prompt": "# "
                            }
                        }
                    }, 
                    "hidden": True, 
                    "type": "pensa.datatypes.host.configure_settings.VDU_1_1.configure_settings", 
                    "display_order": "2.0", 
                    "properties": {
                        "config_file": {
                            "default": None, 
                            "display_order": "2.0", 
                            "type": "string"
                        }, 
                        "configure_type": {
                            "default": {
                                "type": "pensa.datatypes.host.configure_settings.ssh", 
                                "properties": {
                                    "cli_prompt": {
                                        "default": "# ", 
                                        "display_order": "2.0", 
                                        "type": "string"
                                    }, 
                                    "name": {
                                        "default": "ssh", 
                                        "display_order": "2.0", 
                                        "type": "string", 
                                        "primary_key": True
                                    }
                                }
                            }, 
                            "display_order": "2.0", 
                            "required": True, 
                            "type": "map", 
                            "copy_properties": True, 
                            "constraints": [
                                {
                                    "valid_values": [
                                        {
                                            "type": "pensa.datatypes.host.configure_settings.ssh", 
                                            "properties": {
                                                "cli_prompt": {
                                                    "default": "# ", 
                                                    "display_order": "2.0", 
                                                    "type": "string"
                                                }, 
                                                "name": {
                                                    "default": "ssh", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "primary_key": True
                                                }
                                            }
                                        }, 
                                        {
                                            "type": "pensa.datatypes.host.configure_settings.rest", 
                                            "properties": {
                                                "rest_authentication_method": {
                                                    "default": "Basic", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "constraints": [
                                                        {
                                                            "valid_values": [
                                                                "OAUTH", 
                                                                "OAUTH2", 
                                                                "XAUTH", 
                                                                "Basic"
                                                            ]
                                                        }
                                                    ]
                                                }, 
                                                "rest_endpoint_base_url": {
                                                    "display_order": "2.0", 
                                                    "required": True, 
                                                    "type": "string"
                                                }, 
                                                "rest_authentication_url": {
                                                    "display_order": "2.0", 
                                                    "type": "string"
                                                }, 
                                                "name": {
                                                    "default": "REST", 
                                                    "display_order": "2.0", 
                                                    "type": "string", 
                                                    "primary_key": True
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }, 
                "name": {
                    "constant": True, 
                    "gist": True, 
                    "default": "VDU_1_1", 
                    "display_order": "1.1", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 1
                }, 
                "description": {
                    "default": "DESC VDU_1_1", 
                    "display_order": "2.0", 
                    "type": "string"
                }, 
                "label": {
                    "default": "VDU_1_1_0", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "gist": True, 
                    "order": 0
                }, 
                "instance_type": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0", 
                    "constraints": [
                        {
                            "valid_values": [
                                "m1.small", 
                                "m1.large", 
                                "m1.xlarge"
                            ]
                        }
                    ]
                }, 
                "version": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "cpu_pinning_needed": {
                    "default": False, 
                    "display_order": "2.8", 
                    "type": "boolean", 
                    "order": 8
                }, 
                "cpu_affinity": {
                    "default": "core_affinity", 
                    "display_order": "2.9", 
                    "type": "string", 
                    "order": 9, 
                    "constraints": [
                        {
                            "valid_values": [
                                "core_affinity", 
                                "cpu_affinity", 
                                "hyperthreaded_affinity"
                            ]
                        }
                    ]
                }, 
                "model_name": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }, 
                "vendor_url": {
                    "default": "www.XXXXXXXX.org", 
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "2.0"
                }
            }, 
            "sub_category": "TST_VNF_001"
        }, 
        {
            "category": "Network Objects", 
            "loc": "584 155", 
            "sub_category": "Ports", 
            "key": "vhcxtijt0scsvo6dbhroc9", 
            "__gohashid": 1542, 
            "properties": {
                "sub_category": {
                    "constant": True, 
                    "default": "Ports", 
                    "display_order": "1.3", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 3
                }, 
                "interface_type": {
                    "default": "uplink", 
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "constraints": [
                        {
                            "valid_values": [
                                "uplink", 
                                "internal"
                            ]
                        }
                    ]
                }, 
                "is_default": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "description": "Port to be associated to a default gateway for the  host that is bindable to the port"
                }, 
                "ip_address": {
                    "constant": True, 
                    "display_order": "3.0", 
                    "type": "ip_v4_address", 
                    "gist": True
                }, 
                "source_dest_check": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "3.0"
                }, 
                "physical": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "1.0"
                }, 
                "category": {
                    "constant": True, 
                    "default": "Network Objects", 
                    "display_order": "1.2", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 2
                }, 
                "ip_range_start": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "ip_range_end": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "name": {
                    "constant": True, 
                    "gist": True, 
                    "default": "External Port", 
                    "display_order": "1.1", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 1
                }, 
                "label": {
                    "default": "External Port_1", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "gist": True, 
                    "order": 0
                }, 
                "port_speed": {
                    "default": 1000, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "description": "Interface speed in Mbps"
                }, 
                "order": {
                    "default": 0, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "constraints": [
                        {
                            "greater_or_equal": 0
                        }
                    ]
                }
            }, 
            "name": "pensa-nodes-ExternalPort"
        }
    ], 
    "performence_flavours": [
        {
            "type": "pensa.datatypes.deployment.flavours.multivm_vnf", 
            "properties": {
                "scaling_aspects": {
                    "default": [
                        {
                            "type": "pensa.datatypes.deployment.scaling_aspects", 
                            "properties": {
                                "max_scale_level": 10, 
                                "associated_group": [
                                    "GRP1"
                                ], 
                                "description": "DESC1", 
                                "name": "SCALE_1"
                            }
                        }
                    ], 
                    "display_order": "2.0", 
                    "type": "list", 
                    "entry_schema": {
                        "type": "pensa.datatypes.deployment.scaling_aspects", 
                        "properties": {
                            "max_scale_level": {
                                "display_order": "2.0", 
                                "type": "integer"
                            }, 
                            "associated_group": {
                                "display_order": "2.0", 
                                "type": "list", 
                                "entry_schema": {
                                    "type": "string"
                                }, 
                                "defaults": [
                                    "GRP1"
                                ]
                            }, 
                            "description": {
                                "display_order": "2.0", 
                                "type": "string"
                            }, 
                            "name": {
                                "display_order": "2.0", 
                                "type": "string"
                            }
                        }
                    }
                }, 
                "instantiation_levels": {
                    "default": [
                        {
                            "type": "pensa.datatypes.deployment.instantiation_levels", 
                            "properties": {
                                "scale_info": [
                                    {
                                        "type": "pensa.datatypes.deployment.scale_info", 
                                        "properties": {
                                            "scale_aspect_name": "SCALE_1", 
                                            "scale_level": 2
                                        }
                                    }
                                ], 
                                "name": "INST_1", 
                                "vdu_level": [
                                    {
                                        "type": "pensa.datatypes.deployment.vdu_level", 
                                        "properties": {
                                            "number_of_instances": 2, 
                                            "vdu_name": "VDU_1_1_0"
                                        }
                                    }
                                ]
                            }
                        }
                    ], 
                    "display_order": "2.0", 
                    "type": "list", 
                    "entry_schema": {
                        "type": "pensa.datatypes.deployment.instantiation_levels", 
                        "properties": {
                            "assurance_param": {
                                "constant": True, 
                                "display_order": "2.0", 
                                "type": "pensa.datatypes.deployment.flavours.assurance_param", 
                                "gist": True, 
                                "properties": {}
                            }, 
                            "scale_info": {
                                "display_order": "2.0", 
                                "type": "list", 
                                "entry_schema": {
                                    "type": "pensa.datatypes.deployment.scale_info", 
                                    "properties": {
                                        "scale_aspect_name": {
                                            "display_order": "2.0", 
                                            "type": "string"
                                        }, 
                                        "scale_level": {
                                            "display_order": "2.0", 
                                            "type": "integer"
                                        }
                                    }
                                }
                            }, 
                            "name": {
                                "display_order": "2.0", 
                                "type": "string"
                            }, 
                            "vdu_level": {
                                "display_order": "2.0", 
                                "type": "list", 
                                "entry_schema": {
                                    "type": "pensa.datatypes.deployment.vdu_level", 
                                    "properties": {
                                        "number_of_instances": {
                                            "display_order": "2.0", 
                                            "type": "integer"
                                        }, 
                                        "vdu_name": {
                                            "display_order": "2.0", 
                                            "type": "string", 
                                            "constraints": [
                                                {
                                                    "valid_values": [
                                                        "VDU_1_1_0"
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }, 
                "default_instantiation_level": {
                    "default": "INST_1", 
                    "display_order": "2.0", 
                    "type": "string"
                }, 
                "name": {
                    "default": "INST_1", 
                    "display_order": "2.0", 
                    "type": "string", 
                    "gist": True
                }
            }
        }
    ]
  }
  
  
  TEMPLATE_VNF_POLICY_AFFINITY = {
            "type": "pensa.policies.nfv.local_affinity", 
            "properties": {
                "scope": {
                    "default": "nfvi_node", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "constraints": [
                        {
                            "valid_values": [
                                "nfvi_node"
                            ]
                        }
                    ]
                }, 
                "name": {
                    "default": "Affinity Policy", 
                    "display_order": "2.0", 
                    "type": "string"
                }
            }, 
            "targets": []
  }
  
  TEMPLATE_VNF_POLICY_ANTI_AFFINITY = {
            "type": "pensa.policies.nfv.local_anti_affinity", 
            "properties": {
                "scope": {
                    "default": "nfvi_node", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "constraints": [
                        {
                            "valid_values": [
                                "nfvi_node"
                            ]
                        }
                    ]
                }, 
                "name": {
                    "default": "Anti-Affinity Policy", 
                    "display_order": "2.0", 
                    "type": "string"
                }
            }, 
            "targets": []
  }
  
  TEMPLATE_VNF_POLICY_ANTI_AFFINITY_SCALE = {
            "type": "pensa.policies.nfv.local_scalable_anti_affinity", 
            "properties": {
                "scope": {
                    "default": "nfvi_node", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "constraints": [
                        {
                            "valid_values": [
                                "nfvi_node"
                            ]
                        }
                    ]
                }, 
                "name": {
                    "default": "Scalable Anti-Affinity Policy", 
                    "display_order": "2.0", 
                    "type": "string"
                },
                "no_of_instances": {
                    "default": 3,
                    "display_order": "2.0",
                    "type": "integer"
                }
            }, 
            "targets": []
  }
  
  TEMPLATE_EXPORT = {
            "category": "Network Objects", 
            "loc": "584 155", 
            "sub_category": "Ports", 
            "key": "vhcxtijt0scsvo6dbhroc9", 
#            "__gohashid": 1542, 
            "properties": {
                "sub_category": {
                    "constant": True, 
                    "default": "Ports", 
                    "display_order": "1.3", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 3
                }, 
                "interface_type": {
                    "default": "uplink", 
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "constraints": [
                        {
                            "valid_values": [
                                "uplink", 
                                "internal"
                            ]
                        }
                    ]
                }, 
                "is_default": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "description": "Port to be associated to a default gateway for the  host that is bindable to the port"
                }, 
                "ip_address": {
                    "constant": True, 
                    "display_order": "3.0", 
                    "type": "ip_v4_address", 
                    "gist": True
                }, 
                "source_dest_check": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "3.0"
                }, 
                "physical": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "1.0"
                }, 
                "category": {
                    "constant": True, 
                    "default": "Network Objects", 
                    "display_order": "1.2", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 2
                }, 
                "ip_range_start": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "ip_range_end": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "name": {
                    "constant": True, 
                    "gist": True, 
                    "default": "External Port", 
                    "display_order": "1.1", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 1
                }, 
                "label": {
                    "default": "External Port_1", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "gist": True, 
                    "order": 0
                }, 
                "port_speed": {
                    "default": 1000, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "description": "Interface speed in Mbps"
                }, 
                "order": {
                    "default": 0, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "constraints": [
                        {
                            "greater_or_equal": 0
                        }
                    ]
                }
            }, 
            "name": "pensa-nodes-ExternalPort"
  }

  TEMPLATE_PORT = {
            "category": "Network Objects", 
            "loc": "881 369", 
            "name": "pensa-nodes-port", 
            "key": "cqt9dil8pmprjw0aimfa", 
            "properties": {
                "sub_category": {
                    "constant": True, 
                    "default": "Ports", 
                    "display_order": "1.3", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 3
                }, 
                "interface_type": {
                    "default": "internal", 
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "constraints": [
                        {
                            "valid_values": [
                                "uplink", 
                                "internal"
                            ]
                        }
                    ]
                }, 
                "is_default": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0", 
                    "description": "Port to be associated to a default gateway for the  host that is bindable to the port"
                }, 
                "ip_address": {
                    "constant": True, 
                    "display_order": "3.0", 
                    "type": "ip_v4_address", 
                    "gist": True, 
                    "build_required": True
                }, 
                "source_dest_check": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "3.0"
                }, 
                "physical": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "1.0"
                }, 
                "category": {
                    "constant": True, 
                    "default": "Network Objects", 
                    "display_order": "1.2", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 2
                }, 
                "ip_range_start": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "ip_range_end": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "name": {
                    "constant": True, 
                    "gist": True, 
                    "default": "Port", 
                    "display_order": "1.1", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 1
                }, 
                "label": {
                    "default": "Port_5", 
                    "display_order": "1.0", 
                    "type": "string", 
                    "gist": True, 
                    "order": 0
                }, 
                "port_speed": {
                    "default": 1000, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "description": "Interface speed in Mbps"
                }, 
                "order": {
                    "default": 0, 
                    "hidden": True, 
                    "type": "integer", 
                    "display_order": "2.0", 
                    "constraints": [
                        {
                            "greater_or_equal": 0
                        }
                    ]
                }
            }, 
            "sub_category": "Ports"
        
  }

  TEMPLATE_NETWORK = {
            "category": "Network Objects", 
            "loc": "742 405", 
            "name": "pensa-nodes-network", 
            "key": "xrffjjxjg2np94vjc1tw", 
            "properties": {
                "sub_category": {
                    "constant": True, 
                    "default": "Networks", 
                    "display_order": "1.3", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 3
                }, 
                "is_management": {
                    "default": False, 
                    "constant": True, 
                    "display_order": "3.4", 
                    "type": "boolean", 
                    "order": 4
                }, 
                "ip_range": {
                    "hidden": True, 
                    "type": "list", 
                    "display_order": "3.0", 
                    "constraints": [
                        {
                            "max_length": 2
                        }
                    ]
                }, 
                "external_network": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "network_cidr": {
                    "constant": True, 
                    "display_order": "3.1", 
                    "type": "string", 
                    "order": 1, 
                    "build_required": True
                }, 
                "physical": {
                    "default": False, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "1.0"
                }, 
                "category": {
                    "constant": True, 
                    "default": "Network Objects", 
                    "display_order": "1.2", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 2
                }, 
                "name": {
                    "constant": True, 
                    "gist": True, 
                    "default": "IPv4 Network", 
                    "display_order": "1.1", 
                    "hidden": True, 
                    "type": "string", 
                    "order": 1
                }, 
                "network_id": {
                    "hidden": True, 
                    "type": "string", 
                    "display_order": "3.0"
                }, 
                "last_hop_to_external_network": {
                    "constant": True, 
                    "hidden": True, 
                    "type": "boolean", 
                    "display_order": "3.6", 
                    "order": 6
                }, 
                "label": {
                    "default": "IPv4 Network_3", 
                    "display_order": "1.1", 
                    "type": "string", 
                    "gist": True, 
                    "order": 1
                }, 
                "gateway_ip": {
                    "constant": True, 
                    "display_order": "3.2", 
                    "type": "string", 
                    "order": 2, 
                    "build_required": True
                }, 
                "ip_dhcp_managed": {
                    "display_order": "3.5", 
                    "type": "boolean", 
                    "order": 5
                }, 
                "is_external_network": {
                    "display_order": "3.3", 
                    "type": "boolean", 
                    "order": 3
                }
            }, 
            "sub_category": "Networks"
  }
  
  TEMPLATE_SITE = {
    "description": "TST_SITE_1", 
    "migrate": None, 
    "building_status": 0, 
    "visibility": 1, 
    "running_traffic_status": 0, 
    "validation_status": 0, 
    "design_errors": None, 
    "validation_errors": None, 
    "name": "TST_SITE_1", 
    "roles": {
        "designer": [
            "admin", 
            "automation"
        ], 
        "modeler": [
            "admin", 
            "automation"
        ], 
        "reporter": [
            "admin", 
            "automation"
        ]
    }, 
    "design_data": "{\"nodes\":[],\"relationships\":[]}", 
    "project": 1, 
    "draft": "[[],[]]"
  }

  TEMPLATE_SITE_DRAFT_CLOUD = {
  #            "group": "zvcvxyy3qbe48fnhtwoz5b", 
            "key": "uwbhej7znshx7grtfl6rdo", 
            "id": "pensa-nodes-cloud-openstack-tenant_",
            "category": "Cloud", 
            "sub_category": "Private Clouds",
            "loc": "191 160", 
            "name": "pensa-nodes-cloud-openstack-tenant", 
            "isGroup": True, 
            "currentSelectedVPCNetwork": "cmdt_vpc_cidr:172.21.0.0/16", 
            "size": "500 500"
  }

  TEMPLATE_SITE_DRAFT_VNF = {
            "category": "VNF Device", 
            "loc": "246 234.08037109375", 
            "group": "rudutwkl5cmmoph5g0tpbd", 
            "name": "pensa-nodes-appliance-composite-root-TST_VNF_002", 
            "key": "99v5mqpadd5oyi3t83xlh", 
            "id": "pensa-nodes-appliance-composite-root-TST_VNF_002_99v5mqpadd5oyi3t83xlh_0", 
            "sub_category": "TST_PROJ_1"
  }

  TEMPLATE_SITE_DRAFT_NETWORK = {        
            "category": "Network Objects",
            "sub_category": "Networks",
            "loc": "146 96.08037109374999", 
            "group": "rudutwkl5cmmoph5g0tpbd", 
            "name": "pensa-nodes-network", 
            "key": "7oou3jfuzifkxm3beig2j", 
            "id": "pensa-nodes-network_7oou3jfuzifkxm3beig2j_0", 
  }

  TEMPLATE_SITE_DRAFT_L3_LINK = {
            "subCategory": "L3", 
            "key": "pensa-relationships-network-connects_to_",
            "from": "5xumjqwpxwp45agc8xremz", 
            "to": "7oou3jfuzifkxm3beig2j", 
            "fromPort": "pensa-nodes-ExternalPort_",
            "toPort": "pensa-nodes-network_",
  }

  TEMPLATE_SITE_DESIGN_REL = {
            "id": "pensa-relationships-network_hosted_on_997wv0xefyg0qvffyw5h8ib", 
            "source": "pensa-nodes-vpc_network_uwbhej7znshx7grtfl6rdo_0", 
            "type": "pensa-relationships-network_hosted_on", 
            "requirement_name": "network_host", 
            "target": "pensa-nodes-cloud-openstack-tenant_uwbhej7znshx7grtfl6rdo_0"
  }

  TEMPLATE_SITE_DESIGN_NODE_TENANT = {
        "group": "", 
        "uiProperties": {}, 
        "capabilities": {}, 
        "id": "pensa-nodes-cloud-openstack-tenant_mhbpgl9drripmhygwp6jpw_0", 
        "isGroup": True, 
        "deployment": {}, 
        "device_name": "pensa-nodes-cloud-openstack-tenant", 
        "properties": {
            "category": "Cloud", 
            "cloud_type": "openstack", 
            "sub_category": "Private Clouds", 
            "zone": "zone1", 
            "name": "OpenStack Private Cloud", 
            "cloud_service_provider": "private", 
            "label": "OpenStack Private Cloud_0", 
            "zone_info_id": "nova", 
            "credentials": {
                "ssh_tunnel_params": {
                    "gateway_vm_prompt": "$ ", 
                    "gate_vm_port": 22, 
                    "remote_port": 22
                }
            }, 
            "private_cloud": True, 
            "physical": False, 
            "description": "Tenant in an OpenStack Private Cloud"
        }
  }

  TEMPLATE_SITE_DESIGN_NODE_VPC = {
        "group": "mhbpgl9drripmhygwp6jpw", 
        "uiProperties": {
            "locUseIPAM": False
        }, 
        "capabilities": {}, 
        "id": "pensa-nodes-vpc_network_mhbpgl9drripmhygwp6jpw_0", 
        "isGroup": False, 
        "deployment": {}, 
        "device_name": "pensa-nodes-vpc_network", 
        "properties": {
            "network_cidr": "172.21.0.0/16", 
            "physical": False, 
            "name": "VPC Network", 
            "label": "VPC Network_0"
        }
  }

  TEMPLATE_SITE_DESIGN_NODE_NEUTRON = {
        "group": "mhbpgl9drripmhygwp6jpw", 
        "uiProperties": {}, 
        "capabilities": {}, 
        "id": "pensa-nodes-application-sdn-neutron_mhbpgl9drripmhygwp6jpw_0", 
        "isGroup": False, 
        "deployment": {}, 
        "device_name": "pensa-nodes-application-sdn-neutron", 
        "properties": {
            "category": "SDN Controller", 
            "physical": False, 
            "sub_category": "SDN Controller", 
            "name": "Openstack Neutron Controller", 
            "label": "Openstack Neutron Controller_0"
        }
  }

  TEMPLATE_SITE_DESIGN_NODE_VNF = {
            "group": "rudutwkl5cmmoph5g0tpbd", 
            "uiProperties": {}, 
            "capabilities": {}, 
            "id": "pensa-nodes-appliance-composite-root-TST_VNF_001_5xumjqwpxwp45agc8xremz_0", 
            "isGroup": False, 
            "deployment": {}, 
            "device_name": "pensa-nodes-appliance-composite-root-TST_VNF_001", 
            "properties": {
                "category": "VNF Device", 
                "sub_category": "TST_PROJ_1", 
                "description": "TST_VNF_001", 
                "label": "TST_VNF_001_0", 
                "components": [], 
                "physical": False, 
                "name": "TST_VNF_001"
            }
  }

  TEMPLATE_SITE_DESIGN_NODE_EXPORT = {
    "group": "sasaorzi5cm6wi1kd85id", 
    "uiProperties": {}, 
    "capabilities": {}, 
    "id": "pensa-nodes-ExternalPort_yr58t3yz5jhawj48217miv_0", 
    "isGroup": False, 
    "deployment": {}, 
    "device_name": "pensa-nodes-ExternalPort", 
    "properties": {
        "category": "Network Objects", 
        "sub_category": "Ports", 
        "name": "External Port", 
        "interface_type": "uplink", 
        "label": "External Port_0", 
        "port_speed": 1000, 
        "order": 0, 
        "source_dest_check": False, 
        "physical": False
    }
  }

  TEMPLATE_SITE_DESIGN_NODE_NETWORK = {
            "group": "8w7h48ekrhe1d20wr1kc8a", 
            "uiProperties": {}, 
            "capabilities": {}, 
            "id": "pensa-nodes-network_23ij2gs5i5rnds29muzdem_0", 
            "isGroup": False, 
            "deployment": {}, 
            "device_name": "pensa-nodes-network", 
            "properties": {
                "category": "Network Objects", 
                "network_cidr": "192.168.1.0/24", 
                "physical": False, 
                "sub_category": "Networks", 
                "label": "IPv4 Network_0", 
                "is_management": False, 
                "name": "IPv4 Network"
            }
  }

  TEMPLATE_SCN_VDULEVEL = {
    "application_kpis": None, 
    "user_id": 5, 
    "vdu_levels": None, 
    "description": "TST_SCN_201", 
    "site_id": "6", 
    "vnf_flavours": None, 
    "other_kpis": {
        'cost': {
            'type': "number",
            'unit': "USD"
        },
        'lead_time': {
            'type': "number",
            'unit': "Days"
        }
    }, 
    "name": "TST_SCN_201"
  }
  
  