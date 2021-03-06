import sys
import urllib, urllib2
import logging
from dbs.apis.dbsClient import DbsApi
#import reqMgrClient
import httplib
import os
import json 
from collections import defaultdict
import random
from xml.dom.minidom import getDOMImplementation
import copy 
import pickle
import itertools
import time
import math 

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email.utils import make_msgid


FORMAT = "%(module)s.%(funcName)s(%(lineno)s) => %(message)s (%(asctime)s)"
DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format = FORMAT, datefmt = DATEFMT, level=logging.DEBUG)


def sendEmail( subject, text, sender=None, destination=None ):
    #print subject
    #print text
    #print sender
    #print destination
    
    if not destination:
        destination = ['vlimant@cern.ch','matteoc@fnal.gov']
    else:
        destination = list(set(destination+['vlimant@cern.ch','matteoc@fnal.gov']))
    if not sender:
        map_who = { 'vlimant' : 'vlimant@cern.ch',
                    'mcremone' : 'matteoc@fnal.gov' }
        user = os.getenv('USER')
        if user in map_who:
            sender = map_who[user]
        else:
            sender = 'vlimant@cern.ch'

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = COMMASPACE.join( destination )
    msg['Date'] = formatdate(localtime=True)
    new_msg_ID = make_msgid()  
    msg['Subject'] = '[Ops] '+subject
    msg.attach(MIMEText(text))
    smtpObj = smtplib.SMTP()
    smtpObj.connect()
    smtpObj.sendmail(sender, destination, msg.as_string())
    smtpObj.quit()


def url_encode_params(params = {}):
    """
    encodes given parameters dictionary. Dictionary values
    can contain list, in that case, encoded params will look
    like this: param=val1&param=val2...
    """
    params_list = []
    for key, value in params.items():
        if isinstance(value, list):
            params_list.extend([(key, x) for x in value])
        else:
            params_list.append((key, value))
    return urllib.urlencode(params_list)

def download_data(url = None, params = None, headers = None, logger = None):
    """
    Returns data got from server.
    params has to be a dictionary, which can contain 
    "key : [value1, value2,...], and that will be 
    converted to key=value1&key=value2&... 
    """
    if not logger:
        logger = logging
    try:
        if params:
            params = url_encode_params(params)
            url = "{url}?{params}".format(url = url, params = params)
        response = urllib2.urlopen(url)
        data = response.read()
        return data
    except urllib2.HTTPError as err:
        error = "{msg} (HTTP Error: {code})"
        logger.error(error.format(code = err.code, msg = err.msg))
        logger.error("URL called: {url}".format(url = url))
        return None
        
def download_file(url, params, path = None, logger = None):
    if not logger:
        logger = logging
    if params:
        params = url_encode_params(params)
        url = "{url}?{params}".format(url = url, params = params)
    logger.debug(url)
    try:
        filename, message = urllib.urlretrieve(url)
        return filename
    except urllib2.HTTPError as err:
        error = "{msg} (HTTP Error: {code})"
        logger.error(error.format(code = err.code, msg = err.msg))
        logger.error("URL called: {url}".format(url = url))
        return None

def GET(url, there, l=True):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    if l:
        return json.loads(r2.read())
    else:
        return r2

def check_ggus( ticket ):
    conn  =  httplib.HTTPSConnection('ggus.eu', cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/index.php?mode=ticket_info&ticket_id=%s&writeFormat=XML'%ticket)
    r2=conn.getresponse()
    print r2
    return False

def getSubscriptions(url, dataset):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/phedex/datasvc/json/prod/subscriptions?dataset='+dataset 
    r1=conn.request("GET", there)
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']
    return items

def listRequests(url, dataset, site=None):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/phedex/datasvc/json/prod/requestlist?dataset='+dataset
    r1=conn.request("GET", there)
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['request']
    res= defaultdict(list)
    for item in items:
        for node in item['node']:
            if site and node['name']!=site: continue
            if not item['id'] in res[node['name']]:
                res[node['name']].append(item['id'])
    for s in res:
        res[s] = sorted(res[s])
    return dict(res)

def listCustodial(url, site='T1_*MSS'):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/phedex/datasvc/json/prod/requestlist?node=%s&decision=pending'%site
    r1=conn.request("GET", there)
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['request']
    res= defaultdict(list)
    for item in items:
        if item['type'] != 'xfer': continue
        for node in item['node']:
            if not item['id'] in res[node['name']]:
                res[node['name']].append(item['id'])
    for s in res:
        res[s] = sorted(res[s])
    return dict(res)

def listDelete(url, user, site=None):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/phedex/datasvc/json/prod/requestlist?type=delete&approval=pending&requested_by=%s'% user
    if site:
        there += 'node=%s'% ','.join(site)
    r1=conn.request("GET", there)

    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['request']
    #print json.dumps(items, indent=2)
    
    return list(itertools.chain.from_iterable([(subitem['name'],item['requested_by'],item['id']) for subitem in item['node'] if subitem['decision']=='pending' ] for item in items))

def listSubscriptions(url, dataset, within_sites=None):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?dataset=%s'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['request']
    destinations ={}
    deletes = defaultdict(int)
    for item in items:
        for node in item['node']:
            site = node['name']
            if item['type'] == 'delete' and node['decision'] in [ 'approved','pending']:
                deletes[ site ] = max(deletes[ site ], node['time_decided'])

    for item in items:
        for node in item['node']:
            if item['type']!='xfer': continue
            site = node['name']            
            if within_sites and not site in within_sites: continue
            #print item
            if not 'MSS' in site:
                ## pending delete
                if site in deletes and not deletes[site]: continue
                ## delete after transfer
                #print  node['time_decided'],site
                if site in deletes and deletes[site] > node['time_decided']: continue

                destinations[site]=(item['id'], node['decision']=='approved')
                #print node['name'],node['decision']
                #print node
    #print destinations
    return destinations

import dataLock

class newLockInfo:
    def __init__(self):
        self.db = json.loads(open('/afs/cern.ch/user/c/cmst2/www/unified/globallocks.json').read())
        os.system('echo `date` > /afs/cern.ch/user/c/cmst2/www/unified/globallocks.json.lock')

    def __del__(self):
        open('/afs/cern.ch/user/c/cmst2/www/unified/globallocks.json.new','w').write(json.dumps( sorted(list(set(self.db))) , indent=2 ))
        os.system('mv /afs/cern.ch/user/c/cmst2/www/unified/globallocks.json.new /afs/cern.ch/user/c/cmst2/www/unified/globallocks.json')
        os.system('rm -f /afs/cern.ch/user/c/cmst2/www/unified/globallocks.json.lock')

    def lock(self, dataset):
        print "[new lock]",dataset,"to be locked"
        # just put the 
        if dataset in self.db:
            print "\t",dataset,"was already locked"
        else:
            self.db.append(dataset)

    def release(self, dataset):
        print "[new lock] should never release datasets"
        return
        if not dataset in self.db:
            print "\t",dataset,"was not locked already"
        else:
            self.db.remove( dataset )
        


class lockInfo:
    def __init__(self):
        pass

    def __del__(self):
        if random.random() < 0.5:
            print "Cleaning locks"
            #self.clean_block()
            self.clean_unlock()
            print "... cleaning locks done"

        jdump = {}
        for l in dataLock.locksession.query(dataLock.Lock).all():
            ## don't print lock=False ??
            #if not l.lock: continue 
            site= l.site
            if not site in jdump: jdump[site] = {}
            jdump[site][l.item] = { 
                'lock' : l.lock,
                'time' : l.time,
                'date' : time.asctime( time.gmtime(l.time) ),
                'reason' : l.reason
                }
        now = time.mktime(time.gmtime())
        jdump['lastupdate'] = now
        open('/afs/cern.ch/user/c/cmst2/www/unified/datalocks.json.new','w').write( json.dumps( jdump , indent=2))
        os.system('mv /afs/cern.ch/user/c/cmst2/www/unified/datalocks.json.new /afs/cern.ch/user/c/cmst2/www/unified/datalocks.json')

    def _lock(self, item, site, reason):
        print "[lock] of %s at %s because of %s"%( item, site, reason )
        now = time.mktime(time.gmtime())
        l = dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.site == site).filter(dataLock.Lock.item == item).first()
        if not l:
            l = dataLock.Lock(lock=False)
            l.site = site
            l.item = item
            l.is_block = '#' in item
            dataLock.locksession.add ( l )
        if l.lock:
            print l.item,item,"already locked at",site
        
        ## overwrite the lock 
        l.reason = reason
        l.time = now
        l.lock = True
        dataLock.locksession.commit()

    def lock(self, item, site, reason):
        try:
            self._lock( item, site, reason)
        except Exception as e:
            ## to be removed once we have a fully functional lock db
            print "could not lock",item,"at",site
            print str(e)
            
    def _release(self, item, site, reason='releasing'):
        print "[lock release] of %s at %s because of %s" %( item, site, reason)
        now = time.mktime(time.gmtime())
        # get the lock on the item itself
        l = dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.site==site).filter(dataLock.Lock.item==item).first()
        if not l:
            print item,"was not locked at",site
            l = dataLock.Lock(lock=False)
            l.site = site
            l.item = item
            l.is_block = '#' in item
            dataLock.locksession.add ( l )
            dataLock.locksession.commit()
            
        #then unlock all of everything starting with item (itself for block, all block for dataset)
        for l in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.site==site).filter(dataLock.Lock.item.startswith(item)).all():
            l.time = now
            l.reason = reason
            l.lock = False
        dataLock.locksession.commit()

    def release_except(self, item, except_site, reason='releasing'):
        print "[lock release] of %s except at %s because of %s" %( item, except_site, reason)
        try:
            for l in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.item.startswith(item)).all():
                site = l.site
                if not site in except_site:
                    self._release(l.item, site, reason)
                else:
                    print "We are told to not release",item,"at site",site,"per request of",except_site
        except Exception as e:
            print "could not unlock",item,"everywhere but",except_site
            print str(e)

    def release_everywhere(self, item, reason='releasing'):
        print "[lock release] of %s everywhere because of %s" % ( item, reason )
        try:
            for l in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.item.startswith(item)).all():
                site = l.site
                self._release(item, site, reason)
        except Exception as e:
            print "could not unlock",item,"everywhere"
            print str(e)

    def release(self, item, site, reason='releasing'):
        print "[lock release] of %s at %s because of %s" %( item, site, reason)
        try:
            self._release(item, site, reason)
        except Exception as e:
            print "could not unlock",item,"at",site
            print str(e)

    def tell(self, comment):
        print "---",comment,"---"
        for l in dataLock.locksession.query(dataLock.Lock).all():
            print l.item,l.site,l.lock
        print "------"+"-"*len(comment)

    def clean_block(self, view=False):
        print "start cleaning lock info"
        ## go and remove all blocks for which the dataset is specified
        # if the dataset is locked, nothing matters for blocks -> remove
        # if the dataset is unlocked, it means we don't want to keep anything of it -> remove
        clean_timeout=0
        for l in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.lock==True).filter(dataLock.Lock.is_block==False).all():
            site = l.site
            item = l.item
            if view:  print item,"@",site
            ## get all the blocks at that site, for that dataset, under the same condition
            for block in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.site==site).filter(dataLock.Lock.item.startswith(item)).filter(dataLock.Lock.is_block==True).all():
                print "removing lock item for",block.item,"at",site,"due to the presence of overriding dataset information"
                dataLock.locksession.delete( block )
                clean_timeout+=1
                if view: print block.name
                if clean_timeout> 10:                    break
            dataLock.locksession.commit()
            if clean_timeout> 10:                break

    def clean_unlock(self, view=False):
        clean_timeout=0
        ## go and remove all items that have 'lock':False
        for l in dataLock.locksession.query(dataLock.Lock).filter(dataLock.Lock.lock==False).all():
            print "removing lock=false for",l.item,"at",l.site
            dataLock.locksession.delete( l )            
            clean_timeout+=1
            #if clean_timeout> 10:                break

        dataLock.locksession.commit()

