#/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-

import sys
from omniORB import CORBA, URI
# from omniORB import any
from omniORB import any, cdrMarshal, cdrUnmarshal, findType, findTypeCode

import OpenRTM_aist
import RTC


from CorbaNaming import *
import SDOPackage
# from EmbryonicRtc import *

#
# helper functions
#
#  comparison of corba object references
#
def is_included(a_ref, reflist) :
    for ref in reflist :
        if a_ref._is_equivalent(ref) :
            return True
    return False
#
def is_ge_refset(refs1, refs2) :
    for ref in refs2 :
        if not is_included(ref, refs1) :
            return False
    return True
#
def is_equiv_refs(refs1, refs2) :
    if not len(refs1) == len(refs2) :
        return False
    return is_ge_refset(refs1, refs2)

# class RtmEnv :
#       rtm environment manager
#       orb, naming service, rtc proxy list
#
class RtmEnv : 

    def __init__(self, orb_args, nserver_names=["localhost"], 
                                     orb=None, naming=None):
        if not orb :
            orb = CORBA.ORB_init(orb_args)
        self.orb = orb
        self.name_space = {}
        if naming : # naming can specify only one naming service
            self.name_space['default']=NameSpace(orb, naming=naming)
        else :
            for ns in nserver_names :
              self.name_space[ns]=NameSpace(orb, server_name=ns)

    def __del__(self):
        self.orb.shutdown(wait_for_completion=CORBA.FALSE)
        self.orb.destroy()
#
# class NameSpace :
#       rtc_handles and object list in naming service
#
class NameSpace :
    def __init__(self, orb, server_name=None, naming=None):
        self.orb = orb
        self.name = server_name
        if naming :
          self.naming = naming
        else :
          self.naming = CorbaNaming(self.orb, server_name) 

        self.b_len = 10 # iteration cut off no.
        self.rtc_handles = {}
        self.obj_list = {}

    def get_object_by_name(self, name, cl=RTC.RTObject):
        ref = self.naming.resolveStr(name)
        if ref is None: return None     # return CORBA.nil ?
        if cl :
            return ref._narrow(cl)
        else :
            return ref

    def list_obj(self) :
        self.rtc_handles = {}
        self.obj_list = {}
        return self.list_obj1(self.naming._rootContext, "")

    def list_obj1(self, name_context, parent) :
        if not name_context :
            name_context = self.naming._rootContext 
        rslt = []
        b_list = name_context.list(self.b_len)
        for bd in b_list[0] :
            rslt = rslt + self.proc_bd(bd, name_context, parent)
        if b_list[1] :  # iterator : there exists remaining.
            t_list = b_list[1].next_n(self.b_len)
            while t_list[0] :
                for bd in t_list[1] :
                    rslt = rslt + self.proc_bd(bd, name_context, parent)
                t_list = b_list[1].next_n(self.b_len)
        return rslt

    def proc_bd(self, bd, name_context, parent) :
#        print ('-------------------------------------------------------------------')
#        print( 'bd= ', bd)
#        print( 'name_context= ', name_context)
#        print( 'parent= ', parent)
        rslt = []
        pre = ""
        if parent :
            pre = parent + "/"
        nam = pre + URI.nameToString(bd.binding_name)
        if bd.binding_type == CosNaming.nobject :
            tmp = name_context.resolve(bd.binding_name)
            self.obj_list[nam]=tmp
            print( 'objcet '+nam+' was listed.')
            try :
                tmp = tmp._narrow(RTC.RTObject)
            except Exception as e:
                print( e.args, nam+' is not RTC.')
                tmp = None
            try :
                if tmp :
                   rslt = [[nam, tmp]]
                   self.rtc_handles[nam]=RtcHandle(nam,self,tmp)
                   print( 'handle for '+nam+' was created.')
                else :
                   pass
            except Exception as e:
                print(e.args, nam+' is not alive.' , sys.exc_info()[0])
                pass
        else :
            tmp = name_context.resolve(bd.binding_name)
            tmp = tmp._narrow(CosNaming.NamingContext)
            rslt = self.list_obj1(tmp, nam)
        return rslt

#
# data conversion
#
def nvlist2dict(nvlist) :
    rslt = {}
    for tmp in nvlist :
        rslt[tmp.name]=tmp.value.value()   # nv.value and any.value()
    return rslt
