"""Read-only CPU/RAM snapshot and conservative independent-worker recommendation."""
import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import time


def snapshot(worker_gib=2.0):
    if worker_gib <= 0: raise ValueError('worker_gib must be positive')
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)] + [
                (k,ctypes.c_ulonglong) for k in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        m=Memory(); m.length=ctypes.sizeof(m)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            raise OSError('GlobalMemoryStatusEx failed')
        total,available=m.total,m.available
        def ticks():
            a,b,c=ctypes.c_ulonglong(),ctypes.c_ulonglong(),ctypes.c_ulonglong()
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(a),ctypes.byref(b),ctypes.byref(c)):
                raise OSError('GetSystemTimes failed')
            return a.value,b.value+c.value
    else:
        mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        total,available=mem['MemTotal'],mem['MemAvailable']
        def ticks():
            values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
            return values[3]+values[4],sum(values[:8])
    a=ticks();time.sleep(.5);b=ticks()
    idle=max(0,min(1,(b[0]-a[0])/max(1,b[1]-a[1])))
    cpus=os.cpu_count() or 1
    reserve=max(1.0,total/2**30*.1)
    memory_slots=max(0,int((available/2**30-reserve)/worker_gib))
    cpu_slots=max(1,int(cpus*idle*.8))
    return {'host':platform.node(),'python':platform.python_version(),'logical_cpus':cpus,
            'cpu_idle_fraction':idle,'total_gib':total/2**30,'available_gib':available/2**30,
            'reserve_gib':reserve,'assumed_peak_worker_gib':worker_gib,
            'disk_free_gib':shutil.disk_usage('.').free/2**30,
            'recommended_workers':min(memory_slots,cpu_slots),
            'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}


if __name__=='__main__': print(json.dumps(snapshot(),indent=2))