class unifiedConfiguration:
    def __init__(self):
        self.configs = json.loads(open('/afs/cern.ch/user/c/cmst2/Unified/WmAgentScripts/unifiedConfiguration.json').read())
        
    def get(self, parameter):
        if parameter in self.configs:
            return self.configs[parameter]['value']
        else:
            print parameter,'is not defined in global configuration'
            print ','.join(self.configs.keys()),'possible'
            sys.exit(124)

def checkDownTime():
    conn  =  httplib.HTTPSConnection('cmsweb.cern.ch', cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/couchdb/reqmgr_workload_cache/jbadillo_BTV-RunIISpring15MiniAODv2-00011_00081_v0__151030_162715_5312')
    r2=conn.getresponse()
    r = r2.read()
    if r2.status ==503:#if 'The site you requested is not unavailable' in r:
        return True
    else:
        return False

class componentInfo:
    def __init__(self, block=True, mcm=False,soft=None):
        self.mcm = mcm
        self.soft = soft
        self.block = block
        self.status ={
            'reqmgr' : False,
            'mcm' : False,
            'dbs' : False,
            'phedex' : False
            }
        self.code = 0
        #if not self.check():
        #    sys.exit( self.code)
        

    def check(self):
        try:
            print "checking reqmgr"
            wfi = workflowInfo('cmsweb.cern.ch','pdmvserv_task_B2G-RunIIWinter15wmLHE-00067__v1_T_150505_082426_497')
            self.status['reqmgr'] = True
        except Exception as e:
            self.tell('reqmgr')
            print "cmsweb.cern.ch unreachable"
            print str(e)
            if self.block and not (self.soft and 'reqmgr' in self.soft):
                self.code = 123
                return False

        from McMClient import McMClient

        if self.mcm:
            try:
                mcmC = McMClient(dev=False)
                print "checking mcm"
                test = mcmC.getA('requests',page=0)
                time.sleep(1)
                if not test: 
                    self.tell('mcm')
                    print "mcm corrupted"
                    if self.block and not (self.soft and 'mcm' in self.soft):
                        self.code = 124
                        return False
                else:
                    self.status['mcm'] = True
            except Exception as e:
                self.tell('mcm')
                print "mcm unreachable"
                print str(e)
                if self.block and not (self.soft and 'mcm' in self.soft):
                    self.code = 125
                    return False
        
        try:
            print "checking dbs"
            dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
            blocks = dbsapi.listBlockSummaries( dataset = '/TTJets_mtop1695_TuneCUETP8M1_13TeV-amcatnloFXFX-pythia8/RunIIWinter15GS-MCRUN2_71_V1-v1/GEN-SIM', detail=True)
            if not blocks:
                self.tell('dbs')
                print "dbs corrupted"
                if self.block and not (self.soft and 'dbs' in self.soft):
                    self.code = 126
                    return False

        except Exception as e:
            self.tell('dbs')
            print "dbs unreachable"
            print str(e)
            if self.block and not (self.soft and 'dbs' in self.soft):
                self.code = 127
                return False

        try:
            print "checking phedex"
            cust = findCustodialLocation('cmsweb.cern.ch','/TTJets_mtop1695_TuneCUETP8M1_13TeV-amcatnloFXFX-pythia8/RunIIWinter15GS-MCRUN2_71_V1-v1/GEN-SIM')
            
        except Exception as e:
            self.tell('phedex')
            print "phedex unreachable"
            print str(e)
            if self.block and not (self.soft and 'phedex' in self.soft):
                self.code = 128
                return False

        return True

    def tell(self, c):
        sendEmail("%s Component Down"%c,"The component is down, just annoying you with this","vlimant@cern.ch",['vlimant@cern.ch','matteoc@fnal.gov'])

class campaignInfo:
    def __init__(self):
        #this contains accessor to aggreed campaigns, with maybe specific parameters
        self.campaigns = json.loads(open('/afs/cern.ch/user/c/cmst2/Unified/WmAgentScripts/campaigns.json').read())
        SI = siteInfo()
        for c in self.campaigns:
            if 'parameters' in self.campaigns[c]:
                if 'SiteBlacklist' in self.campaigns[c]['parameters']:
                    for black in copy.deepcopy(self.campaigns[c]['parameters']['SiteBlacklist']):
                        if black.endswith('*'):
                            self.campaigns[c]['parameters']['SiteBlacklist'].remove( black )
                            reg = black[0:-1]
                            self.campaigns[c]['parameters']['SiteBlacklist'].extend( [site for site in (SI.all_sites) if site.startswith(reg)] )
                            #print self.campaigns[c]['parameters']['SiteBlacklist']
                            
    def go(self, c):
        if c in self.campaigns and self.campaigns[c]['go']:
            return True
        else:
            print "Not allowed to go for",c
            return False
    def get(self, c, key, default):
        if c in self.campaigns:
            if key in self.campaigns[c]:
                return copy.deepcopy(self.campaigns[c][key])
        return copy.deepcopy(default)

    def parameters(self, c):
        if c in self.campaigns and 'parameters' in self.campaigns[c]:
            return self.campaigns[c]['parameters']
        else:
            return {}

def notRunningBefore( component, time_out = 60*5 ):
    s = 10
    while True:
        if time_out<0:
            print "Could not wait any longer for %s to finish"% component
            return False
        process_check = filter(None,os.popen('ps -f -e | grep %s.py | grep -v grep  |grep python'%component).read().split('\n'))
        if len(process_check):
            ## there is still the component running. wait
            time.sleep(s)
            time_out-=s
            continue
        break
    return True


def duplicateLock(component=None):
    if not component:
        ## get the caller
        component = sys._getframe(1).f_code.co_name

    ## check that no other instances of assignor is running
    process_check = filter(None,os.popen('ps -f -e | grep %s.py | grep -v grep  |grep python'%component).read().split('\n'))
    if len(process_check)>1:
        ## another component is running on the machine : stop
        sendEmail('overlapping %s'%component,'There are %s instances running %s'%(len(process_check), '\n'.join(process_check)))
        print "quitting because of overlapping processes"
        return True
    return False

    
def userLock(component=None):
    if not component:  
        ## get the caller
        component = sys._getframe(1).f_code.co_name        
    lockers = ['dmytro','mcremone','vlimant']
    for who in lockers:
        if os.path.isfile('/afs/cern.ch/user/%s/%s/public/ops/%s.lock'%(who[0],who,component)):
            print "disabled by",who
            return True
    return False

class docCache:
    def __init__(self):
        self.cache = {}
        def default_expiration():
            return 20*60+random.random()*10*60
        self.cache['ssb_106'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=106&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_107'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=107&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_108'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=108&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_109'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=109&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_136'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=136&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_158'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=158&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_159'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=159&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['ssb_160'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl -s --retry 5 "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=160&batch=1&lastdata=1"').read())['csvdata'],
            'cachefile' : None,
            'default' : []
            }
        self.cache['gwmsmon_totals'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl --retry 5 -s http://cms-gwmsmon.cern.ch/scheddview/json/totals').read()),
            'cachefile' : None,
            'default' : {}
            }
        self.cache['gwmsmon_prod_site_summary' ] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl --retry 5 -s http://cms-gwmsmon.cern.ch/prodview//json/site_summary').read()),
            'cachefile' : None,
            'default' : {}
            }
        self.cache['gwmsmon_site_summary' ] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads(os.popen('curl --retry 5 -s http://cms-gwmsmon.cern.ch/totalview//json/site_summary').read()),
            'cachefile' : None,
            'default' : {}
            }
        self.cache['detox_sites'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : os.popen('curl --retry 5 -s http://t3serv001.mit.edu/~cmsprod/IntelROCCS/Detox/SitesInfo.txt').read().split('\n'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_DE_KIT_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_DE_KIT_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_US_FNAL_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_US_FNAL_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_ES_PIC_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_ES_PIC_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_UK_RAL_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_UK_RAL_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_IT_CNAF_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_IT_CNAF_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_FR_CCIN2P3_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_FR_CCIN2P3_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T1_RU_JINR_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T1_RU_JINR_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['T0_CH_CERN_MSS_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : getNodeUsage('cmsweb.cern.ch','T0_CH_CERN_MSS'),
            'cachefile' : None,
            'default' : ""
            }
        self.cache['mss_usage'] = {
            'data' : None,
            'timestamp' : time.mktime( time.gmtime()),
            'expiration' : default_expiration(),
            'getter' : lambda : json.loads( os.popen('curl -s --retry 5 http://cmsmonitoring.web.cern.ch/cmsmonitoring/StorageOverview/latest/StorageOverview.json').read()),
            'cachefile' : None,
            'default' : {}
            }

        #create the cache files from the labels
        for src in self.cache:
            self.cache[src]['cachefile'] = '.'+src+'.cache.json'
            

    def get(self, label, fresh=False):
        now = time.mktime( time.gmtime())
        if label in self.cache:
            try:
                cache = self.cache[label]
                if not cache['data']:
                    #check the file version
                    if os.path.isfile(cache['cachefile']):
                        print "load",label,"from file",cache['cachefile']
                        f_cache = json.loads(open(cache['cachefile']).read())
                        cache['data' ] = f_cache['data']
                        cache['timestamp' ] = f_cache['timestamp']
                    else:
                        print "no file cache for", label,"getting fresh"
                        cache['data'] = cache['getter']()
                        cache['timestamp'] = now
                        open(cache['cachefile'],'w').write( json.dumps({'data': cache['data'], 'timestamp' : cache['timestamp']}, indent=2) )
                    
                ## check the time stamp
                if cache['expiration']+cache['timestamp'] < now or fresh:
                    print "getting fresh",label
                    cache['data'] = cache['getter']()
                    cache['timestamp'] = now
                    open(cache['cachefile'],'w').write( json.dumps({'data': cache['data'], 'timestamp' : cache['timestamp']}, indent=2) )

                return cache['data']
            except Exception as e: 
                print "failed to get",label
                print str(e)
                return copy.deepcopy(cache['default'])

def getNodes(url, kind):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/nodes')
    r2=conn.getresponse()
    result = json.loads(r2.read())
    return [node['name'] for node in result['phedex']['node'] if node['kind']==kind]

def getNodeUsage(url, node):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/nodeusage?node=%s'%node)
    r2=conn.getresponse()
    result = json.loads(r2.read())
    if len(result['phedex']['node']):
        s= max([sum([node[k] for k in node.keys() if k.endswith('_node_bytes')]) for node in result['phedex']['node']])
        return int(s / 1023.**4) #in TB
    else:
        return None

dataCache = docCache()

class siteInfo:
    def __init__(self):
        
        try:
            ## get all sites from SSB readiness
            self.sites_ready = []
            self.sites_not_ready = []
            self.all_sites = []
            
            self.sites_banned = [
                #'T2_CH_CERN_HLT',
                'T0_CH_CERN_MSS'
                ]

            data = dataCache.get('ssb_158') ## 158 is the site readyness metric
            for siteInfo in data:
                #print siteInfo['Status']
                self.all_sites.append( siteInfo['VOName'] )
                if siteInfo['VOName'] in self.sites_banned: continue
                if not siteInfo['Tier'] in [1,2]: continue
                if siteInfo['Status'] == 'on': 
                    self.sites_ready.append( siteInfo['VOName'] )
                else:#if siteInfo['Status'] in ['drain']:
                    self.sites_not_ready.append( siteInfo['VOName'] )

            
        except Exception as e:
            print "issue with getting SSB readiness"
            print str(e)
            sendEmail('bad sites configuration','falling to get any sites')
            sys.exit(-9)

        self.sites_auto_approve = ['T0_CH_CERN_MSS','T1_FR_CCIN2P3_MSS']

        self.sites_eos = [ s for s in self.sites_ready if s in ['T2_CH_CERN','T2_CH_CERN_AI','T2_CH_CERN_T0','T2_CH_CERN_HLT'] ]
        self.sites_T2s = [ s for s in self.sites_ready if s.startswith('T2_')]
        self.sites_T1s = [ s for s in self.sites_ready if s.startswith('T1_')]
        self.sites_with_goodIO = [ "T2_DE_DESY","T2_DE_RWTH",
                                   "T2_ES_CIEMAT",
                                   "T2_FR_GRIF_LLR", "T2_FR_GRIF_IRFU", "T2_FR_IPHC","T2_FR_CCIN2P3",
                                   "T2_IT_Bari", "T2_IT_Legnaro", "T2_IT_Pisa", "T2_IT_Rome",
                                   "T2_UK_London_Brunel", "T2_UK_London_IC", "T2_UK_SGrid_RALPP",
                                   "T2_US_Caltech","T2_US_MIT","T2_US_Nebraska","T2_US_Purdue","T2_US_UCSD","T2_US_Wisconsin","T2_US_Florida",
                                   "T2_BE_IIHE",
                                   "T2_EE_Estonia",
                                   ## to be tried out "T2_PL_Swierk"
                                   "T2_CH_CERN","T2_CH_CERN_HLT","T2_CH_CERN_AI"
                                   ]
        self.sites_with_goodIO = [s for s in self.sites_with_goodIO if s in self.sites_ready]
        allowed_T2_for_transfer = ["T2_DE_RWTH","T2_DE_DESY", 
                                   #not inquired# "T2_ES_CIEMAT",
                                   #no space# ##"T2_FR_GRIF_IRFU", #not inquired# ##"T2_FR_GRIF_LLR", #not inquired"## "T2_FR_IPHC",##not inquired"## "T2_FR_CCIN2P3",
                                   "T2_IT_Legnaro", "T2_IT_Pisa", "T2_IT_Rome", "T2_IT_Bari",
                                   "T2_UK_London_Brunel", "T2_UK_London_IC", "T2_UK_SGrid_RALPP",
                                   "T2_US_Nebraska","T2_US_Wisconsin","T2_US_Purdue","T2_US_Caltech", "T2_US_Florida", "T2_US_UCSD", "T2_US_MIT",
                                   "T2_BE_IIHE",
                                   "T2_EE_Estonia",
                                   "T2_CH_CERN", 
                                   
                                   ]
        allowed_T2_for_transfer = [s for s in allowed_T2_for_transfer if s in self.sites_ready]
        self.sites_veto_transfer = [site for site in self.sites_with_goodIO if not site in allowed_T2_for_transfer]

        self.storage = defaultdict(int)
        self.disk = defaultdict(int)
        self.quota = defaultdict(int)
        self.locked = defaultdict(int)
        self.cpu_pledges = defaultdict(int)
        self.addHocStorage = {
            'T2_CH_CERN_T0': 'T2_CH_CERN',
            'T2_CH_CERN_HLT' : 'T2_CH_CERN',
            'T2_CH_CERN_AI' : 'T2_CH_CERN'
            }
        ## list here the site which can accomodate high memory requests
        self.sites_memory = {}

        for s in self.all_sites:
            ## will get it later from SSB
            self.cpu_pledges[s]=1
            ## will get is later from SSB
            self.disk[ self.CE_to_SE(s)]=0

        tapes = getNodes('cmsweb.cern.ch', 'MSS')
        for mss in tapes:
            if mss in self.sites_banned: continue # not using these tapes for MC familly
            self.storage[mss] = 0

        ## and get SSB sync
        self.fetch_ssb_info(talk=False)
        

        mss_usage = dataCache.get('mss_usage')
        for mss in self.storage:
            #used = dataCache.get(mss+'_usage')
            #print mss,'used',used
            #if used == None: self.storage[mss] = 0
            #else:  self.storage[mss] = max(0, self.storage[mss]-used)
            if not mss in mss_usage['Tape']['Free']: self.storage[mss] = 0 
            else: self.storage[mss]  = mss_usage['Tape']['Free'][mss]

        ## and detox info
        self.fetch_detox_info(talk=False)
        
        ## transform no disks in veto transfer
        for (dse,free) in self.disk.items():
            if free<=0:
                if not dse in self.sites_veto_transfer:
                    self.sites_veto_transfer.append( dse )

        ## and glidein info
        self.fetch_glidein_info(talk=False)

    def usage(self,site):
        try:
            info = json.loads( os.popen('curl -s "http://dashb-cms-job.cern.ch/dashboard/request.py/jobsummary-plot-or-table2?site=%s&check=submitted&sortby=activity&prettyprint"' % site ).read() )
            return info
        except:
            return {}
        
    def availableSlots(self, sites=None):
        s=0
        for site in self.cpu_pledges:
            if sites and not site in sites: continue
            s+=self.cpu_pledges[site]
        return s

    def getRemainingDatasets(self, site):
        start_reading=False
        datasets=[]
        s=0
        for line in os.popen('curl -s http://t3serv001.mit.edu/~cmsprod/IntelROCCS/Detox/result/%s/RemainingDatasets.txt'%site).read().split("\n"):
            if 'DDM Partition: DataOps' in line:
                start_reading=True
                continue

            if start_reading:
                splt=line.split()
                if len(splt)==5 and splt[-1].count('/')==3:
                    (_,size,_,_,dataset) = splt
                    size= float(size)
                    #print dataset
                    s+=size
                    datasets.append( (size,dataset) )
            if start_reading and 'DDM Partition' in line:
                break

        #print s
        return datasets
                    
    def fetch_glidein_info(self, talk=True):
        self.sites_memory = dataCache.get('gwmsmon_totals')

        for_max_running = dataCache.get('gwmsmon_site_summary')
        for site in self.cpu_pledges:
            if not site in for_max_running: continue
            new_max = int(for_max_running[site]['MaxWasRunning'] * 0.70) ## put a fudge factor
            if new_max > self.cpu_pledges[site]:
                #print "could raise",site,"from",self.cpu_pledges[site],"to",for_max_running[site]['MaxWasRunning']
                #print "raising",site,"from",self.cpu_pledges[site],"to",new_max
                self.cpu_pledges[site] = new_max
        
        for_site_pressure = dataCache.get('gwmsmon_prod_site_summary')
        self.sites_pressure = {}
        for site in self.sites_ready:
            pressure = 0
            m = 0
            r = 0
            if site in for_site_pressure:
                m = for_site_pressure[site]['MatchingIdle']
                r = for_site_pressure[site]['Running']
                if not r: r = 1
                pressure = m /float(r)
            ## ~1 = equilibrium
            ## < 1 : no pressure, running with low matching
            ## > 1 : pressure, plenty of matching
            self.sites_pressure[site] = (m, r, pressure)



        #try:
        #    self.sites_memory = json.loads(os.popen('curl --retry 5 -s http://cms-gwmsmon.cern.ch/scheddview/json/totals').read())
        #except:
        #    self.sites_memory = {}

    def sitesByMemory( self, maxMem, maxCore=1):
        if not self.sites_memory:
            print "no memory information from glidein mon"
            return None
        allowed = set()
        for site,slots in self.sites_memory.items():
            if any([slot['MaxMemMB']>= maxMem and slot['MaxCpus']>=maxCore for slot in slots]):
                allowed.add(site)
        return list(allowed)

    def restrictByMemory( self, maxMem, allowed_sites):
        allowed = self.sitesByMemory(maxMem)
        if allowed!=None:
            return list(set(allowed_sites) & set(allowed))
        return allowed_sites

    def fetch_detox_info(self, talk=True):
        ## put a retry in command line
        info = dataCache.get('detox_sites')
        #info = os.popen('curl --retry 5 -s http://t3serv001.mit.edu/~cmsprod/IntelROCCS/Detox/SitesInfo.txt').read().split('\n')
        if len(info) < 15: 
            ## fall back to dev
            info = dataCache.get('detox_sites', fresh = True)
            #info = os.popen('curl --retry 5 -s http://t3serv001.mit.edu/~cmsprod/IntelROCCS-Dev/DetoxDataOps/SitesInfo.txt').read().split('\n')
            if len(info) < 15:
                print "detox info is gone"
                return
        pcount = 0
        read = False
        for line in info:
            if 'Partition:' in line:
                read = ('DataOps' in line)
                continue
            if line.startswith('#'): continue
            if not read: continue
            _,quota,taken,locked,site = line.split()
            available = int(quota) - int(locked)
            if available >0:
                self.disk[site] = available
            else:
                self.disk[site] = 0 
            self.quota[site] = quota
            self.locked[site] = locked


    def fetch_ssb_info(self,talk=True):
        ## and complement information from ssb
        columns= {
            'PledgeTape' : 107,
            'realCPU' : 136,
            'prodCPU' : 159,
            'CPUbound' : 160,
            'FreeDisk' : 106,
            #'UsedTape' : 108,
            #'FreeTape' : 109
            }
        
        all_data = {}
        for name,column in columns.items():
            if talk: print name,column
            try:
                #data = json.loads(os.popen('curl -s "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=%s&batch=1&lastdata=1"'%column).read())
                #all_data[name] =  data['csvdata']
                all_data[name] =  dataCache.get('ssb_%d'% column) #data['csvdata']
            except:
                print "cannot get info from ssb for",name
        _info_by_site = {}
        for info in all_data:
            for item in all_data[info]:
                site = item['VOName']
                if site.startswith('T3'): continue
                value = item['Value']
                if not site in _info_by_site: _info_by_site[site]={}
                _info_by_site[site][info] = value
        
        if talk: print json.dumps( _info_by_site, indent =2 )

        if talk: print self.disk.keys()
        for (site,info) in _info_by_site.items():
            if talk: print "\n\tSite:",site
            ssite = self.CE_to_SE( site )
            tsite = site+'_MSS'
            #key_for_cpu ='prodCPU'
            key_for_cpu ='CPUbound'
            if key_for_cpu in info and site in self.cpu_pledges and info[key_for_cpu]:
                if self.cpu_pledges[site] < info[key_for_cpu]:
                    if talk: print site,"could use",info[key_for_cpu],"instead of",self.cpu_pledges[site],"for CPU"
                    self.cpu_pledges[site] = int(info[key_for_cpu])
                elif self.cpu_pledges[site] > 1.5* info[key_for_cpu]:
                    if talk: print site,"could correct",info[key_for_cpu],"instead of",self.cpu_pledges[site],"for CPU"
                    self.cpu_pledges[site] = int(info[key_for_cpu])                    

            if 'FreeDisk' in info and info['FreeDisk']:
                if site in self.disk:
                    if self.disk[site] < info['FreeDisk']:
                        if talk: print site,"could use",info['FreeDisk'],"instead of",self.disk[site],"for disk"
                        self.disk[site] = int(info['FreeDisk'])
                else:
                    if not ssite in self.disk:
                        if talk: print "setting",info['FreeDisk']," disk for",ssite
                        self.disk[ssite] = int(info['FreeDisk'])

            if 'FreeDisk' in info and site!=ssite and info['FreeDisk']:
                if ssite in self.disk:
                    if self.disk[ssite] < info['FreeDisk']:
                        if talk: print ssite,"could use",info['FreeDisk'],"instead of",self.disk[ssite],"for disk"
                        self.disk[ssite] = int(info['FreeDisk'])
                else:
                    if talk: print "setting",info['FreeDisk']," disk for",ssite
                    self.disk[ssite] = int(info['FreeDisk'])

            #if 'FreeTape' in info and 'UsedTape' in info and tsite in self.storage and info['FreeTape']:
            #    if info['UsedTape'] and self.storage[tsite] < info['FreeTape']:
            #        if talk: print tsite,"could use",info['FreeTape'],"instead of",self.storage[tsite],"for tape"
            #        self.storage[tsite] = int(info['FreeTape'])
            #if 'PledgeTape' in info and tsite in self.storage:
            #     self.storage[tsite] = int(info['PledgeTape'])


    def types(self):
        return ['sites_with_goodIO','sites_T1s','sites_T2s']#,'sites_veto_transfer']#,'sites_auto_approve']

    def CE_to_SE(self, ce):
        if ce.startswith('T1') and not ce.endswith('_Disk'):
            return ce+'_Disk'
        else:

            if ce in self.addHocStorage:
                return self.addHocStorage[ce]
            else:
                return ce

    def SE_to_CE(self, se):
        if se.endswith('_Disk'):
            return se.replace('_Disk','')
        elif se.endswith('_MSS'):
            return se.replace('_MSS','')
        else:
            return se

    def pick_SE(self, sites=None, size=None): ## size needs to be in TB
        if size:
            return self._pick(sites, dict([(se,free) for (se,free) in self.storage.items() if free>size]))
        else:
            return self._pick(sites, self.storage)

    def pick_dSE(self, sites=None):
        return self._pick(sites, self.disk, and_fail=True)

    def _pick(self, sites, from_weights, and_fail=True):
        r_weights = {}
        if sites:
            for site in sites:
                if site in from_weights or and_fail:
                    r_weights[site] = from_weights[site]
                else:
                    r_weights = from_weights
                    break
        else:
            r_weights = from_weights

        return r_weights.keys()[self._weighted_choice_sub(r_weights.values())]

    def _weighted_choice_sub(self,ws):
        rnd = random.random() * sum(ws)
        #print ws
        for i, w in enumerate(ws):
            rnd -= w
            if rnd <= 0:
                return i
        print "could not make a choice from ",ws,"and",rnd
        return None


    def pick_CE(self, sites):
        #print len(sites),"to pick from"
        #r_weights = {}
        #for site in sites:
        #    r_weights[site] = self.cpu_pledges[site]
        #return r_weights.keys()[self._weighted_choice_sub(r_weights.values())]
        return self._pick(sites, self.cpu_pledges)



class closeoutInfo:
    def __init__(self):
        self.record = json.loads(open('closedout.json').read())

    def table_header(self):
        text = '<table border=1><thead><tr><th>workflow</th><th>OutputDataSet</th><th>%Compl</th><th>acdc</th><th>Dupl</th><th>CorrectLumis</th><th>Scubscr</th><th>Tran</th><th>dbsF</th><th>dbsIF</th><th>\
phdF</th><th>ClosOut</th></tr></thead>'
        return text

    def one_line(self, wf, wfo, count):
        if count%2:            color='lightblue'
        else:            color='white'
        text=""
        try:
            pid = filter(lambda b :b.count('-')==2, wf.split('_'))[0]
            tpid = 'task_'+pid if 'task' in wf else pid
        except:
            wl = getWorkLoad('cmsweb.cern.ch', wf)
            pid =wl['PrepID']
            tpid=wl['PrepID']
            
        ## return the corresponding html
        order = ['percentage','acdc','duplicate','correctLumis','missingSubs','phedexReqs','dbsFiles','dbsInvFiles','phedexFiles']
        wf_and_anchor = '<a id="%s">%s</a>'%(wf,wf)
        for out in self.record[wf]['datasets']:
            text+='<tr bgcolor=%s>'%color
            text+='<td>%s<br><a href=https://cmsweb.cern.ch/reqmgr/view/details/%s>dts</a>, <a href=https://cmsweb.cern.ch/reqmgr/view/splitting/%s>splt</a>, <a href=https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/%s>perf</a>, <a href=https://dmytro.web.cern.ch/dmytro/cmsprodmon/workflows.php?prep_id=%s>ac</a>, <a href=assistance.html#%s>%s</a></td>'% (wf_and_anchor,
                                                                                                                                                                                                                                                                                                                            wf, wf, wf,tpid,wf,
                                                                                                                                                                                                                                                                                                                            wfo.status)

            text+='<td>%s</td>'% out
            for f in order:
                if f in self.record[wf]['datasets'][out]:
                    value = self.record[wf]['datasets'][out][f]
                else:
                    value = "-NA-"
                if f =='acdc':
                    text+='<td><a href=https://cmsweb.cern.ch/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byprepid?key="%s">%s</a></td>'%(tpid , value)
                else:
                    text+='<td>%s</td>'% value
            text+='<td>%s</td>'%self.record[wf]['closeOutWorkflow']
            text+='</tr>'
            wf_and_anchor = wf

        return text

    def html(self):
        self.summary()
        self.assistance()

    def summary(self):
        os.system('cp closedout.json closedout.json.last')
        
        html = open('/afs/cern.ch/user/c/cmst2/www/unified/closeout.html','w')
        html.write('<html>')
        html.write('Last update on %s(CET), %s(GMT), <a href=logs/checkor/ target=_blank> logs</a> <br><br>'%(time.asctime(time.localtime()),time.asctime(time.gmtime())))

        html.write( self.table_header() )

        from assignSession import session, Workflow
        for (count,wf) in enumerate(sorted(self.record.keys())):
            wfo = session.query(Workflow).filter(Workflow.name == wf).first()
            if not wfo: continue
            if not (wfo.status == 'away' or wfo.status.startswith('assistance')):
                print "Taking",wf,"out of the close-out record"
                self.record.pop(wf)
                continue
            html.write( self.one_line( wf, wfo , count) )

        html.write('</table>')
        html.write('<br>'*100) ## so that the anchor works ok
        html.write('bottom of page</html>')

        open('closedout.json','w').write( json.dumps( self.record , indent=2 ) )

    def assistance(self):
        from assignSession import session, Workflow
        wfs = session.query(Workflow).filter(Workflow.status.startswith('assistance')).all()

        short_html = open('/afs/cern.ch/user/c/cmst2/www/unified/assistance_summary.html','w')
        html = open('/afs/cern.ch/user/c/cmst2/www/unified/assistance.html','w')
        html.write("""
<html>
<head>
<META HTTP-EQUIV="refresh" CONTENT="900">
</head>
""")
        short_html.write("""
<html>
<head>
<META HTTP-EQUIV="refresh" CONTENT="900">
</head>
""")
    
        short_html.write('Last update on %s(CET), %s(GMT), <a href=logs/checkor/last.log target=_blank> log</a> <a href=logs/recoveror/last.log target=_blank> postlog</a> <br>'%(time.asctime(time.localtime()),time.asctime(time.gmtime())))
        html.write('Last update on %s(CET), %s(GMT), <a href=logs/checkor/last.log target=_blank> log</a> <a href=logs/recoveror/last.log target=_blank> postlog</a><br>'%(time.asctime(time.localtime()),time.asctime(time.gmtime())))

        html.write('<a href=assistance_summary.html> Summary </a> <br>')    
        short_html.write('<a href=assistance.html> Details </a> <br>')

        assist = defaultdict(list)
        for wfo in wfs:
            assist[wfo.status].append( wfo )
        

        for status in sorted(assist.keys()):
            html.write("Workflow in status <b> %s </b> (%d)"% (status, len(assist[status])))
            html.write( self.table_header())
            short_html.write("""
Workflow in status <b> %s </b>
<table border=1>
<thead>
<tr>
<th> workflow </th> <th> output dataset </th><th> completion </th>
</tr>
</thead>
"""% (status))
            for (count,wfo) in enumerate(assist[status]):
                if count%2:            color='lightblue'
                else:            color='white'
                if not wfo.name in self.record: 
                    print "wtf with",wfo.name
                    continue            
                html.write( self.one_line( wfo.name, wfo, count))
                for out in self.record[wfo.name]['datasets']:
                    short_html.write("""
<tr bgcolor=%s>
<td> <a id=%s>%s</a> </td><td> %s </td><td> <a href=closeout.html#%s>%s</a> </td>
</tr>
"""%( color, 
      wfo.name,wfo.name,
      out, 
      wfo.name,
      self.record[wfo.name]['datasets'][out]['percentage'],
      
      ))
            html.write("</table><br><br>")
            short_html.write("</table><br><br>")

        short_html.write("<br>"*100)
        short_html.write("bottom of page</html>")    
        html.write("<br>"*100)
        html.write("bottom of page</html>")    


global_SI = siteInfo()
def getSiteWhiteList( inputs , pickone=False):
    SI = global_SI
    (lheinput,primary,parent,secondary) = inputs
    sites_allowed=[]
    if lheinput:
        sites_allowed = ['T2_CH_CERN'] ## and that's it
    elif secondary:
        sites_allowed = list(set(SI.sites_T1s + SI.sites_with_goodIO))
    elif primary:
        sites_allowed =list(set( SI.sites_T1s + SI.sites_T2s ))
    else:
        # no input at all
        sites_allowed =list(set( SI.sites_T2s + SI.sites_T1s))

    if pickone:
        sites_allowed = [SI.pick_CE( sites_allowed )]

    return sites_allowed
    
def checkTransferApproval(url, phedexid):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?request='+str(phedexid))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['request']
    approved={}
    for item in items:
        for node in item['node']:
            approved[node['name']] = (node['decision']=='approved')
    return approved

def findLostBlocks(url, dataset):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))

    r1=conn.request("GET",'/phedex/datasvc/json/prod/subscriptions?block=%s%%23*&collapse=n'% dataset)
    r2=conn.getresponse()
    result = json.loads(r2.read())
    lost = []
    for dataset in result['phedex']['dataset']:
        for item in dataset['block']:
            exist=0
            for loc in item['subscription']:
                exist = max(exist, loc['percent_bytes'])
            if not exist:
                #print "We have lost:",item['name']
                #print json.dumps( item, indent=2)
                lost.append( item )
    return lost