def dict2nvlist(dict) :
    rslt = []
    for tmp in dict.keys() :
        rslt.append(SDOPackage.NameValue(tmp, any.to_any(dict[tmp])))
    return rslt
#
#  connector, port, inport, outport, service
#                

class Connector :
    def __init__(self, plist, name = None, id="", prop_dict={}) :
        self.profile = None
        self.connectp=False
        self.plist = plist
        self.port_reflist = [tmp.port_profile.port_ref for tmp in plist]
        if name :
           self.name = name
        else :
#           self.name = string.join([tmp.name for tmp in plist],'_')
           self.name = '_'.join([tmp.name for tmp in plist])
        self.nego_prop(prop_dict)
        self.profile_req = RTC.ConnectorProfile(self.name, id, 
              self.port_reflist, self.prop_nvlist_req)

    def connect(self, force=False) :
        conlist = self.plist[0].get_connections()
        if conlist :
            for con in conlist :
                if is_equiv_refs(self.port_reflist, con.ports) :
                    if self.profile and (self.profile.connector_id == con.connector_id) :
                        print('already connected')
                        return 'OK'
                    elif force :
                        self.port_reflist[0].disconnect(con.connector_id)
                    else :
                        print('there exists another connection. please try force=True.')
                        return 'NO'
        ret, self.profile = self.port_reflist[0].connect(self.profile_req)
        self.prop_nvlist = self.profile.properties
        self.prop_dict = nvlist2dict(self.prop_nvlist)
        return ret

    def disconnect(self, force=False) :
        conlist = self.plist[0].get_connections()        
        if conlist :
            for con in conlist :
                if is_equiv_refs(self.port_reflist, con.ports) :
                    if self.profile and (self.profile.connector_id == con.connector_id) :
                        ret = self.port_reflist[0].disconnect(self.profile.connector_id)
                        self.profile = None
                        return ret
                    elif force :
                        self.port_reflist[0].disconnect(con.connector_id)
                    else :
                        print('there exists another connection. please try force=True.')
                        return 'NO'
        else :
            print('no connection exits.')
            self.profile = None
            return 'No'

