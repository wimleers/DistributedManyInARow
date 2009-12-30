from distutils.core import setup
import py2exe

#to run this py2exe script: python setup.py py2exe
excludes = ["PyQt4.uic.port_v3", "PyQt4.uic.port_v3.ascii_upper", "PyQt4.uic.port_v3.load_plugin", "PyQt4.uic.port_v3.proxy_base",
"PyQt4.uic.port_v3.encode_utf8",  "PyQt4.uic.port_v3.string_io", "PyQt4.uic.port_v3.invoke", "uic.port_v3.ascii_upper",
"uic.port_v3.load_plugin", "uic.port_v3.proxy_base", "uic.port_v3.encode_utf8", "uic.port_v3.string_io",
"uic.port_v3.invoke", "uic.port_v3"]



setup(windows=[{"script" : "main.py"}], options={"py2exe" : {"includes":["sip"], "excludes" : excludes, "dll_excludes": ["MSVCP90.dll",]}})