def checkTransferLag( url, xfer_id , datasets=None):
    try:
        v = try_checkTransferLag( url, xfer_id , datasets)
    except:
        try:
            time.sleep(1)
            v = try_checkTransferLag( url, xfer_id , datasets)
        except Exception as e:
            print "fatal execption in checkTransferLag\n","%s\n%s\n%s"%(xfer_id,datasets,str(e))
            sendEmail('fatal execption in checkTransferLag',"%s\n%s\n%s"%(xfer_id,datasets,str(e)))
            v = {}
    return v

def try_checkTransferLag( url, xfer_id , datasets=None):
    ## xfer_id tells us what has to go where via subscriptions
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    #r1=conn.request("GET",'/phedex/datasvc/json/prod/subscriptions?request=%s'%(str(xfer_id)))
    #r2=conn.getresponse()
    #result = json.loads(r2.read())
    #timestamp = result['phedex']['request_timestamp']
    r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?request='+str(xfer_id))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    timecreate=min([r['time_create'] for r in result['phedex']['request']])
    subs_url = '/phedex/datasvc/json/prod/subscriptions?request=%s&create_since=%d'%(str(xfer_id),timecreate)
    subs_url+='&collapse=n'
    r1=conn.request("GET",subs_url)
    r2=conn.getresponse()
    result = json.loads(r2.read())

    now = time.mktime( time.gmtime() )
    #print result
    stuck = defaultdict(lambda : defaultdict(lambda : defaultdict(tuple)))
    if len(result['phedex']['dataset'])==0:
        print "trying with an earlier date than",timecreate,"for",xfer_id
        subs_url = '/phedex/datasvc/json/prod/subscriptions?request=%s&create_since=%d'%(str(xfer_id),0)
        subs_url+='&collapse=n' 
        r1=conn.request("GET",subs_url)
        r2=conn.getresponse()
        result = json.loads(r2.read())

    for item in  result['phedex']['dataset']:
        if 'subscription' not in item:            
            #print "sub"
            loop_on = list(itertools.chain.from_iterable([[(subitem['name'],i) for i in subitem['subscription']] for subitem in item['block']]))
        else:
            #print "no sub"
            loop_on = [(item['name'],i) for i in item['subscription']]
        #print loop_on
        for item,sub in loop_on:
            if datasets and not item in datasets: continue
            if sub['percent_files']!=100:
                destination = sub['node']
                time_then = sub['time_create']
                delay = (now - time_then)/(60.*60.*24.)
                delay_s = (now - time_then)
                print "\n",item,"is not complete at",destination,"since", delay ,"[d]"
                
                if '#' in item:
                    item_url = '/phedex/datasvc/json/prod/blockreplicas?block=%s'%( item.replace('#','%23') )
                else:
                    item_url = '/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%( item )
                r1=conn.request("GET",item_url)
                r2=conn.getresponse()    
                item_result = json.loads(r2.read()) 

                for subitem in item_result['phedex']['block']:
                    dones = [replica['node'] for replica in subitem['replica'] if replica['complete'] == 'y']
                    if not dones: 
                        print "\t\t",subitem['name'],"lost"
                        continue
                    block_size = max([replica['bytes'] for replica in subitem['replica']])
                    ssitems = [replica['bytes'] for replica in subitem['replica'] if replica['node']==destination]
                    destination_size = min(ssitems) if ssitems else 0
                    block_size_GB = block_size / (1024.**3)
                    destination_size_GB = destination_size / (1024.**3)
                    ### rate
                    rate = destination_size_GB / delay_s
                    if destination in dones: continue
                    if delay>0: # more than 7 days is way to much !!
                        print subitem['name'],' of size',block_size_GB,'[GB] missing',block_size_GB-destination_size_GB,'[GB]'
                        print '\tis complete at',dones
                        print "\tincoming at",rate,"[GB/s]"
                    if rate < 10:
                        stuck[item][subitem['name']][destination] = (block_size,destination_size,delay,rate,dones)
                        
    return stuck