"""
OutPortProfile:

Name: cin0.str_out
Data Type: IDL:RTC/TimedString:1.0
Interface Type: corba_cdr
Dataflow Type: pull,push
Subscription Type: flush,new,periodic
properties:
  port.port_type: DataOutPort
  dataport.data_type: IDL:RTC/TimedString:1.0
  dataport.subscription_type: flush,new,periodic
  dataport.dataflow_type: push,pull
  dataport.interface_type: corba_cdr

InPortProfile:

Name: cout0.str_in
Data Type: IDL:RTC/TimedString:1.0
Interface Type: corba_cdr
Dataflow Type: pull,push
Subscription Type: Any
properties:
  port.port_type: DataInPort
  dataport.data_type: IDL:RTC/TimedString:1.0
  dataport.subscription_type: Any
  dataport.dataflow_type: push,pull
  dataport.interface_type: corba_cdr

ConnectorProfile:

Connector ID: 6b25330c-493d-11e4-9d86-28d24452aadf
Name: cin0.str_out_cout0.str_in
Data Type: IDL:RTC/TimedString:1.0
Interface Type: corba_cdr
Dataflow Type: push
Subscription Type: flush
Outport Buffer length: 1
Outport Buffer full policy: overwrite
Outport Buffer write timeout: 1.0
Outport Buffer empty polycy: do_nothing
Outport Buffer read timeout: 1.0
Inport Buffer length: 1
Inport Buffer full policy: block
Inport Buffer write timeout: 1.0
Inport Buffer empty polycy: readback
Inport Buffer read timeout: 1.0
properties:
  dataport.data_type: IDL:RTC/TimedString:1.0
  dataport.interface_type: corba_cdr
  dataport.dataflow_type: push
  dataport.subscription_type: flush
  dataport.publisher.push_policy: all
  dataport.outport.buffer.length: 1
  dataport.outport.buffer.write.full_policy: overwrite
  dataport.outport.buffer.write.timeout: 1.0
  dataport.outport.buffer.read.empty_policy: do_nothing
  dataport_outport.buffer.read.timeout: 1.0
  dataport.inport.buffer.length: 1
  dataport.inport.buffer.write.full_policy: block
  dataport.inport.buffer.write.timeout: 1.0
  dataport.inport.buffer.read.empty_policy: readback
  dataport_inport.buffer.read.timeout: 1.0
  dataport.serializer.cdr.endian: little,big
  dataport.corba_cdr.inport_ior: IOR:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  dataport.corba_cdr.inport_ref: 

"""
class IOConnector(Connector) :
    def __init__(self, plist, name = None, id="", prop_dict={}) :
      self.nego_prop_keys=(
#        'dataport.data_type',             #
        'dataport.interface_type',        # corba_cdr
        'dataport.dataflow_type',         # push, pull, Any 
        'dataport.subscription_type',     # flush, new, periodic
      )
      self.dataport_prop_keys=(
        'dataport.push_interval',         # [Hz]
        'dataport.publisher.push_policy', # all, fifo, skip, new
        'dataport.publisher.skip_cout'   #
      )
      self.outport_prop_keys=(
        'dataport.outport.buffer.length',             #
        'dataport.outport.buffer.write.full_policy',  # overwrite, do_nothing, block
        'dataport.outport.buffer.write.timeout',      # [sec]
        'dataport.outport.buffer.read.empty_policy',  # readback, do_nothing, block
        'dataport.outport.buffer.read.timeout'        # [sec]
      )
      self.inport_prop_keys=(
        'dataport.inport.buffer.length',             #
        'dataport.inport.buffer.write.full_policy',  # overwrite, do_nothing, block
        'dataport.inport.buffer.write.timeout',      # [sec]
        'dataport.inport.buffer.read.empty_policy',  # readback, do_nothing, block
        'dataport.inport.buffer.read.timeout'        # [sec]
      )

      self.def_prop = {
#        'dataport.data_type':'',
        'dataport.dataflow_type':'push',
        'dataport.interface_type':'corba_cdr' ,
        'dataport.subscription_type':'new',
        'dataport.publisher.push_policy':'new',
        'dataport.inport.buffer.length':'1',
        'dataport.inport.buffer.read.empty_policy':'do_nothing',
        'dataport.inport.buffer.write.full_policy':'overwrite',
        'dataport.outport.buffer.length' : '1',
        'dataport.outport.buffer.write.full_policy':'overwrite',
        'dataport.outport.buffer.read.empty_policy':'do_nothing'}

      Connector.__init__(self, plist, name, id, prop_dict)


    def nego_prop(self,prop_dict) :
       self.possible = True

       self.prop_dict_req = self.def_prop.copy()
       if prop_dict :
         for kk in prop_dict :
           self.prop_dict_req[kk]=prop_dict[kk]
#
       tmp = self.plist[0].get_data_type()
       for pp in self.plist :
         if not tmp == pp.get_data_type() :
             print( 'port data_type unmutched')
             self.possible = False
       self.prop_dict_req['dataport.data_type']=tmp
#
       for kk in self.nego_prop_keys :
         for pp in self.plist :  
           if not ((self.prop_dict_req[kk] in pp.prop[kk]) or 
                                   ('Any' in    pp.prop[kk])) :
             print( kk, self.prop_dict_req[kk])
             self.prop_dict_req[kk] = ""
             self.possible = False
       self.prop_nvlist_req = dict2nvlist(self.prop_dict_req)
 #      self.profile_req.properties = self.prop_nvlist_req
       return self.possible

class ServiceConnector(Connector) :
    def __init__(self, plist, name = None, id="", prop_dict={}) :
#       self.nego_prop_keys=['port.port_type']
#       self.nego_prop_keys=('port.port_type')
       self.nego_prop_keys=('port.port_type',)
       self.def_prop = {'port.port_type':'CorbaPort' }
       Connector.__init__(self, plist, name, id, prop_dict)
 
    def nego_prop(self,prop_dict) :

       self.possible = True

       self.prop_dict_req = self.def_prop.copy()
       if prop_dict :
         for kk in prop_dict :
           self.prop_dict_req[kk]=prop_dict[kk]
#
       for kk in self.nego_prop_keys :
         for pp in self.plist :  
            if not ((self.prop_dict_req[kk] in pp.prop[kk]) or 
                                   ('Any' in    pp.prop[kk])) :
             print( kk, self.prop_dict_req[kk])
             self.prop_dict_req[kk] = ""
             self.possible = False
       self.prop_nvlist_req = dict2nvlist(self.prop_dict_req)
 #      self.profile_req.properties = self.prop_nvlist_req
       return self.possible

