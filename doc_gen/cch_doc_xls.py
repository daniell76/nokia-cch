import math
from libXls import *
from copy import deepcopy
import datetime
import json
import re
import collections

class CCH_DOC_XLS(object):
  def __init__(self,filename=None,data_only=True):
    self.title = {}
    self.wb = openpyxl.load_workbook(filename, data_only=data_only)
    self.customTable = {}
    self.loadTable()
  
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
  
  def loadTable(self):
    for wsName in self.wb.get_sheet_names():
      m = re.search('^Table-.+\s*$', wsName)
      if m is None: continue
      self.customTable[wsName] = {}
      self.customTable[wsName]['ws'] = self.wb[wsName]
      self.customTable[wsName]['title'] = self.readTitle(wsName)
      self.customTable[wsName]['body'] = []
      for n in range(2,self.customTable[wsName]['ws'].max_row+1):
        d = self.readRow(wsName, n)
        self.customTable[wsName]['body'].append(d)
      # remove empty lines in the end
      dz = {}
      for k in self.customTable[wsName]['title']: dz[k] = None
      while self.customTable[wsName]['body'][-1] == dz:
        self.customTable[wsName]['body'].pop()

class CCH_PARAM_XLS(CCH_DOC_XLS):
  
  def __init__(self,filename=None,data_only=True):
    super(CCH_PARAM_XLS,self).__init__(filename,data_only)
    self.param = {}
    
  def parse(self):
    # Read Tab 'parameters'
    self.readTitle('parameters')
    for r in range(2,self.wb['parameters'].max_row+1):
      d = self.readRow('parameters',r)
      try:
        self.param[d['Parameter_Category']]
      except:
        self.param[d['Parameter_Category']] = {}
      self.param[d['Parameter_Category']][d['Parameter_Name']] = d['Value']
    
    # Sanity Check some values
    try:
      assert self.param['Generic']['DocumentDate'] is not None
    except:
      self.param['Generic']['DocumentDate'] = datetime.datetime.now().strftime('%Y-%b-%d')

class CCH_CONTENT_XLS(CCH_DOC_XLS):
  
  def __init__(self,filename=None,data_only=True):
    super(CCH_CONTENT_XLS,self).__init__(filename,data_only)
    self.contents = {}
    
  def parse(self):
    self.readTitle('contents')
    for r in range(2,self.wb['contents'].max_row+1):
      d = self.readRow('contents',r)
      try:
        self.contents[d['Section']]
      except:
        self.contents[d['Section']] = {}
        self.contents[d['Section']]['Title'] = d['Title']
        self.contents[d['Section']]['Paragraphs'] = []
      self.contents[d['Section']]['Paragraphs']
      p = {}
      p['Condition'] = d['Condition']
      try:
        assert d['Bullet'] == 'Y' or d['Bullet'] == 'y'
        p['Bullet'] = True
      except:
        p['Bullet'] = False
      p['Contents'] = d['Contents']
      self.contents[d['Section']]['Paragraphs'].append(p)      
      