def checkTransferStatus(url, xfer_id, nocollapse=False):
    try:
        v = try_checkTransferStatus(url, xfer_id, nocollapse=False)
    except:
        try:
            time.sleep(1)
            v = try_checkTransferStatus(url, xfer_id, nocollapse=False)
        except Exception as e:
            print srt(e)
            sendEmail('fatal execption in checkTransferStatus',str(e))
            v = {}
    return v
        

def try_checkTransferStatus(url, xfer_id, nocollapse=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))

    r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?request='+str(xfer_id))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    timecreate=min([r['time_create'] for r in result['phedex']['request']])
    subs_url = '/phedex/datasvc/json/prod/subscriptions?request=%s&create_since=%d'%(str(xfer_id),timecreate)
    if nocollapse:
        subs_url+='&collapse=n'
    r1=conn.request("GET",subs_url)
    r2=conn.getresponse()
    result = json.loads(r2.read())

    #print result
    completions={}
    if len(result['phedex']['dataset'])==0:
        print "trying with an earlier date than",timecreate,"for",xfer_id
        subs_url = '/phedex/datasvc/json/prod/subscriptions?request=%s&create_since=%d'%(str(xfer_id),0)
        r1=conn.request("GET",subs_url)
        r2=conn.getresponse()
        result = json.loads(r2.read())

    for item in  result['phedex']['dataset']:
        completions[item['name']]={}
        if 'subscription' not in item:            
            loop_on = list(itertools.chain.from_iterable([subitem['subscription'] for subitem in item['block']]))
        else:
            loop_on = item['subscription']
        for sub in loop_on:
            if not sub['node'] in completions[item['name']]:
                completions[item['name']][sub['node']] = []
            if sub['percent_bytes']:
                #print sub
                #print sub['node'],sub['percent_files']
                completions[item['name']] [sub['node']].append(float(sub['percent_files']))
            else:
                completions[item['name']] [sub['node']].append(0.)
        
    for item in completions:
        for site in completions[item]:
            ## average it !
            completions[item][site] = sum(completions[item][site]) / len(completions[item][site])

    #print result
    """
    completions={}
    ## that level of completion is worthless !!!!
    # falling back to dbs
    print result
    if not len(result['phedex']['dataset']):
        print "no data at all"
        print result
    for item in  result['phedex']['dataset']:
        dsname = item['name']
        #print dsname
        completions[dsname]={}
        presence = getDatasetPresence(url, dsname)
        for sub in item['subscription']:
            #print sub
            site = sub['node']
            if site in presence:
                completions[dsname][site] = presence[site][1]
            else:
                completions[dsname][site] = 0.
    """

    #print completions
    return completions