class Port :
    def __init__(self, profile,nv_dict=None,handle=None) :
        self.handle=handle
        self.name=profile.name    
        self.port_profile = profile
        if not nv_dict :
            nv_dict = nvlist2dict(profile.properties)
        self.prop = nv_dict
        self.con = None           # this must be set in each subclasses

    def get_info(self) :
        self.con.connect(force=True)
        tmp1 = self.get_connections()
        tmp2 = [pp.connector_id for pp in tmp1]
        if self.con.profile.connector_id in tmp2 :
#            print( "connecting", self.con.profile.connector_id, tmp2)
            self.con.disconnect(force=True)

    def get_connections(self) :
        return self.port_profile.port_ref.get_connector_profiles()

    def disconnect_all(self) :
        connectors = self.get_connections()
        err = 0
        for con in connectors :
            try :
                ret = con.ports[0].disconnect(con.connector_id)
            except Exception as e :
                print(e)
                err += 1
        if err > 0 :
            return -1
        else :
            return ret

class CorbaServer :
    def __init__(self, profile, port) :
        self.profile = profile
        self.port = port
        self.name = profile.instance_name
        self.type = profile.type_name
        self.ref = None
        ref_key = 'port.' + self.type + '.' + self.name
        self.ref=self.port.con.prop_dict[ref_key]
        if isinstance(self.ref,str) :
            self.ref=port.handle.env.orb.string_to_object(self.ref)
#
# if we import stubs before we create instances,
# we rarely need to narrow the object references.
# we need to specify global symbol table to evaluate class symbols.
#
    def narrow_ref(self, gls) :
        if self.type.find('::') == -1 :
            self.narrow_sym = eval('_GlobalIDL.' + self.type, gls)
        else :
            self.narrow_sym = eval(self.type.replace('::','.'), gls)
        self.ref = self.ref._narrow(self.narrow_sym)

class CorbaClient :
    def __init__(self, profile) :
        self.profile = profile
        self.name = profile.instance_name
        self.type = profile.type_name
#
# to connect to an outside corba client,
# we need an implementation of the corresponding corba server.
# but ....
#

class RtcService(Port) :
    def __init__(self, profile,nv_dict=None, handle=None) :
        Port.__init__(self, profile, nv_dict, handle)
        self.con = ServiceConnector([self])
        self.get_info()
        self.provided={}
        self.required={}
        tmp = self.port_profile.interfaces
        for itf in tmp :
            if itf.polarity == RTC.PROVIDED :
                self.provided[itf.instance_name] = CorbaServer(itf,self)
            elif itf.polarity == RTC.REQUIRED :
                self.required[itf.instance_name] = CorbaClient(itf)

#    def open(self) :
#        self.con.connect()
#        self.provided={}
#        self.required={}
#        tmp = self.port_profile.interfaces
#        for itf in tmp :
#            if itf.polarity == RTC.PROVIDED :
#                self.provided[itf.instance_name] = CorbaServer(itf,self)
#            elif itf.polarity == RTC.REQUIRED :
#                self.required[itf.instance_name] = CorbaClient(itf)

#    def close(self) :
#        return self.con.disconnect()

def strip_data_class(data_class_str) :
    tmp = data_class_str.split(':')
    if len(tmp) == 1 :
        return data_class_str
    else :
        tmp = tmp[1].split('/')
        return tmp[1]

class RtcInport(Port) :
    def __init__(self, profile, nv_dict=None, handle=None) :
        Port.__init__(self, profile, nv_dict, handle)
        tmp=strip_data_class(self.prop['dataport.data_type'])
        dtype = findType(self.prop['dataport.data_type'])
        if isinstance(dtype, tuple) :
            self.data_type=tmp
            self.data_class = dtype[1]
            self.data_tc = findTypeCode(self.prop['dataport.data_type'])
        else:
            self.data_type=tmp
            self.data_class = eval('RTC.' + tmp)
            self.data_tc = eval('RTC._tc_' + tmp)
        self.con = IOConnector([self])

    def write(self,data) :
        ret = self.ref.put(cdrMarshal(self.data_tc,
                                self.data_class(RTC.Time(0,0),data), 1))
        return ret
        
    def open(self) :
        ret = self.con.connect(force=True)
        self.ref = self.con.prop_dict['dataport.corba_cdr.inport_ref']
        return ret

    def close(self) :
        return self.con.disconnect(force=True)

    def get_data_type(self) :
        return self.data_type

