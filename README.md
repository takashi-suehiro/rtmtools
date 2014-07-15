rtmtools
==========

tools for OpenRTM mainly based on rtc_handle

Requirements
-----------------

rtmtools requires OpenRTM-aist-Python 1.x

Files
----------------

 rtmtools +- rtc_handle -+- rtc_handle.py : base module
          |              +- rtc_handle_util.py : extra utilities
          |
          +- embryonic_rtc -+- EmbryonicRtc.py : 
          |
          +- rtc_handle_example -+- cin : a rtc with outport
            (under construction) +- cout : a rtc with inport
                                 +- replace : a rtc with service
                                 +- script : sample script

Installation
----------------

Just put files appropriate place.

Usage
-----------------

import as python modules.

rtc_handle.py : basic proxy function for RTC
rtc_handle_util.py : extra utilities
EmbryonicRtc.py : your python will be a RTC after you execute main().
                  you can create ports dynamically to access ports of
                  other rtcs.
                  this is used in rtc_handle to create Pipe objects.

see example script for detail.