def findCustodialCompletion(url, dataset):
    return findCustodialLocation(url, dataset, True)

def findCustodialLocation(url, dataset, with_completion=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    request=result['phedex']
    if 'block' not in request.keys():
        return [],None
    if len(request['block'])==0:
        return [],None
    cust=[]
    #veto = ["T0_CH_CERN_MSS"]
    veto = []
    blocks = set()
    cust_blocks = set()
    for block in request['block']:
        blocks.add( block['name'] )
        for replica in block['replica']:
            #print replica
            ## find a replica, custodial and COMPLETED !
            if replica['custodial']=="y" and (not with_completion or replica['complete']=="y"):
                if (replica['node'] in veto):
                    #print replica['node']
                    pass
                else:
                    cust.append(replica['node'])
                    cust_blocks.add( block['name'] )



    more_information = {"checked" : time.mktime( time.gmtime())}
    ## make sure all known blocks are complete at custodial
    if with_completion and len(blocks)!=len(cust_blocks):
        #print blocks
        #print cust_blocks

        print "Missing",len(blocks - cust_blocks),"blocks out of",len(blocks)
        more_information['nblocks'] = len(blocks)
        #more_information['blocks'] = list(blocks)
        more_information['nmissing'] = len(blocks - cust_blocks)
        more_information['missing'] = list(blocks - cust_blocks)
        if len(cust_blocks)!=0:
            print json.dumps(list(blocks - cust_blocks), indent=2)
        r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?dataset=%s&node=T1*MSS'%dataset)
        r2=conn.getresponse()
        result = json.loads(r2.read())
        request=result['phedex']['request']
        more_information['nodes']={}
        for nodes in request:
            created = nodes['time_create']
            for node in nodes['node']:
                decided = node['time_decided']
                print "request",nodes['id'],"to",node['name'],"is",node['decision'],
                if decided:
                    print "on",time.asctime( time.gmtime( decided))
                more_information['nodes'][node['name']] = { 'id': nodes['id'], 'created' : created, 'decided' : decided}


                print ". Created since",time.asctime( time.gmtime( created ))

        return [],more_information
    else:
        return list(set(cust)), more_information

def getDatasetBlocksFraction(url, dataset, complete='y', group=None, vetoes=None, sites=None, only_blocks=None):
    ###count how manytimes a dataset is replicated < 100%: not all blocks > 100% several copies exis
    if vetoes==None:
        vetoes = ['MSS','Buffer','Export']

    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    #all_blocks = dbsapi.listBlockSummaries( dataset = dataset, detail=True)
    #all_block_names=set([block['block_name'] for block in all_blocks])
    files = dbsapi.listFileArray( dataset= dataset,validFileOnly=1, detail=True)
    all_block_names = list(set([f['block_name'] for f in files]))
    if only_blocks:
        all_block_names = [b for b in all_block_names if b in only_blocks]

    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))

    r1=conn.request("GET",'/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%(dataset))
    r2=conn.getresponse()
    #retry since it does not look like its getting the right info in the first shot
    #print "retry"
    #time.sleep(2)
    #r1=conn.request("GET",'/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%(dataset))
    #r2=conn.getresponse()

    result = json.loads(r2.read())
    items=result['phedex']['block']

    block_counts = {}
    #initialize
    for block in all_block_names:
        block_counts[block] = 0
    
    for item in items:
        for replica in item['replica']:
            if not any(replica['node'].endswith(v) for v in vetoes):
                if replica['group'] == None: replica['group']=""
                if complete and not replica['complete']==complete: continue
                if group!=None and not replica['group'].lower()==group.lower(): continue 
                if sites and not replica['node'] in sites:
                    #print "leaving",replica['node'],"out"
                    continue
                b = item['name']
                if not b in all_block_names: continue
                block_counts[ b ] +=1
    
    if not len(block_counts):
        print "no blocks for",dataset
        return 0
    first_order = float(len(block_counts) - block_counts.values().count(0)) / float(len(block_counts))
    if first_order <1.:
        print dataset,":not all",len(block_counts)," blocks are available, only",len(block_counts)-block_counts.values().count(0)
        return first_order
    else:
        second_order = sum(block_counts.values())/ float(len(block_counts))
        print dataset,":all",len(block_counts),"available",second_order,"times"
        return second_order
    
def getDatasetDestinations( url, dataset, only_blocks=None, group=None, vetoes=None, within_sites=None, complement=True):
    if vetoes==None:
        vetoes = ['MSS','Buffer','Export']
    #print "presence of",dataset
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    all_blocks = dbsapi.listBlockSummaries( dataset = dataset, detail=True)
    all_dbs_block_names=set([block['block_name'] for block in all_blocks])
    all_block_names=set([block['block_name'] for block in all_blocks])
    if only_blocks:
        all_block_names = filter( lambda b : b in only_blocks, all_block_names)
        full_size = sum([block['file_size'] for block in all_blocks if (block['block_name'] in only_blocks)])
        #print all_block_names
        #print [block['block_name'] for block in all_blocks if block['block_name'] in only_blocks]
    else:
        full_size = sum([block['file_size'] for block in all_blocks])

    if not full_size:
        print dataset,"is nowhere"
        return {}, all_block_names

    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/subscriptions?block=%s%%23*&collapse=n'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    destinations=defaultdict(set)

    if not len(result['phedex']['dataset']):
        return destinations, all_block_names

    items=result['phedex']['dataset'][0]['block']

    ## the final answer is site : data_fraction_subscribed

    for item in items:
        if item['name'] not in all_block_names:
            if not only_blocks:
                print item['name'],'not yet injected in dbs, counting anyways'
                all_block_names.add( item['name'] )
            else:
                continue
        for sub in item['subscription']:
            if not any(sub['node'].endswith(v) for v in vetoes):
                if within_sites and not sub['node'] in within_sites: continue
                #if sub['group'] == None: sub['group']=""
                if sub['group'] == None: sub['group']="DataOps" ## assume "" group is dataops
                if group!=None and not sub['group'].lower()==group.lower(): continue 
                destinations[sub['node']].add( (item['name'], int(sub['percent_bytes']), sub['request']) )
    ## per site, a list of the blocks that are subscribed to the site
    ## transform into data_fraction or something valuable
            
    #complement with transfer request, approved, but without subscriptions yet
    if complement:
        time.sleep(1)
        print "Complementing the destinations with request with no subscriptions"
        print "we have",destinations.keys(),"for now"
        try:
            r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?dataset=%s'%dataset)
            r2=conn.getresponse()
        except:
            r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?dataset=%s'%dataset)
            r2=conn.getresponse()
        result = json.loads(r2.read())
        items=result['phedex']['request']
    else:
        items=[]

    deletes = {}
    for item in items:
        phedex_id = item['id']
        if item['type']!='delete': continue
        #if item['approval']!='approved': continue
        for node in item['node']:
            if node['decision'] != 'approved': continue
            if not node['name'] in deletes or deletes[node['name']]< int(node['time_decided']):
                ## add it if not or later delete
                deletes[node['name']] = int(node['time_decided'])


    times = {}
    for item in items:
        phedex_id = item['id']
        if item['type']=='delete': continue
        sites_destinations = []
        for req in item['node']:
            if within_sites and not req['name'] in within_sites: continue
            if req['decision'] != 'approved' : continue
            if not req['time_decided']: continue
            if req['name'] in deletes and int(req['time_decided'])< deletes[req['name']]:
                ## this request is void by now
                continue
            if not req['decision'] in ['approved']:
                continue
            if req['name'] in times:
                if int(req['time_decided']) > times[req['name']]: 
                    ## the node was already seen as a destination with an ealier time, and no delete in between
                    continue
            times[req['name']] = int(req['time_decided'])

            sites_destinations.append( req['name'] )
        sites_destinations = [site for site in sites_destinations if not any(site.endswith(v) for v in vetoes)]
        ## what are the sites for which we have missing information ?
        sites_missing_information = [site for site in sites_destinations if site not in destinations.keys()]
        print phedex_id,sites_destinations,"fetching for missing",sites_missing_information


        if len(sites_missing_information)==0: continue

        r3 = conn.request("GET",'/phedex/datasvc/json/prod/transferrequests?request=%s'%phedex_id)
        r4 = conn.getresponse()
        sub_result = json.loads(r4.read())
        sub_items = sub_result['phedex']['request']
        ## skip if we specified group
        for req in sub_items:
            if group!=None and not req['group'].lower()==group.lower(): continue
            for requested_dataset in req['data']['dbs']['dataset']:
                if requested_dataset != dataset: continue
                for site in sites_missing_information:
                    for b in all_block_names:
                        destinations[site].add( (b, 0, phedex_id) )
                    
            for b in req['data']['dbs']['block']:
                if not b['name'] in all_block_names: continue
                destinations[site].add((b['name'], 0, phedex_id) )
        
        
    for site in destinations:
        blocks = [b[0] for b in destinations[site]]
        blocks_and_id = dict([(b[0],b[2]) for b in destinations[site]])
        #print blocks_and_id
        completion = sum([b[1] for b in destinations[site]]) / float(len(destinations[site]))
        
        destinations[site] = { "blocks" : blocks_and_id, 
                               #"all_blocks" : list(all_block_names),
                               "data_fraction" : len(blocks) / float(len(all_block_names)) ,
                               "completion" : completion,
                               }

    """
    #print json.dumps( destinations, indent=2)
    for site in destinations:
        print site
        destinations[site]['overlap'] = dict([ (other_site, len(list(set( destinations[site]['blocks']) & set( destinations[other_site]['blocks']))) / float(len(destinations[other_site]['blocks']))) for other_site in destinations.keys()])
        #destinations[site]['overlap'].pop(site)

        destinations[site]['replication'] = sum([sum([destinations[other_site]['blocks'].count(block) for block in destinations[site]['blocks'] ]) / float(len(destinations[site]['blocks'])) for other_site in destinations.keys()])
    """
    
    return destinations, all_block_names

def getDatasetOnGoingDeletion( url, dataset ):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/deletions?dataset=%s&complete=n'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())['phedex']
    return result['dataset']
    
def getDatasetBlocks( dataset, runs=None, lumis=None):
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    all_blocks = set()
    if runs:
        for r in runs:
            all_blocks.update([item['block_name'] for item in dbsapi.listBlocks(run_num=r, dataset= dataset) ])
    if lumis:
        #needs a series of convoluted calls
        #all_blocks.update([item['block_name'] for item in dbsapi.listBlocks( dataset = dataset )])
        pass

    return list( all_blocks )

def getDatasetBlockAndSite( url, dataset, group="",vetoes=None):
    if vetoes==None:
        vetoes = ['MSS','Buffer','Export']
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['block']
    blocks_at_sites=defaultdict(set)
    for item in items:
        for replica in item['replica']:
            if replica['group'] == None: replica['group']=""
            if group!=None and not replica['group'].lower()==group.lower(): continue
            if vetoes and replica['node'] in vetoes: continue
            blocks_at_sites[replica['node']].add( item['name'] )
    #return dict([(site,list(blocks)) for site,blocks in blocks_at_sites.items()])
    return dict(blocks_at_sites)

def getDatasetPresence( url, dataset, complete='y', only_blocks=None, group=None, vetoes=None, within_sites=None):
    try:
        return try_getDatasetPresence( url, dataset, complete, only_blocks, group, vetoes, within_sites)
    except Exception as a:
        sendEmail("fatal exception in getDatasetPresence",str(e))
        return {}

def try_getDatasetPresence( url, dataset, complete='y', only_blocks=None, group=None, vetoes=None, within_sites=None):
    if vetoes==None:
        vetoes = ['MSS','Buffer','Export']
    #print "presence of",dataset
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    all_blocks = dbsapi.listBlockSummaries( dataset = dataset, detail=True)
    all_block_names=set([block['block_name'] for block in all_blocks])
    if only_blocks:
        all_block_names = filter( lambda b : b in only_blocks, all_block_names)
        full_size = sum([block['file_size'] for block in all_blocks if (block['block_name'] in only_blocks)])
        #print all_block_names
        #print [block['block_name'] for block in all_blocks if block['block_name'] in only_blocks]
    else:
        full_size = sum([block['file_size'] for block in all_blocks])
    if not full_size:
        print dataset,"is nowhere"
        return {}
    #print full_size
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1=conn.request("GET",'/phedex/datasvc/json/prod/blockreplicas?dataset=%s'%(dataset))
    r2=conn.getresponse()
    result = json.loads(r2.read())
    items=result['phedex']['block']


    locations=defaultdict(set)
    for item in items:
        for replica in item['replica']:
            if not any(replica['node'].endswith(v) for v in vetoes):
                if within_sites and not replica['node'] in within_sites: continue
                if replica['group'] == None: replica['group']=""
                if complete and not replica['complete']==complete: continue
                #if group!=None and replica['group']==None: continue
                if group!=None and not replica['group'].lower()==group.lower(): continue 
                locations[replica['node']].add( item['name'] )
                if item['name'] not in all_block_names and not only_blocks:
                    print item['name'],'not yet injected in dbs, counting anyways'
                    all_block_names.add( item['name'] )
                    full_size += item['bytes']

    presence={}
    for (site,blocks) in locations.items():
        site_size = sum([ block['file_size'] for block in all_blocks if (block['block_name'] in blocks and block['block_name'] in all_block_names)])
        #print site,blocks,all_block_names
        #presence[site] = (set(blocks).issubset(set(all_block_names)), site_size/float(full_size)*100.)
        presence[site] = (set(all_block_names).issubset(set(blocks)), site_size/float(full_size)*100.)
    #print json.dumps( presence , indent=2)
    return presence

def getDatasetSize(dataset):
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    blocks = dbsapi.listBlockSummaries( dataset = dataset, detail=True)
    ## put everything in terms of GB
    return sum([block['file_size'] / (1024.**3) for block in blocks])

def getDatasetChops(dataset, chop_threshold =1000., talk=False, only_blocks=None):
    chop_threshold = float(chop_threshold)
    ## does a *flat* choping of the input in chunk of size less than chop threshold
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    blocks = dbsapi.listBlockSummaries( dataset = dataset, detail=True)

    ## restrict to these blocks only
    if only_blocks:
        blocks = [block for block in blocks if block['block_name'] in only_blocks]

    sum_all = 0

    ## put everything in terms of GB
    for block in blocks:
        block['file_size'] /= (1024.**3)

    for block in blocks:
        sum_all += block['file_size']

    items=[]
    sizes=[]
    if sum_all > chop_threshold:
        items.extend( [[block['block_name']] for block in filter(lambda b : b['file_size'] > chop_threshold, blocks)] )
        small_block = filter(lambda b : b['file_size'] <= chop_threshold, blocks)
        small_block.sort( lambda b1,b2 : cmp(b1['file_size'],b2['file_size']), reverse=True)

        while len(small_block):
            first,small_block = small_block[0],small_block[1:]
            items.append([first['block_name']])
            size_chunk = first['file_size']
            while size_chunk < chop_threshold and small_block:
                last,small_block = small_block[-1], small_block[:-1]
                size_chunk += last['file_size']
                items[-1].append( last['block_name'] )
            sizes.append( size_chunk )

                
            if talk:
                print len(items[-1]),"items below thresholds",size_chunk
                print items[-1]
    else:
        if talk:
            print "one big",sum_all
        if only_blocks:
            items = [[block['block_name'] for block in blocks]]
        else:
            items = [[dataset]] 
        sizes = [sum_all]
        if talk:
            print items
    ## a list of list of blocks or dataset
    print "Choped",dataset,"of size",sum_all,"GB (",chop_threshold,"GB) in",len(items),"pieces"
    return items,sizes

def distributeToSites( items, sites , n_copies, weights=None,sizes=None):
    ## assuming all items have equal size or priority of placement
    spreading = defaultdict(list)
    if not weights:
        for item in items:
            for site in random.sample(sites, n_copies):
                spreading[site].extend(item)
        return dict(spreading)
    else:
        ## pick the sites according to computing element plege
        SI = siteInfo()

        for iitem,item in enumerate(items):
            at=set()
            chunk_size = None
            if sizes:
                chunk_size = sizes[iitem]
            #print item,"requires",n_copies,"copies to",len(sites),"sites"
            if len(sites) <= n_copies:
                #more copies than sites
                at = set(sites)
            else:
                # pick at random according to weights
                for pick in range(n_copies):
                    picked_site = SI.pick_CE( list(set(sites)-at))
                    picked_site_se = SI.CE_to_SE( picked_site )
                    ## check on destination free space
                    if chunk_size:
                        overflow=10
                        while (SI.disk[picked_site_se]*1024.)< chunk_size and overflow>0:
                            overflow-=1
                            picked_site = SI.pick_CE( list(set(sites)-at))
                            picked_site_se = SI.CE_to_SE( picked_site )
                        if overflow<0:
                            print "We have run out of options to distribute chunks of data because of lack of space"
                            ## should I crash ?
                            print picked_site_se,"has",SI.disk[picked_site_se]*1024.,"GB free, while trying to put an item of size", chunk_size," that is",json.dumps( item, indent=2)
                            sendEmail('possibly going over quota','We have a potential over quota usage while distributing \n%s check transferor logs'%(json.dumps( item, indent=2)))
                    at.add( picked_site )
                #print list(at)
            for site in at:
                spreading[site].extend(item)                
        return dict(spreading)

def getDatasetEventsAndLumis(dataset, blocks=None):
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    all_files = []
    if blocks:
        for b in blocks:
            all_files.extend( dbsapi.listFileSummaries( block_name = b  , validFileOnly=1))
    else:
        all_files = dbsapi.listFileSummaries( dataset = dataset , validFileOnly=1)
    if all_files == [None]:        all_files = []

    all_events = sum([f['num_event'] for f in all_files])
    all_lumis = sum([f['num_lumi'] for f in all_files])
    return all_events,all_lumis

def getDatasetEventsPerLumi(dataset):
    dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
    try:
        all_files = dbsapi.listFileSummaries( dataset = dataset , validFileOnly=1)
    except:
        print "We had to have a DBS listfilesummaries retry"
        time.sleep(1)
        all_files = dbsapi.listFileSummaries( dataset = dataset , validFileOnly=1)        
    try:
        average = sum([f['num_event']/float(f['num_lumi']) for f in all_files]) / float(len(all_files))
    except:
        average = 100
    return average
                    
def setDatasetStatus(dataset, status):
    dbswrite = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSWriter')

    new_status = getDatasetStatus( dataset )
    if new_status == None:
        ## means the dataset does not exist in the first place
        print "setting dataset status",status,"to inexistant dataset",dataset,"considered succeeding"
        return True

    max_try=3
    while new_status != status:
        dbswrite.updateDatasetType(dataset = dataset, dataset_access_type= status)
        new_status = getDatasetStatus( dataset )
        max_try-=1
        if max_try<0: return False
    return True
     
def getDatasetStatus(dataset):
        # initialize API to DBS3                                                                                                                                                                                                                                                     
        dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
        # retrieve dataset summary                                                                                                                                                                                                                                                   
        reply = dbsapi.listDatasets(dataset=dataset,dataset_access_type='*',detail=True)
        if len(reply):
            return reply[0]['dataset_access_type']
        else:
            return None

def getDatasets(dataset):
       # initialize API to DBS3                                                                                                                                                                                                                                                      
        dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
        # retrieve dataset summary                                                                                                                                                                                                                                                   
        reply = dbsapi.listDatasets(dataset=dataset,dataset_access_type='*')
        return reply

def createXML(datasets):
    """
    From a list of datasets return an XML of the datasets in the format required by Phedex
    """
    # Create the minidom document
    impl=getDOMImplementation()
    doc=impl.createDocument(None, "data", None)
    result = doc.createElement("data")
    result.setAttribute('version', '2')
    # Create the <dbs> base element
    dbs = doc.createElement("dbs")
    dbs.setAttribute("name", "https://cmsweb.cern.ch/dbs/prod/global/DBSReader")
    result.appendChild(dbs)    
    #Create each of the <dataset> element
    for datasetname in datasets:
        dataset=doc.createElement("dataset")
        dataset.setAttribute("is-open","y")
        dataset.setAttribute("is-transient","y")
        dataset.setAttribute("name",datasetname)
        dbs.appendChild(dataset)
    return result.toprettyxml(indent="  ")

def phedexPost(url, request, params):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    encodedParams = urllib.urlencode(params, doseq=True)
    r1 = conn.request("POST", request, encodedParams)
    r2 = conn.getresponse()
    res = r2.read()
    try:
        result = json.loads(res)
    except:
        print "PHEDEX error",res
        return None
    conn.close()
    return result

def approveSubscription(url, phedexid, nodes=None , comments =None, decision = 'approve'):
    if comments==None:
        comments = 'auto-approve of production prestaging'
    if not nodes:
        conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
        r1=conn.request("GET",'/phedex/datasvc/json/prod/requestlist?request='+str(phedexid))
        r2=conn.getresponse()
        result = json.loads(r2.read())
        items=result['phedex']['request']
        nodes=set()
        for item in items:
            for node in item['node']:
                nodes.add(node['name'])
        ## find out from the request itself ?
        nodes = list(nodes)

    params = {
        'decision' : decision,
        'request' : phedexid,
        'node' : ','.join(nodes),
        'comments' : comments
        }
    
    result = phedexPost(url, "/phedex/datasvc/json/prod/updaterequest", params)
    if not result:
        return False

    if 'already' in result:
        return True
    return result

def makeDeleteRequest(url, site,datasets, comments):
    dataXML = createXML(datasets)
    params = { "node" : site,
               "data" : dataXML,
               "level" : "dataset",
               "rm_subscriptions":"y",
               #"group": "DataOps",
               #"priority": priority,
               #"request_only":"y" ,
               #"delete":"y",
               "comments":comments
               }
    print site
    response = phedexPost(url, "/phedex/datasvc/json/prod/delete", params)
    return response

def makeReplicaRequest(url, site,datasets, comments, priority='normal',custodial='n',approve=False,mail=True): # priority used to be normal
    dataXML = createXML(datasets)
    r_only = "n" if approve else "y"
    notice = "n" if mail else "y"
    params = { "node" : site,"data" : dataXML, "group": "DataOps", "priority": priority,
                 "custodial":custodial,"request_only":r_only ,"move":"n","no_mail":notice,"comments":comments}
    response = phedexPost(url, "/phedex/datasvc/json/prod/subscribe", params)
    return response

def updateSubscription(url, site, item, priority=None, user_group=None):
    params = { "node" : site }
    params['block' if '#' in item else 'dataset'] = item
    if priority:   params['priority'] = priority
    if user_group: params['user_group'] = user_group
    response = phedexPost(url, "/phedex/datasvc/json/prod/updatesubscription", params) 
    print response

def getWorkLoad(url, wf ):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    r1 = conn.request("GET",'/couchdb/reqmgr_workload_cache/'+wf)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    return data

def getViewByInput( url, details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byinputdataset?'
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    return items
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]

def getViewByOutput( url, details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byoutputdataset?'
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    return items
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]
        
def getWorkflowByInput( url, dataset , details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byinputdataset?key="%s"'%(dataset)
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]

def getWorkflowByOutput( url, dataset , details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byoutputdataset?key="%s"'%(dataset)
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]

def getWorkflowByMCPileup( url, dataset , details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/bymcpileup?key="%s"'%(dataset)
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]

def getWorkflowById( url, pid , details=False):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    there = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/byprepid?key="%s"'%(pid)
    if details:
        there+='&include_docs=true'
    r1=conn.request("GET",there)
    r2=conn.getresponse()
    data = json.loads(r2.read())
    items = data['rows']
    if details:
        return [item['doc'] for item in items]
    else:
        return [item['id'] for item in items]
    
def getWorkflows(url,status,user=None,details=False,rtype=None):
    conn  =  httplib.HTTPSConnection(url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
    if rtype:
        go_to = '/reqmgr2/data/request?status=%s&request_type=%s&detail=%s'%( status, rtype , 'true' if details else 'false')
        r1=conn.request("GET",go_to, headers={"Accept":"application/json"})
    else:
        go_to = '/couchdb/reqmgr_workload_cache/_design/ReqMgr/_view/bystatus?key="%s"'%(status)
        if details:
            go_to+='&include_docs=true'
        r1=conn.request("GET",go_to)

    r2=conn.getresponse()
    data = json.loads(r2.read())
    if rtype:
        items = data['result']
    else:
        items = data['rows']

    users=[]
    if user:
        users=user.split(',')
    workflows = []
    for item in items:
        those = item.keys()
        if users:
            those = filter(lambda k : any([k.startswith(u) for u in users]), those)
        if rtype:
            if details:
                workflows.extend([item[k] for k in those])
            else:
                workflows.extend(those)
        else:
            wf = item['id']
            if (users and any([wf.startswith(u) for u in users])) or not users:
                workflows.append(item['doc' if details else 'id'])

    return workflows

def getPrepIDs(wl):
    pids = list()
    if wl['RequestType'] == 'TaskChain':
        itask=1
        while True:
            t = 'Task%s'% itask
            itask+=1
            if t in wl:
                if 'PrepID' in wl[t]:
                    if not wl[t]['PrepID'] in pids:
                        pids.append( wl[t]['PrepID'] )
            else:
                break
        if pids:
            return pids
        else:
            return [wl['PrepID']]
    else:
        return [wl['PrepID']]

def getLFNbase(dataset):
        # initialize API to DBS3
        dbsapi = DbsApi(url='https://cmsweb.cern.ch/dbs/prod/global/DBSReader')
        # retrieve file
        reply = dbsapi.listFiles(dataset=dataset)
        file = reply[0]['logical_file_name']
        return '/'.join(file.split('/')[:3])

class workflowInfo:
    def __init__(self, url, workflow, deprecated=False, spec=True, request=None,stats=False):
        self.url = url
        self.conn  =  httplib.HTTPSConnection(self.url, cert_file = os.getenv('X509_USER_PROXY'), key_file = os.getenv('X509_USER_PROXY'))
        self.deprecated_request = {}
        if deprecated:
            r1=self.conn.request("GET",'/reqmgr/reqMgr/request?requestName='+workflow)
            r2=self.conn.getresponse()
            self.deprecated_request = json.loads(r2.read())
        if request == None:
            r1=self.conn.request("GET",'/couchdb/reqmgr_workload_cache/'+workflow)
            r2=self.conn.getresponse()
            self.request = json.loads(r2.read())
        else:
            self.request = copy.deepcopy( request )

        self.full_spec=None
        if spec:
            self.get_spec()

        if stats:
            r1=self.conn.request("GET",'/wmstatsserver/data/request/%s'%workflow)
            r2=self.conn.getresponse()
            self.wmstats = r2.read()#json.loads(r2.read())

    def get_spec(self):
        if not self.full_spec:
            r1=self.conn.request("GET",'/couchdb/reqmgr_workload_cache/%s/spec'%self.request['RequestName'])
            r2=self.conn.getresponse()
            self.full_spec = pickle.loads(r2.read())
        return self.full_spec

    def getWorkQueue(self):
        r1=self.conn.request("GET",'/couchdb/workqueue/_design/WorkQueue/_view/elementsByParent?key="%s"&include_docs=true'% self.request['RequestName'])
        r2=self.conn.getresponse()
        self.workqueue = list([d['doc'] for d in json.loads(r2.read())['rows']])
        
    def getSummary(self):
        r1=self.conn.request("GET",'/couchdb/workloadsummary/'+self.request['RequestName'])
        r2=self.conn.getresponse()
        
        self.summary = json.loads(r2.read())
        
    def getGlideMon(self):
        try:
            gmon = json.loads(os.popen('curl -s http://cms-gwmsmon.cern.ch/prodview/json/%s/summary'%self.request['RequestName']).read())
            return gmon
        except:
            print "cannot get glidemon info",self.request['RequestName']
            return None

    def _tasks(self):
        return self.get_spec().tasks.tasklist

    def firstTask(self):
        return self._tasks()[0]

    def getPrepIDs(self):
        return getPrepIDs(self.request)

    def getComputingTime(self,unit='h'):
        cput = None
        ## look for it in a cache
        

        if 'InputDataset' in self.request:
            ds = self.request['InputDataset']
            if 'BlockWhitelist' in self.request and self.request['BlockWhitelist']:
                (ne,_) = getDatasetEventsAndLumis( ds , eval(self.request['BlockWhitelist']) )
            else:
                (ne,_) = getDatasetEventsAndLumis( ds )
            tpe = self.request['TimePerEvent']
            
            cput = ne * tpe
        elif self.request['RequestType'] == 'TaskChain':
            print "not implemented yet"
            itask=1
            cput=0
            carry_on = {}
            while True:
                t = 'Task%s'% itask
                itask+=1
                if t in self.request:
                    #print t
                    task = self.request[t]
                    if 'InputDataset' in task:
                        ds = task['InputDataset']
                        if 'BlockWhitelist' in task and task['BlockWhitelist']:
                            (ne,_) = getDatasetEventsAndLumis( ds, task['BlockWhitelist'] )
                        else:
                            (ne,_) = getDatasetEventsAndLumis( ds )
                    elif 'InputTask' in task:
                        ## we might have a problem with convoluted tasks, but maybe not
                        ne = carry_on[task['InputTask']]
                    elif 'RequestNumEvents' in task:
                        ne = float(task['RequestNumEvents'])
                    else:
                        print "this is not supported, making it zero cput"
                        ne = 0
                    tpe =task['TimePerEvent']
                    carry_on[task['TaskName']] = ne
                    if 'FilterEfficiency' in task:
                        carry_on[task['TaskName']] *= task['FilterEfficiency']
                    cput += tpe * ne
                    #print cput,tpe,ne
                else:
                    break
        else:
            ne = float(self.request['RequestNumEvents'])
            tpe = self.request['TimePerEvent']
            
            cput = ne * tpe

        if cput==None:
            return 0

        if unit=='m':
            cput = cput / (60.)
        if unit=='h':
            cput = cput / (60.*60.)
        if unit=='d':
            cput = cput / (60.*60.*24.)
        return cput
    
    def getNCopies(self, CPUh=None, m = 2, M = 6, w = 50000, C0 = 100000):
        def sigmoid(x):      
            return 1 / (1 + math.exp(-x)) 
        if CPUh==None:
            CPUh = self.getComputingTime()
        f = sigmoid(-C0/w)
        D = (M-m) / (1-f)
        O = (f*M - m)/(f-1) 
        #print O
        #print D
        return int(O + D * sigmoid( (CPUh - C0)/w)), CPUh

    def availableSlots(self):
        av = 0
        SI = global_SI
        if 'SiteWhitelist' in self.request:
            return SI.availableSlots( self.request['SiteWhitelist'] )
        else:
            allowed = getSiteWhiteList( self.getIO() )
            return SI.availableSlots( allowed )

    def getSystemTime(self):
        ct = self.getComputingTime()
        resource = self.availableSlots()
        if resource:
            return ct / resource
        else:
            print "cannot compute system time for",self.request['RequestName']
            return 0

    def getBlowupFactors(self):
        if self.request['RequestType']=='TaskChain':
            min_child_job_per_event=None
            root_job_per_event=None
            max_blow_up=0
            splits = self.getSplittings()
            for task in splits:
                c_size=None
                p_size=None
                t=task['splittingTask']
                for k in ['events_per_job','avg_events_per_job']:
                    if k in task: c_size = task[k]
                parents = filter(lambda o : t.startswith(o['splittingTask']) and t!=o['splittingTask'], splits)
                if parents:
                    for parent in parents:
                        for k in ['events_per_job','avg_events_per_job']:
                            if k in parent: p_size = parent[k]

                        #print parent['splittingTask'],"is parent of",t
                        #print p_size,c_size
                        if not min_child_job_per_event or min_child_job_per_event > c_size:
                            min_child_job_per_event = c_size
                else:
                    root_job_per_event = c_size
                    
                if c_size and p_size:
                    blow_up = float(p_size)/ c_size
                    #print "parent jobs",p_size,"compared to my size",c_size
                    #print blow_up
                    if blow_up > max_blow_up:
                        max_blow_up = blow_up
            return (min_child_job_per_event, root_job_per_event, max_blow_up)    
        return (1.,1.,1.)
    def getSiteWhiteList( self, pickone=False):
        ### this is not used yet, but should replace most
        SI = global_SI
        (lheinput,primary,parent,secondary) = self.getIO()
        sites_allowed=[]
        if lheinput:
            sites_allowed = ['T2_CH_CERN'] ## and that's it                                                                                                                                   
        elif secondary:
            sites_allowed = list(set(SI.sites_T1s + SI.sites_with_goodIO))
        elif primary:
            sites_allowed =list(set( SI.sites_T1s + SI.sites_T2s ))
        else:
            # no input at all
            sites_allowed =list(set( SI.sites_T2s + SI.sites_T1s))

        if pickone:
            sites_allowed = [SI.pick_CE( sites_allowed )]
            
        # do further restrictions based on memory
        # do further restrictions based on blow-up factor
        (min_child_job_per_event, root_job_per_event, max_blow_up) = self.getBlowupFactors()
        if max_blow_up > 5.:
            ## then restrict to only sites with >4k slots
            print "restricting site white list because of blow-up factor",min_child_job_per_event, root_job_per_event, max_blow_up
            sites_allowed = [site for site in sites_allowed if SI.cpu_pledges[site] > 4000]


        return (lheinput,primary,parent,secondary,sites_allowed)

    def checkWorkflowSplitting( self ):
        if self.request['RequestType']=='TaskChain':
            (min_child_job_per_event, root_job_per_event, max_blow_up) = self.getBlowupFactors()
            if min_child_job_per_event and max_blow_up>2.:
                print min_child_job_per_event,"should be the best non exploding split"
                print "to be set instead of",root_job_per_event
                setting_to = min_child_job_per_event*1.5
                print "using",setting_to
                print "Not setting anything yet, just informing about this"
                return True
                #return {'EventsPerJob': setting_to }
            return True
        ## this isn't functioning for taskchain BTW
        if 'InputDataset' in self.request:
            average = getDatasetEventsPerLumi(self.request['InputDataset'])
            timing = self.request['TimePerEvent']
  
            ## if we can stay within 48 with one lumi. do it
            timeout = 48 *60.*60. #self.request['OpenRunningTimeout']
            if (average * timing) < timeout:
                ## we are within overboard with one lumi only
                return True

            spl = self.getSplittings()[0]
            algo = spl['splittingAlgo']
            if algo == 'EventAwareLumiBased':
                events_per_job = spl['avg_events_per_job']
                if average > events_per_job:
                    ## need to do something
                    print "This is going to fail",average,"in and requiring",events_per_job
                    return {'SplittingAlgorithm': 'EventBased'}
        return True

    def getSchema(self):
        new_schema = copy.deepcopy( self.get_spec().request.schema.dictionary_())
        ## put in the era accordingly ## although this could be done in re-assignment
        ## take care of the splitting specifications ## although this could be done in re-assignment
        for (k,v) in new_schema.items():
            if v in [None,'None']:
                new_schema.pop(k)
        return new_schema 

    def _taskDescending(self, node, select=None):
        all_tasks=[]
        if (not select):# or (select and node.taskType == select):
            all_tasks.append( node )
        else:
            for (key,value) in select.items():
                if (type(value)==list and getattr(node,key) in value) or (type(value)!=list and getattr(node, key) == value):
                    all_tasks.append( node )
                    break

        for child in node.tree.childNames:
            ch = getattr(node.tree.children, child)
            all_tasks.extend( self._taskDescending( ch, select) )
        return all_tasks

    def getWorkTasks(self):
        return self.getAllTasks(select={'taskType':['Production','Processing']})

    def getAllTasks(self, select=None):
        all_tasks = []
        for task in self._tasks():
            ts = getattr(self.get_spec().tasks, task)
            all_tasks.extend( self._taskDescending( ts, select ) )
        return all_tasks

    def getSplittings(self):
        spl =[]
        for task in self.getWorkTasks():
            ts = task.input.splitting
            spl.append( { "splittingAlgo" : ts.algorithm,
                          "splittingTask" : task.pathName,
                          } )
            get_those = ['events_per_lumi','events_per_job','lumis_per_job','halt_job_on_file_boundaries','max_events_per_lumi','halt_job_on_file_boundaries_event_aware']#,'couchdDB']#,'couchURL']#,'filesetName']
            #print ts.__dict__.keys()
            translate = { 
                'EventAwareLumiBased' : [('events_per_job','avg_events_per_job')]
                }
            include = {
                'EventAwareLumiBased' : { 'halt_job_on_file_boundaries_event_aware' : 'True' },
                'LumiBased' : { 'halt_job_on_file_boundaries' : 'True'}
                }
            if ts.algorithm in include:
                for k,v in include[ts.algorithm].items():
                    spl[-1][k] = v

            for get in get_those:
                if hasattr(ts,get):
                    set_to = get
                    if ts.algorithm in translate:
                        for (src,des) in translate[ts.algorithm]:
                            if src==get:
                                set_to = des
                                break
                    spl[-1][set_to] = getattr(ts,get)

        return spl

    def getEra(self):
        return self.request['AcquisitionEra']
    def getCurrentStatus(self):
        return self.request['RequestStatus']
    def getProcString(self):
        return self.request['ProcessingString']
    def getRequestNumEvents(self):
        if 'RequestNumEvents' in self.request:
            return int(self.request['RequestNumEvents'])
        else:
            return int(self.request['Task1']['RequestNumEvents'])

    def getPileupDataset(self):
        if 'MCPileup' in self.request:
            return self.request['MCPileup']
        return None
    def getPriority(self):
        return self.request['RequestPriority']

    def getBlockWhiteList(self):
        bwl=[]
        if self.request['RequestType'] == 'TaskChain':
            bwl_t = self._collectintaskchain('BlockWhitelist')
            for task in bwl_t:
                bwl.extend(eval(bwl_t[task]))
        else:
            if 'BlockWhitelist' in self.request:
                bwl.extend(eval(self.request['BlockWhitelist']))

        return bwl
    def getLumiWhiteList(self):
        lwl=[]
        if self.request['RequestType'] == 'TaskChain':
            lwl_t = self._collectintaskchain('LumiWhitelist')
            for task in lwl_t:
                lwl.extend(eval(lwl_t[task]))
        else:
            if 'LumiWhitelist' in self.request:
                lwl.extend(eval(self.request['LumiWhitelist']))
        return lwl

    def getIO(self):
        lhe=False
        primary=set()
        parent=set()
        secondary=set()
        def IOforTask( blob ):
            lhe=False
            primary=set()
            parent=set()
            secondary=set()
            if 'InputDataset' in blob:  
                primary = set([blob['InputDataset']])
            if primary and 'IncludeParent' in blob and blob['IncludeParent']:
                parent = findParent( primary )
            if 'MCPileup' in blob:
                secondary = set([blob['MCPileup']])
            if 'LheInputFiles' in blob and blob['LheInputFiles'] in ['True',True]:
                lhe=True
                
            return (lhe,primary, parent, secondary)

        if self.request['RequestType'] == 'TaskChain':
            t=1
            while 'Task%d'%t in self.request:
                (alhe,aprimary, aparent, asecondary) = IOforTask(self.request['Task%d'%t])
                if alhe: lhe=True
                primary.update(aprimary)
                parent.update(aparent)
                secondary.update(asecondary)
                t+=1
        else:
            (lhe,primary, parent, secondary) = IOforTask( self.request )

        return (lhe,primary, parent, secondary)

    def _collectintaskchain( self , member, func=None):
        coll = {}
        t=1                              
        while 'Task%d'%t in self.request:
            if member in self.request['Task%d'%t]:
                if func:
                    coll[self.request['Task%d'%t]['TaskName']] = func(self.request['Task%d'%t][member])
                else:
                    coll[self.request['Task%d'%t]['TaskName']] = self.request['Task%d'%t][member]
            t+=1
        return coll

    def acquisitionEra( self ):
        def invertDigits( st ):
            if st[0].isdigit():
                number=''
                while st[0].isdigit():
                    number+=st[0]
                    st=st[1:]
                isolated=[(st[i-1].isupper() and st[i].isupper() and st[i+1].islower()) for i in range(1,len(st)-1)]
                if any(isolated):
                    insert_at=isolated.index(True)+1
                    st = st[:insert_at]+number+st[insert_at:]
                    return st
                print "not yet implemented",st
                sys.exit(34)
            return st

        if self.request['RequestType'] == 'TaskChain':
            acqEra = self._collectintaskchain('AcquisitionEra', func=invertDigits)
        else:
            acqEra = invertDigits(self.request['Campaign'])
        return acqEra

    def processingString(self):
        if self.request['RequestType'] == 'TaskChain':
            return self._collectintaskchain('ProcessingString')
        else:
            return self.request['ProcessingString']
        
    def getCampaign( self ):
        #if self.request['RequestType'] == 'TaskChain':
        #    return self._collectintaskchain('Campaign')
        #else:
        return self.request['Campaign']

            
    def getNextVersion( self ):
        ## returns 1 if nothing is in the way
        if 'ProcessingVersion' in self.request:
            version = max(0,int(self.request['ProcessingVersion'])-1)
        else:
            version = 0
        outputs = self.request['OutputDatasets']
        #print outputs
        era = self.acquisitionEra()
        ps = self.processingString()
        if self.request['RequestType'] == 'TaskChain':
            for output in outputs:
                (_,dsn,ps,tier) = output.split('/')
                if ps.count('-')==2:
                    (aera,aps,_) = ps.split('-')
                elif ps.count('-')==3:
                    (aera,fn,aps,_) = ps.split('-')
                else:
                    aera='*'
                    aps='*'
                pattern = '/'.join(['',dsn,'-'.join([aera,aps,'v*']),tier])
                wilds = getDatasets( pattern )
                print pattern,"->",len(wilds),"match(es)"                    
                for wild in [wildd['dataset'] for wildd in wilds]:
                    (_,_,mid,_) = wild.split('/')
                    v = int(mid.split('-')[-1].replace('v',''))
                    version = max(v,version)
            #print "version found so far",version
            for output in outputs:
                (_,dsn,ps,tier) = output.split('/')
                if ps.count('-')==2:
                    (aera,aps,_) = ps.split('-')
                elif ps.count('-')==3:
                    (aera,fn,aps,_) = ps.split('-')
                else:
                    print "Cannot check output in reqmgr"
                    print output,"is what is in the request workload"
                    continue
                while True:
                    predicted = '/'.join(['',dsn,'-'.join([aera,aps,'v%d'%(version+1)]),tier])
                    conflicts = getWorkflowByOutput( self.url, predicted )
                    conflicts = filter(lambda wfn : wfn!=self.request['RequestName'], conflicts)
                    if len(conflicts):
                        print "There is an output conflict for",self.request['RequestName'],"with",conflicts
                        #return None
                        ## since we are not planned for pure extension and ever writing in the same dataset, go +1
                        version += 1
                    else:
                        break

        else:
            for output in  outputs:
                print output
                (_,dsn,ps,tier) = output.split('/')
                if ps.count("-") == 2:
                    (aera,aps,_) = ps.split('-')
                elif ps.count("-") == 3:
                    (aera,fn,aps,_) = ps.split('-')
                else:
                    ## cannot so anything
                    print "the processing string is mal-formated",ps
                    return None

                if aera == 'None' or aera == 'FAKE':
                    print "no era, using ",era
                    aera=era
                if aps == 'None':
                    print "no process string, using wild char"
                    aps='*'
                pattern = '/'.join(['',dsn,'-'.join([aera,aps,'v*']),tier])
                print "looking for",pattern
                wilds = getDatasets( pattern )
                print pattern,"->",len(wilds),"match(es)"
                for wild in [wildd['dataset'] for wildd in wilds]:
                    (_,_,mid,_) = wild.split('/')
                    v = int(mid.split('-')[-1].replace('v',''))
                    version = max(v,version)
            #print "version found so far",version
            for output in  outputs:
                print output
                (_,dsn,ps,tier) = output.split('/')
                if ps.count("-") == 2:
                    (aera,aps,_) = ps.split('-')
                elif ps.count("-") == 3:
                    (aera,fn,aps,_) = ps.split('-')
                else:
                    print "the processing string is mal-formated",ps
                    return None

                if aera == 'None' or aera == 'FAKE':
                    print "no era, using ",era
                    aera=era
                if aps == 'None':
                    print "no process string, cannot parse"
                    continue
                while True:
                    predicted = '/'.join(['',dsn,'-'.join([aera,aps,'v%d'%(version+1)]),tier])
                    conflicts = getWorkflowByOutput( self.url, predicted )
                    conflicts = filter(lambda wfn : wfn!=self.request['RequestName'], conflicts)
                    if len(conflicts):
                        print "There is an output conflict for",self.request['RequestName'],"with",conflicts
                        #return None
                        ## since we are not planned for pure extension and ever writing in the same dataset, go +1
                        version += 1
                    else:
                        break
    
        return version+1