class RtcOutport(Port) :
    def __init__(self, profile,nv_dict=None, handle=None) :
        Port.__init__(self, profile, nv_dict, handle)
        tmp=strip_data_class(self.prop['dataport.data_type'])
        dtype = findType(self.prop['dataport.data_type'])
        if isinstance(dtype, tuple) :
            self.data_type=tmp
            self.data_class = dtype[1]
            self.data_tc = findTypeCode(self.prop['dataport.data_type'])
        else:
            self.data_type=tmp
            self.data_class = eval('RTC.' + tmp)
            self.data_tc = eval('RTC._tc_' + tmp)
        p_dict={'dataport.dataflow_type':'pull'}             
        self.con = IOConnector([self],prop_dict=p_dict)

    def read(self) :
        if self.ref :
           try :
                tmp1=self.ref.get()
                tmp2= cdrUnmarshal(self.data_tc,tmp1[1], 1)
                return tmp2.data
                # return tmp2
           except :
                return None
        else :
           print( "not supported")
           return None

    def open(self) :
        ret = self.con.connect(force=True)
        if 'dataport.corba_cdr.outport_ref' in self.con.prop_dict :
           self.ref = self.con.prop_dict['dataport.corba_cdr.outport_ref']
        return ret

    def close(self) :
        return self.con.disconnect(force=True)

    def get_data_type(self) :
        return self.data_type

#
# RtcHandle
#
class RtcHandle :
  def __init__(self, name, env, ref=None) :
    self.name = name
    self.env = env
    if ref :
        self.rtc_ref = ref
    else :
        self.rtc_ref = env.naming.resolve(name)._narrow(RTC.RTObject)
    self.conf_ref = None
    self.retrieve_info()

  def retrieve_info(self) :
    self.conf_set={}
    self.conf_set_data={}
    self.port_refs = []
    self.execution_contexts =[]
    if self.rtc_ref :
        self.conf_ref = self.rtc_ref.get_configuration()
        conf_set = self.conf_ref.get_configuration_sets()
        for cc in conf_set :
            self.conf_set[cc.id]=cc
            self.conf_set_data[cc.id]=nvlist2dict(cc.configuration_data)
        self.profile = self.rtc_ref.get_component_profile()
        self.prop = nvlist2dict(self.profile.properties)
        #self.execution_contexts = self.rtc_ref.get_contexts()
        self.execution_contexts = self.rtc_ref.get_owned_contexts()
        self.port_refs = self.rtc_ref.get_ports()  
    # this includes inports, outports and service ports
    self.ports = {}
    self.services = {}
    self.inports = {}
    self.outports = {}
    for pp in self.port_refs :
        tmp = pp.get_port_profile()
        tmp_prop = nvlist2dict(tmp.properties)
#        tmp_name = tmp.name.lstrip(self.name.split('.')[0]).lstrip('.')
#        tmp_name = tmp.name.replace(self.prop['instance_name']+'.','')

        tmp_name = tmp.name
        if tmp.name.count('.') > 0:
            tmp_name = tmp.name.split('.')[1]
        else:
            pass

        print( 'port_name:', tmp_name)
#       self.ports[tmp.name]=Port(tmp, tmp_prop)
        if tmp_prop['port.port_type']=='DataInPort' :
            self.inports[tmp_name]=RtcInport(tmp,tmp_prop, self)
#            self.inports[tmp.name]=Port(tmp, tmp_prop)
        elif tmp_prop['port.port_type']=='DataOutPort' :
            self.outports[tmp_name]=RtcOutport(tmp, tmp_prop, self)
#            self.outports[tmp.name]=Port(tmp, tmp_prop)
        elif tmp_prop['port.port_type']=='CorbaPort' :
            self.services[tmp_name]=RtcService(tmp, tmp_prop, self)
#            self.services[tmp.name]=Port(tmp, tmp_prop)

  def set_conf(self,conf_set_name,param_name,value) :
      conf_set=self.conf_set[conf_set_name]
      conf_set_data=self.conf_set_data[conf_set_name]
      conf_set_data[param_name]=value
      conf_set.configuration_data=dict2nvlist(conf_set_data)
#      self.conf_ref.set_configuration_set_values(conf_set_name,conf_set)
      self.conf_ref.set_configuration_set_values(conf_set)
  def set_conf_activate(self,conf_set_name,param_name,value) :
      self.set_conf(conf_set_name,param_name,value)
      self.conf_ref.activate_configuration_set(conf_set_name)
  def activate_conf_set(self, conf_set_name) :
      self.conf_ref.activate_configuration_set(conf_set_name)

  def get_conf_set(self) :
      try:
          return self.conf_set.keys()
      except:
          return None

  def get_conf_set_params(self, conf_set_name) :
      try:
         return self.conf_set_data[conf_set_name].keys()
      except:
         return None

  def activate(self):
      return self.execution_contexts[0].activate_component(self.rtc_ref)
  def deactivate(self):
      return self.execution_contexts[0].deactivate_component(self.rtc_ref)
  def reset(self):
      return self.execution_contexts[0].reset_component(self.rtc_ref)
  def get_state(self):
      return self.execution_contexts[0].get_component_state(self.rtc_ref)

  def exit(self):
      return self.rtc_ref.exit()

#
# pipe
#  a pipe is an port (interface & implementation)
#  for a port(an RtcInport or RtcOutport object) of an outside rtc.
#  you need an empty rtc (comp) to create pipes.
#  you can subscribe and communicate to the outside port with the pipe.
#  
#
def shallow_dummy_data(tc) :
#    return apply(tc._d[1],[ None for xx in range(tc.member_count())])
    return tc._d[1](*[ None for xx in range(tc.member_count())])
def deep_dummy_data(tcd) :
    if not isinstance(tcd,tuple) :
        return tcd
    elif tcd[0] == 15 :
#        return apply(tcd[1],[deep_dummy_data(tcd[5+2*x]) for x in range((len(tcd)-4)/2)])
        return tcd[1](*[deep_dummy_data(tcd[5+2*x]) for x in range(int((len(tcd)-4)/2))])
    elif tcd[0] == 19 :
        return [deep_dummy_data(tcd[1+x]) for x in range(len(tcd)-2)]
    elif tcd[0] == 18 :
        return ""
    elif tcd[0] == 21 :
        return deep_dummy_data(tcd[3])
    else :
        return tcd

class InPipe() :
  def __init__(self,comp, port) :
    self.comp=comp
    self.port=port
    self.pname=(port.handle.name+port.name).replace('.','_')
#    self.pipe=comp.makeOutPort(self.pname,port.data_class(RTC.Time(0,0),[]),OpenRTM_aist.RingBuffer(1))
    dd = deep_dummy_data(port.data_tc._d)
#    self.pipe=comp.makeOutPort(self.pname,dd,OpenRTM_aist.RingBuffer(1))
    self.pipe=comp.makeOutPort(self.pname,dd)
    self.buf=getattr(comp,'_d_'+self.pname)
    tmp = self.pipe.getPortProfile()
    self.pipe_port = RtcOutport(tmp, nvlist2dict(tmp.properties))
    self.con = IOConnector([self.pipe_port,self.port])
  def connect(self):
    return self.con.connect()
  def disconnect(self):
    return self.con.disconnect()
  def write(self, data) :
    self.buf.data=data
    self.pipe.write()
class OutPipe() :
  def __init__(self,comp, port) :
    self.comp=comp
    self.port=port
    self.pname=(port.handle.name+port.name).replace('.','_')
#    self.pipe=comp.makeInPort(self.pname,port.data_class(RTC.Time(0,0),[]),OpenRTM_aist.RingBuffer(1))
    dd = deep_dummy_data(port.data_tc._d)
#    self.pipe=comp.makeInPort(self.pname,dd,OpenRTM_aist.RingBuffer(1))
    self.pipe=comp.makeInPort(self.pname,dd)
    self.buf=getattr(comp,'_d_'+self.pname)
    tmp = self.pipe.getPortProfile()
    self.pipe_port = RtcInport(tmp, nvlist2dict(tmp.properties))
    self.con = IOConnector([self.pipe_port,self.port])
  def connect(self):
    return self.con.connect()
  def disconnect(self):
    return self.con.disconnect()
  def read(self) :
    return self.pipe.read().data
#
#
#
def make_pipe(comp, handle) :
  handle.in_pipe={}
  for i_port in handle.inports :
    handle.in_pipe[i_port]=InPipe(comp, handle.inports[i_port])
  handle.out_pipe={}
  for o_port in handle.outports :
    handle.out_pipe[o_port]=OutPipe(comp, handle.outports[o_port])
