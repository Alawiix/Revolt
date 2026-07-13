import os ,sys ,json ,ctypes ,subprocess ,math ,threading ,urllib .request 
import socket ,struct ,re ,atexit ,webbrowser ,hashlib ,secrets ,time ,shutil 
import logging ,logging .handlers ,tempfile ,io 
from collections import deque 
import tkinter as tk 
from tkinter import messagebox ,simpledialog ,ttk ,colorchooser ,filedialog 
import tkinter .font as tkfont 

if os .name =="nt":
    import winreg 

def _enable_windows_dpi_awareness ():
    # has to run before any Tk window exists, otherwise Windows bitmap-stretches
    # the whole window to match the display scale and everything looks blurry
    if os .name !="nt":
        return 
    try :
        # 2 = per-monitor DPI aware, works right even with mixed monitor setups
        ctypes .windll .shcore .SetProcessDpiAwareness (2 )
        return 
    except Exception :
        pass 
    try :
        ctypes .windll .shcore .SetProcessDpiAwareness (1 )
        return 
    except Exception :
        pass 
    try :
        # older Windows without shcore
        ctypes .windll .user32 .SetProcessDPIAware ()
    except Exception :
        pass 

_enable_windows_dpi_awareness ()

_PIL_AVAILABLE =False 
_SVG_ICONS_AVAILABLE =False 
try :
    from PIL import Image as _PILImage ,ImageTk as _PILImageTk 
    _PIL_AVAILABLE =True 
except Exception :
    _PIL_AVAILABLE =False 

try :
    import cairosvg as _cairosvg 
    _SVG_ICONS_AVAILABLE =_PIL_AVAILABLE 
except Exception :
    _cairosvg =None 
    _SVG_ICONS_AVAILABLE =False 

def _win_titlebar_hwnd (tk_window ):
    try :
        return ctypes .windll .user32 .GetParent (tk_window .winfo_id ())
    except Exception :
        return None 

def _win_dwm_set (hwnd ,attribute :int ,value :int ):
    try :
        v =ctypes .c_int (value )
        ctypes .windll .dwmapi .DwmSetWindowAttribute (
        hwnd ,attribute ,ctypes .byref (v ),ctypes .sizeof (v ))
    except Exception :
        pass 

def _hex_to_colorref (hex_color :str )->int :

    h =hex_color .lstrip ("#")
    r =int (h [0 :2 ],16 )
    g =int (h [2 :4 ],16 )
    b =int (h [4 :6 ],16 )
    return r |(g <<8 )|(b <<16 )

def _hex_luminance (hex_color :str )->float :
    h =hex_color .lstrip ("#")
    r =int (h [0 :2 ],16 )/255 
    g =int (h [2 :4 ],16 )/255 
    b =int (h [4 :6 ],16 )/255 
    return 0.299 *r +0.587 *g +0.114 *b 

def apply_titlebar_theme (tk_window ,hex_color :str |None =None ):

    if os .name !="nt":
        return 
    hwnd =_win_titlebar_hwnd (tk_window )
    if not hwnd :
        return 

    DWMWA_USE_IMMERSIVE_DARK_MODE =20 
    DWMWA_CAPTION_COLOR =35 
    DWMWA_TEXT_COLOR =36 

    _win_dwm_set (hwnd ,DWMWA_USE_IMMERSIVE_DARK_MODE ,1 )

    if hex_color and is_valid_hex_color (hex_color ):

        _win_dwm_set (hwnd ,DWMWA_CAPTION_COLOR ,_hex_to_colorref (hex_color ))
        text_hex ="#000000"if _hex_luminance (hex_color )>0.5 else "#ffffff"
        _win_dwm_set (hwnd ,DWMWA_TEXT_COLOR ,_hex_to_colorref (text_hex ))
    else :

        _win_dwm_set (hwnd ,DWMWA_CAPTION_COLOR ,0xFFFFFFFF )
        _win_dwm_set (hwnd ,DWMWA_TEXT_COLOR ,0xFFFFFFFF )

def is_valid_hex_color (s :str )->bool :
    return bool (re .fullmatch (r"#[0-9A-Fa-f]{6}",s or ""))

REDIRECT_IP ="127.0.0.1"
CONFIG_FILE =os .path .join (os .path .expanduser ("~"),"revolt_config.json")
REMOTE_CACHE_FILE =os .path .join (os .path .expanduser ("~"),"revolt_remote_cache.json")
CUSTOM_FEEDS_FILE =os .path .join (os .path .expanduser ("~"),"revolt_custom_feeds.json")
CUSTOM_DNS_FILE =os .path .join (os .path .expanduser ("~"),"revolt_custom_dns.json")
ALLOWLIST_FILE =os .path .join (os .path .expanduser ("~"),"revolt_allowlist.json")
LOCK_FILE =os .path .join (os .path .expanduser ("~"),"revolt_lock.json")
VPN_CONFIG_FILE =os .path .join (os .path .expanduser ("~"),"revolt_vpn_config.json")
VPN_PID_FILE =os .path .join (os .path .expanduser ("~"),"revolt_vpn.pid")
VPN_STATE_FILE =os .path .join (os .path .expanduser ("~"),"revolt_vpn_state.json")
VPN_LOG_FILE =os .path .join (os .path .expanduser ("~"),"revolt_vpn_openvpn.log")
DNS_STATE_FILE =os .path .join (os .path .expanduser ("~"),"revolt_dns_state.json")
APP_LOG_FILE =os .path .join (os .path .expanduser ("~"),"revolt_app.log")
_APP_NAME ="Revolt"
SHIELD_QUOTE ="You're making yourself a better human."
_REG_KEY =r"Software\Microsoft\Windows\CurrentVersion\Run"
_DESK_FILE =os .path .expanduser ("~/.config/autostart/revolt.desktop")
_SHORTCUT_MARKER =os .path .join (os .path .expanduser ("~"),".revolt_shortcut_created")
_ONBOARDING_MARKER =os .path .join (os .path .expanduser ("~"),".revolt_onboarding_done")

def _app_base_dir ()->str :
    if getattr (sys ,"frozen",False ):
        return os .path .dirname (sys .executable )
    return os .path .dirname (os .path .abspath (__file__ ))

def _setup_logging ()->logging .Logger :
    lg =logging .getLogger ("revolt")
    lg .setLevel (logging .DEBUG )
    try :
        handler =logging .handlers .RotatingFileHandler (
        APP_LOG_FILE ,maxBytes =512_000 ,backupCount =2 ,encoding ="utf-8")
        handler .setFormatter (logging .Formatter (
        "%(asctime)s  %(levelname)-7s  %(name)s:%(funcName)s  %(message)s",
        datefmt ="%Y-%m-%d %H:%M:%S"))
        lg .addHandler (handler )
    except Exception :

        lg .addHandler (logging .NullHandler ())
    return lg 

log =_setup_logging ()

def _atomic_write_json (path :str ,data )->bool :
    directory =os .path .dirname (path )or "."
    try :
        fd ,tmp_path =tempfile .mkstemp (prefix =".revolt_tmp_",dir =directory )
        try :
            with os .fdopen (fd ,"w",encoding ="utf-8")as f :
                json .dump (data ,f )
                f .flush ()
                os .fsync (f .fileno ())
            os .replace (tmp_path ,path )
            return True 
        except Exception :
            try :
                os .remove (tmp_path )
            except Exception :
                pass 
            raise 
    except Exception :
        return False 

import base64 

_ICON_ICO_B64 =(
"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"
"ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3"
"ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3ci/3"
"ci+fTvhVn8C9vHLyea8Jfc6f92nlZa7nqz7Hr0zuDcC9/FXWwPN+9+OU6ctStL/quv6pMQj3BuCnV17m2X/eivRFK9Ynne/d73/S"
"+XztDYF91SdwL6+kEJ/P5nD3M76qDedF1/N5XedPrPxUX/xPubzss/+rrJFXzQP4NPK13/2BewNwLx+Vn0YQEPjqz/Ne7uVe7uXL"
"lXsP4F5edfm0wN29fAq5NwD38mXLZ11zp7/3KqQavxZybwC+3vIqFcHwzuun+Z2XEd35+t4QvITcG4Cvr7wo7XUqz1OSL0JxTpX/"
"0665z2IETl/vDcHHyL0B+PrKZ8nB391FP89zOVX+z7LuPu53nnfeL3q9lxPJX/UJ3MsrK6vC/VUV527szk/5mZ/mPD7uZz7t3/2p"
"kHsP4KdDPstz/rw9gC/rd1903vfK/xy5NwD38lnlZV3ye3mF5d4AvJryIrf3C0H1yZdbBu5OAHj8+DEB4J133iEA/PCHP+Qbb7xx"
"+LtvvvmmHj9+LDMTAEhfjT34uOtyd5IEya/0HL9quTcAX418HrnwVT61y/tJCn/3+7VWAuBbb73Ft99+mz/4wQ/4wQcf8NmzZwSA"
"7XZLAJimSRcXF3r06JH+x//xf/S3335bv//7v++HE/oClexljNhdA3ZXHj9+fOsE22d+rS3DvQH48uRF9/pl0nWfRoRPSH/dVZYX"
"KU9TfPvud7/LP//zP+ef/umf2tOnT/nee+/Zfr/nPM+cpunQUfq079U9eaKLiwt//fXXfRiG+s//+T+vZubAl28A1vdqrXzrrbfs"
"1HgBwNtvv43f/M3fxKNHj/Qnf/InOD8/1xtvvKE333zzcKKPHz/Wnc/+WhmEewPw5cjLKPnn1TorvMAIfJzik0Qp5ZCu+4M/+AP7"
"/ve/z+9973t2c3PDYRjs3adPbX9zY/NuZ+N+b8uy2DRNXHdWM1Pf915rrefn5zXnXH7rt36rPH78uJiZf1kG4PTrP/zDP0wffPCB"
"/et//a/Tn/7pn9qyLGzXCQD4+Z//eQ3DoB//+McahkFvvPGGv/vuuzo/PxcAvPHGG3rrrbckSV9Hj+DeAHw58mmU/eOeyacph41F"
"ayY0xVsV43RnBMDvfve79qMf/ch+8IMf8Hvf+5796Ec/sqdPn9o8z7y6ukqlFC7LYvv9PpVSrJSS+r63Wqv1fW/uTjMTSaWU3N3L"
"OI6F5PLGG28sv/RLvzT/3b/7d8s/+Af/oAKfjyfwSV7MH/7hH6Z/9a/+Vf5P/+k/pffffz9dX1+nZVmslGKnBsvM1HWdX19fu5lp"
"s9nUzWbjDx8+9P/8n/+zpmnSr/zKr/ibb76pf/JP/snXrqbg3gB8OfJZPIBPen+VF1bz6UTTSPI73/kOAeDNN9/kO++8Y5vNxt57"
"7z17//33U9d1ab/f2263S8MwWFP0VWGslJLc3Wqtyd1Tzjm5u+WcLTZHalkWpZRqSqlImiXNZ2dne5Jzznk+Pz+f//iP/7h8UQag"
"1srHjx+n7373uxlAfv/997vtdptzzrmUkq6vr83d7eR3dHZ25mbm8zzXruvqNE1lu93WzWZT33//ff+bf/Nv+na7rd/+9re9GYCX"
"OfmfmAamewPw1cjnTcbx3AUmCY8fP+Y777zDH/7wh5ymKX344Yd2cXFhT548SWaWd7td2u122cy6UkqqtaZVyd3dJCVJJsncPbX/"
"p5TS+nowACSdZEkpLZL2kvbDMOxI7lJKOzPb/+Iv/uLyd/7O31l+//d//1OFBHcVvu3ifPz4sf3gBz/gfr9P3/ve9/LV1VV68uRJ"
"v9/vu5RSV0rpaq3Z3XO7jsMHmVkdx7GaWa21Ll3XlWEYllJKmaapLMtSLi8v67Is5Vd+5Vf8rbfe8hfd67un+zLP51WQ+0rAr0Ze"
"dkF8LlV47777rv34xz9OZ2dn+fr6Or///vt5t9t1ZtaXUrpSSp9S6mqtnbt3q5I3hUkATJIB+FgDAMBJLmY2S9pJ2pVSbgB0krK7"
"5+vr6/2///f/Pv3qr/5q/Y//8T/Wj7lGAuBv/dZv4cmTJ/Zrv/Zr+PDDD+3m5sZKKfzrf/2vm7uzlGLLsqRxHNOyLHlZlq7W2tda"
"u5TS0K4nt8NwrAiUmRVJJaW01FrnUspcStm7++zuXJYFOWfd3NwYAH/Bef5Ey70BOMqLdttPUsLP+ntfuJiZfvu3fzudn5+nq6ur"
"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"
)
_ICON_PNG_B64 =(
"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"
"TkSuQmCC"
)

_CHIP_ICON_PNG_B64 =(
"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"
"TkSuQmCC"
)

_CREDIT_ICON_PNG_B64 =(
"iVBORw0KGgoAAAANSUhEUgAAACEAAAAaCAYAAAA5WTUBAAAE/klEQVR4nIWXa4iWVRDH//Ou67YL5t3KCiM1Ms0KLSyK7lkmmGlq"
"SgVmZOKHiIqoPvRBie4hahARFSni3czALAsvoXldNbWgTDIrvISa2rr7vr8+nP/Dnt62Gnh4zjkz8z8z88wzc04AEREA10m6X9KV"
"kpA0NSJ2ALUR0SxJwLmShkm6VVJ/SedIai/plKQDkjZLWi5plTFLkvB4gKROko5J2h8Rx40Z8mA60Mzf6U2DCDgfeA04wP9TGdgA"
"jJIJeAg45T1OAfuAt4GehcDkKpC9wKfAVeaPB35rQ2YR8CrwCjAP2N6GIwuABuDxfzH4e6CngJ22/hBwK1CbefB8ptAMfABcD7Q3"
"/yygvggrcDnwEnA009sC9ATGAFOMudF7AswScNCTZQZr5/eTGdAe4EZlBHSz4YeB7hTfNvEuBj7O9BurdGscuTLQKGAHUAEagXb2"
"6KYMYD3QrTAQqLPMxExmktfaF05YfnYms8gyReRWeH2bgBmeVIDbLLA3i0DnqggVyfq5PSkDX1TxSkCNxwsyQ0Z6raujWAHmChgA"
"nDbYaOAeK/wJDP4XA3oDTRn4GaBvG4aUgE7AT8b/xrznMt1RRdje80JHYI3Hs3MDqox52jKH/AA8+x/yj2abXgPMAVpIqVBXZPVF"
"pFrRl/QXNAH9SAlUykDD3m1yKF8HXvR4m3lRJR9AB9IPUAGmAffZoNGqJmCCmWuztSK8xTceROvvdR1whccVYEguWxWNDwtsYCAw"
"t8AvNqi1Ym/rrgDuAoZERMVAhYfjJJUk7ZO0RdJOSXvMH2eZKCKR6W3y+1JJP0XEeFLLqBShJiLKkjp7vkPSWEkrgUER0SKpDNRJ"
"GmmZZRHRFBEVSfO9dg/QEBEtQE1EEBHNpJ6z3zIdJHVxhEP2KKdmv0/4fbak1cDYiEDSzY4W2caStMC6vSTdYg/Ljsb7kqZJOpxF"
"qZQ9/zDiZ2/QTtLqzJB5wHmSRpi/S9LXRaJGxDeSNpg3wV2zB7BY0oOSDkrqYrzTko5HRIsjFoURRVZvtaX9I+IDSY+Z/62VR5q/"
"0BvWZo7MN+9OUoWdp9ZP1yjp6szRY6R6dKEj3EpAPXCSVDeK5BoBjALudnafAS7JdGodkQuAE5a5178vwCrgbFIVrpBK+VPmbcdl"
"XMC1QFePZwNHPM4Lz8cGWQIMA5YC/TJ+CVju33cJ0J90JgngdlrpNuAJYwFMEvCCJ1+SGlQP4Ahwh8FrSMXsD8s9AHzm8XHgDaCX"
"Zcd6/STQJzPwKxv3o/foCvxuQ9YI+MGT3fgsAfQBetFaoB4x+BFSC5+ZeQKpnb9IauFFGZ9i3fxIMJHWnrK0wJS9AXiryIvMgzor"
"zPKmn2S8G4HV/J12OVILSaV6OCmHAD6qyr/Fxjwhe1EmnXbq1QaRTktlYHPVepA670rSkWBoxptCa6fdTepFl5FK/TTSWRNgS95B"
"i0/yDuncOIN08JhO6nzYkBk4idswtkQ6xq3LorPdhu7OolJQBRgaQHdJn0ga3BawabCkyZImef6LpPWSvlOqH50k9ZM0SOkaUNAc"
"Se9KWqlUAHPaJemZiFhR1IIGSVMlDVcqvfWSWiQdVbpPTI+ItcDLNqbDfxjcJGmdpJkRsRToImmMpI7G/NXGb42IMlAKfPnJQtpR"
"UoNSLziWXXyKS9JASQ9LukHS+UoV85CBNypdfDZbp+QG1yaRmlz5L9pCUqcFy0FdAAAAAElFTkSuQmCC"
)

def _materialize_icon_files ():
    tmp_dir =tempfile .gettempdir ()
    ico_path =os .path .join (tmp_dir ,"revolt_icon.ico")
    png_path =os .path .join (tmp_dir ,"revolt_icon.png")
    chip_path =os .path .join (tmp_dir ,"revolt_chip_icon.png")
    credit_path =os .path .join (tmp_dir ,"revolt_credit_icon.png")
    try :
        with open (ico_path ,"wb")as f :
            f .write (base64 .b64decode (_ICON_ICO_B64 ))
    except Exception :
        pass 
    try :
        with open (png_path ,"wb")as f :
            f .write (base64 .b64decode (_ICON_PNG_B64 ))
    except Exception :
        pass 
    try :
        with open (chip_path ,"wb")as f :
            f .write (base64 .b64decode (_CHIP_ICON_PNG_B64 ))
    except Exception :
        pass 
    try :
        with open (credit_path ,"wb")as f :
            f .write (base64 .b64decode (_CREDIT_ICON_PNG_B64 ))
    except Exception :
        pass 
    return ico_path ,png_path ,chip_path ,credit_path 

ICON_PATH ,ICON_PNG_PATH ,CHIP_ICON_PATH ,CREDIT_ICON_PATH =_materialize_icon_files ()

_FONT_HUBOT_REGULAR_B64 =(
"AAEAAAANAIAAAwBQR0RFRjusOt8AAKsMAAABEEdQT1PVenquAACsHAAAwkBHU1VCvMXX0wABblwAAA3yT1MvMkXtZrkAAAFYAAAA"
"YGNtYXDll5scAAANOAAABc5nbHlmEzLnWAAAGMwAAHW6aGVhZBoLXAoAAADcAAAANmhoZWEHwAM8AAABFAAAACRobXR4BCRxsQAA"
"AbgAAAuAbG9jYZsEfMMAABMIAAAFwm1heHAC+AE0AAABOAAAACBuYW1lTH53VgAAjogAAAMUcG9zdMGJqjoAAJGcAAAZcAABAAAA"
"AgAAEnZUtF8PPPUAAwPoAAAAANVUmEoAAAAA4iN/x/73/vUEhAQhAAAABgACAAAAAAAAAAEAAARC/sAAAASh/vf8+gSEAAEAAAAA"
"AAAAAAAAAAAAAALgAAEAAALgAJgADACYAAgAAQAAAAAAAAAAAAAAAAADAAMABAI2AZAABgAIAooCWAAAAEsCigJYAAABXgBGARgA"
"AAAAAAAAAAAAAACgAADvUADkewAAAAAAAAAATk9ORQDAACD7AgRC/sAAAARCAUAgAACTAAAAAAINAtkAAAAgAAMDYQAyAvQAIAL0"
"ACAC9AAgAvQAIAL0ACAC9AAgAvQAIAL0ACAC9AAgAvQAIAL0ACAC9AAgAvQAIAL0ACAC9AAgAvQAIAL0ACAC9AAgAvQAIAL0ACAC"
"9AAgAvQAIAP9ACACpQBEAucALgLnAC4C5wAuAucALgLnAC4C5wAuAtAARALQAEQC0P/uAtD/7gJwAEQCcABEAnAARAJwAEQCcABE"
"AnAARAJwAEQCcABEAnAARAJwAEQCcABEAnAARAJwAEQCcABEAnAARAJwAEQCcABEAnAARAJkAEQC+AAvAvgALwL4AC8C+AAvAvgA"
"LwL4AC8C7wBEAyQAIwLvAEQCNgApA70AKQI2ACkCNgApAjYAKQI2ACkCNgApAjYAKQI2ACkCNgApAjYAKQI2ACkCNgApAYAAIwGA"
"ACMBgAAjArgARAK4AEQCSABEAkgAQQJIAEQCSABEAkgARAJ/ACQDdABEAuYARALmAEQC5gBEAuYARALmAEQC+ABEAwUALgMFAC4D"
"BQAuAwUALgMFAC4DBQAuAwUALgMFAC4DBQAuAwUALgMFAC4DBQAuAwUALgMFAC4DBQAuAwUALgMFAC4DBQAuAwUALgMFAC4DBQAu"
"AwUALgRhAC8CgQBEAmAARAMFAC4CqgBEAqoARAKqAEQCqgBEAosAJgKLACYCiwAmAosAJgKLACYCiwAmAqsARAKRACMCkQAjApEA"
"IwKRACMCkQAjAtUAOwLVADsC1QA7AtUAOwLVADsC1QA7AtUAOwLVADsC1QA7AtUAOwLVADsC1QA7AtUAOwLVADsC1QA7AtUAOwLV"
"ADsC1QA7AtUAOwLtACAD8gAiA/IAIgPyACID8gAiA/IAIgLlAB8CvgAeAr4AHgK+AB4CvgAeAr4AHgK+AB4CvgAeAr4AHgKRACYC"
"kQAmApEAJgKRACYC9AAgAvQAIAL0ACAC9AAgAucALgJwAEQCcABEAnAARAJwAEQC+AAvAjYAKQI2ACkCNgApAkgARAMFAC4DBQAu"
"AwUALgMFAC4DBQAuAtUAOwLVADsC1QA7A/IAIgK+AB4CvgAeApEAJgDiAEQCXQBEAOIAQQDi/+MA4v/MAOL/8QDiAEQA4gBAAOL/"
"2QDiACkA4v/DAOIABQDi/9QA4v/mAOIANQDiADUCTAAmAkwAJgJMACYCTAAmAkwAJgJMACYCTAAmAkwAJgJMACYCTAAmAkwAJgJM"
"ACYCTAAmAkwAJgJMACYCTAAmAkwAJgJMACYCTAAmAkwAJgJMACYCTAAmA4IAIQJMADkCLwAlAi8AJQIvACUCLwAlAi8AJQIvACUC"
"TAAmAqsAJgJMACYCMwAjAjsAJQI7ACUCOwAlAjsAJQI7ACUCOwAlAjsAJQI7ACUCOwAlAjsAJQI7ACUCOwAlAjsAJQI7ACUCOwAl"
"AjsAJQI7ACUCOwAlAWMAGQJEACYCRAAmAkQAJgJEACYCRAAmAkQAJgJBADkCQf/qAkH/wADKADkAygA5AMoANQDK/9cAyv/AAMr/"
"5QDKADkAygA0AMr/zQDKAB0Ayv+3AMr/+QDK/8gBlAA5AMr/0ADK/9AAyv/QAMr/wAI4ADkCOAA5AMoAOQDKADUAygA5AMoALQFO"
"ADkBBAAbA7AAOQJBADkCQQA5AkEAOQJBADkCQQA5AkEAOQJHACUCRwAlAkcAJQJHACUCRwAlAkcAJQJHACUCRwAlAkcAJQJHACUC"
"RwAlAkcAJQJBACUCQQAlAkEAJQJBACUCQQAlAkEAJQJHACUCRwAlAkQAJAJHACUD3AAlAkwAOQJMADkCTAAmAVQAOQFUADkBVP/4"
"AVQALAH2ABwB9gAcAfYAHAH2ABwB9gAcAfYAHAJ3ABkBagAZAXgAIQFqABkBagAZAWoAGQJBADICQQAyAkEAMgJBADICQQAyAkEA"
"MgJBADICQQAyAmoAMgJqADICagAyAmoAMgJqADICagAyAkEAMgJBADICQQAyAkEAMgJBADICSAAWAzkAFwM5ABcDOQAXAzkAFwM5"
"ABcCQAAVAkIAFgJCABYCQgAWAkIAFgJCABYCQgAWAkIAFgJCABYB8QAcAfEAHAHxABwB8QAcAMoANADK//kCNQAyAjUAMgI1ADIC"
"NQAyAjUAMgI1ADICNQAyAjUAMgI1ADICNQAyAjUAMgI1ADICNQAyAjUAMgI1ADICNQAyAjUAMgI1ADICNQAyAjUAMgI1ADICNQAy"
"Ai8AJQI7ACUCOwAlAjsAJQI7ACUCRAAmAMoAKQDK/9oAygApAMoAKQDK/9ABbAA5AkcAJQJHACUCRwAlAkEAJQJBADICQQAyAmoA"
"MgM5ABcCTAAWAkwAFgJMABYCTAAWAkwAFgJMABYB8QAcAQQAOQEEABUBBAA5AQQAOQFeADkBIgAcAU4AOQFOADkBTgAkAU4ALADK"
"ACkBdgA5AoMAGQMrABkDTwAZAgcAGQIxABkCawAZA4wAGQFYABUBYgAVAkYAMgJNABkCmQAxAWkAJAJcACcCYQAnApgAJAJnACkC"
"fgAyAlYAKgJxACsCfgArAyYAMQMmADEDJgAxAyYAMQMmADEDJgAxAyYAMQMmADEDJgAxAyYAMQMmADEDJgAxAyYAMQMmADEDJgAx"
"AyYAMQMmADEDJgAxAyYAMQMmADEChwA0AocAUQKHADkChwA2AocAIwKHADgChwA8AocAMgKHADQChwA1AZQAKQD/AB0BagAhAW8A"
"IQGBAB0BeQAqAYQAKwFoACEBfgAkAYQAJwGUACkA/wAdAWoAIQFvACEBgQAdAXkAKgGEACsBaAAhAX4AJAGEACcAkP83Au4AHQLR"
"AB0DOAAhAv8AHQNmACEDbgAqAx8AIQG5ACgBCgAbAY0AIAGRACABqgAcAZsAJwGnACoBiwAhAaAAIwGnACUBuQAoAQoAGwGNACAB"
"kQAgAaoAHAGbACcBpwAqAYsAIQGgACMBpwAlALEAAACxAAAAvQAoAL4AFwC9ACgAvQAXAj0AKADKADoAygA6AfMAGQHzACcAvQAo"
"AQYAFwEoABACjQAeAbcABAG2AB4AygA6AfMAJwCEAAsAyQAjAMMAGwDJACMAxQAbAlcAIwDKACMAygAjAf0AJAH9ACcAyQAjAAD/"
"CgDKACMB/QAnAKIACAAA/vcBZQAoAecAKAKYACgBWwABAWUAKAHnACgCmAAoATMAKwEzAB0BiAAiAYgAJQFQAEQBUAAlAScAKwEl"
"AB0BhAAiAYMAJAFQAEQBUAAkAL4AFwFsABcBbAAoAWwAFwC+ACgAvgAXAgIAJwICADEBLgAnAS4AMQFJACkAmwApAMMAGwF6ABsB"
"egAhAXoAGwDDACEAwwAbAh4AGgNnADIDZwAyAzsAPANhADIDWgAkAr4ALAKtABUB2QArAygAMgJMADIDKAAyAuEAHgGAACsBGABl"
"ARgAZQIWAC0DVQBaBG0ARAKwAEkCRQAxAokAPwKXACwDNwA7AooALwJ9ADMC4gBKAo8ALQLKACQChwBbAocASwKHAE0ChwBIAocA"
"UAKHAFAChwA9AocAVQKHACsChwA2AocASgKHAHIChwA0AmkAcwKHAHUDdgAjAw0AHwGuABcCawA5Ai4AHQJvABgDNgAdBKEAHQKH"
"AFcCIABJArwAUQIgAEoCvABFAv0ARQMmADEDJgAxAtoAMgAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACcA"
"AAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAqAAAAKAAAACgAAAAo"
"AAAAKgAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgBUgAoAKkAKAEYACgBGAAoAckAKAGbACgBmwAoAWwAKAEhACgBigAnAawA"
"KAExACgA9QAoAAAAAgAAAAMAAAAUAAMAAQAAABQABAW6AAAAjACAAAYADAAvADkAfgCsALQBNwFIAU0BfgGSAaEBsAHnAhsCNwLH"
"At0DBAMMAxIDGwMjAygDOAO8A8AehR6eHvkgFCAaIB4gIiAmIDAgOiBEIHAgeSCJIKogrCC6IL8hEyEXISIhLiFeIZQiBSIPIhIi"
"GiIeIisiSCJgImUkaCTqJP8lzCXPJjonEyd++P/7Av//AAAAIAAwADoAoACuALYBOQFKAVABkgGgAa8B5gIYAjcCxgLYAwADBgMS"
"AxsDIwMmAzUDvAPAHoAenh6gIBMgGCAcICIgJiAwIDkgRCBwIHQggCCqIKwguSC/IRMhFiEiIS4hWyGQIgUiDyIRIhoiHiIrIkgi"
"YCJkJGAk6iT/JcslzyY5JxMndvj/+wH//wAAAaEAAAAAAAAAAAAAAAAAAADfAAAAAAAAAAD+7gASAAAAAAAA/6j/oP+Z/5f/i/4T"
"/hAAAOHkAADiOgAAAADiE+IJ4nTiLuHJ4a/hr+GV4eHh3AAA4cXhbgAA4VvhVOC2AADgmeCRAADgiOB/4HTgUeAzAADdhtz73Nzc"
"4dzc3DnbYdpmCXYGyAABAIwAAACoATABSAFUAlYCdAJ6AAAC1ALWAtgC2gAAAAAC3ALmAu4AAAAAAAAAAAAAAAAAAALsAAAC9AAA"
"A6QDqAAAAAAAAAAAAAAAAAAAAAAAAAAAA5gAAAAAA5YAAAAAAAADkgAAAAADlgAAAAAAAAAAAAADjgAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAACKQIwAmkCNwKHAqMCdwJqAlMCVAI2Ao4CLAJMAisCOAItAi4ClQKSApQCMgJ2AAEAGAAZAB8AIwA1ADYAPAA/AEwATwBR"
"AFcAWABeAHUAdwB4AHwAgwCIAJsAnAChAKIAqgJXAjkCWAKcAk8C1QDYAO8A8AD2APoBDAENARMBFgEkASgBKgEwATEBNwFOAVAB"
"UQFVAVwBYQF0AXUBegF7AYMCVQJ/AlYCmwIqAjEChQKMAoYCjQKAAnkC0wJ6Ac0CZQKaAnsC3QJ+ApgCIQIiAtYCeAI0At4CIAHO"
"AmYCDwIOAhACMwARAAIACQAWAA8AFQAXABwAMAAkACcALQBHAEEAQwBEACIAXABoAF8AYABzAGYCkAByAI4AiQCLAIwAowB2AVsA"
"6ADZAOAA7QDmAOwA7gDzAQcA+wD+AQQBHgEYARoBGwD5ATUBQQE4ATkBTAE/ApEBSwFnAWIBZAFlAXwBTwF+ABMA6gADANoAFADr"
"ABoA8QAdAPQAHgD1ABsA8gAgAPcAIQD4ADIBCQAlAPwALgEFADMBCgAmAP0AOQEQADcBDgA7ARIAOgERAD4BFQA9ARQASwEiAEkB"
"IABCARkASgEhAEUBFwBAASMATgEnAFABKQBSASsAVAEtAFMBLABVAS4AVgEvAFkBMgBbATQAWgEzAF0BNgBxAUoAcAFJAHQBTQB5"
"AVIAewFUAHoBUwB9AVYAgAFZAH8BWAB+AVcAhgFfAIUBXgCEAV0AmgFzAJcBcACKAWMAmQFyAJYBbwCYAXEAngF3AKQBfQClAKsB"
"hACtAYYArAGFAGoBQwCQAWkAOAEPAIEBWgCHAWAC2gLUAtsC3wLcAtcCsAKxArMCtwK4ArUCrwKuArkCtgKyArQAoAF5AJ0BdgCf"
"AXgAEADnABIA6QAKAOEADADjAA0A5AAOAOUACwDiAAQA2wAGAN0ABwDeAAgA3wAFANwALwEGADEBCAA0AQsAKAD/ACoBAQArAQIA"
"LAEDACkBAABIAR8ARgEdAGcBQABpAUIAYQE6AGMBPABkAT0AZQE+AGIBOwBrAUQAbQFGAG4BRwBvAUgAbAFFAI0BZgCPAWgAkQFq"
"AJMBbACUAW0AlQFuAJIBawCnAYAApgF/AKgBgQCpAYICYwJkAl8CYQJiAmACigKJAoMCfAKpAqYCpwKoAqoCoQKPApcClgAAAAAA"
"2gD2AQIBDgEaASoBNgFCAU4BWgFmAXYBggGOAZoBpgGyAb4BygHWAeIB7gH6AiECVgKFApECnQKpArUCwQLiAu4C9gMBAxgDJAMw"
"AzwDSANUA2QDcAN8A4gDlAOgA6wDuAPEA9AD3APoA/wENQRBBE0EWQRlBHEEiASUBKAEtQTBBM0E2QTlBPEE/QUJBRUFIQUtBTkF"
"RQVXBWMFbwWJBZUFpAWwBccF0wXfBeoGDQYoBjQGQAZMBlgGfAayBr4GygbWBuYG8gb+BwoHFgciBy4HOgdGB1IHXgdqB3YHggeO"
"B5oHpQexB9wH/gghCGAIiAiUCKAIrAjtCPkJBQkRCR0JKQlRCWIJbQl5CYUJkQmyCb4JygnWCeIJ7gn6CgYKEgoeCioKNgpCCk4K"
"WgpmCnIKfgqKCqAKxwrTCt8K6wr3CxQLLgs6C0YLUgteC2oLdguCC5gLpAuwC7wLzAvcC+gL9AwADBAMHAwoDDQMQAxMDFgMZAxw"
"DIAMjAyYDKQM5gzyDP4NCg0WDSINLg06DUYNUg1eDWoNdg2CDY4NmQ2lDbENvQ3IDdQN4A3sDfcOLQ45DkQOTw5eDmkOdA5/DooO"
"lQ6kDq8Oug7FDtAO3A7nDvMO/g8KDxYPIQ+DD7kP5g/yD/0QCRAUECAQVhCUEKAQ6REfESsRNhFBEUwRVxFmEXERfBGHEZIRnhGq"
"EbURwRHMEdgR4xH8EkESTBJXEmISbhJ6EpsSphKyEr0SyRLUEt8S6hL1EwATCxMWEyETLBM6E0UTURNcE24TeROEE5wTqBO0E8AT"
"0xPeE+oT9RQuFE8UWxRmFHIUfRSlFNUU4RTsFPcVBhURFRwVJxUyFT4VSRVVFWEVbRV5FYQVkBWbFaYVsRW8FccV0xYIFj0WcxaN"
"FpgWoxauFuwW+BcDFw4XGRclF2AXeBeXF7cXwhfOF9gX5BfvF/oYBRgRGBwYKBg0GEAYTBhXGGMYbhh5GIQYkBicGKcYvBjjGO8Y"
"+xkHGRMZLBlKGVYZYRlsGXgZgxmPGZoZsBm8GccZ0xneGekaIhouGjkaRBpTGl4aaRp0Gn8aihqZGqQarxq6GsUa0RrcGuga8xr/"
"GwsbFhsiGzEbPBtIG1QbYBtrG3YbgRuMG5cboxuyG70byRvVG+Ab7Bv4HAQcHBwoHDMcPhxKHFUcYRxxHH0clRygHKwctxzIHNMc"
"3hzpHPQdAB0oHVQdfx2cHbkd2h4JHkMebR6QHqse3B7sHxsfWx93H6kf6x//IE0gVyBjIG8geyCHIJMgnyCrILcgwyDQINwg6CD0"
"IQAhDCEYISQhMCE8IUkheiGPIb4h/SIZIksijSKhIvAi+iMjIzMjXyOcI7Yj5yQhJDUkfSSHJJAkmSSiJKsktCS9JMYkzyTYJOEk"
"7iT+JQ4lHiUuJT4lTiVeJYclmCXEJgEmGyZMJoYmmiblJu8m+CcBJwonEyccJyUnLic3J0AnSSdJJ0knVCdjJ28neyeLJ6AnqifY"
"J+In6ygBKDMoXChpKHcogSiLKJcorSjHKNMo3yjvKQ4pGClQKVopYylvKXkpgymZKa8pvCnJKdYp4ynrKfMp+yoZKiMqUSpbKmsq"
"dSqTKp0qySrTKuMq7Sr1KwErCysUKx4rJyszKz0rTCtWK2IrcSt5K4UrjyuZK6MrrCvPLC4slyyqLLItGy12LZEt9S5OLpsu6i8T"
"LzkvRS9YL5MvyDAMMFMwhjDMMRUxVjGAMasx0DH7MiUyOTJGMl8ydzKLMqoyvjLIMuIy/DMXM1wzbDOSM6Mz9DQ6NFI0ZDSDNJg0"
"7jVoNZU1qDW1Nb81yTXjNgE2Nzb5Nws3FzckNzE3RDdVN2Y3fzelN8g31Tf1OAU4GTglODU4XTh9OIo4lzikOLE40TjxOSQ5WTlw"
"OYc5rjnaOec59ToCOiM6STpfOnU6fTqFOo06lTqdOqU6rTq1Or06xTrNOtU63QAAAAgAMv/1Ay8C4gBXAGAAaQBzAHsAgwCOAJcA"
"AAEiDgIVFBYWFxY2NTUGLgIxJiYxJjY2MR4CMRYWNjc2NjcuAzU0NjcmJjcwNhYXNjYzMhYXNjYWMRYGBxYWFRQOAgcWFhUVFBY3"
"PgI1NC4CATQjJgYVBhcWFzYnJgcGFxYWFzYnJgcGFBcWFhc2JyYHBhcWFzQnJgcUFxY3NCYHIgYXFDM2Ngc0IyIVFBYzNgGwT4tp"
"O0N2TQsOKDMcCwwcEQMPExsOECsoCgMPCCA/Mh4VEwMJEBYuJBgwGBkwGCUtFhEKAxMVHjI/IAoQDwxMdUM7aYv+xAUCBAEEBw4C"
"AgQFAwUCBBMCAgYFAQECBxUDBQUFAwYEIQUIAgUIPgUDBAQBCAMGHwcHBAMHAuI7aYtPVZNrGQMKC0YICxcUIhYMCgIBFRMdDggE"
"EhsHBBMpRzceNBMINigBDxoIBgYIGg8BKDYIEzQeOEcpEgQIJRppCwoDGWuTVU+LaTv92wMDAQICAwIOAQcEAwMFAQIVAwcGAwEH"
"AgICFAMHBQMEBgcHBgIDBgUDAggCAwEFAgQBBAIEBAIHBAACACAAAALTAtkABwANAAAzMzchFzMBIxc3MxcTISBeRQFtRV7+4ngl"
"EwcUgv7PsLAC2ZJHR/61//8AIAAAAtMDpQImAAEAAAAHArEBIgDM//8AIAAAAtMDpAImAAEAAAAHArUAxADM//8AIAAAAtMEEAIm"
"AAEAAAAHAsQAxADM//8AIP9aAtMDpAImAAEAAAAnArwBIQAAAAcCtQDEAMz//wAgAAAC0wQQAiYAAQAAAAcCxQDEAMz//wAgAAAC"
"0wQXAiYAAQAAAAcCxgDEAMz//wAgAAAC0wQNAiYAAQAAAAcCxwDAAMz//wAgAAAC0wOkAiYAAQAAAAcCswCsAMz//wAgAAAC0wQc"
"AiYAAQAAAAcCyACsAMz//wAg/1oC0wOkAiYAAQAAACcCvAEhAAAABwKzAKwAzP//ACAAAALTBBwCJgABAAAABwLJAKwAzP//ACAA"
"AALTBCECJgABAAAABwLKAKwAzP//ACAAAALTBA0CJgABAAAABwLLAK0AzP//ACAAAALTA6cCJgABAAAABwKuANEAzP//ACD/WgLT"
"AtkCJgABAAAABwK8ASEAAP//ACAAAALTA6UCJgABAAAABwKwALoAzP//ACAAAALTA9oCJgABAAAABwK5AQoAzP//ACAAAALTA30C"
"JgABAAAABwK4AKMAzP//ACD/RALfAtkCJgABAAAABwK/AhIAAP//ACAAAALTA+YCJgABAAAABwK2AOkAzP//ACAAAALTA54CJgAB"
"AAAABwK3ALYAywACACAAAAPVAtkADwAVAAAzMzchFyE1IQMhNSEnITUhFzczFxMhIF5FAW1FAWD+32UBCf7aXgH//WolEwcUgv7P"
"sLBPAQFL70+SR0f+tQADAEQAAAJ7AtkADwAZACMAADMhMjY1NCYnNTY2NTQmIyEFMhYVFRQGIyM1EREzMhYVFRQGI0QBTHB7Skc7"
"Rmln/qkBTjpDPkDz9EBKR0RmXkdeDQYOV0NTYks1NCIvPPb9vQEENzciNT8AAQAu//YCvwLjAB4AAAUyNjcjBgYjIiY1NTQ2NjMy"
"FhczJiYjIgYGFRUUFhYBgYmmD1sQc19yhDluT150EFsPpYlkmlZWmQqEdVVWdmeXQWQ4VVZ1hEqOZnFlj0oA//8ALv/2Ar8DpQIm"
"ABkAAAAHArEBKwDM//8ALv/2Ar8DpAImABkAAAAHArQAtgDM//8ALv8oAr8C4wImABkAAAAHAr4A8QAA//8ALv/2Ar8DpAImABkA"
"AAAHArMAtgDM//8ALv/2Ar8DpQImABkAAAAHAq8BLwDMAAIARAAAAqIC2QAJABMAADMhMjY1NTQmIyEFMhYVFRQGIyMRRAEJoLWw"
"pf73ARBzfXl3t6OjTZ+nTnJrg2d2Aj0A//8ARAAAAqIDpAImAB8AAAAHArQAlwDM////7gAAAqIC2QIGACIAAP///+4AAAKiAtkC"
"JgAfAAAABgLMxmYAAQBEAAACSQLZAAsAADMhNSERITUhNSE1IUQCBf5UAS/+0QGq/f1PAQFL708A//8ARAAAAkkDpQImACMAAAAH"
"ArEA2wDM//8ARAAAAkkDpAImACMAAAAHArUAfQDM//8ARAAAAkkDpAImACMAAAAHArQAZQDM//8ARAAAAkkDpAImACMAAAAHArMA"
"ZQDM//8ARAAAAkkEHAImACMAAAAHAsgAZQDM//8ARP9aAkkDpAImACMAAAAnArwA2gAAAAcCswBlAMz//wBEAAACSQQcAiYAIwAA"
"AAcCyQBlAMz//wBEAAACSQQhAiYAIwAAAAcCygBlAMz//wBEAAACSQQNAiYAIwAAAAcCywBmAMz//wBEAAACSQOnAiYAIwAAAAcC"
"rgCKAMz//wBEAAACSQOlAiYAIwAAAAcCrwDeAMz//wBE/1oCSQLZAiYAIwAAAAcCvADaAAD//wBEAAACSQOlAiYAIwAAAAcCsABz"
"AMz//wBEAAACSQPaAiYAIwAAAAcCuQDDAMz//wBEAAACSQN9AiYAIwAAAAcCuABcAMz//wBE/0QCVQLZAiYAIwAAAAcCvwGIAAD/"
"/wBEAAACSQOeAiYAIwAAAAcCtwBvAMsAAQBEAAACQQLZAAkAADMzESE1ITUhNSFEWQF7/oUBpP4DAT9P/E8AAAEAL//3AsEC4wAm"
"AAAFMjY3MxczESEVMxUGBiMiJiY1NTQ2NjMyFhczJiYjIgYGFRUUFhYBdFCGIwYIRf7L3RR+VUtuOztuTF9zEF0PpollmlVSkwk5"
"M2MBdkpoOkY2YD+oPmA2UlRwhE2OYnlfjEsA//8AL//3AsEDpAImADYAAAAHArUAygDM//8AL//3AsEDpAImADYAAAAHArQAsgDM"
"//8AL//3AsEDpAImADYAAAAHArMAsgDM//8AL/71AsEC4wImADYAAAAHAr0BHwAA//8AL//3AsEDpQImADYAAAAHAq8BKwDMAAEA"
"RAAAAqsC2QALAAAzMxEhETMRIxEhESNEWQG1WVn+S1kBTP60Atn+wwE9AP//ACMAAAMBAtkAJgA8GwAABwLB//sBLP//AEQAAAKr"
"A6QCJgA8AAAABwKzAKsAzAABACkAAAIOAtkACwAAMyE1IxEzNSEVMxEjKQHlxsb+G8bGTwI7T0/9xf//ACkAAAN7AtkAJgA/AAAA"
"BwBMAj4AAP//ACkAAAIOA6UCJgA/AAAABwKxAMQAzP//ACkAAAIOA6QCJgA/AAAABwK1AGYAzP//ACkAAAIOA6QCJgA/AAAABwKz"
"AE8AzP//ACkAAAIOA6cCJgA/AAAABwKuAHQAzP//ACkAAAIOA6UCJgA/AAAABwKvAMgAzP//ACn/WgIOAtkCJgA/AAAABwK8AMMA"
"AP//ACkAAAIOA6UCJgA/AAAABwKwAFwAzP//ACkAAAIOA9oCJgA/AAAABwK5AKwAzP//ACkAAAIOA30CJgA/AAAABwK4AEYAzP//"
"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"
"FBYXFxYWFRQGIyImJyMWFv4/YThVUE0wLjo3NUQFWAdvYDlbNUlPUDA1PD49SAVbCHMKIkQzREYRDwslICQqKi1FUSNCMTpEEg8M"
"JiclLC4xR1kA//8AHP/2AdYC2QImAVUAAAAHArEAoAAA//8AHP/2AdYC2AImAVUAAAAGArQrAP//ABz/KAHWAhYCJgFVAAAABgK+"
"ZwD//wAc//YB1gLYAiYBVQAAAAYCsysA//8AHP71AdYCFgImAVUAAAAHAr0AmAAAAAEAGQAAAlgC4gAsAAAzMxE0NjMyFhUUBiMj"
"FTMyFhUVFAYjIxUzMjY1NCYnNTY2NTQmIyIGBhUjFTN+VEVCPUVBQCU+P09MVE5Zbn5PRzI3cmA9YztlZQIDR0o+OzdCPT0+JjFL"
"SG1jTWUKBhBQO1JjL15IRwABABkAAAFMAqUADwAAMzM1IxEzNSM1IxUjFTMRFMKKe3NzWV9fTAF4SZiYSf6DRwABACEAAAFUAqUA"
"FwAAMzM1IzUzNSM1MzUjNSMVIxUzFSMVMxUUyop7c3Nzc1lfX19fTKFJjkmYmEmOSaZHAAIAGQAAAW0C2QADABMAABMzNyMDMzUj"
"ETM1IzUjFSMVMxEU/0okSmGKe3NzWV9fAj6b/SdMAXhJmJhJ/oNHAP//ABn/KAFjAqUCJgFcAAAABgK+WgD//wAZ/vUBTAKlAiYB"
"XAAAAAcCvQCLAAD//wAy//cCCAINAA8BMQJBAg3AAP//ADL/9wIIAtkCJgFhAAAABwKxAM0AAP//ADL/9wIIAtgCJgFhAAAABgK1"
"bwD//wAy//cCCALYAiYBYQAAAAYCs1cA//8AMv/3AggC2wImAWEAAAAGAq58AP//ADL/WgIIAg0CJgFhAAAABwK8AMwAAP//ADL/"
"9wIIAtkCJgFhAAAABgKwZQD//wAy//cCCAMOAiYBYQAAAAcCuQC1AAD//wAy//cCYgJ1ACYBYQAAAAcCuwGb//P//wAy//cCYgLZ"
"AiYBaQAAAAcCsQDNAAD//wAy/1oCYgJ1AiYBaQAAAAcCvADMAAD//wAy//cCYgLZAiYBaQAAAAYCsGUA//8AMv/3AmIDDgImAWkA"
"AAAHArkAtQAA//8AMv/3AmIC0gImAWkAAAAGArdh////ADL/9wINAtkCJgFhAAAABgKybAD//wAy//cCCAKxAiYBYQAAAAYCuE4A"
"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"
"JicjFhYBLX2Sd3U3XyMJEQGM/iYZUx9YOkpaYVNOWgVWBogKfHtxfiMn+U7+bAUqL0dHPkBMRkNhcwACADL/9gJTAuMAHwAtAAAF"
"MjY2NTQmIyIGByM2NjU0NjMyFhczJiYjIgYGFRUUFjciJjU1NjYzMhYVFRQGAURPekZ1c0R1JgYBAWVgRFkKUwx8cVSASI+DUmkg"
"ZUVLV14KNW9Vcn03OA8pE3RuPTpTa0KNcZCOj01ZWzE1P0dJN0NPAAABACoAAAIyAtkACQAAMzMBNSEVMzUhFYplAUP9+EYBYAKG"
"U9eJCwAAAwAr//YCRwLjABoAKAA2AAAFMjY1NCYnNTY2NTQmIyIGBhUUFhcVBgYVFBYTIiY1NTQ2MzIWFRUUBgMiJjU1NDYzMhYV"
"FRQGATiCjVlEREiMcktyQEhERFiMgVVPV01PVk9WU15TXl9TXwpoZE9ZDQcOWEBiXSlUQkBYDgcNWVBjaAGiQS4jNTo6NSMuQf6o"
"PjkmM0ZGMyY5PgD//wAr//YCTALjAA8B1wJ+AtnAAP//ADH/4wL1AvcCJgKrAAAABwH5AMoApP//ADH/4wL1AvcCJgKrAAAABwH6"
"AQIApP//ADH/4wL1AvcCJgKrAAAABwH7ANwApP//ADH/4wL1AvcCJgKrAAAABwH8AN4ApP//ADH/4wL1AvcCJgKrAAAABwH9ANUA"
"pP//ADH/4wL1AvcCJgKrAAAABwH+ANQApP//ADH/4wL1AvcCJgKrAAAABwH/AM8ApP//ADH/4wL1AvcCJgKrAAAABwIAAN8ApP//"
"ADH/4wL1AvcCJgKrAAAABwIBANUApP//ADH/4wL1AvcCJgKrAAAADwH/AlgCNsAA//8AMf/jAvUC9wImAqwAAAAHAfkAygCk//8A"
"Mf/jAvUC9wImAqwAAAAHAfoBAgCk//8AMf/jAvUC9wImAqwAAAAHAfsA3ACk//8AMf/jAvUC9wImAqwAAAAHAfwA3gCk//8AMf/j"
"AvUC9wImAqwAAAAHAf0A1QCk//8AMf/jAvUC9wImAqwAAAAHAf4A1ACk//8AMf/jAvUC9wImAqwAAAAHAf8AzwCk//8AMf/jAvUC"
"9wImAqwAAAAHAgAA3wCk//8AMf/jAvUC9wImAqwAAAAHAgEA1QCk//8AMf/jAvUC9wImAqwAAAAPAf8CWAI2wAAAAwA0//YCUwLj"
"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"
"QLW3PAFvRpFOCf6XAAMAI/+9AXwBgAAZACcANQAAFzI2NTQmJzU2NjU0JiMiBhUUFhcVBgYVFBYTIiY1NTQ2MzIWFRUUBgciJjU1"
"NDYzMhYVFRQGz1VYNScoKVhKSVgqJyc1WVMoKCslJiwpKSgwKy4uKjBDQjovNQkECTMkOzs7OyQzCQQJNS86QgEDIBcRGh4eGhEX"
"IMIgHBIaIyMaEhwg//8AJf+9AX0BgAAPAhsBpwE9wAD//wAoAWQBkQMnAgcCFQAAAaf//wAbAWsA0gMgAgcCFgAAAaf//wAgAWsB"
"awMmAgcCFwAAAaf//wAgAWQBbQMnAgcCGAAAAaf//wAcAWsBjgMgAgcCGQAAAaf//wAnAWQBdwMgAgcCGgAAAaf//wAqAWQBggMn"
"AgcCGwAAAaf//wAhAWsBbwMgAgcCHAAAAaf//wAjAWQBfAMnAgcCHQAAAaf//wAlAWQBfQMnAgcCHgAAAacAAQAoAAAAlgBqAAMA"
"ADMzNSMobm5qAAEAF/9mAJYAagAGAAAXMzc1IxUzF0U6bjianWdq//8AKAAAAJYCDAImAisAAAAHAisAAAGi//8AF/9mAJYCDAAm"
"AiwAAAIHAisAAAGi//8AKAAAAhUAagAmAisAAAAnAisAwAAAAAcCKwF/AAAAAgA6AAAAkALZAAUACQAANzMTNSMVAzM1I1AqFFIC"
"VlbCATXi4v4JYAD//wA6AAAAkALZAA8CMADKAtnAAAACABkAAAHMAuMAGwAfAAA3MzU0PgM1NCYjIgYHMzY2MzIWFRQOAxUHMzUj"
"zU0kNTUkb2ZiegJQAUZCO0giMjIiBFhYvA0jPDpBTzNWaGtpPko8PypCOjpELMxg//8AJ//2AdoC2QAPAjIB8wLZwAD//wAoAOEA"
"lgFLAgcCKwAAAOEAAQAXAKoA8AGBAAsAABMUFjMyNjU0JiMiBhc+LjE8PDEuPgEVLj09Li89PQABABABwQEYAtkAHQAAEzM1JxcX"
"NycnNzcnBwc3NSMVFycnBxcXBwcXNzcHfyoLNy4VLzw8LhQuNwsqCjQxEy48PC8UMTQKAcE1QywaJxoaGBomGSpCNDRCKhkmGhga"
"GicaLEMAAgAeAAACcALZABsAHwAAMzM1MxUzNTM1IzUzNSM1IxUjNSMVIxUzFSMVMzc1MxWeSsNJfHx8fEnDSoCAgIBKw8nJyUTQ"
"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"
"BTI2NjU0LgIjIg4CFRQWFjciJiY1NDY2MzIWFhUUBgYDMjU1NCMiFRUUMzI1NTQjIhUVFAc2NjMyFhc3JiYjIgYHAbVwrWQ5aIxU"
"VI1pOWSvcGOZV1eZY2KYV1eYuiAgIM4hIR/1GWNCQmIZJBt1UVJ1GwpeqnBTiWM2NmOJU3CqXixUlWNjlFJSlGNjlVQBZiU7JSU7"
"JSU7JSU7Jc8pNDQpDzZDQzYAAAUAMv/2AzYC4wARACEAKwA1AE0AAAUyNjY1NC4CIyIOAhUUFhY3IiYmNTQ2NjMyFhYVFAYGAzI1"
"NTQjIhUVFDMyNTU0IyIVFRQDMjY2NzM1IxUzBgYjIiYnMzUjFTMeAgG1cK1kOWiMVFSNaTlkr3BjmVdXmWNimFdXmLogICDOISEf"
"OURrRAkhdiYLcVFRcAsodyEJQ2sKXqpwU4ljNjZjiVNwql4sVJVjY5RSUpRjY5VUAWYlOyUlOyUlOyUlOyX+5zFYOhYWRFNUQxYW"
"OlgxAAEAPABxAv8CYwAFAAAlAScBJwcBCAH3L/4/nTZxAbY8/n3ONAD//wAy//UDLwLiAgYAAAAAAAIAJP+bAzcC4gA+AEoAAAUy"
"NjY3JwYGIyImJjU0NjYzMhYWFRQGIyImNzcjByMmJiMiBgYVFBYzMjY3MxYWMzI2NjU0JiYjIgYGFRQWFhMiJjU0NjMyFhcGBgGz"
"K1lPGxola0JmmFNSl2hhklJANSQkBA8sCgUMQSwxSipYPypKDwUFOTE1UC1jrnB3tmVfs2IuNjo5LTgDBDtlESIXMR0iVaBwaqNd"
"T45gWHA2Qt9MKC82YkJdYTAyLTdCdk5vp11rvn98u2gBCUVDR1pLQ0ZVAAMALP/2ApcC4wAmADQAPwAAFzI2NxczJzY2NzM1IxUU"
"BgcnNjY1NTQmIyIGFRUUFhcVBgYVFRQWEyYmNTU0NjMyFhUVFAYDIiY1NTQ2NxcGBvNEbiBicKcJDQN1tgcGkUVMWlFUYiwuQEhu"
"ZywnMTEvLjQ4OkUqN7ETTAo2NmSqFzkfRBMdNBedJF86FkNQVEUZKE8zBSJiQB1OXQGwLkAfGycvLSkWKET+cTszHClDH70qLgAA"
"AQAV/2kCdQLZAA8AABczETMRMxEzNSEiBhUUFjfaUahQUv5tX25kYZcDIPzgAyBQWFhPYAEAAgAr//YBpQLjADIARAAAFzI2NTQm"
"JzY2NTQmJicmJjU0NjMyFhczJiYjIgYVFBYXBgYVFBYXFhYVFAYjIiYnIxYWEyYmJyYmNTQ2NxYWFxYWFRQG51NkGBYYGyVELzw/"
"MzIxNwFHAl5QTWEbGhsfUEZDOjc1Nz4CRwJkrBAnFjU0FREOJBM1NRAKTUYmNBIUNh8xOiMMDigsJS0yN09RTEMlMxMTOCBCPBIS"
"Ki4oLzk3T1gBGwgLBA4pKhQlDwcIBQ0rLhYiAAADADL/4wL2AvcAEQAjAD8AAAUyNjY1NTQmJiMiBgYVFRQWFjciJiY1NTQ2NjMy"
"FhYVFRQGBicyNjcjBgYjIiY1NTQ2MzIWFzMmJiMiBhUVFBYBlWmfWVmeammgWlmgaluKTUyKXFuJTkyKXlZtBEkHQzI9S0ZCMkMH"
"SQRtVl50bx1UmWZuZphVVJhnbWWaVS9IhFhuV4RKSYRYbViESVxcUDc1QUR0Pkc1NlBbbWlTZm8ABAAyAPECGgLhAA8AHwAtADUA"
"ACUyNjY1NCYmIyIGBhUUFhY3IiYmNTQ2NjMyFhYVFAYGJzM1MxczJzY2NTQmIyMXMhUVFCMjNQEmRW5BQG5GRW9AP29GOlw2Nlw6"
"O1w1NVyeMDFDOUkcJSwpgHwmJkzxP3BJSm8/P29KSXA/JTVfPj9gNTZfPz5fNVJjY2gCKh8mKikhDSJQAAQAMv/jAvYC9wARACMA"
"LgA3AAAFMjY2NTU0JiYjIgYGFRUUFhY3IiYmNTU0NjYzMhYWFRUUBgYnMzUzMjY1NCYjIxcyFhUUBiMjNQGVaZ9ZWZ5qaaBaWaBq"
"W4pNTIpcW4lOTIrwRHtKUU5Nv7YsMiszch1UmWZuZphVVJhnbWWaVS9IhFhuV4RKSYRYbViESXKuS0dGTDcqMiszugAAAgAeAaEC"
"vALZABEAGQAAATM1JzMXMzczBxUzESMHIycjAzM1MzUhFTMBVDwBAl4wXwMCPVdbBF1V1T9m/vphAaGBaOnpaIEBOOTk/sj/OTkA"
"AAIAKwGvAVUC4QALABcAABMyNjU0JiMiBhUUFjciJjU0NjMyFhUUBsBBVFRBQVRUQSczMycmMzMBr1VDRlRURkRUNjQuLzU1Ly40"
"AAABAGX/vQCzAtkAAwAAFzMRI2VOTkMDHAACAGX/vQCzAtkAAwAHAAATMxEjETMRI2VOTk5OAZQBRfzkAUUAAAIALf/3AdIC4wAb"
"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"
"FBYFMjY1NCYjIgYVFBYhMjY1NCYjIgYVFBYFMjY1NCYjIgYVFBYhMjY1NCYjIgYVFBYFMjY1NCYjIgYVFBYjMjY1NCYjIgYVFBYX"
"MjY1NCYjIgYVFBYBbRQZGRQTGhqaFBkZFBMaGvsUGRkUExoaAYQUGRkUExoa/j8UGRkUExoaAgsUGRkUExoa/fcUGRkUExoaAgsU"
"GRkUExoa/j8UGRkUExoaAYQUGRkUExoa+xQZGRQTGhqaFBkZFBMaGgJNGhMUGRkUExokGhMUGRkUExoaExQZGRQTGmMaExQZGRQT"
"GhoTFBkZFBMahhkUFBgYFBQZGRQUGBgUFBmHGhMUGRkUExoaExQZGRQTGmMaExQZGRQTGhoTFBkZFBMaJBoTFBkZFBMaAAIAKAJj"
"ASoC2wADAAcAABMzNSMXMzUjKE1Ns09PAmN4eHgAAAEAKAJiAIEC2QADAAATMzUjKFlZAmJ3AAEAKAJYAPAC2QADAAATMycjkGBk"
"ZAJYgQAAAQAoAlgA8ALZAAMAABMzNyMoYGhkAliBAAACACgCWAGhAtkAAwAHAAATMzcjFzM3IyhfaGNKX2xkAliBgYEAAAEAKAJY"
"AXMC2AAGAAATMzcXMycjKF1ISV13XAJYTk6AAAABACgCWAFzAtgABgAAEzM3IwcnI59ceF1JSF0CWIBPTwAAAQAoAksBRALYAA0A"
"ABMyNjcjFAYjIiY1IxYWtkNKAUUnIiInRQFJAktMQSoqKStATQACACgCSwD5AxoACwAXAAATMjY1NCYjIgYVFBY3IiY1NDYzMhYV"
"FAaQLD08LSs9PCwXHRwYGB0dAks4MC84NzAvOS0fHBohHxwaIQAAAQAnAl4BZALTABQAAAEyNicjBiMiJiYjIgYXMyY2MzIWFgEP"
"JDECKwIoGC4xHh8yASsBEhUWLTQCXzY+MRgYM0EUHRgYAAEAKAJqAYQCsQADAAATITUhKAFc/qQCakcAAQAoAkMAxwMOABIAABM2"
"NjU0JiMiBgcXNjYzMhUUBgdZOjQ1Lw8eDgEKFQsyISUCQxo9JCUrBAUsAwQpFSQUAAEAKAJcAJQDLwAGAAATMzUjNyMHKF0rOjsx"
"AlxYe4IAAQAoAecAxwKCAAkAABMyNjU1IxUUBgcoTlFOKSgB5zo/Ih0pIgEAAAEAKP9aAIn/xAADAAAXMzUjKGFhpmoAAAEAKP71"
"AJD/wwAGAAATMzc1IxUzKDstXy/+9XZYXAAAAQAo/ygBCQAGABgAABcyNjU0JiYHNyMHFzYWFhUUBiMiJicjFhaZMEAeLhgKOA0V"
"DSQbGhoWHAI7Aj3YMC0fJRABLkQQBAIUGBQaFhEoMQABACj/RADNABoAEgAAFzI2NzUGIyImNTQ3JycGBhUUFokSJwsTGRYZTwkN"
"O0g0vAcHLwsVFC4zDwsYRiokKgAAAQAoAkoBdQKQAAMAABMhNSEoAU3+swJKRgABACgA+QMGATwAAwAANyE1ISgC3v0i+UMAAAEA"
"KAEJAPYB0QADAAATNzUHKM7OAQl0VHQAAQAo/+wCKQIoAAMAABczASMoSQG4SRQCPAACACgCPwFEA0QAAwARAAATMzcjAzI2NyMU"
"BiMiJjUjFhaLTUtQHUNKAUQoIiIoRAFJAttp/vtLQissKyxBTAAAAgAoAj8BRANEAAMAEQAAEzMnIxMyNjcjFAYjIiY1IxYWk01I"
"UG5ESQFEKSEiKEQBSgLbaf77TEEsKywrQksAAAIAKAI/AUQDSwASACAAABM2NjU0JiMiBgcXNjMyFhUUBgcXMjY3IxQGIyImNSMW"
"FrElJy0lDR0OARMUERQTFB1DSgFEKCIiKEQCSQK6ECkaHSEEBSUHDw4PFQuZS0IrLCssQUwAAAIAKgJBAUkDQQAUACIAABMyNicj"
"FCMiJiYjIgYXMzQ2MzIWFgcyNjcjBgYjIiYnIxYW+CYrAickFCotGSYoASgQERIpLyQ/SQVEBCYfHycERAVJAuUuLiMRETErERQS"
"EqREPSUmJSY8RQACACgCPAFzA1AAAwAKAAATMzcjAzM3FzMnI6hPSFHGXUhJXXdcAupm/uxPT4EAAgAoAjwBcwNQAAMACgAAEzMn"
"IwMzNxczJyOkT0ZRNF1JSF13XALqZv7sT0+BAAIAKAI8AZwDVQAPABYAAAE2NTQmIyIHFzYzMhYVFAcFMzcXMycjAUlTMykZGwER"
"ERMXLf78XUlIXXdcApgvQCQqCCwFFBIiIIJPT4EAAAIAKgI8AXUDQQAUABsAAAEyNicjFCMiJiYjIgYXMzQ2MzIWFgczNxczJyMB"
"CyYrAiclFCosGSYoASgQERIpLsZdSUhdd1wC5S4uIxERMSsRFBISqU9PgQABACgA5AGAASsAAwAANyE1ISgBWP6o5EcAAAEAKAEX"
"AXsB1wADAAATJTUFKAFT/q0BF21TbAABACj/7AJSAvYAAwAAFzMBIyhbAc9aFAMKAAEAKP9CAMUALQATAAAXMjY3NQYGIyImNTQ3"
"JycGBhUUFn4VJgsIFQ0UGFcICjpRL74JBy8FBxcUNE4JAh9ULSIpAAIAKAJnAT4C0AALABcAAAEyNjU0JiMiBhUUFiMyNjU0JiMi"
"BhUUFgEBGiMjGhoiIoIaIiIaGiMiAmcdGBgcHBgYHR0YGBwcGBgdAAABACgCZgChAs8ACwAAEzI2NTQmIyIGFRQWZRoiIhoaIyIC"
"Zh0YGBwcGBgdAAEAKP9dAKH/xgALAAAXMjY1NCYjIgYVFBZlGiIiGhojIqMdGBgcHBgYHQD//wAoAmMBKgLbAAYCrgAA//8AKAJi"
"AIEC2QAGAq8AAP//ACgCWADwAtkABgKwAAD//wAoAlgA8ALZAAYCsQAA//8AKAJYAaEC2QAGArIAAP//ACgCWAFzAtgABgKzAAD/"
"/wAoAlgBcwLYAAYCtAAA//8AKAJLAUQC2AAGArUAAP//ACgCSwD5AxoABgK2AAD//wAnAl4BZALTAAYCtwAA//8AKAJqAYQCsQAG"
"ArgAAP//ACj/KAEJAAYABgK+AAD//wAo/0QAzQAaAAYCvwAAAAAAAAAPALoAAwABBAkAAABoAAAAAwABBAkAAQAUAGgAAwABBAkA"
"AgAOAHwAAwABBAkAAwA4AIoAAwABBAkABAAkAMIAAwABBAkABQAaAOYAAwABBAkABgAiAQAAAwABBAkACABiASIAAwABBAkACQAY"
"AYQAAwABBAkACwAcAZwAAwABBAkADAAgAbgAAwABBAkBAAAYAdgAAwABBAkBAQAqAfAAAwABBAkBAgAWAhoAAwABBAkBAwAqAjAA"
"QwBvAHAAeQByAGkAZwBoAHQAIACpACAAMgAwADIAMQAgAGIAeQAgAEcAaQB0AEgAdQBiAC4ASQBuAGMALgAgAEEAbABsACAAcgBp"
"AGcAaAB0AHMAIAByAGUAcwBlAHIAdgBlAGQALgBIAHUAYgBvAHQAIABTAGEAbgBzAFIAZQBnAHUAbABhAHIAMgAuADAAMAAwADsA"
"TgBPAE4ARQA7AEgAdQBiAG8AdABTAGEAbgBzAC0AUgBlAGcAdQBsAGEAcgBIAHUAYgBvAHQAIABTAGEAbgBzACAAUgBlAGcAdQBs"
"AGEAcgBWAGUAcgBzAGkAbwBuACAAMgAuADAAMAAwAEgAdQBiAG8AdABTAGEAbgBzAC0AUgBlAGcAdQBsAGEAcgBHAGkAdABIAHUA"
"YgAsACAASQBuAGMALgAsACAAUwB1AGIAcwBpAGQAaQBhAHIAeQAgAG8AZgAgAE0AaQBjAHIAbwBzAG8AZgB0ACAAQwBvAHIAcABv"
"AHIAYQB0AGkAbwBuAEQAZQBuAGkAIABBAG4AZwBnAGEAcgBhAHcAdwB3AC4AZwBpAHQAaAB1AGIALgBjAG8AbQB3AHcAdwAuAGQA"
"ZQBnAGEAcgBpAHMAbQAuAGMAbwBtAFIAbwB1AG4AZABlAGQAIABkAG8AdABzAEEAbAB0AGUAcgBuAGEAdABlACAAbABvAHcAZQBy"
"AGMAYQBzAGUAIABsAEEAbAB0AGUAcgBuAGEAdABlACAAcgBTAGUAcgBpAGYAbABlAHMAcwAgAHUAcABwAGUAcgBjAGEAcwBlACAA"
"SQACAAAAAAAA/3QARgAAAAAAAAAAAAAAAAAAAAAAAAAAAuAAAAAkAMkBAgEDAQQBBQEGAQcAxwEIAQkBCgELAQwAYgENAK0BDgEP"
"ARAAYwCuAJAAJQAmAP0A/wBkAREBEgAnARMBFADpACgAZQEVARYAyAEXARgBGQEaARsAygEcAR0AywEeAR8BIAEhACkAKgD4ASIB"
"IwEkASUAKwEmAScALAEoAMwBKQDNAM4A+gEqAM8BKwEsAS0BLgAtAS8BMAAuATEALwEyATMBNAE1AOIAMAAxATYBNwE4AGYBOQAy"
"ANAA0QE6ATsBPAE9AT4AZwE/ANMBQAFBAUIBQwFEAUUBRgFHAUgAkQCvALAAMwDtADQANQFJAUoBSwA2AUwA5AD7AU0BTgFPADcB"
"UAFRAVIBUwA4ANQBVADVAGgBVQDWAVYBVwFYAVkBWgFbAVwBXQFeAV8BYAFhADkAOgFiAWMBZAFlADsAPADrAWYAuwFnAWgBaQFq"
"AD0BawDmAWwBbQFuAW8BcAFxAXIBcwF0AXUBdgF3AXgBeQF6AXsBfAF9AX4BfwGAAYEBggGDAYQBhQGGAYcBiAGJAYoBiwGMAY0B"
"jgGPAZABkQGSAZMBlAGVAZYARABpAZcBmAGZAZoBmwGcAGsBnQGeAZ8BoAGhAGwBogBqAaMBpAGlAG4AbQCgAEUARgD+AQAAbwGm"
"AacARwGoAQEA6gBIAHABqQGqAHIBqwGsAa0BrgGvAHMBsAGxAHEBsgGzAbQBtQBJAEoA+QG2AbcBuAG5AEsBugG7AEwA1wB0AbwA"
"dgB3Ab0BvgB1Ab8BwAHBAcIBwwBNAcQBxQHGAE4BxwBPAcgByQHKAcsA4wBQAFEBzAHNAc4AeAHPAFIAeQB7AdAB0QHSAdMB1AB8"
"AdUAegHWAdcB2AHZAdoB2wHcAd0B3gChAH0AsQBTAO4AVABVAd8B4AHhAFYB4gDlAPwB4wHkAIkAVwHlAeYB5wHoAFgAfgHpAIAA"
"gQHqAH8B6wHsAe0B7gHvAfAB8QHyAfMB9AH1AfYAWQBaAfcB+AH5AfoAWwBcAOwB+wC6AfwB/QH+Af8AXQIAAOcCAQICAgMCBAIF"
"AgYCBwIIAgkCCgILAgwCDQIOAg8CEAIRAhICEwIUAhUCFgIXAhgCGQIaAhsCHAIdAh4CHwIgAiECIgIjAiQCJQImAicCKAIpAioC"
"KwIsAi0CLgIvAjACMQIyAjMCNAI1AjYCNwI4AjkCOgI7AjwCPQI+Aj8CQAJBAkICQwDAAMECRAJFAJ0AngJGAJsAEwAUABUAFgAX"
"ABgAGQAaABsAHAJHAkgCSQJKAksCTAJNAk4CTwJQAlECUgJTAlQCVQJWAlcCWAJZAloCWwJcAl0CXgJfAmACYQJiAmMCZAJlAmYC"
"ZwJoAmkCagJrAmwCbQJuAm8CcAJxAnICcwJ0AnUCdgJ3AngAvAD0APUA9gJ5AnoCewJ8An0CfgJ/AoACgQKCAoMChAKFAoYChwKI"
"AokCigKLAowCjQKOAo8CkAADApEAEQAPAB0AHgCrAAQAowAiAKIAwwCHAA0ABgASAD8CkgKTApQClQKWApcCmAKZApoCmwKcAp0C"
"ngKfAqACoQKiAqMAEACyALMAQgKkAqUCpgALAAwAXgBgAD4AQAKnAqgCqQKqAqsCrADEAMUAtAC1ALYAtwCpAKoAvgC/AAUACgKt"
"Aq4CrwKwArECsgCmArMCtAK1ArYAIwAJAIgAhgCLAIoCtwCMAIMAXwDoArgCuQK6ArsAhAC9AAcCvAK9Ar4CvwCFAJYADgDvAPAA"
"uAAgAI8AIQAfAJUAlACTAKcApABhAEEAkgLAAJwAmgCZAKUACADGAsECwgLDAsQCxQLGAscCyALJAsoCywLMAs0CzgLPAtAC0QLS"
"AtMC1ALVAtYC1wLYAtkC2gLbAtwC3QLeAt8C4ALhAuIC4wLkAuUC5gLnAugC6QLqAusC7ALtAu4AjgDcAEMAjQDfANgA4QDbAN0A"
"2QDaAN4A4AZBYnJldmUHdW5pMUVBRQd1bmkxRUI2B3VuaTFFQjAHdW5pMUVCMgd1bmkxRUI0B3VuaTFFQTQHdW5pMUVBQwd1bmkx"
"RUE2B3VuaTFFQTgHdW5pMUVBQQd1bmkxRUEwB3VuaTFFQTIHQW1hY3JvbgdBb2dvbmVrC0NjaXJjdW1mbGV4CkNkb3RhY2NlbnQG"
"RGNhcm9uBkRjcm9hdAZFYnJldmUGRWNhcm9uB3VuaTFFQkUHdW5pMUVDNgd1bmkxRUMwB3VuaTFFQzIHdW5pMUVDNApFZG90YWNj"
"ZW50B3VuaTFFQjgHdW5pMUVCQQdFbWFjcm9uB0VvZ29uZWsHdW5pMUVCQwZHY2Fyb24LR2NpcmN1bWZsZXgHdW5pMDEyMgpHZG90"
"YWNjZW50BEhiYXILSGNpcmN1bWZsZXgCSUoGSWJyZXZlB3VuaTFFQ0EHdW5pMUVDOAdJbWFjcm9uB0lvZ29uZWsGSXRpbGRlC3Vu"
"aTAwNEEwMzAxC0pjaXJjdW1mbGV4B3VuaTAxMzYGTGFjdXRlBkxjYXJvbgd1bmkwMTNCBExkb3QGTmFjdXRlBk5jYXJvbgd1bmkw"
"MTQ1A0VuZwd1bmkxRUQwB3VuaTFFRDgHdW5pMUVEMgd1bmkxRUQ0B3VuaTFFRDYHdW5pMUVDQwd1bmkxRUNFBU9ob3JuB3VuaTFF"
"REEHdW5pMUVFMgd1bmkxRURDB3VuaTFFREUHdW5pMUVFMA1PaHVuZ2FydW1sYXV0B09tYWNyb24GUmFjdXRlBlJjYXJvbgd1bmkw"
"MTU2BlNhY3V0ZQtTY2lyY3VtZmxleAd1bmkwMjE4B3VuaTFFOUUEVGJhcgZUY2Fyb24HdW5pMDE2Mgd1bmkwMjFBBlVicmV2ZQd1"
"bmkxRUU0B3VuaTFFRTYFVWhvcm4HdW5pMUVFOAd1bmkxRUYwB3VuaTFFRUEHdW5pMUVFQwd1bmkxRUVFDVVodW5nYXJ1bWxhdXQH"
"VW1hY3JvbgdVb2dvbmVrBVVyaW5nBlV0aWxkZQZXYWN1dGULV2NpcmN1bWZsZXgJV2RpZXJlc2lzBldncmF2ZQtZY2lyY3VtZmxl"
"eAd1bmkxRUY0BllncmF2ZQd1bmkxRUY2B3VuaTFFRjgGWmFjdXRlClpkb3RhY2NlbnQMdW5pMUVCNi5zczAxDHVuaTFFQUMuc3Mw"
"MQ5BZGllcmVzaXMuc3MwMQx1bmkxRUEwLnNzMDEPQ2RvdGFjY2VudC5zczAxDHVuaTFFQzYuc3MwMQ5FZGllcmVzaXMuc3MwMQ9F"
"ZG90YWNjZW50LnNzMDEMdW5pMUVCOC5zczAxD0dkb3RhY2NlbnQuc3MwMQ5JZGllcmVzaXMuc3MwMQ9JZG90YWNjZW50LnNzMDEM"
"dW5pMUVDQS5zczAxCUxkb3Quc3MwMQx1bmkxRUQ4LnNzMDEOT2RpZXJlc2lzLnNzMDEMdW5pMUVDQy5zczAxDHVuaTFFRTIuc3Mw"
"MQZRLnNzMDEOVWRpZXJlc2lzLnNzMDEMdW5pMUVFNC5zczAxDHVuaTFFRjAuc3MwMQ5XZGllcmVzaXMuc3MwMQ5ZZGllcmVzaXMu"
"c3MwMQx1bmkxRUY0LnNzMDEPWmRvdGFjY2VudC5zczAxBkkuc3MwNAdJSi5zczA0C0lhY3V0ZS5zczA0C0licmV2ZS5zczA0EElj"
"aXJjdW1mbGV4LnNzMDQOSWRpZXJlc2lzLnNzMDQPSWRvdGFjY2VudC5zczA0DHVuaTFFQ0Euc3MwNAtJZ3JhdmUuc3MwNAx1bmkx"
"RUM4LnNzMDQMSW1hY3Jvbi5zczA0DElvZ29uZWsuc3MwNAtJdGlsZGUuc3MwNBNJZGllcmVzaXMuc3MwMS5zczA0FElkb3RhY2Nl"
"bnQuc3MwMS5zczA0EXVuaTFFQ0Euc3MwMS5zczA0BmFicmV2ZQd1bmkxRUFGB3VuaTFFQjcHdW5pMUVCMQd1bmkxRUIzB3VuaTFF"
"QjUHdW5pMUVBNQd1bmkxRUFEB3VuaTFFQTcHdW5pMUVBOQd1bmkxRUFCB3VuaTFFQTEHdW5pMUVBMwdhbWFjcm9uB2FvZ29uZWsL"
"Y2NpcmN1bWZsZXgKY2RvdGFjY2VudAZkY2Fyb24GZWJyZXZlBmVjYXJvbgd1bmkxRUJGB3VuaTFFQzcHdW5pMUVDMQd1bmkxRUMz"
"B3VuaTFFQzUKZWRvdGFjY2VudAd1bmkxRUI5B3VuaTFFQkIHZW1hY3Jvbgdlb2dvbmVrB3VuaTFFQkQGZ2Nhcm9uC2djaXJjdW1m"
"bGV4B3VuaTAxMjMKZ2RvdGFjY2VudARoYmFyC2hjaXJjdW1mbGV4BmlicmV2ZQlpLmxvY2xUUksHdW5pMUVDQgd1bmkxRUM5B2lt"
"YWNyb24HaW9nb25lawZpdGlsZGUCaWoHdW5pMDIzNwt1bmkwMDZBMDMwMQtqY2lyY3VtZmxleAd1bmkwMTM3BmxhY3V0ZQZsY2Fy"
"b24HdW5pMDEzQwRsZG90Bm5hY3V0ZQZuY2Fyb24HdW5pMDE0NgNlbmcHdW5pMUVEMQd1bmkxRUQ5B3VuaTFFRDMHdW5pMUVENQd1"
"bmkxRUQ3B3VuaTFFQ0QHdW5pMUVDRgVvaG9ybgd1bmkxRURCB3VuaTFFRTMHdW5pMUVERAd1bmkxRURGB3VuaTFFRTENb2h1bmdh"
"cnVtbGF1dAdvbWFjcm9uBnJhY3V0ZQZyY2Fyb24HdW5pMDE1NwZzYWN1dGULc2NpcmN1bWZsZXgHdW5pMDIxOQR0YmFyBnRjYXJv"
"bgd1bmkwMTYzB3VuaTAyMUIGdWJyZXZlB3VuaTFFRTUHdW5pMUVFNwV1aG9ybgd1bmkxRUU5B3VuaTFFRjEHdW5pMUVFQgd1bmkx"
"RUVEB3VuaTFFRUYNdWh1bmdhcnVtbGF1dAd1bWFjcm9uB3VvZ29uZWsFdXJpbmcGdXRpbGRlBndhY3V0ZQt3Y2lyY3VtZmxleAl3"
"ZGllcmVzaXMGd2dyYXZlC3ljaXJjdW1mbGV4B3VuaTFFRjUGeWdyYXZlB3VuaTFFRjcHdW5pMUVGOQZ6YWN1dGUKemRvdGFjY2Vu"
"dA91bmkxRUNCLmRvdGxlc3MPaW9nb25lay5kb3RsZXNzBmEuc3MwMQthYWN1dGUuc3MwMQthYnJldmUuc3MwMQx1bmkxRUFGLnNz"
"MDEMdW5pMUVCNy5zczAxDHVuaTFFQjEuc3MwMQx1bmkxRUIzLnNzMDEMdW5pMUVCNS5zczAxEGFjaXJjdW1mbGV4LnNzMDEMdW5p"
"MUVBNS5zczAxDHVuaTFFQUQuc3MwMQx1bmkxRUE3LnNzMDEMdW5pMUVBOS5zczAxDHVuaTFFQUIuc3MwMQ5hZGllcmVzaXMuc3Mw"
"MQx1bmkxRUExLnNzMDELYWdyYXZlLnNzMDEMdW5pMUVBMy5zczAxDGFtYWNyb24uc3MwMQxhb2dvbmVrLnNzMDEKYXJpbmcuc3Mw"
"MQthdGlsZGUuc3MwMQ9jZG90YWNjZW50LnNzMDEMdW5pMUVDNy5zczAxDmVkaWVyZXNpcy5zczAxD2Vkb3RhY2NlbnQuc3MwMQx1"
"bmkxRUI5LnNzMDEPZ2RvdGFjY2VudC5zczAxBmkuc3MwMQ5pZGllcmVzaXMuc3MwMQ5pLmxvY2xUUksuc3MwMQx1bmkxRUNCLnNz"
"MDEGai5zczAxCWxkb3Quc3MwMQx1bmkxRUQ5LnNzMDEOb2RpZXJlc2lzLnNzMDEMdW5pMUVDRC5zczAxDHVuaTFFRTMuc3MwMQ51"
"ZGllcmVzaXMuc3MwMQx1bmkxRUU1LnNzMDEMdW5pMUVGMS5zczAxDndkaWVyZXNpcy5zczAxBnkuc3MwMQt5YWN1dGUuc3MwMRB5"
"Y2lyY3VtZmxleC5zczAxDnlkaWVyZXNpcy5zczAxDHVuaTFFRjUuc3MwMQt5Z3JhdmUuc3MwMQ96ZG90YWNjZW50LnNzMDEGbC5z"
"czAyC2xhY3V0ZS5zczAyC2xjYXJvbi5zczAyDHVuaTAxM0Muc3MwMglsZG90LnNzMDILbHNsYXNoLnNzMDIGci5zczAzC3JhY3V0"
"ZS5zczAzC3JjYXJvbi5zczAzDHVuaTAxNTcuc3MwMxR1bmkxRUNCLmRvdGxlc3Muc3MwMQ5sZG90LnNzMDEuc3MwMghmX2YubGln"
"YQpmX2ZfaS5saWdhCmZfZl9sLmxpZ2EHZmwuc3MwMg9mX2ZfbC5saWdhLnNzMDIHdW5pMDNCQwd1bmkyNEZGB3VuaTI3NzYHdW5p"
"Mjc3Nwd1bmkyNzc4B3VuaTI3NzkHdW5pMjc3QQd1bmkyNzdCB3VuaTI3N0MHdW5pMjc3RAd1bmkyNzdFB3VuaTI0RUEHdW5pMjQ2"
"MAd1bmkyNDYxB3VuaTI0NjIHdW5pMjQ2Mwd1bmkyNDY0B3VuaTI0NjUHdW5pMjQ2Ngd1bmkyNDY3B3VuaTI0NjgHemVyby50ZgZv"
"bmUudGYGdHdvLnRmCHRocmVlLnRmB2ZvdXIudGYHZml2ZS50ZgZzaXgudGYIc2V2ZW4udGYIZWlnaHQudGYHbmluZS50Zgl6ZXJv"
"LmRub20Ib25lLmRub20IdHdvLmRub20KdGhyZWUuZG5vbQlmb3VyLmRub20JZml2ZS5kbm9tCHNpeC5kbm9tCnNldmVuLmRub20K"
"ZWlnaHQuZG5vbQluaW5lLmRub20JemVyby5udW1yCG9uZS5udW1yCHR3by5udW1yCnRocmVlLm51bXIJZm91ci5udW1yCWZpdmUu"
"bnVtcghzaXgubnVtcgpzZXZlbi5udW1yCmVpZ2h0Lm51bXIJbmluZS5udW1yCW9uZWVpZ2h0aAx0aHJlZWVpZ2h0aHMLZml2ZWVp"
"Z2h0aHMMc2V2ZW5laWdodGhzB3VuaTIwODAHdW5pMjA4MQd1bmkyMDgyB3VuaTIwODMHdW5pMjA4NAd1bmkyMDg1B3VuaTIwODYH"
"dW5pMjA4Nwd1bmkyMDg4B3VuaTIwODkHdW5pMjA3MAd1bmkwMEI5B3VuaTAwQjIHdW5pMDBCMwd1bmkyMDc0B3VuaTIwNzUHdW5p"
"MjA3Ngd1bmkyMDc3B3VuaTIwNzgHdW5pMjA3OQd1bmkwMEEwD2V4Y2xhbWRvd24uY2FzZRFxdWVzdGlvbmRvd24uY2FzZRZwZXJp"
"b2RjZW50ZXJlZC5sb2NsQ0FUC3BlcmlvZC5zczAxCmNvbW1hLnNzMDEKY29sb24uc3MwMQ5zZW1pY29sb24uc3MwMQ1lbGxpcHNp"
"cy5zczAxC2V4Y2xhbS5zczAxD2V4Y2xhbWRvd24uc3MwMQ1xdWVzdGlvbi5zczAxEXF1ZXN0aW9uZG93bi5zczAxE3BlcmlvZGNl"
"bnRlcmVkLnNzMDEbcGVyaW9kY2VudGVyZWQubG9jbENBVC5jYXNlFGV4Y2xhbWRvd24uY2FzZS5zczAxFnF1ZXN0aW9uZG93bi5j"
"YXNlLnNzMDEbcGVyaW9kY2VudGVyZWQubG9jbENBVC5zczAxIHBlcmlvZGNlbnRlcmVkLmxvY2xDQVQuY2FzZS5zczAxC2h5cGhl"
"bi5jYXNlC2VuZGFzaC5jYXNlC2VtZGFzaC5jYXNlDnBhcmVubGVmdC5jYXNlD3BhcmVucmlnaHQuY2FzZQ5icmFjZWxlZnQuY2Fz"
"ZQ9icmFjZXJpZ2h0LmNhc2UQYnJhY2tldGxlZnQuY2FzZRFicmFja2V0cmlnaHQuY2FzZRNxdW90ZXNpbmdsYmFzZS5zczAxEXF1"
"b3RlZGJsYmFzZS5zczAxEXF1b3RlZGJsbGVmdC5zczAxEnF1b3RlZGJscmlnaHQuc3MwMQ5xdW90ZWxlZnQuc3MwMQ9xdW90ZXJp"
"Z2h0LnNzMDEHdW5pMjYzOQlzbWlsZWZhY2UHdW5pMjcxMwd1bmlGOEZGB3VuaTIxMTcHdW5pMjExMwllc3RpbWF0ZWQHdW5pMjEx"
"Ngd1bmkyMEJGBEV1cm8HdW5pMjBCQQd1bmkyMEI5B3VuaTIwQUEIZW1wdHlzZXQLZGl2aWRlLnNzMDEHYXJyb3d1cAphcnJvd3Jp"
"Z2h0CWFycm93ZG93bglhcnJvd2xlZnQJYXJyb3dib3RoB3VuaTI1Q0YGY2lyY2xlB3VuaTI1Q0MHdW5pMDMwOAd1bmkwMzA3CWdy"
"YXZlY29tYglhY3V0ZWNvbWIHdW5pMDMwQgd1bmkwMzAyB3VuaTAzMEMHdW5pMDMwNgd1bmkwMzBBCXRpbGRlY29tYgd1bmkwMzA0"
"DWhvb2thYm92ZWNvbWIHdW5pMDMxMgd1bmkwMzFCDGRvdGJlbG93Y29tYgd1bmkwMzI2B3VuaTAzMjcHdW5pMDMyOAd1bmkwMzM1"
"B3VuaTAzMzYHdW5pMDMzNwd1bmkwMzM4C3VuaTAzMDYwMzAxC3VuaTAzMDYwMzAwC3VuaTAzMDYwMzA5C3VuaTAzMDYwMzAzC3Vu"
"aTAzMDIwMzAxC3VuaTAzMDIwMzAwC3VuaTAzMDIwMzA5C3VuaTAzMDIwMzAzDHVuaTAzMzUuY2FzZQx1bmkwMzM3LmNhc2UMdW5p"
"MDMzOC5jYXNlCXVuaTAzMjguZQx1bmkwMzA4LnNzMDEMdW5pMDMwNy5zczAxEWRvdGJlbG93Y29tYi5zczAxAAEAAgAOAAAAogAA"
"APIAAgAYAAEAXAABAF4AdQABAHcAgQABAIMA7QABAO8A+AABAPoBNQABATcBTgABAVABWgABAVwBxQABAcYBzAACAdsB7gABAisC"
"LAABAi4CLgABAj0CPgABAkACQAABAl8CcAABAnoCegABAnwCfAABAoQChQABAocCiAABAo0CjQABApICkgABAqsCrQABAq4C0gAD"
"ABIABwAcACQAQgAyADoAOgBCAAIAAQHGAcwAAAABAAQAAQDuAAIABgAKAAEA0AABAaEAAQAEAAEAzQABAAQAAQDhAAIABgAKAAEA"
"3gABAbsAAQABAAAACAACAAMCrgK6AAACxALLAA0C0ALRABUAAQAAAAoAYgCIAAJERkxUAA5sYXRuABIAPgAAADoACUFaRSAAOkNB"
"VCAAOkNSVCAAOktBWiAAOk1PTCAAOk5MRCAAOlJPTSAAOlRBVCAAOlRSSyAAOgAA//8AAwAAAAEAAgADa2VybgAUbWFyawAabWtt"
"awAgAAAAAQAAAAAAAQABAAAAAQACAAMACKe8wK4AAgAIAAIACjpuAAECwgAEAAABXAVaBiQGxAZSBlgGhhPWBpYGkAaWBpwGtgbE"
"BsoG4Ab2BwQHEgccB0YHeAeqB/wIAggMCHIIoAjaCRAJFglMCVIJaAmCCbgJxgpcCmILFAu2C8AL1gvsDBoMJAwuDDwMQg1yDMwM"
"0gzwDQoNLA1KDWANcg14DYYNyA5yDpQO5g8wD2YQ9BEuETwRUhFoEdYR4BKOEtATFhOgE9YT4BPyFAAUshS4FMYUzBTSFNgU4hTw"
"FPYVGhUQFRoVGhU4FSQVMhU4Hj4VPhVEFVYVdBWOFtoVlBW+FewWchbaFqwWzhbUFtoW4BbqFxwXPhdEF0oXVBdiF3QXohfAF84X"
"2BgqGDAYNhhAGPYZCBlGGWwZmhmgGcoaABoOGhgaYhqEGrYavBrCGwQbChs0GzobdBueG8Qb9hwsHFIcWBxiHPgdFh08HX4dqB3+"
"HjAePh5EHroe6B72H3Qfgh+MH5ofoB+uH8Qf5h/8ICogbCCGIKAgriDAIMYg0CDQINYg1iDcIOYg7CD6IQAhBiEUITIhRCFSIVwh"
"uiHQIdoh6CIWIlQifiJUIn4inCKcIsIi0CLmIuwjKiOoI8okGCReJPglciXAJfomNCZuJpwmwibkJw4nQCdaJ4QnoifMJ/In+Cf+"
"KDgoPihIKGYofCiqKLgoyijYKPopGCkuKUQpWimIKZ4ptCnyKhwqLio8Kn4qnCqyKyArWiuQK/osnCy6LQgtEi0YLSYtaC12LYAt"
"qi3ALl4uiC62LsQu5i70Lv4wMDB6MLgw0jEgMWoxdDGCMcAx8jIwMl4yeDKyMuQzCjNQM2IzlDPaNAg0HjRENFY0bDR+NKg02jT4"
"NQ41MDU6NWA1jjWUNaI1wDX2Nhg2WjZkNn42vDbaN0A3pjfIOAY4HDheOGw4ljigOMo4/DlWOXA5gjmQOa45tDnaOgw6OgACAG4A"
"AQAEAAAACQAPAAQAEQAZAAsAHwAfABQAIwAkABUAMwAzABcANQA2ABgAPAA/ABoARABEAB4ASgBKAB8ATABRACAAUwBUACYAVgBc"
"ACgAXgBfAC8AZwBnADEAagBvADIAcQByADgAdQB4ADoAfAB8AD4AggCJAD8AmwCcAEcAoQCiAEkAqgCqAEsArwCwAEwAvwDAAE4A"
"yADIAFAAygDNAFEA0gDSAFUA1ADVAFYA2ADYAFgA2wDfAFkA4wDmAF4A6gDrAGIA7wDwAGQA8gDzAGYA9gD2AGgA+AD6AGkA/QD9"
"AGwBAgECAG0BBAEEAG4BBwEHAG8BCQEKAHABDAEOAHIBEAETAHUBFgEWAHkBGAEdAHoBHwEiAIABJAEkAIQBJgEoAIUBKgEqAIgB"
"LAEtAIkBLwExAIsBMwEzAI4BNgE4AI8BPQE9AJIBPwE/AJMBQwFLAJQBTgFOAJ0BUAFTAJ4BVQFVAKIBVwFYAKMBWwFhAKUBZQFl"
"AKwBbwFvAK0BcQFxAK4BdAF1AK8BegF7ALEBfwF/ALMBgwGDALQBhQGFALUBiQGJALYBjQGQALcBlAGWALsBnAGcAL4BpQGmAL8B"
"qAGpAMEBrgGuAMMBswGzAMQBtwG3AMUBugG6AMYBvAG8AMcBvwHCAMgBxgHaAMwB+QICAOECBAIEAOsCBgIGAOwCDQINAO0CFQIc"
"AO4CHwIgAPYCIwIoAPgCKwIwAP4CMgIzAQQCNgI5AQYCOwI7AQoCPQJCAQsCRAJFARECSQJJARMCTAJXARQCWQJbASACXQJdASMC"
"XwJwASQCdgJ3ATYCegJ+ATgCgQKBAT0CgwKDAT4ChQKFAT8ChwKKAUACjAKdAUQCnwKfAVYCoQKlAVcAMgA9/+EATgAJAF3/+wB2"
"//sAhP9xAIj/1ACl/2IApv9iAKf/YgDF/2IAxv9iAPn/6QEb//4BL//nAVv/yQFd/9MBuv/5Ab//4AHO/5IB0f/ZAdMABQHW/+kB"
"1//fAdj/xAHZ/+0B2v/jAjD/+wI2/4kCN//ZAjn/VwJT/+kCVv/RAln/1wJj/68CZP+yAmr/twJt/4sCbv+NAnD/rwJ2/94Ce/+Q"
"An3/ZwKH/9sCkP/gApL/xwKT/7AClP/zApn/swKa/6ACm/+WAAsAdv/7AIT/cQD5/+kBL//nAbr/+QG//+ACNv+JAmr/twJu/40C"
"e/+QAn3/ZwABAIP/cgALAIP/gwCH/4MAm/+CAKL/ggCl/4IApv+CAMX/ggDG/4ICZP+yAmr/twJw/68AAgCD/4UAov+EAAEAov+E"
"AAEAov+DAAYAg/9yAJv/bACl/2wCav+3Anv/kAJ9/2oAAwI2/4kCav+3Am7/jQABAm7/jQAFAIP/ewCb/3kAov93Amr/twJu/40A"
"BQIsAB4CNv+JAlQAGAJj/68Cbv+NAAMApf9iAMX/YgI2/4kAAwHN/5oCNv+JAm7/jQACAPn/5gF0/7gACgEUAB0BGwAkAdYACwHY"
"AAIB2QAOAdoABQI5/94CVv/SAn3/4AKUABQADAB0AAMB0wANAdYACgHYAAcB2QAPAdoADgI5/9cCVv/FAl7/0QJwAAACff/aApQA"
"GQAMAE7/zgEkAAQBLwAMAdP//QHXAA0B2gAJAjn/ywJW/7sCXP/AAl7/wQJ9/84ClAAIABQA+f/kARsANQEk//4BJwAlAS//6wFO"
"//sBW//LAbr//QHR/+IB1//lAdr/8QI3/8sCU//nAnb/2gJ7/9ECkP/VApL/wQKU/+gCmv+eApv/igABAU7/+wACAiwAHAJUABoA"
"GQB0/+sBGP/oARsALQFl/+QBpf/9AdH/7AHT/+cB1v/3Adf/7AHZ/+4B2v/yAhf/1wIY/9YCGf+WAhr/0wIb/8kCHf/SAjf/2QI/"
"/8MCQP/HAkH/UgJT/+YCe//dApL/3gKU/+gACwEUABEBGwAXAScAJwEvAAgB0wAHAdj/+wHaAAQCOf/MAlb/zQJ9/9IClAARAA4A"
"PAAAAGb//gB3//4AiAAAARkAMAEnADMB2gAAAjD//wI///sCQv//AmoAAAJwAAAClAALApv/0wANAAH/4QA9AA4ATP/iAIP/9ACh"
"/+cA2P/kAPb/5AD6/+MBEv/kATf/4wFV/+EBYf/zAYn/3gABAAH/+wANAHT/1gD5/+YBJwAnAVv/0AHR/+AB1//kAjf/zQJT/+sC"
"dv/eAnv/0QKS/8ICmv+AApv/cQABARsAOAAFASEAKQEkADQBTgAFAiwAGwJUABkABgAZAAAAXv//AF///wCIAAIB2gAAApQADQAN"
"AA//9AAjAAAALQAIADIACgBJAA0AzABAANAAQADSAGgBpQABAdoAAAJUAAYCWgAMApQADQADAAH/8wBe//8BJwAqACUAdP/BAKf/"
"/wDq/9MBBP/QAQn/1AEv/+UBP//QAUr/1AFTAAwBYf/XAYD/vgGC/78Bl//nAaz/0gG4/6EBuv/7Ab//4AHR/8sB0//6Adb/7AHX"
"/9AB2f/lAdr/2wI3/7kCP//1AlP/4AJZ/88Cdv/OAnv/uAKH/84Ckf99ApL/qQKT/5oClP/wApr/aQKb/20Cpf9vAAEBCf/UACwA"
"Kf/2ACz/9gAx//YAMv/2ADT/9gA9/90AdP/LAHb/9gCE/20Apf9TAKb/VQCn/1MAxf9TAMb/VQEk//wBzf9cAc7/WQHR/9QB1v/o"
"Adf/2QHY/74B2f/tAdr/4gI2/3YCN//BAjn/WwJT/+cCVv/MAln/1AJj/6sCZP+rAmn/aQJu/2UCb/+qAnD/qgJ2/9kCe/9OAn3+"
"/wKH/9sCkP/KApL/pwKU/+UCmv8mApv/SgAoAAEACQAYAAAAGf/WABv/1gAfAAAANv/WADwAAABPAAAAVwAAAFgAAABaAAAAXv/W"
"AGD/1gB4AAAAfP/wAH7/8ACD/8AAiP/iAIn/4gCb/8UA2P/iAWH/6gFi/+oBdP+gAXX/tgGJ//MCIP+3AiH/rwIi/60CI/+iAiT/"
"qQIl/60CJv+0Aif/rAIo/68CMv+tAkz/gQJQ/30CVP/kAmH/owACADL/9wJu/2UABQCl/1MAxf9TAS//4AJk/64Cbv9vAAUAZv/+"
"AIgAAAEbACUB2gAAApQACwALABz//wBm//4Ad//+AIgAAAEnADMBzgAHAdoAAAJ+//cCkP/yApQACwKb/9MAAgAZ//8Be//8AAIA"
"Af/7AF7//gADAAH/+wAT//sBIABCAAEAXv/+ACIAGP/+AB///gAj//4ANf/+ADz//gA9//cATv/OAE///gBR//4AV//+AFj//gBc"
"//4Adf/+AHj//gCC//4AhP/RAJv/1gCl/8UAxf/FAO8ABAETAAQBFAAQARsAEwEoAAQBKgAEAboABQHT//wB2gAIAjn/ygJTAAsC"
"Vv+8Al7/wwJ9/8wClAAHAAEBJAADAAcAP//qAFgAAgCD/+YCK//RAiz/0AI9/78CVP/uAAYAGQAPAD//6gBXAAIAWAACAHUAAgCD"
"/+YACAAZAA8AP//qAFgAAgB1AAIAg//mAIgACAIr/9ECLP/QAAcAP//qAFgAAgIr/9ECLP/QAj3/vwI+/8YCVP/uAAUAP//qAFgA"
"AgIr/9ECLP/QAj3/vwAEAD//6gBYAAICK//RAiz/0AABAPkABwADAIP/1wCb/94Aov/XABAATv+YARsAKQEv//MBU///AdMADgHY"
"ABQB2gAPAhf/xgIY/8YCGf+FAjn/6AJB/0MCVv/UAl7/1AJ9/+wClAANACoAAf/IAAL/yAAT/8gAF//IACIAQgA//7gAQf+4AEn/"
"uABM/7IAXgAOAF8ADgBmAA4Ag/+lAIgABQCJAAUAm//JAKL/qQCj/6kA2AAKANkACgDqAAoA7gAAAPoACwD7AAsBCQALARYAAQEk"
"AAEBNwALATgACwE/AAsBUQABAWEABwFiAAcBdP/7AXv/+AF8//gBtP/5AiD/xwIr/7sCLP+6Aj3/sAJU/7kACAHT//wB2gAIAjn/"
"ygJP/8MCVP/IAlb/xwJ9/8wClAAHABQAMf/8AHb//ACl/90Axf/dAScANQHTAAoB1v/1Adf/+AHYAAMB2f/3Adr//wI5/9kCU//2"
"Alb/4AJu//0Cff/dAof/7QKS//AClAAIApv/uAASARQAGgEZACABGwAiAS8AAQFOAAAB0wAGAdgABQHZAA4B2gAFAjn/2AJW/8sC"
"Xv/aAm7/+gJw//sCff/YAocAAwKUABgCm//GAA0AAf/tADYAAwA///YAfAAPAIP/5gCb/+gAnP/qANgADwIj/8oCTAAPAlT/4AJh"
"/9ICY//SAGMACf+DAAr/hAAL/4MADP+FABb/fwBO/7gAdP/NANr/swDb/68A3P+zAN3/rwDg/6cA4f+aAOL/pwDj/5oA5P+ZAOX/"
"rQDm/6cA6P+fAOn/kgDq/78A7P+jAO3/rAD7/3gA/f+8AQT/qAEF/4EBB/+eAQn/wgEX/7kBGP/eARkAOAEbAC4BH//6AST/+gEv"
"/+EBOP94ATr/nAE9/5wBP/+nAUH/ngFG/54BSf+NAUr/wAFM/6wBUv+/AVMACwFX/9UBY//EAWT/tQFl/7sBZ/+1AWz/tQFt/6YB"
"cP/NAXL/uAF9/7wBgP+6AYH/rwGJ/4ABiv+CAY7/uQGV/6UBmP+AAZn/rAGa/5gBm//LAZz/gAGd/6wBpf/0Aa//uAG1/7wBv//h"
"AdH/1wHT/+UB1v/1Adf/2AHYAAoB2f/mAdr/5gIV/1gCF/9eAjf/xgI//7oCQP+9AkH/UgJT/84CZf96Anb/twJ7/9UCh//TApD/"
"1QKR/3wCkv+0ApT/7AKZ/48Cmv9aApv/UgKl/2AADgAB/3IAAv9yAHL/0ACEAAwBS/+hAV3/zQIr/60CLP+sAi3/yAIu/8gCOP9p"
"Aj7/qwJl/5oCZ/+aAAMBZf+7AYn/gAI//7oABQDa/7MA4P+nAOr/vwFw/80Bif+BAAUA2v+zAOD/pwDq/78Bif+AAYv/vQAbABgA"
"AAAZAAYAHwAAACMAAAAkAAAANQAAADYABgA8AAAATv/XAE8AAABRAAAAVwAAAFgAAABeAAYAdQAAAHgAAACIAAUA7wAGARMABgEU"
"ACIBJwAwASgABgEqAAYBugAGAdoABAKUAA4Cm//YAAIBJAACAVMACwArAAn/gQAK/4MAC/+BAA7/gwAT/3kAJv/7ACn/+wBO/7sA"
"dP/YANr/uQDm/6sA6v/FAPL/xwD9/8MBB/+oAQn/xwEY/94BGQBAARsAPAEk//oBP/+sAUz/rAFX/9sBi//GAZb/uwGX/7cBm//R"
"AaX/+wHR/9wB0//nAdb/9QHX/94B2AAaAdn/5QHa/+kCF/+VAjf/2gI//8UCQP/JAlP/0gJ2/8ACe//XApL/yAAQAOb/ywEv/+kB"
"l//MAaUAAQG//+kB0//xAdf/6wHYABkB2v/1Ahj/ugI//9YCU//hAnb/2wKS/94ClP/6Apv/pwARAHT/xAHR/8wB1v/nAdf/0gHZ"
"/+YB2v/cAjb/6QI3/7oCU//hAnb/zwJ7/7gCkP/MApL/rAKT/5oClP/vApr/dAKb/3AAIgAp//sAK//7ACz/+wDm/6cA6P+gAOr/"
"vwD+/5cA//+NAQL/jQEH/6QBGP/WATn/lgFK/8EBZf+4AXD/xwGb/8kB0f/NAdP/3wHX/84B2f/hAdr/3gIX/2UCN//FAj//sAJA"
"/7UCQf9HAlP/xgJ2/6UCe//NApD/zwKS/7QClP/uApr/ggKb/2oADQEZAD0BL//tAVMADwG//+gB0f/jAdf/5wHa//ICN//bAlP/"
"7AJ2/94Ce//ZApL/xgKb/3MAAgCD/4MAov+CAAQAxf9mAm7/jQJ7/5ACff9nAAMAGQAPAD//6gCD/+YALAABACIAGAAQABkAEAAf"
"ABAAIQBEACMAEAA1ABAAPAAQAD8AGABDABgATAAbAE8AEABRABAAVwAQAFgAEAB1ABAAeAAQAHwABQCD/80AiAAIAJv/1gCc/+gA"
"oQAbAKL/xQCqACAAtAAQAPoADwETABMBFwASARoAKAEgACgBKgATATcADwFRABIBVQATAWEADQGDACIBiQANAaEAEAGlABIBpwAS"
"AdMAHwI9AA4CPgAXAAEBJwAzAAMAAf/7ACIALADQAD8AAQDSAIQAAQDMAHYAAQDNAGwAAgDLAIQA0gCcAAMAzQB4ANQAhwDVAHEA"
"AQDVAGcABgEnAAAB2P/vAdoAAAKS//gCk//YApr/4gACAiD/wwJU/9IAAgIg/8ECVP/QAAMBe///AiD/wAJU/88AAQF7//8AAQIg"
"/8IAAQJU/9IABAEkAAMCLAAIAlT/+QJY//sABwBM/+MBdv/vAboAAAHT/+gB2P/GAnv/6QKP//MABgHY/8wCe//yAo//8wKS//YC"
"k//TApT//QABAlT/zAAKARoABQEbAAYBHgADASAABwEiAAQBJwAIAdoABAKS//kClAAMApr/4gALAP8AAAEBAAABFgABAR0AAQEe"
"AAQBIgAHATwAAAFhAAABaAAAAWkAAAFqAAAAIQDYAAwA2QAMAPYADAD5AAsA+gAMAQz/8wENAAwBNwAMAT8ADAFVAAEBXP/zAWEA"
"BQF0/+YBe//jAbP/4wHG//MBx//zAcj/8wHJ//MByv/zAiv/7gIs//ECMv/cAjj/1wI9/9ACPv/aAkwADgJU/8sCWP/KAmH/3gJj"
"/94Caf/kAm3/2wAOAEz/7ACD/3wAhv98AIf/fAG/AAwB0//vAdj/xwJA//ACUwAHAmH/ygJ7/+sCj//0ApL/+AKa//AACAFhAAMC"
"K//0Aiz/9QI9/9wCPv/lAlT/+QJi/+cCaf/vAAECVP/JAAEAg/9+AAECVP/KAAIBvwANAlT/1gAMAEz/uAEaAAUBGwAJAR4ABAEg"
"AAgBKgAAAc4AGQHV/8UB2gAPAnf/4gKP/+AClf/oAAgBJAACAakAAgIr//4CLP/+AjgABQJU/+YCVv/lAlj/5AABAlT/5gABAiD/"
"xAACAiD/vgIm/8gAAwEkAAICIP++Aib/yAAEAY///wHY/88Ce//oAo//8AALARoABAEbAAYBJwAHAdoAAAJU//kCYf/yAmL//AJk"
"//wCaf/8Amr//AKa/+IABwEeAAUBTwADAVMABQFXAAEBhQABAjj/+wJUAB4AAwCDADgCIQA8AlQAPQACARoAEAJTABIAFABEADkA"
"7wAGAQwAAgETAAYBFgAGARsAEAEoAAYBKgAGAVwAAgG6AAYBxgAGAccABgHIAAYByQAGAcoABgIhADICJQAxAjIAKwJUADECaQAz"
"AAEBGwAGAAECLAALAAICYgASAmkAEQAtAD8APABYAEMAdQBDAJsASADqAAYA7wAHAPIAAwETAAcBIAARASQABwEoAAcBKQAHASoA"
"BwEtAAcBTwAHAVcABQFcAAIBdP//AYUABQGpAAgBugAHAb0ABwHGABsBxwAbAcgAGwHJABsBygAbAcsAGwHMABsCIQA9AiQAQgIl"
"AEkCJwBDAigATAIwADgCMgBAAj3/7AJUACgCYQA9AmIASgJjAD0CZABKAmkASQJqAEkCbgBKAAQBJAADAXT//wIsAAgCPf/sAA8B"
"EwAEASIACwEoAAQCIQA8AiQAOAIlAD4CJgA6AicAPAIwADUCMgA3AlQAMgJiADoCZAA6AmkAQgJqAEIACQEaAAQBHgADASAABwEk"
"AAMB2gAAAiwABwI4ABECTwAKAlQABQALARQABAEaAAYBHgAFASAACwEhAAQBVwABAakAAwHYACQB2gAFAiwABwI+AAAAAQEnABgA"
"CgG6//0Bv//kAdX/xQJAAAsCU//3Anf/5gKP/8MCkv/tApX/0QKa/7IADQEZAAMBGgAFARsABgEeAAMBIAAHASIABAEnAAgB2gAE"
"AjAAAAJTAAACdgAAApQADAKa/+IAAwFXACMBqQA8AkIAggACASAABwIsAAsAEgDYAAIA6wACAPAAAAD2AAIA+gAAAQoAAAENAAMB"
"NwAAATgAAAFVAAUBYQAFAXUABwGG//4CK//mAiz/6AI9/84CPv/VAlT/4QAIAXn/7QHO/+gB0//9Adj/zwJ7/+cCj//wApD/8QKa"
"/+UADAAhADEAhv+FAIf/hQHO/+gB2P/PAkD//QJ2AAYCe//oAn7/yAKP//ACkv/3Apr/5QABAKP/wwABAlj/+QAQAEz/4gCl/4EA"
"xf+BATEAAAFdAAkBugAAAb8ACwHT/+UB2P/EAkD/5AJTAAgCYv/RAnv/6AKP//IClAACApr/7AABAb8ACwAKARYAAAIr/+wCLP/x"
"AjL/yQI9/88CPv/XAlT/8wJi/+ECZv/nAmn/6gABACIANwAOARYADAEcAAwBMAALATEACwFcAAcBYQARAaUACwGnAAsCK//vAiz/"
"9AI9/9ECPv/aAlT/4AJpAAsACgDwABABFgAMARwADAEwAAsBMQALAU4ACwFcAAcBYQARAaUACwGnAAsACQDwABABFgAMARwADAEw"
"AAsBMQALAU4ACwFcAAcBYQARAlT/4AAMARYADAEcAAwBMAALATEACwGlAAsBpwALAiv/7wIs//QCPf/RAj7/2gJU/+ACaQALAA0B"
"FgAMARwADAEwAAsBMQALAaUACwGnAAsCK//vAiz/9AItAAkCPf/RAj7/2gJU/+ACaQALAAkBFgAMARwADAExAAsBpQALAiv/7wIs"
"//QCPf/RAj7/2gJU/+EAAQJU/9YAAgCD/8ACVP/EACUA2AAPAO8AAwD2AA8A+QANAPoADgEMAAABDQAPASQAAwEoAAMBKgADATAA"
"AwExAAMBNwAOAUsADQFOAAMBUQADAVUAAwFc//8BYQAIAXQAAgF7AAABugAEAcAABQHGAAEBxwABAcgAAQHJAAEBygABAiD/yQIr"
"/+8CLP/0Ajj/2gI9/9ICPv/ZAkwADQJU/8UCWP+6AAcATP/jAboAAAHT/+cB2P/GAkD/6AJ7/+kCj//zAAkBJAADAdoAAAIsAAoC"
"OAASAj4AAQJPAAsCVP//Alb//QJY//0AEABM/5oBjv/rAb//6QHV/8MB2gAKAhb/rgIX/7sCGP+7Ahn/oAIa/8gCG/+tAkAABAJ3"
"/9sCj//dApX/5wKa/8sACgDy/+MA9v/lAVX/9gFX//kBXAAHAiv/rQIs/64CPf+lAj7/qwJM/8UAFQDY/+QA2f/lAPD/4QDy/+MA"
"+v/hAP3/4wEWAAABN//iAVX/9gFcAAcBYQAFAXIABQGJ/+sBiv/tAiv/rQIs/64CL/+NAj3/pQI+/6sCQf+IAkz/xQAMASoAAAF2"
"//MBkAAGAdj/0AIt//8CQP/7AlMAAQJ7/+8Cj//uApL/9wKUAAgCmv/hAAMBIAAEAlT/2wJY/90AAQJU/9MAHQDYAAwA8AANAPYA"
"DAD6AA0BDP/vAQ0ADQE3AA0BVQAEAVz/7gFhAAUBdP/uAXX/8QHG//ABx//wAcj/8AHJ//AByv/wAcv/8AHM//ACK//0Aiz/+AI9"
"/90CPv/nAkwADQJU/8YCWP/JAmH/4gJj/+ICav/lAAsBGgABASAAAQEhAAMBv//sAdX/xgHaAAYCLgANAkAADgKP/9cCkv/3ApX/"
"3QADAV0ABQIg/78CJv+9AB8A2P/tANn/7QDvAAwA9v/tAQwABQETAAwBFgAMASQADAEoAAwBKgAMATf/7AFcAAYBxgAMAccADAHI"
"AAwByQAMAcoADAIrAAoCLAAJAi0ADgIwABcCMgASAkz/yQJUABkCYQASAmIAIAJjABICZf/NAmf/zQJpAB0CagAdAAMAhv/CAiwA"
"KQJUAB8AAgCH/74CVP/xAAMB2gAAAkL//AKa/+IAAQCD/7sAAwF0//8CPf/sAlT/5QAFASQAAwGpAAMCLAAIAlT/+QJY//sACABM"
"/5UATv+VAR7//wGW/+QB1f/NAdoACgJ3/+MCj//kAAUATP+wAdX/2gHaAA0Cd//mAo//7AALAdT/+gHV/8QB1v/2Adn/+QHa//kC"
"U//0Anf/5QKP/8cCkv/tApX/0gKa/7cAEABM/48Apf++ARr//AFT//sBv//qAcL/8wHV/8AB2gAGAhX/tgIX/8ECU//7Anf/3gKP"
"/98ClP/3ApX/6QKa/9IABgEA/9wCIP/JAib/ugIr/74CLP/wAlT/8AAGAb//7AHV/8gB2gALAkAADgKP/+QClf/qAAMBFgAAASAA"
"BgJU/+UABACD/34Bpv/8Adj/ywJA//sAAQFc/+kAAgEw//wBMf/8AAEBMf/8AAEBs//dAAIBMf/8AbP/3QABAlT/+QADAaYABwJU"
"/+8CWP/yAAEBKgAGAAECPf/sAAMBIAAIAakAAwI+AAAABwDwABABMQALAU4ACwFcAAcBYQARAaUACwI9/9EABABM/48Axf++Aan/"
"+wHV/74AAwI9/6kCPv/NAlT/4QACAjz/1gKS/9cAFwDY//wA7wAfAPL//gETAB8BFgAZASQAHwEoAB8BMAAQATEAEAEzABEBN//4"
"AVEAEAFVAAcBVwAOAVwACwFhAAkBYgAJAXQACwJM/+ECVAA9AmEANgJpAEsCagBLAAUA2P/zAPr/8gEK//IBN//zATj/8wACAEz/"
"nQIZ/6IAAwFcAAwCK/+1Aiz/twALANj/5wDZ/+cA+v/kARYABAEoAAQBN//lAiv/tQIs/7cCPf+rAj7/swJM/8QADwBM/7gA7v/w"
"APn/3AFL/+UBTwAHAakADAHOABkB1f/FAdoADwIv/6sCMAAGAjYAFwJP/78Cj//gApv/wgAKAIP/8gFTAAgBev//AakAAAG6AAEC"
"RP/qAlj//wKa/+ICm//UApz/yQAHAU8AAAGpAAAB2gAFAlj//wKUAAwCm//UApz/0QAJAIP/0gI8/9YCRP/QAkr/0AJY/+cCbv/b"
"AnD/2wKb/60CnP+vAAMCPf+hAj7/pgJU//MABQI4/4kCPf+hAj7/pgJM/78CVP/xAAEBzwAFAA8BzwAGAdAABAIg/8QCJv/AAisA"
"CAIsAAgCLQAPAjgAAwJM/98CVP/aAlb/zQJY/84Cav/9An3/wwKO/9gAHwAB/9kAGQANAD//4ABM/9gAfAADAIP/1wCb/90AnP/r"
"AKH/zACi/80Ao//NANgACADwAAkA9gAIAPoACQENAAkBGgAZAVUAAwFcAAUBev/0Ac0ADQHOAAsCKP/9Ai//zQJP/7kCVv/AAl7/"
"zAKP//ICkP/2Apv/4AKc/9YACAAB//sBGgAlAVX//wHOAAcB0wAAAo//7AKQ//ICm//TABMAGf/6ADb/+gBe//oAg//jAJv/5ACc"
"/+4Aov/eANj/7gDw/+wA9v/vAPr/7AEx//4BzQAHAc4ADQJW/90Cj//eApD/8QKb/70CnP/UABEAAf/rAIP/5wCb/+YAof/jAKL/"
"4gDYAAoA+gAKARoAJwFc//sBev/5Ac0AAwHOAAoCVv/OAl7/4QKP/+UCkP/+Apv/ywAmAc3/qAID/7UCBP+zAgb/vQIH/6cCCP+7"
"Agn/twIK/78CC/++Agz/uwIf/5MCIP+WAiH/uQIi/6ACI/+YAiT/mwIl/5UCJv+oAif/nwIo/5wCL//FAjn/jgI//8YCQP/MAkT/"
"jAJP/7kCVv+0Al7/vgJi/5cCaf+eAm7/kgJw/7ECe/+8An3/gwKP/9cCkP/yApv/ygKc/3cAHgAB/+gAGQAGADYABgCD//kAof/y"
"ANgADADwAA4A9gAMAPoADgEM/98BDQAOAVz/3QF0/90Bev/cAXv/1wHG/98Bx//fAcj/3wHJ/98Byv/fAc3/+AHO//gCP//bAkD/"
"5wJP/80CVv/yAo//7wKQ//UCm//aApz/qwATAAH/5gCD/+MAm//kAKH/3QCi/94A2AANAPYADQD6AA0BGgAgAVz/9QF6//IBzgAD"
"Aj//7QJP/8oCVv/LAl7/3QKP/+8CkP/7Apz/wQAOARoAKQHP/9kCL/9WAj//0gJA/9cCT/9aAlP/3gKI/8UCj/+0ApD/6wKT/7oC"
"lf+6Apj/vwKb/40ADgAB/+0Ag//mAJv/5QCc/+wAov/hANgACgD6AAoBXP/8Ac4ACgJW/88CXv/hAo//4gKQ//8Cm//JAA4BzQAP"
"AiD/2wIm/94CL//OAjn/1QI///wCQP//Ak//uQJTAAoCVv/DAl7/1QJ9/9gCj//yApD/9wALAjL/jAJE/4kCVP/CAmH/lwJi/50C"
"ZP+8Amn/tgJq/7wCbf+KAm7/lgJ+/4sACQH5//8B+v/+AjL/lQJE/5MCVP/OAmH/twJi/74CZP/IAn7/sQAIAjL/kAJh/50CYv+j"
"AmT/vQJp/7wCav+9Am3/kAJ+/5UACgIy/44CRP+LAlT/yQJh/58CYv+lAmT/vwJp/70Cav++Am3/kQJ+/5cADAIy/4sCVP/JAmH/"
"jAJi/5MCZP+0Amn/oAJq/7MCbf+FAm7/jAJ+/4ACjv+yAo//uwAGAjL/lwJU/8gCYf+vAmL/swJk/8UCfv+1AAoCMv+MAkT/igJU"
"/8YCYf+dAmL/owJk/78Caf+8Amr/vgJt/5ECfv+VAAcCMv+PAjj/uAJE/4oCVP+8AmH/ugJi/70Cfv++AAoCMv+NAkT/iwJU/8oC"
"Yf+eAmL/pAJk/78Caf+8Amr/vQJt/5ECfv+WAAkCMv+MAlT/wgJh/5gCYv+eAmT/vQJp/7gCav+9Am3/iwJ+/44AAQIN//4AAQIN"
"//UADgH5/+kB+//2Af3/wwIB//UCFf/aAhb/6wIX/+cCGP/lAhn/tAIa//QCG//bAhwACwId/+YCHv/lAAECVP/NAAICFf//Ahb/"
"/gAHAIP/VwCb/5IAnP+1AKL/YgFc/84Bdf/XAlT/6AAFAIP/WwCb/5IAnP+3AKL/ZQJU/9sACwAZ/9wANv/dAF7/2wCD/10AiP/h"
"AJv/cgCc/58CFv/QAkz/ywJU/9oCWP/NAAMAg/9cAJz/xAJU/9oABACD/1sAnP+2AlT/2AJY/80AAwA//8ACGf/VAlT/uwAIAAH/"
"hwIN/9ECK/+pAiz/qAI4/38CPf+hAlT/9wJl/70ABwAB/5gCDf/uAiv/qQIs/6gCOP+RAj3/ogI+/6YABQIN/94CK/+pAiz/qAI4"
"/4sCPf+hAAUCDf/eAiv/qQIs/6gCOP+IAj3/oQAFAg3/3QIr/6kCLP+oAjj/hwI9/6EACwAB/1YAGf+/Ag3/sAIr/6kCLP+oAi3/"
"wAIu/78COP9PAj3/oQJl/3oCZ/+EAAUCDf/iAiv/qQIs/6gCOP+LAj3/oQAFAg3/0wIr/6kCLP+oAjj/fwI9/6EADwHN/6kCIP+p"
"AiH/qQIi/6kCI/+pAiT/qQIl/6kCJv+pAif/qQIo/6kCKwAAAlP/8gJW/8wCWf/hAmr/sQAKAiD/qAIh/6gCIv+oAiP/qAIk/6gC"
"Jf+oAib/qAIn/6gCKP+oAmr/sQAEAc8ACAJT//8CVv/NAln//wADAiD/wgIm/8ECVP/zABAAhP9jAV3/wAIg/4ICIf9CAiL/QQIj"
"/zwCJP8/AiX/OwIm/0ACJ/89Aij/OwJT/+ACWf/QAmP/qAJk/6gCav+xAAcCMP/8AlT/9wJh//cCZf/nAmb/+gJn/+cCaf/9AAUC"
"MP/7AjP/rgI7/64CVv/aAl7/2gAbAAH/9AAZ//gAXv/5AHX//QB3//kAfAAOAIP/kwCb/5YAnP+zAKL/kQDwAAsBDP/SAVAACwFc"
"/88BdP+5AXX/zAF7/68Bxv/SAcf/0gHI/9IByf/SAcr/0gHS/5gB2P+gAlT/xQJh/4YCaf+NAA4AAf+IAEz/jQCh/+gA2P/GAPD/"
"wwD2/8YA+v/CAQ3/yAE3/8MBTv/3AVD/xgFV/9cBXAAHAYn/yQANAAH/2gA//88ATP/KAIP/yACb/9sAof+8AKL/xgHS//wB2gAL"
"Aiv/zQIs/9ACPf/AAlT/ywAaAHL/yADu/6cA+f+qARkAOAEgAEMBS/+eAc//yAIW/5cCGf9pAh3/jQIv/1gCN//SAk//YQJT/8sC"
"YP90Amz/eAKF/7cCh//RAoj/twKJ/8gCjP+kAo//qwKc/6wCnf+6Ap//mwKi/6gAKAAZ/8IANv/DAF7/wgB3/8IAfP/bAIP/aACI"
"/8YAm/9TAJz/jwCi/1cA2P/ZAPD/1wD2/9kA+v/XAQz/zQE3/9cBXP+/AXT/igF1/58Bxv/NAcf/zQHI/80Byf/NAcr/zQHR/8oB"
"0v+VAdf/0AHY/7oCNv+AAjn/TAJh/4ECYv+GAmP/rAJk/60CZf+4Amf/uAJp/4QCav+0Am3/hAJu/4gABwAZ//gAd//4AIP/kACb"
"/5QAov+PAmH/hQJp/4wAEwCi/6MBqf/wAc3/oQIg/6ICIf+hAiL/oQIj/6ECJP+hAiX/oQIm/6ECJ/+hAij/oQJE/6YCU//XAlb/"
"wAJZ/8YCaf+hAm7/oQJw/6YAAgJu/6YCcP+mAAECU//3AAMCTP/BAlT/7QJp//UAEACE/1kCIP+CAiH/PwIi/z0CI/86AiT/PAIl"
"/zkCJv8/Aif/OgIo/zkCRP+EAlP/1wJp/1wCbf9TAm7/UwJw/6YAAwJCAAICVP/4AmX/6AACAkX/rwJuAAwACgAZ//EAg/+PAJv/"
"kACi/4wAwP/xAVz/xwF0/7EBs/+kAmn/iQJt/4MABQCD/48Am/+QAKL/jAJp/4kCbf+DACcAIQAwAD3/4wBWAA0AcgAJAHb//ACG"
"/3AApP+CAKX/ggCm/4IAp/+CAMX/ggDG/4IBLwATAUsADQHPAAQCB//IAiD/twIi/9MCI/+IAiT/zAIl/8QCJv/KAif/0gIo/80C"
"P/+/AkD/wwJE/4sCTP/0AlMACgJW/6gCX/+8AmD/iQJj/8cCZP/NAmr/wgJs/4wCbv+VAnD/wgKH//AACgCG/2wCIP+7AiP/kAIk"
"/9ACJf/KAij/0AJE/4sCTQAAAmD/jQJs/4wACwIg/7sCI/+QAiT/0AIl/8oCKP/QAkD/wwJE/4sCYP+NAmT/zQJs/4wCbv+WAAMB"
"TgALAk8ALQJu/2cACAAhAD8APf/mAHb//ACG/3UApP+bAl7/qwJg/2kCbP9yAAMAhv91AmD/agJs/3IAAgJg/2oCbP9yAEwAIf/7"
"AD3/6ABW/8sAZv/EAHL/ygB0/78Adv/2AMwALgDm/8QA6P/AAO7/yQDy/8cA+f/CARUAKwEZAD0BGgAOASAAKAEhAC4BJwBEAS//"
"4QE//8UBS//aAU7//wFPAAoBV//dAVv/xwFd/8YBZf/EAXb/yAF5/8gBhf/tAaX/8AGpADUBv//gAc///gIH/8MCLgAZAi//1wIz"
"/78CN//MAj//1QJE/9oCRf+/AlP/xQJgABkCbAAZAm7//wJw//oCdv+5Anf/xgJ5/9UCev+6Anz/ugKB/7gCg//1AoX/swKH/8gC"
"iP+uAon/vwKM/9ECj/+lApD/vwKR/6cCk/+hApT/3QKV/6EClv/jApf/wwKY/80Cmf+KApr/ogKb/4ECnP+OAp3/uAKi/7YCpf+i"
"ABIAAf/pAIP/zgCE/9IAm//SAJz/4QCi/8cAo//HANgABwD2AAcA+gAIATcACAF0//wBe//7Aj//9wJA//0CUwAIAlb/1QKc/8sA"
"DwFO//0B0f/AAdL/xwHT/+AB1P/OAdX/swHX/8ECK//MAkz/qAJT/9QCZf+hAmb/rwKO/5ICj/+gApz/lwAGAiv/ywIs/9oCPf+4"
"AlT/1QJW/9oCnP+nABMAcv/CAO7/vQD5/7sBFQAkAScAOwFL/9gBTv/9AVf/3wGpADMCL//JAjP/sgI3/8UCRf+yAlP/1AJ2/7cC"
"j/+cApv/fgKc/5UCnf+xABIAVv/RAHL/1gB0/8YCN//YAjv/3QJZ/9ACYAAJAmwACQJ2/9ECef/hAof/0AKI/7kCj/+tApX/rQKY"
"/+sCmf+TApv/igKc/5MAAgCD/9cCXv/fAAMAGf+/AdL/wQKO/4sADwAZ/8AAHf/AADb/wAA5/8EAXv+/AHf/vwB8/9YB0v/CAdT/"
"2QHV/7oB1//HAlD/qwKO/44Ckv+rApv/fQAMAFb/xwBy/9QAdv/yAIP/rACF/6wAm/+tAJz/tACi/6kBdP+vAXX/vAJM/7wCj/+o"
"AA8AVv/CAHL/1AB2//IAhv9zASEAFAFO//sBW/+8Ajf/wAJT/+gCYf9QAmL/UAKI/5sCj/9oApH/cAKZ/5kACwAhAAMBIABOAScA"
"KAHP//ACL/9QAjP/ngI7/54CT/9hAmD/UAKP/7oCm/+nAAYA7v+zAUv/pwFd/+YCL/9QAlP/3AKb/4wADgAB/68AEf+vABP/rwAV"
"/68AF/+vAEz/swEgAE4BS//HAi//qAIz/7kCO/+5Akz/xwJO/8cCYP+oAAwAdP/iAOj/vADu/7oA/v/CARQAFgEaACkBHgAaASAA"
"RQEiADsBS/+3Ai//qAJg/6gACQAhAAwAVv/XAIb/mQFL/+cCIP+/Aib/rQIv//MCM//xAlb/swARACEAGQCD/3oCIP+rAiL/zAIj"
"/8ACJP/HAiX/wQIm/7wCJ//MAij/xQIv/7ACP//CAkD/xgJE/6UCVv+hAl7/rwJf/7oABACG/6YCIP+/Aib/rQIz//EADAIg/6wC"
"Iv/MAiP/wAIk/8cCJf/BAib/vAIn/8wCKP/FAi//rwI//8ICQP/GAl//ugARACEABABW/9QA7v/eARQAHgEaAC8BIABIAScALwFL"
"/9IBz//0Ai//XAIz/7ACO/+wAkH/XAJF/7ICT/9kAlP/9AKb/7UACwDu/94BFAAeARoALwEbADIBHgAZASAASAEiAEECL/+xAjP/"
"uAI7/7gCRf+7AAUAg/+rAJv/rACc/7IAov+oAXT/rQAJAFb/wABy/88Adv/xAIb/ewJt/1MCbv9TAnD/pgKP/28Cpf+CAAQCQf9T"
"AkX/mQJP/2cCbP9TAAUBS/+eAj//ywJA/88CQf9TApv/ggAEAAH/rgBM/7ICRf+zAmz/pgAKAHT/2wEaACcB1f+sAj3/pgI+/6YC"
"Qf+mAkz/tAJU//UCZf+sAmf/rAAMAAH/xgA//8oATP+7AIP/vwCb/8oAnP/hAKH/pgCi/7EAqv/KAPYACAENAAkCVP+8AAcB0v+Y"
"Adj/swJU/8oCYf+PAmL/kwJk/7wCaf+kAAUATP/HAIP/xACh/7MAov+3AlT/uwAIAiv/qQIs/6gCOP+IAj3/oQI+/6YCVP/GAlr/"
"ygJ9/9gAAgCi/7cCVP+7AAkCK/+pAiz/qAI4/44CPf+hAj7/pgJM/8ICVAAGAmX/zQJn/80ACwAB/3oAGf/zACP/9wA1//cATP+E"
"AFj/9wDY/8MA8P+/APb/wwEN/8UBN//AAAECVP+/AAMB1f/mAdoABQJU/9sABwIg/8ECJv+7Aiv/wQIs/8ECOP+8AlT/uQJY/6cA"
"DQHS//EB0//9AdQAAQHV//4B1v//Adf//QHY//cB2v/9Aiv/6wI4/9YCVP/HAlj/xAJa/9YACAHS//cCK//bAiz/3wI4/8oCPf/C"
"Aj7/yQJU/8QCWv/MABAB0v+dAdP/wgHY/5YCIP+uAiL/wQIj/5QCJP++AiX/uQIm/78CJ//BAij/vgIy/5oCOP++AlT/qwJp/7MC"
"av/AAAIB1f+iAjj/wgAGAdL/9AHV//YB1//2Adj/9wHa//0CVP/UAA8B0f+8AdL/0AHT/8kB1P/NAdX/sgHW/+YB1/+9Adn/zQHa"
"/8kCI//BAiv/rwIs/64CLf+1Ai7/tAI4/5IABwIE/7UCVv+SAlz/jAJe/48Cbv+4Aof/vQKN/6cAGQAB/5sAGP/XABn/5QA8/9cA"
"P/9zAEz/cwBY/9cAfP++AIP/UwCb/58Aof9nAKL/dgCq/30A2P/iASr/2AF1/9UBev+2AXv/ywHP/94B0P/OAgT/rAIK/7sCh/+x"
"Aov/zAKN/50AGQAB/8wAGP/gADX/4AA8/+AAP//NAFj/4AB1/+AAfP/qAIP/vgCb/8wAov+5ATD/4QEx/+EBTv/hAVX/4QHS/+MB"
"0//oAdT/6gHV/+cB1v/oAdf/5QHY/+UB2f/rAlT/qAJa/7IACAA//3MAov95AdL/rQHT/7QB1P+tAdj/qQJU/44CWv+aAA8AAf/H"
"ABkAAwA2AAMAP//CAEz/twBeAAMAg/+0AJv/yQCc/94Aof+sAKL/tACq/8cBVf/2AXr/7gKN/7cABQAB/6sAov+dAO//2AHR/98C"
"VP+hABAAAf+xAD//jwBM/44Ag/94AJv/swCc/9AAof9+AKL/jgCq/50Bev/TAYP/1QHS/74B0//JAdj/uwJU/6EClP/FAAMB1AAZ"
"AlT/3AKV/8UACgCD/00B0f/KAdL/lgHT/8gB1P+xAdX/uAHY/5sB2f+4AlP/ywJU/6UAAgEx/9MCVP+9AAoB0f/oAdL/uAHT/+kB"
"1P/TAdX/0wHW/+kB2P/CAgT/tAIK/7wCVP+4AAwAAf+JAdH/zAHS/7cB0/+9AdT/vwHV/8oB1v/GAdj/uAHZ/8YCU//LAlT/fQJa"
"/4QAFgAB/7UAGP/IAHX/yACD/zsAm/+GAKH/pACi/14A9v/XAQz/vAEq/80BMP/NATH/zQFR/80BVf/RAVz/vAF6/6cBe/+1AYP/"
"uwHS/4wB0/+1Adj/jgJU/4gABgIw/8wCQv/MAkT/rAJT/9wCXv9+Am7/rwAEAc//ugIw/7wCU/+4Al7/ggADAlT/uAJY/7ACWv/D"
"AAcAAf+kANj/qQD2/6kA+v+pAVX/qwGJ/6UCn/+xAAECU//ZAAkAAf90ANj/tgDw/7QA9v+2AQ3/twFV/74Bev/NAdD/3QHV/5kA"
"DAIg/7UCIf/ZAiL/ugIj/5oCJP+3AiX/tQIm/7oCJ/+5Aij/uQJE/44Cbv+sAnD/tQALAjL/iwI2/38CRP+IAlT/xQJa/+gCYf+F"
"AmL/igJj/7ECZP+0Am3/fQJu/4AACgA//1YAov9OAdL/hQHT/4UB1P+PAdj/fQJU/3sCWv+FAm3/iQJu/4kAAmK0AAQAAGRKaFYA"
"awB2AAD//wACAAD//AAAAAAAAAAA//3/+AAAAAD//wAAAAAAAv/7AAD/2wAAAAAAAP//AAD/rQAAAAD//f/y/+f/6//v/+wAAP/9"
"//n/9AAB/5IAAAAA//////////UAAP+4//cAAP/5//cAAP/LAAAAAP/y/+//5P/u/+QAAAAA//4AAP/NAAAAAP+//+X/8QAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//wAAP/1AAAAAP/4//8AAP/x//0AAAAA//7/+//F/8T/xP/2/9T/yQAAAAAAAP/5"
"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"
"AAAAAAAEAAAABQAAAAAAAAAA/6z/8P/5AAAABQAD///////h/9IAAAAJAAAAAP/+////+////////wAA//z//////////P//////"
"///5/////QAAAAD//wAA////+//9//z//P////r/+gAA/+kAAP/8//f/8v/+//4ALAAA//3//P/9//0AAAAA//3////5//0AAP/6"
"AAD//wAAAAD/+f/9/+EAAAAA//z//P/3//8AAP/7//3//QAA/+wAAP/uAAAAAAA1AEIAFQAAAAAAKgAAAAAAAAAA//3//v/7AAD/"
"/wAAAAAAAP/w//0AAAAA//wAAP/7AAAAAAAAAAD/0P/9AAD/+//8//v//v/+//7//QAA//sAAP/+/87/qP9w/33/eP+WAAP/swAH"
"/5L//P+g/4D/1f/O/6D/iAAI/+T/l//6//3/0AAI/5//df+UAAD/7//zAAD/pgAA/5v/iv+r/8cACv/+AAD/mv+g/3H//QAAAAD/"
"+//l/2n//gAAAAAAAP+JAAAAAP/r//T/dwAAAAD/rf/6//n/egAAAAD/7f//AAD/bAAA/3kAAAAAABoALwAgAAAAAAAUAAAAAAAA"
"AAD/1f+B//wAAP/VAAAAAAAA/1f//QAAAAD/rAAA//8AAAAAAAAAAP+t/87/hQAI//MACAAKAAr/zf/NAAD/kAAA//z/9f/gAAP/"
"4v/f//j/+P/wAAH//f/9//z/9wAC//X/9//z/+3/9gAF//0AAwAB/93//f/u/9P//f/7//v//f/0AAD//P/F//cAAv/hABMAAAAB"
"//oAC//1AAAAAP/2//r//f/8AAD/5QAA//0AAAAA//b////SAAAAAP/9//b/2v/3AAD/4/////oAAP/eAAD/5gAAAAAAMQA2AAAA"
"AAAAACwAAAAAAAAAAP///8//+gAAAAIAAAAAAAD/+//8AAAAAAABAAD/4AAAAAAAAAAA/9T/5f/5/90AAv/j/+H/4f/4/+MAAAAB"
"AAD/9v/L/94ACP/g/97/5v/R//MAB//6//r/sv/r/8j/zv+P//X/oP/oAAX/+gAJ/8T/U/+q/13/gv9e/2P/Xv+0//0AAP/4/7AA"
"AP///17/9gAAAAD/jgAP/0oAAAAA/0j/6gAA/z0AAP9MAAD//AAAAAD/i/+O/20AAAAAAAX/+f/V//0AAP+G/5n/PQAA/zUAAP9t"
"AAAAAP/6//r/+gAAAAD/+gAAAAAAAAAA/z//sP9DAAD/yAAAAAAAAP///0EAAAAAAAYAAP/NAAAAAAAAAAD+7f/u//r/UwAC/2r/"
"YP9j/9b/zAAAAAoAAAAA///////zAAD//wAAAAL//P////8AAP/7AAEAAAAA//sAAP/9AAAAAAAA//8AAP/7//7//v/9AAD/+//7"
"AAD/5wAA//r/+P/w//3//gAuAAD/+v/9/+n//wAAAAD//v///+3//gAA//sAAP//AAAAAP/6//3/4gAAAAD/+f/4//YAAAAA//wA"
"AP/+AAD/7gAA/+8AAAAAAAAARQAXAAAAAAAqAAAAAAAAAAD//f////sAAAAAAAAAAAAA/+v//gAAAAD/+gAA//cAAAAAAAAAAP/R"
"//4AAAAA//X//AAAAAD/////AAD/+QAA//8ADwAK/9UACQAJAAcABgAB/9UAAwAEAAMACgAFAA4AAwAD/+kAAf/7AAT/3AAF/8YA"
"BAARAA3////5//j//f+8AAD/+QAC/8T//v/NAEAAAP/zAAP/rP/+AAAAAP/+//7/w//7AAD/2gAAAAIAAAAA//D/+P/uAAAAAP/Q"
"/8b/vgAJAAD/0f/7//wAAP/zAAD//gAAAAAAHAAYAAUAAAAAABoAAAAAAAAAAP/9AAj//QAAAAUAAAAAAAD/xQABAAAAAP/QAAD/"
"uQAAAAAAAAAA/9T/+QAE/8b/w//X/83/zQAMABAAAP/OAAAAAP///+wABv/t/+wAAf////n//wAAAAAAA//zAAL//wAB//3/4v//"
"AAwAAAAEAAH/uwADAAD/yf/9//P/9v/8//0AAP///8wABAAO/70AAAAAAAQABAAO/+IAAP/A//sAAAAD//4AAP++AAAAAP/6//r/"
"8P/9/84AAAAAAAoAAP/c//sAAP/D//D/+AAAAAD/7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAP/9AAAAAgAA/+wAAAAA"
"//8AAAAAAAkACf/O/87/yf///73/1QAAAAAAAP/7/9AAAAAAAAAAAAAAAAAAAP///+L/7wAK//D/7//v/+D//AACAAAAAP/c//T/"
"3f/j/9T//f/Y//EADAAAAAr/2//S/9oAAP/i/9f/0P/R/9f//wAA//3/0QAKAAr/0gAAAAAABf/XABD/1gAA/83/1QAAAAr/1wAA"
"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"
"/8z/qgAA//gADgAIAAj/1P/RAAD/kAAA//8ABf/u/5z/8P/t//8ABv/w/+n//AABAAj/8QANAAUAB//7//kAAP/7////3wAN/+cA"
"C//+/90ADgAHAAYAC/+hAAD//P/U/6YAAv/sACIAAP/3AAv/VP/9AAAAAAAFAAb/igALAAD/9AAA//wAAAAAAAIADv/lAAAAAP+p"
"/+D/3f/rAAD/7gAHAAcAAP/uAAD/7gAAAAAANgA8AAsAAAAAADMAAAAAAAAAAAAP/88ABQAAAA0AAAAAAAD/TAALAAAAAP+oAAD/"
"0gAAAAAAAAAA/+D/5P/z/+f/0v/u/+z/7AAD//AAAP+UAAD//v/r/+L/ov/h/+H/4wAB/9gACP/bAAD/1//j/9r/6v/X/9wACP/p"
"/8H////9/9QACP/d//T/5AAD//D/9QAC/6MAAP/L/9f/qf/RAAoAFAAA/8T/2f9aAAMAAAAA//3/6f+P//8AAAACAAD/2AAAAAD/"
"6//0/9UAAAAA/6v/+f/5/+AAAAAA/+0AAwAA/94AAP/iAAAAAAAAADQAIAAAAAAAFQAAAAAAAAAA/9j/1P/+AAD/2gAAAAAAAP9Z"
"//4AAAAA/6oAAP//AAAAAAAAAAD/tf/U/9gAAP/zAAgACgAK/+n/6gAA/50AAAAAAAIAC//tAAoACwAEAAMAAf/3AAAABP/5AAr/"
"/QAD//gABP/uAA///wAA//v//P/i//r/9gAF//3/+//5//z/3wAA//z/+v/oAAD/5wAVAAD/+f/5/9f/9QAAAAD/9wAP/+L//AAA"
"/+UAAP//AAAAAP/5////3AAAAAD/8//j/9YACgAA/+UAAP/6AAD/5AAA/+sAAAAAADQAOAAIAAAAAAAuAAAAAAAAAAD//AAR//oA"
"AP/9AAAAAAAA/+n//AAAAAD/9wAA/9AAAAAAAAAAAP/PAAYAC//i/+b/5v/n/+cAAP//AAD/7QACAEMAAQA8AAAAPwBNADwATwBS"
"AEsAVABUAE8AVgBYAFAAXABcAFMAXgBpAFQAcAB1AGAAdwCBAGYAgwCDAHEAhQC6AHIAvAC+AKgAwQDJAKsA2ADaALQA4ADiALcA"
"5gD3ALoA+gEBAMwBAwEYANQBGgEaAOoBHAEcAOsBHgEeAOwBIwEkAO0BJgEqAO8BLAEsAPQBMAE8APUBPgFCAQIBSQFKAQcBTAFR"
"AQkBVAFaAQ8BXAFcARYBXwFuARcBcAF+AScBgAGGATYBiQGMAT0BkQGTAUEBlwGjAUQBpQGlAVEBpwGnAVIBqQGpAVMBqwGtAVQB"
"rwG2AVcBuAG7AV8BvQG9AWMBwAHAAWQBwwHDAWUBxgHPAWYB0QHaAXACCAIIAXoCCgIKAXsCIQIiAXwCKwIvAX4CMgIyAYMCNgI2"
"AYQCOAI4AYUCPQI/AYYCQQJBAYkCRAJEAYoCTAJVAYsCVwJXAZUCWQJaAZYCXwJwAZgCdwJ3AaoCfgJ+AasCjgKPAawCkgKSAa4C"
"mwKcAa8CowKjAbEAAgCsAAEAFgABABcAFwACABgAGABqABkAHgARAB8AIgAdACMANAACADUANQBpADYAOwAQADwAPAAYAD8APwAI"
"AEAAQAAcAEEASwAIAEwATQAcAE8AUAA0AFEAUgAbAFQAVAAbAFYAVgAbAFcAWAAYAFwAXAAYAF4AaQAEAHAAcwAEAHQAdAACAHUA"
"dQBoAHcAdwAEAHgAewAaAHwAgQAVAIMAgwAZAIUAhwAZAIgAjwAHAJAAlQAPAJYAmgAHAJsAmwBnAJwAoAAUAKEAoQBmAKIAqQAL"
"AKoArQAXAK4AsQABALIAsgARALMAtgACALcAtwAQALgAugAIALwAvgAEAMEAwgAHAMMAwwAPAMQAxAAUAMUAxgALAMcAxwAXAMgA"
"yAAYAMkAyQAcAO4A7gADAO8A7wAjAPAA9QAOAPYA9gAMAPcA9wBdAPoBAQADAQMBCwADAQwBDABYARMBFQAKARYBFgAMARgBGAAt"
"ARoBGgAsARwBHAAMASMBJAAMASYBJgAtAScBJwAsASgBKQArASoBKgAMASwBLABTATABNgAKATcBPAAFAT4BQgAFAUkBSgAFAUwB"
"TAAFAU0BTQADAU4BTwAjAVEBUQAlAVQBVAAlAVUBWgATAVwBXAAeAV8BYAAeAWkBbgANAXQBdAA3AXUBeQASAXoBegA2AXsBfgAJ"
"AYABggAJAYMBhgAWAYkBjAAGAZEBkwAGAZcBngAGAZ8BnwAOAaABowADAaUBpQAMAacBpwAMAakBqQAMAasBrQAFAbEBsQANAbIB"
"sgASAbMBtgAJAbgBuAAJAbkBuQAWAboBuwAfAb0BvQAfAcABwAAkAcMBwwAkAcYBxgBXAccBxwAyAcgByAAxAckByQAyAcoBygAx"
"AcsBzAAwAc0BzQBPAc4BzgBOAdEB0QA1AdIB0gBQAdMB0wA6AdQB1AA8AdUB1QBUAdYB1gBWAdcB1wA+AdgB2ABAAdkB2QBbAdoB"
"2gBRAggCCABVAgoCCgA/AiECIQA5AiICIgA7AisCKwBIAiwCLABeAi0CLgAzAi8CLwBaAjICMgApAjYCNgBiAjgCOAA9Aj0CPQAq"
"Aj4CPgAiAj8CPwBfAkECQQAqAkQCRAApAkwCTgAhAk8CTwA4AlACUgAgAlMCUwBNAlQCVABLAlUCVQBhAlcCVwBgAlkCWQBMAloC"
"WgBKAl8CYAAmAmECYQAoAmICYgBFAmMCYwAoAmQCZABDAmUCZQAvAmYCZgAuAmcCZwAvAmgCaAAuAmkCaQBGAmoCagBBAmsCbAAi"
"Am0CbQAnAm4CbgBEAm8CbwAnAnACcABCAncCdwBlAn4CfgBcAo4CjgBHAo8CjwBSApICkgBZApsCmwBjApwCnABkAqMCowBJAAIA"
"0gABABcABAAYABgAAQAZAB4AAgAfACAAAQAhACIAKAAjACQAAQAnACgAAQAqACoAAQAtADAAAQAzADMAAQA1ADUAAQA2ADsAEAA8"
"ADwAAQA+AD4AAQA/AEsACgBMAEwAdQBOAE4AdABPAFEAAQBTAFUAAQBWAFYAcwBXAFwAAQBeAHEAAgByAHIAcgBzAHMAAgB1AHUA"
"AQB3AHcAAgB4AHgAAQB6AHoAAQB8AIEAFACCAIIAAQCDAIMAJwCFAIUAJwCGAIYAcQCHAIcAcACIAJoACACbAJsAbwCcAKAAEwCh"
"AKEAbgCiAKMAGQCkAKQAbQCoAKkAGQCqAK0AFwCuALEABACyALIAAgC3ALcAEAC4ALoACgC7ALsAAQC8AMAAAgDBAMMACADEAMQA"
"EwDHAMcAFwDIAMoAAQDYAO0ABQDuAO4AbADvAO8ADADwAPEABgDyAPIAAwDzAPMABgD0APQAAwD1APUABgD2APgABQD5APkAXQD6"
"APsABgD8AQQAAwEFAQYABgEHAQcAAwEIAQgABgEJAQkAAwEKAQoABgELAQsAAwEMAQwAWwENARIADgETARMADAEUARQAVAEWARYA"
"FgEXARgACwEZARkAUwEaARoAUgEbARsAUQEcAR0AFgEeAR4ATwEgASAATgEiASIATQEkASQATAEmASYACwEnAScASwEoASgADAEq"
"ASoADAEsASwADAEuAS4ADAEvAS8ASQEwATYACwE3ATgABgE5AT8AAwFAAUAABgFBAUEAAwFCAUUABgFGAUYAAwFHAUcABgFIAUgA"
"AwFJAUkABgFKAUoAAwFLAUsAQgFMAUwAAwFNAU0ABgFOAU4ACwFQAVAABQFRAVIACwFVAVoAEgFbAVsAVQFcAVwAGAFeAWAAGAFh"
"AXMABwF0AXQAKwF1AXUAGgF3AXgAGgF6AXoAKgF7AYIADQGDAYYAFQGJAY0ACQGRAZQACQGXAZ4ACQGfAZ8ABgGgAaEAAwGiAaMA"
"BgGkAaQADgGlAaUAFgGmAaYAUAGnAacAFgGqAaoADAGrAawAAwGtAa4ABgGvAbEABwGzAbgAEQG5AbkAFQG6AboADAG8AbwADAG+"
"Ab4ADAHAAcAACwHBAcEANwHFAcUADAHGAcwADwHOAc4AQwHQAdAAPQHRAdEAKQHSAdIARQHTAdMALgHUAdQAMQHVAdUAWAHWAdYA"
"WgHXAdcANAHYAdgANgHZAdkAYQHaAdoARwINAg0AVgIgAiAARAIhAiEALQIiAiIAMAIjAiMAVwIkAiQAWQIlAiUAMwImAiYANQIn"
"AicAYAIoAigARgIrAisAPwIsAiwAYwItAi4AJgIvAi8AXwIwAjAAXAIyAjIAOwI2AjYAaAI4AjgAMgI5AjkAZwI9Aj0AIQI+Aj4A"
"JQI/Aj8AZAJBAkEAIQJEAkQAOgJKAkoAPgJMAk4AHAJPAk8ALAJQAlIAGwJUAlQAQQJWAlYAZgJYAlgAZQJaAloAQAJhAmEAHwJi"
"AmIAHQJjAmMAHwJkAmQAHQJlAmUAJAJmAmYAIwJnAmcAJAJoAmgAIwJpAmoAIAJrAmsAJQJtAm0AHgJuAm4AOQJvAm8AHgJwAnAA"
"OAJ3AncAawJ9An0ALwJ+An4AYgKOAo4APAKPAo8ASAKSApIAXgKVApUASgKbApsAaQKcApwAagKjAqQAIgAEAAAAAQAIAAEADAAW"
"AAUAsAGOAAIAAQKuAtIAAAACABkAAQBcAAAAXgB1AFwAdwCBAHQAgwDtAH8A7wD4AOoA+gE1APQBNwFOATABUAFaAUgBXAHFAVMB"
"2wHuAb0CKwIsAdECLgIuAdMCPQI+AdQCQAJAAdYCXwJfAdcCYwJkAdgCawJrAdoCbwJwAdsCegJ6Ad0CfAJ8Ad4ChAKFAd8ChwKI"
"AeECjQKNAeMCkgKSAeQCqwKtAeUAJQAAGMwAABjSAAAY2AAAGN4AABjkAAAY6gAAGOoAABkOAAAY8AAAGPYAABj8AAAZAgAAGQgA"
"AQCWAAIAnAACAKIAAheYAAMAqAAEAK4ABAC0AAQAugAEAMAAABkOAAAZDgAAGQ4AABkUAAAZGgAAGRoAABkaAAAZIAAEAMYABADM"
"AAQA0gADANgAABkmAAAZLAACF5IAAQAoAhkAAQBZAAAAAQBgAAAAAQDBAAAAAQDPAmwAAQGYARsAAQCPAW0AAQEpAQoAAQDUAQcA"
"AQCsAW0AAQE+AXEAAQCuAAAB6BQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQa"
"FCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABMSAAAUGhQgAAAT"
"GAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQa"
"FCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAEx4AABMkAAAAABQmAAAUegAAAAAUJgAAFHoAAAAAFCYAABR6AAAAABQmAAAUegAAAAAU"
"JgAAFHoAAAAAFCYAABR6AAAAABMqAAATMAAAEzYTKgAAEzAAABM2EyoAABMwAAATNhMqAAATMAAAEzYULAAAFDIUOAAAFCwAABQy"
"FDgAABQsAAAUMhQ4AAAULAAAFDIUOAAAFCwAABQyFDgAABQsAAAUMhQ4AAAULAAAFDIUOAAAFCwAABQyFDgAABM8AAAUMhQ4AAAT"
"QgAAFDIUOAAAFCwAABQyFDgAABQsAAAUMhQ4AAAULAAAFDIUOAAAFCwAABQyFDgAABQsAAAUMhQ4AAAULAAAFDIUOAAAFCwAABQy"
"FDgAABQsAAAUMhQ4AAATSAAAFZoAAAAAFD4AABREAAAAABQ+AAAURAAAAAAUPgAAFEQAAAAAFD4AABREAAAAABQ+AAAURAAAAAAU"
"PgAAFEQAAAAAE2AAABNmAAATbBNOAAATVAAAE1oTYAAAE2YAABNsFEoAABRQFFYAAAAAAAAAABRWAAAUSgAAFFAUVgAAFEoAABRQ"
"FFYAABRKAAAUUBRWAAAUSgAAFFAUVgAAFEoAABRQFFYAABRKAAAUUBRWAAAUSgAAFFAUVgAAFEoAABRQFFYAABRKAAAUUBRWAAAU"
"SgAAFFAUVgAAFEoAABRQFFYAABNyAAATeAAAAAATcgAAE3gAAAAAE3IAABN4AAAAABOKAAATfgAAAAATigAAE34AAAAAFM4UXBRi"
"AAAUaBTOFFwUYgAAFGgUzhRcFGIAABRoFM4UXBRiAAAUaBTOFFwUYgAAFGgThBOKFJgAABOQE5YAABOcAAAAABOiAAATqAAAAAAT"
"ogAAE6gAAAAAE6IAABOoAAAAABOiAAATqAAAAAATogAAE6gAAAAAFG4UdBR6FIAUhhRuFHQUehSAFIYUbhR0FHoUgBSGFG4UdBR6"
"FIAUhhRuFHQUehSAFIYUbhR0FHoUgBSGE64UdBR6FIAUhhO0FHQUehSAFIYUbhR0FHoUgBSGFG4UdBR6FIAUhhRuFHQUehSAFIYU"
"bhR0FHoUgBSGFG4UdBR6FIAUhhRuFHQUehSAFIYUbhR0FHoUgBSGFG4UdBR6FIAUhhRuFHQUehSAFIYUbhR0FHoUgBSGFG4UdBR6"
"FIAUhhRuFHQUehSAFIYUbhR0FHoTuhSGFG4UdBR6FIAUhhPAAAATxhPMAAAT0gAAE9gAAAAAFG4UdBR6FIAUhhPeAAAT5AAAAAAT"
"3gAAE+QAAAAAE94AABPkAAAAABPeAAAT5AAAAAAT6gAAE/AAAAAAE+oAABPwAAAAABPqAAAT8AAAAAAT6gAAE/AAAAAAE+oAABPw"
"AAAAABPqAAAT8AAAAAAXIAAAFyYAABP2FyAAABcmAAAT9hcgAAAXJgAAE/YXIAAAFyYAABP2FyAAABcmAAAT9hSMFJIUmBSeAAAU"
"jBSSFJgUngAAFIwUkhSYFJ4AABSMFJIUmBSeAAAUjBSSFJgUngAAFIwUkhSYFJ4AABSMFJIUmBSeAAAUjBSSFJgUngAAFIwUkhSY"
"FJ4AABSMFJIUmBSeAAAUjBSSFJgUngAAFIwUkhSYFJ4AABSMFJIUmBSeAAAUjBSSFJgUngAAFIwUkhSYFJ4AABSMFJIUmBSeAAAU"
"jBSSFJgUngAAFIwUkhSYFJ4AABSMFJIUmBSeAAAT/AAAFAIAAAAAFKQAABSqAAAAABSkAAAUqgAAAAAUpAAAFKoAAAAAFKQAABSq"
"AAAAABSkAAAUqgAAAAAUCAAAFA4AAAAAFLAAABS2AAAAABSwAAAUtgAAAAAUsAAAFLYAAAAAFLAAABS2AAAAABSwAAAUtgAAAAAU"
"sAAAFLYAAAAAFLAAABS2AAAAABSwAAAUtgAAAAAUvAAAFMIAABTIFLwAABTCAAAUyBS8AAAUwgAAFMgUvAAAFMIAABTIFBQAABQa"
"FCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQmAAAUegAAAAAULAAAFDIUOAAAFCwAABQyFDgAABQsAAAUMhQ4AAAU"
"LAAAFDIUOAAAFD4AABREAAAAABRKAAAUUBRWAAAUSgAAFFAUVgAAFEoAABRQFFYAABTOFFwUYgAAFGgUbhR0FHoUgBSGFG4UdBR6"
"FIAUhhRuFHQUehSAFIYUbhR0FHoUgBSGFG4UdBR6FIAUhhSMFJIUmBSeAAAUjBSSFJgUngAAFIwUkhSYFJ4AABSkAAAUqgAAAAAU"
"sAAAFLYAAAAAFLAAABS2AAAAABS8AAAUwgAAFMgUzgAAFNQU2gAAAAAAAAAAFNoAABTOAAAU1BTaAAAUzgAAFNQU2gAAFM4AABTU"
"FNoAABTOAAAU1BTaAAAUzgAAFNQU2gAAFM4AABTUFNoAABTOAAAU1BTaAAAUzgAAFNQU2gAAFM4AABTUFNoAABTOAAAU1BTaAAAU"
"zgAAFNQU2gAAFM4AABTUFNoAABTOAAAU1BTaAAAUzgAAFNQU2gAAFYgAABTsFPIAABWIAAAU7BTyAAAViAAAFOwU8gAAFYgAABTs"
"FPIAABWIAAAU7BTyAAAViAAAFOwU8gAAFYgAABTsFPIAABWIAAAU7BTyAAAViAAAFOwU8gAAFYgAABTsFPIAABWIAAAU7BTyAAAV"
"iAAAFOwU8gAAFOAAABTsFPIAABTmAAAU7BTyAAAViAAAFOwU8gAAFYgAABTsFPIAABWIAAAU7BTyAAAViAAAFOwU8gAAFYgAABTs"
"FPIAABWIAAAU7BTyAAAViAAAFOwU8gAAFYgAABTsFPIAABT4AAAWWgAAAAAWBgAAFgwAAAAAFgYAABYMAAAAABYGAAAWDAAAAAAW"
"BgAAFgwAAAAAFgYAABYMAAAAABYGAAAWDAAAAAAU/hUEFY4AABUKFP4VBBWOAAAVChT+FQQVjgAAFQoWTgAAFjwWEgAAFk4AABY8"
"FhIAABZOAAAWPBYSAAAWTgAAFjwWEgAAFk4AABY8FhIAABZOAAAWPBYSAAAWTgAAFjwWEgAAFk4AABY8FhIAABUQAAAWPBYSAAAV"
"FgAAFjwWEgAAFk4AABY8FhIAABZOAAAWPBYSAAAWTgAAFjwWEgAAFk4AABY8FhIAABZOAAAWPBYSAAAWTgAAFjwWEgAAFk4AABY8"
"FhIAABZOAAAWPBYSAAAVHAAAFSIAAAAAFhgAABYeAAAAABYYAAAWHgAAAAAWGAAAFh4AAAAAFhgAABYeAAAAABYYAAAWHgAAAAAW"
"GAAAFh4AAAAAFiQAABVkAAAVKBYkAAAVZAAAFSgWJAAAFWQAABUoFq4AABa0FroAABauAAAWtBa6AAAWrgAAFrQWugAAFq4AABa0"
"FroAABauAAAWtBa6AAAWrgAAFrQWugAAFq4AABa0FroAABauAAAWtBa6AAAWrgAAFrQWugAAFq4AABa0FroAABauAAAWtBa6AAAW"
"rgAAFrQWugAAFq4AABa0FroAAAAAAAAWtBa6AAAWrgAAAAAAAAAAFq4AAAAAAAAAABauAAAAAAAAAAAWrgAAAAAAAAAAFS4AABU0"
"AAAAABUuAAAVNAAAAAAWJBaWFrQAABYqFiQWlha0AAAWKhYkFpYWtAAAFioWJBaWFrQAABYqFiQWlha0AAAWKhU6FUAVRgAAFUwV"
"UgAAFVgAAAAAFV4AABVkAAAAABVeAAAVZAAAAAAVXgAAFWQAAAAAFV4AABVkAAAAABVeAAAVZAAAAAAWMBY2FjwWQhZIFjAWNhY8"
"FkIWSBYwFjYWPBZCFkgWMBY2FjwWQhZIFjAWNhY8FkIWSBYwFjYWPBZCFkgVahY2FjwWQhZIFXAWNhY8FkIWSBYwFjYWPBZCFkgW"
"MBY2FjwWQhZIFjAWNhY8FkIWSBYwFjYWPBZCFkgWMBY2FjwWQhZIFjAWNhY8FkIWSBYwFjYWPBZCFkgWMBY2FjwWQhZIFjAWNhY8"
"FkIWSBYwFjYWPBZCFkgWMBY2FjwWQhZIFjAWNhY8FkIWSBZOFXYWWhV8FYIWMBY2FjwWQhZIAAAWNgAAAAAWSBWIAAAVjgAAAAAV"
"lAAAFZoAAAAAFaAAABa0AAAAABWgAAAWtAAAAAAVoAAAFrQAAAAAFaAAABa0AAAAABWmAAAVrAAAAAAVpgAAFawAAAAAFaYAABWs"
"AAAAABWmAAAVrAAAAAAVpgAAFawAAAAAFaYAABWsAAAAABgGFcQVygAAFdAX+hWyFbgAABW+GAYVxBXKAAAV0BgGFcQVygAAFdAY"
"BhXEFcoAABXQFk4WVBZaFmAAABZOFlQWWhZgAAAWThZUFloWYAAAFk4WVBZaFmAAABZOFlQWWhZgAAAWThZUFloWYAAAFk4WVBZa"
"FmAAABZOFlQWWhZgAAAWThZUFloWYAAAFk4WVBZaFmAAABZOFlQWWhZgAAAWThZUFloWYAAAFk4WVBZaFmAAABZOFlQWWhZgAAAW"
"ThZUFloWYAAAFk4WVBZaFmAAABZOFlQWWhZgAAAWThZUFloWYAAAFk4WVBZaFmAAABYwAAAWPAAAAAAWZgAAFmwAAAAAFmYAABZs"
"AAAAABZmAAAWbAAAAAAWZgAAFmwAAAAAFmYAABZsAAAAABYYAAAV1gAAAAAV3AAAFeIAAAAAFdwAABXiAAAAABXcAAAV4gAAAAAV"
"3AAAFeIAAAAAFdwAABXiAAAAABXcAAAV4gAAAAAV3AAAFeIAAAAAFdwAABXiAAAAABZ+AAAWhAAAFooWfgAAFoQAABaKFn4AABaE"
"AAAWihZ+AAAWhAAAFooWrgAAFrQWugAAFq4AABa0FroAABX0AAAV+hYAAAAV9AAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAV"
"9AAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAV9AAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAV9AAAFfoWAAAAFfQAABX6"
"FgAAABXoAAAV+hYAAAAV7gAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAV9AAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAV"
"9AAAFfoWAAAAFfQAABX6FgAAABX0AAAV+hYAAAAWBgAAFgwAAAAAFk4AABY8FhIAABZOAAAWPBYSAAAWTgAAFjwWEgAAFk4AABY8"
"FhIAABYYAAAWHgAAAAAWrgAAFrQWugAAFq4AABa0FroAABauAAAWtBa6AAAWrgAAFrQWugAAFq4AAAAAAAAAABYkFpYWtAAAFioW"
"MBY2FjwWQhZIFjAWNhY8FkIWSBYwFjYWPBZCFkgWMBY2FjwWQhZIFk4WVBZaFmAAABZOFlQWWhZgAAAWThZUFloWYAAAFmYAABZs"
"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"
"AAAAfAAAAKAAAACCAAAAiAAAAI4AAACUAAAAmgAAAKAAAACgAAAAoAAAAKYAAACsAAAArAAAAKwAAACyAAAAuAAAAL4AAQCoAg0A"
"AQBUAg0AAQDAAg0AAQBYAg0AAQC4Ag0AAQDNAg0AAQCQAg0AAQDEAg4AAQDWAg0AAQBwAg0AAQBXAg0AAQC2Ag0AAQC6Ag0AAQDO"
"Ag0AAQDMAg0AAQCzAg0AAQBkAg0AAgAGAAwAAQDOA1UAAQDMA04AAQAAAAoCNgOqAAJERkxUAA5sYXRuADwABAAAAAD//wASAAAA"
"AQACAAQABQAGABAAEQASABMAFAAVABYAFwAYABkAGgAbADoACUFaRSAAZENBVCAAkENSVCAAvEtBWiAA6E1PTCABFE5MRCABQFJP"
"TSABbFRBVCABmFRSSyABxAAA//8AEgAAAAEAAwAEAAUABgAQABEAEgATABQAFQAWABcAGAAZABoAGwAA//8AEwAAAAEAAgAEAAUA"
"BgAHABAAEQASABMAFAAVABYAFwAYABkAGgAbAAD//wATAAAAAQACAAQABQAGAAgAEAARABIAEwAUABUAFgAXABgAGQAaABsAAP//"
"ABMAAAABAAIABAAFAAYACQAQABEAEgATABQAFQAWABcAGAAZABoAGwAA//8AEwAAAAEAAgAEAAUABgAKABAAEQASABMAFAAVABYA"
"FwAYABkAGgAbAAD//wATAAAAAQACAAQABQAGAAsAEAARABIAEwAUABUAFgAXABgAGQAaABsAAP//ABMAAAABAAIABAAFAAYADAAQ"
"ABEAEgATABQAFQAWABcAGAAZABoAGwAA//8AEwAAAAEAAgAEAAUABgANABAAEQASABMAFAAVABYAFwAYABkAGgAbAAD//wATAAAA"
"AQACAAQABQAGAA4AEAARABIAEwAUABUAFgAXABgAGQAaABsAAP//ABMAAAABAAIABAAFAAYADwAQABEAEgATABQAFQAWABcAGAAZ"
"ABoAGwAcYWFsdACqY2FzZQCyY2NtcAC4Y2NtcADCZG5vbQDOZnJhYwDUbGlnYQDebG9jbADkbG9jbADqbG9jbADwbG9jbAD2bG9j"
"bAD8bG9jbAECbG9jbAEIbG9jbAEObG9jbAEUbnVtcgEab3JkbgEgcG51bQEoc2FsdAEuc2luZgE0c3MwMQE6c3MwMgFEc3MwMwFO"
"c3MwNAFYc3VicwFic3VwcwFodG51bQFuAAAAAgAAAAEAAAABACQAAAADAAIABQAIAAAABAACAAUACAAIAAAAAQAZAAAAAwAaABsA"
"HAAAAAEAJQAAAAEACQAAAAEAEAAAAAEACgAAAAEACwAAAAEADwAAAAEAEwAAAAEADgAAAAEADAAAAAEADQAAAAEAGAAAAAIAHwAh"
"AAAAAQAiAAAAAQAmAAAAAQAWAAYAAQAnAAABAAAGAAEAKAAAAQEABgABACkAAAECAAYAAQAqAAABAwAAAAEAFQAAAAEAFwAAAAEA"
"IwArAFgC1gP4BHwEfASiBNoE2gT4BVYFVgVWBVYFVgVqBWoFjAXCBdAF5AYaBjQGNAZCBnIGUAZeBnIGgAa+Br4G1gcUBzYHWAdw"
"B4gH1ggaCBoJvAnyCgoAAQAAAAEACAACATwAmwHNAK4ArwCwALEAsgCzALQAtQC2ALcAyADJAMoAywDMANAA0QDSANMA1ABNALsB"
"zgC8AL0AvgC/AMAAgQCHAMEAwgDDAMQAxQDGAMcA1QDWANcBigGLAYwBjQGOAY8BkAGRAZIBkwGUAZUBlgGXAZgBmQGaAZsBnAGd"
"AZ4BnwGgAaEBogGjAaQBpgGnAagBugG7AbwBvQG/Ac4BqwGsAa0BrgHAAcEBwgHDAVoBYAGvAbABsQGyAbMBtAG1AbYBtwG4AbkB"
"xAHFAcwBywHRAdIB0wHUAdUB1gHXAdgB2QHaAfkB+gH7AfwB/QH+Af8CAAIBAgICPQI+Aj8CQAJBAkICRAINAkgCSQJLAlACUQJS"
"AlkCWgJbAlwCXQJeAmsCbAJtAm4CbwJwAqUC0ALRAtICzALNAs4AAQCbAAEABQALAA8AEAAeACkALQAuAC8AOwA/AEAAQQBCAEMA"
"RwBIAEkASgBLAEwAVQBeAGIAZgBnAGwAdwB/AIYAjACNAJIAnwClAKYArQC4ALkAugDZANoA2wDcAN0A3gDfAOAA4QDiAOMA5ADl"
"AOYA5wDoAOkA6gDrAOwA7QD1AQABBAEFAQYBEgEbARwBHQEqASsBLAEtAS8BNwE7AT8BQAFFAVEBUgFTAVQBWAFfAWUBZgFrAXgB"
"ewF8AX0BfgF/AYABhgGHAaoByAHKAe8B8AHxAfIB8wH0AfUB9gH3AfgCAwIEAgUCBgIHAggCCQIKAgsCDAIrAiwCLQIuAi8CMAIy"
"AjgCOgI7AkcCTAJNAk4CUwJUAlUCVgJXAlgCXwJgAmECYgJjAmQCkQKuAq8CvALAAsICwwADAAAAAQAIAAEA7AAVADAANgA8AEIA"
"SABOAFQAWgBmAHIAfgCKAJYAogCuALoAxgDSANgA3gDmAAIAuADNAAIAuQDOAAIAugDPAAIBiQHNAAIBHAGlAAIBJgGpAAIBqgG+"
"AAUB7wH5AgMCFQIfAAUB8AH6AgQCFgIgAAUB8QH7AgUCFwIhAAUB8gH8AgYCGAIiAAUB8wH9AgcCGQIjAAUB9AH+AggCGgIkAAUB"
"9QH/AgkCGwIlAAUB9gIAAgoCHAImAAUB9wIBAgsCHQInAAUB+AICAgwCHgIoAAICOgJDAAICOwJFAAMCPAJGAkcAAgJHAkoAAQAV"
"AEQARQBGANgBFgEkAS4B0QHSAdMB1AHVAdYB1wHYAdkB2gIxAjMCNAI8AAYAAAAEAA4AIABWAGgAAwAAAAEAJgABAD4AAQAAAAMA"
"AwAAAAEAFAACABwALAABAAAABAABAAIBFgEkAAIAAgK7ArwAAAK+AsMAAgACAAECrgK6AAAAAwABAKAAAQCgAAAAAQAAAAMAAwAB"
"ABIAAQCOAAAAAQAAAAQAAgABAAEA1wAAAAEAAAABAAgAAgAQAAUBFwElAswCzQLOAAEABQEWASQCwALCAsMABgAAAAIACgAcAAMA"
"AAABAEIAAQAkAAEAAAAGAAMAAQASAAEAMAAAAAEAAAAHAAEAAwLMAs0CzgABAAAAAQAIAAIADAADAswCzQLOAAEAAwLAAsICwwAE"
"AAAAAQAIAAEATgACAAoALAAEAAoAEAAWABwCyAACArECyQACArACygACArkCywACArcABAAKABAAFgAcAsQAAgKxAsUAAgKwAsYA"
"AgK5AscAAgK3AAEAAgKzArUAAQAAAAEACAABAAYABgABAAEBFgABAAAAAQAIAAIADgAEAIEAhwFaAWAAAQAEAH8AhgFYAV8ABgAA"
"AAEACAABAEoAAQAIAAIABgAWAAEBKgABAAEBKgABAAAAEQABAFEAAQABAFEAAQAAABIAAQAAAAEACAABABQACAABAAAAAQAIAAEA"
"BgATAAEAAQI0AAYAAAABAAgAAQBAAAIACgAcAAEABAABAEEAAQAAAAEAAAAUAAEABAABARgAAQAAAAEAAAAUAAEAAAABAAgAAgAK"
"AAIATQEmAAEAAgBMASQAAQAAAAEACAABAUIARAABAAAAAQAIAAEBNABOAAEAAAABAAgAAQEmACgAAQAAAAEACAABAAb/1QABAAEC"
"OAABAAAAAQAIAAEBBAAyAAYAAAACAAoAIgADAAEAEgABAEIAAAABAAAAHQABAAECDQADAAEAEgABACoAAAABAAAAHgACAAEB+QIC"
"AAAAAQAAAAEACAABAAb/9gACAAECAwIMAAAABgAAAAIACgAkAAMAAQCeAAEAEgAAAAEAAAAgAAEAAgABANgAAwABAIQAAQASAAAA"
"AQAAACAAAQACAF4BNwABAAAAAQAIAAIADgAEAc0BzgHNAc4AAQAEAAEAXgDYATcABAAAAAEACAABABQAAQAIAAEABAKDAAMBNwIr"
"AAEAAQBYAAEAAAABAAgAAQAG/+IAAgABAe8B+AAAAAEAAAABAAgAAQAGAB4AAgABAdEB2gAAAAEAAAABAAgAAgAkAA8COgI7AkcC"
"UAJRAlICWQJaAlsCXAJdAl4CzALNAs4AAQAPAjECMwI8AkwCTQJOAlMCVAJVAlYCVwJYAsACwgLDAAQACAABAAgAAQA2AAEACAAF"
"AAwAFAAcACIAKAHHAAMBDAEWAcgAAwEMASoBxgACAQwByQACARYBygACASoAAQABAQwAAQAAAAEACAACAM4AZACuAK8AsACxALIA"
"swC0ALUAtgC3ALgAuQC6ALsAvAC9AL4AvwDAAMEAwgDDAMQAxQDGAMcBiQGKAYsBjAGNAY4BjwGQAZEBkgGTAZQBlQGWAZcBmAGZ"
"AZoBmwGcAZ0BngGfAaABoQGiAaMBpAGlAaYBpwGoAakBqgGrAawBrQGuAa8BsAGxAbIBswG0AbUBtgG3AbgBuQHEAj0CPgI/AkAC"
"QQJCAkMCRAJFAkYCSAJJAkoCSwJrAmwCbQJuAm8CcAKlAtAC0QLSAAEAZAAFAAsADwAQAB4AKQAtAC4ALwA7AEQARQBGAFUAYgBm"
"AGcAbAB3AIwAjQCSAJ8ApQCmAK0A2ADZANoA2wDcAN0A3gDfAOAA4QDiAOMA5ADlAOYA5wDoAOkA6gDrAOwA7QD1AQABBAEFAQYB"
"EgEWARsBHAEdASQBLgE7AT8BQAFFAWUBZgFrAXgBewF8AX0BfgF/AYABhgGHAisCLAItAi4CLwIwAjECMgIzAjQCOgI7AjwCRwJf"
"AmACYQJiAmMCZAKRAq4CrwK8AAEAAAABAAgAAgAYAAkBugG7AbwBvQG+Ab8BxQHMAcsAAQAJASoBKwEsAS0BLgEvAaoByAHKAAEA"
"AAABAAgAAQAGAG8AAgABAVEBVAAAAAEAAAABAAgAAgAmABAAyADJAMoAywDMAM0AzgDPANAA0QDSANMA1ADVANYA1wACAAIAPwBL"
"AAAAuAC6AA0AAA=="
)
_FONT_HUBOT_BOLD_B64 =(
"AAEAAAANAIAAAwBQR0RFRjusOt8AAKosAAABEEdQT1NlonmsAACrPAAAwlxHU1VCvMXX0wABbZgAAA3yT1MvMkcZZs4AAAFYAAAA"
"YGNtYXDll5scAAANOAAABc5nbHlmTOlhOgAAGMwAAHT0aGVhZBo+W/YAAADcAAAANmhoZWEH8gM5AAABFAAAACRobXR4emFZ3gAA"
"AbgAAAuAbG9jYVvcPdYAABMIAAAFwm1heHAC+AE0AAABOAAAACBuYW1lSTZ0TAAAjcAAAAL8cG9zdMGJqjoAAJC8AAAZcAABAAAA"
"AgAAE/4bel8PPPUAAwPoAAAAANVUmEoAAAAA4iN/y/7v/tcEvgQnAAEABgACAAAAAAAAAAEAAARC/sAAAATW/u/8wgS+AAEAAAAA"
"AAAAAAAAAAAAAALgAAEAAALgAJgADACYAAgAAQAAAAAAAAAAAAAAAAADAAMABAJfArwABgAIAooCWAAAAEsCigJYAAABXgBGARgA"
"AAAAAAAAAAAAAACgAADvUADkewAAAAAAAAAATk9ORQCgACD7AgRC/sAAAARCAUAgAACTAAAAAAIZAtkAAAAgAAMDYQAyAyEAGQMh"
"ABkDIQAZAyEAGQMhABkDIQAZAyEAGQMhABkDIQAZAyEAGQMhABkDIQAZAyEAGQMhABkDIQAZAyEAGQMhABkDIQAZAyEAGQMhABkD"
"IQAZAyEAGQQfABkC0wA4AwcAJAMHACQDBwAkAwcAJAMHACQDBwAkAvoAOAL6ADgC+v/nAvr/5wKSADgCkgA4ApIAOAKSADgCkgA4"
"ApIAOAKSADgCkgA4ApIAOAKSADgCkgA4ApIAOAKSADgCkgA4ApIAOAKSADgCkgA4ApIAOAKBADgDGgAkAxoAJAMaACQDGgAkAxoA"
"JAMaACQDGQA4A1AAHQMZADgCbAAlBCIAJQJsACUCbAAlAmwAJQJsACUCbAAlAmwAJQJsACUCbAAlAmwAJQJsACUCbAAlAbIAHQGy"
"AB0BsgAdAwAAOAMAADgCYgA4AmIAOAJiADgCYgA4Am8AOAKZAB4DvQA4AxUAOAMVADgDFQA4AxUAOAMVADgDJwA4AyQAJAMkACQD"
"JAAkAyQAJAMkACQDJAAkAyQAJAMkACQDJAAkAyQAJAMkACQDJAAkAyQAJAMkACQDJAAkAyQAJAMkACQDJAAkAyQAJAMkACQDJgAl"
"AyQAJARtACQCuwA4ApkAOAMkACQC5wA4AucAOALnADgC5wA4ArMAHwKzAB8CswAfArMAHwKzAB8CswAfAu0AOAK7AB0CuwAdArsA"
"HQK7AB0CuwAdAvkALwL5AC8C+QAvAvkALwL5AC8C+QAvAvkALwL5AC8C+QAvAvkALwL5AC8C+QAvAvkALwL5AC8C+QAvAvkALwL5"
"AC8C+QAvAvkALwMhABkEIQAaBCEAGgQhABoEIQAaBCEAGgMvABgC/gARAv4AEQL+ABEC/gARAv4AEQL+ABEC/gARAv4AEQKzACAC"
"swAgArMAIAKzACADIQAZAyEAGQMhABkDIQAZAwcAJAKSADgCkgA4ApIAOAKSADgDGgAkAmwAJQJsACUCbAAlAm8AOAMkACQDJAAk"
"AyQAJAMkACQDJAAkAvkALwL5AC8C+QAvBCEAGgL+ABEC/gARArMAIAEcADgCyAA4ARwAOAEc/9gBHP+1ARz/3wEcADgBHAA4ARz/"
"2gEcADEBHP/AARwAJAEc/9wBHP/KARwALQEcADQChAAdAoQAHQKEAB0ChAAdAoQAHQKEAB0ChAAdAoQAHQKEAB0ChAAdAoQAHQKE"
"AB0ChAAdAoQAHQKEAB0ChAAdAoQAHQKEAB0ChAAdAoQAHQKEAB0ChAAdA6cAGQKEAC4CZgAcAmYAHAJmABwCZgAcAmYAHAJmABwC"
"hAAdAx8AHQKEAB0CYwAbAm8AHAJvABwCbwAcAm8AHAJvABwCbwAcAm8AHAJvABwCbwAcAm8AHAJvABwCbwAcAm8AHAJvABwCbwAc"
"Am8AHAJvABwCbwAcAZgAFgJ5AB8CeQAfAnkAHwJ5AB8CeQAfAnkAHwJ8AC4CfP/sAnz/pwECAC4BAgAuAQIALgEC/8oBAv+nAQL/"
"0QECAC4BAgAsAQL/zAECACMBAv+yAQIAEwEC/84CAwAuAQL/0QEC/9EBAv/RAQL/pwKJAC4CiQAuAQIALgECAC4BAgAuAQIAJQHH"
"AC4BPAAXA+4ALgJ8AC4CfAAuAnwALgJ8AC4CfAAuAnwALgJ6ABwCegAcAnoAHAJ6ABwCegAcAnoAHAJ6ABwCegAcAnoAHAJ6ABwC"
"egAcAnoAHAJyABwCcgAcAnIAHAJyABwCcgAcAnIAHAJ6ABwCegAcAnEAHAJ6ABwEBwAcAoQALgKEAC4ChAAdAY8ALgGPAC4Bj//l"
"AY8AJAI1ABUCNQAVAjUAFQI1ABUCNQAVAjUAFQKvABYBmwAWAaoAHgGbABYBmwAWAZsAFgJ8ACgCfAAoAnwAKAJ8ACgCfAAoAnwA"
"KAJ8ACgCfAAoAqMAKAKjACgCowAoAqMAKAKjACgCowAoAnwAKAJ8ACgCfAAoAnwAKAJ8ACgCggAQA3QAEgN0ABIDdAASA3QAEgN0"
"ABIClQAQAn0AEAJ9ABACfQAQAn0AEAJ9ABACfQAQAn0AEAJ9ABACHAAZAhwAGQIcABkCHAAZAQIALAECABMCYwAiAmMAIgJjACIC"
"YwAiAmMAIgJjACICYwAiAmMAIgJjACICYwAiAmMAIgJjACICYwAiAmMAIgJjACICYwAiAmMAIgJjACICYwAiAmMAIgJjACICYwAi"
"AmYAHAJvABwCbwAcAm8AHAJvABwCeQAfAQIAHwEC/7wBAgAfAQIAHwEC/9EB0wAuAnoAHAJ6ABwCegAcAnIAHAJ8ACgCfAAoAqMA"
"KAN0ABIChgAQAoYAEAKGABAChgAQAoYAEAKGABACHAAZATcALgE3ACEBNwAuATcALgHVAC4BVgAYAXwALgF8AC4BfAAPAXwAIwEC"
"ACYB3AAuAvAAFgO1ABYD8AAWAl8AFgKbABYC0AAWBCgAFgF3ABEBfAARAn4AKAKIABYCuAAmAaUAHgJ5AB8CfQAeArYAHgKFACAC"
"nwAnAnoAIwKXACACnwAjAysAJgMrACYDKwAmAysAJgMrACYDKwAmAysAJgMrACYDKwAmAysAJgMrACYDKwAmAysAJgMrACYDKwAm"
"AysAJgMrACYDKwAmAysAJgMrACYChwAeAocAPAKHACYChwAkAocAFAKHACUChwAlAocAHgKHAB0ChwAhAZsAHwETABcBdAAZAXYA"
"GQGMABgBfwAgAYsAIAF3ABsBiAAbAYsAHgGbAB8BEwAXAXQAGQF2ABkBjAAYAX8AIAGLACABdwAbAYgAGwGLAB4Ap/81AxUAFwMB"
"ABcDVgAZAykAFwN/ABkDhAAgA0MAGwHDAB8BJAAXAZcAGQGZABgBtAAXAaIAHgGxACABmwAbAasAGgGxAB0BwwAfASQAFwGXABkB"
"mQAYAbQAFwGiAB4BsQAgAZsAGwGrABoBsQAdALAAAACwAAAA7AAhAO0AEQDsACEA7AARAsIAIQD0AC4A9AAuAiEAFQIhAB8A7AAh"
"AR4AEAEyAAsCswAbAeUAAgHkABsA9AAuAiEAHwDGAA0A/gAbAPMAFQD+ABsA+AAVAuUAGwD0ABcA9AAXAigAHAIoAB4A/gAbAA3/"
"CAD0ABcCKAAeANUACwAN/u8BgQAhAg4AIQLEACEBfwAAAYEAIQIOACECxAAhAVkAIQFZABUBqAAcAagAIAFsADgBbAAhAVAAIQFN"
"ABUBpAAcAaMAHwFwADcBbwAgAO0AEQHPABEBzwAhAc8AEQDtACEA7QARAl8AHQJfACEBWwAdAVsAIQGYAB0AwwAdAPMAFQHiABUB"
"4gAXAeIAFQDzABcA8wAVAk8AFwM+ACEDPgAhAz4AMwNhADIDXQAdAv0AIwMWAA8B/gAhAyEAIQJRACcDIQAhAwgAFgGPAB0BOABU"
"ATgAVAIiAB4DVQBaBNMAOALcAD0CcwAmArQAPAK8ACMDUgAtAscAKQKNACwDFAA8ArUAJwMVABUChwBUAocAUgKHAE0ChwBJAocA"
"SAKHAEgChwBEAocARgKHACkChwBAAocATgKHAFwChwBDAn0AXAKHAFYDkQAbAv4AFwHSABMCmQAuAkgAGwKcABQDVQAYBNYAGAKH"
"AD8CKQA1AqEAOwIpADUCoQAwAycAMQMrACYDKwAmAtoAMgAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACYA"
"AAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgAAAAqAAAAKAAAACgAAAAo"
"AAAAKQAAACgAAAAoAAAAKAAAACgAAAAoAAAAKAAAACgBsQAoAPUAKAFUACgBVAAoAg4AKAICACgCAgAoAb0AKAFEACgBtgAmAewA"
"KAFrACgBFwAoAAAAAgAAAAMAAAAUAAMAAQAAABQABAW6AAAAjACAAAYADAAvADkAfgCsALQBNwFIAU0BfgGSAaEBsAHnAhsCNwLH"
"At0DBAMMAxIDGwMjAygDOAO8A8AehR6eHvkgFCAaIB4gIiAmIDAgOiBEIHAgeSCJIKogrCC6IL8hEyEXISIhLiFeIZQiBSIPIhIi"
"GiIeIisiSCJgImUkaCTqJP8lzCXPJjonEyd++P/7Av//AAAAIAAwADoAoACuALYBOQFKAVABkgGgAa8B5gIYAjcCxgLYAwADBgMS"
"AxsDIwMmAzUDvAPAHoAenh6gIBMgGCAcICIgJiAwIDkgRCBwIHQggCCqIKwguSC/IRMhFiEiIS4hWyGQIgUiDyIRIhoiHiIrIkgi"
"YCJkJGAk6iT/JcslzyY5JxMndvj/+wH//wAAAaEAAAAAAAAAAAAAAAAAAADfAAAAAAAAAAD+7gASAAAAAAAA/6j/oP+Z/5f/i/4T"
"/hAAAOHkAADiOgAAAADiE+IJ4nTiLuHJ4a/hr+GV4eHh3AAA4cXhbgAA4VvhVOC2AADgmeCRAADgiOB/4HTgUeAzAADdhtz73Nzc"
"4dzc3DnbYdpmCXYGyAABAIwAAACoATABSAFUAlYCdAJ6AAAC1ALWAtgC2gAAAAAC3ALmAu4AAAAAAAAAAAAAAAAAAALsAAAC9AAA"
"A6QDqAAAAAAAAAAAAAAAAAAAAAAAAAAAA5gAAAAAA5YAAAAAAAADkgAAAAADlgAAAAAAAAAAAAADjgAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAACKQIwAmkCNwKHAqMCdwJqAlMCVAI2Ao4CLAJMAisCOAItAi4ClQKSApQCMgJ2AAEAGAAZAB8AIwA1ADYAPAA/AEwATwBR"
"AFcAWABeAHUAdwB4AHwAgwCIAJsAnAChAKIAqgJXAjkCWAKcAk8C1QDYAO8A8AD2APoBDAENARMBFgEkASgBKgEwATEBNwFOAVAB"
"UQFVAVwBYQF0AXUBegF7AYMCVQJ/AlYCmwIqAjEChQKMAoYCjQKAAnkC0wJ6Ac0CZQKaAnsC3QJ+ApgCIQIiAtYCeAI0At4CIAHO"
"AmYCDwIOAhACMwARAAIACQAWAA8AFQAXABwAMAAkACcALQBHAEEAQwBEACIAXABoAF8AYABzAGYCkAByAI4AiQCLAIwAowB2AVsA"
"6ADZAOAA7QDmAOwA7gDzAQcA+wD+AQQBHgEYARoBGwD5ATUBQQE4ATkBTAE/ApEBSwFnAWIBZAFlAXwBTwF+ABMA6gADANoAFADr"
"ABoA8QAdAPQAHgD1ABsA8gAgAPcAIQD4ADIBCQAlAPwALgEFADMBCgAmAP0AOQEQADcBDgA7ARIAOgERAD4BFQA9ARQASwEiAEkB"
"IABCARkASgEhAEUBFwBAASMATgEnAFABKQBSASsAVAEtAFMBLABVAS4AVgEvAFkBMgBbATQAWgEzAF0BNgBxAUoAcAFJAHQBTQB5"
"AVIAewFUAHoBUwB9AVYAgAFZAH8BWAB+AVcAhgFfAIUBXgCEAV0AmgFzAJcBcACKAWMAmQFyAJYBbwCYAXEAngF3AKQBfQClAKsB"
"hACtAYYArAGFAGoBQwCQAWkAOAEPAIEBWgCHAWAC2gLUAtsC3wLcAtcCsAKxArMCtwK4ArUCrwKuArkCtgKyArQAoAF5AJ0BdgCf"
"AXgAEADnABIA6QAKAOEADADjAA0A5AAOAOUACwDiAAQA2wAGAN0ABwDeAAgA3wAFANwALwEGADEBCAA0AQsAKAD/ACoBAQArAQIA"
"LAEDACkBAABIAR8ARgEdAGcBQABpAUIAYQE6AGMBPABkAT0AZQE+AGIBOwBrAUQAbQFGAG4BRwBvAUgAbAFFAI0BZgCPAWgAkQFq"
"AJMBbACUAW0AlQFuAJIBawCnAYAApgF/AKgBgQCpAYICYwJkAl8CYQJiAmACigKJAoMCfAKpAqYCpwKoAqoCoQKPApcClgAAAAAA"
"2gD1AQEBDQEZASkBNQFBAU0BWQFlAXUBgQGNAZkBpQGxAb0ByQHVAeEB7QH5Ah8CVAKBAo0CmQKlArECvQLfAusC8wL+AxQDIAMs"
"AzgDRANQA2ADbAN4A4QDkAOcA6gDtAPAA8wD2APkA/gELwQ7BEcEUwRfBGsEggSOBJoErwS7BMcE0wTfBOsE9wUDBQ8FGwUnBTMF"
"PwVRBV0FaQWDBY8FngWqBcEFzQXZBeQGCAYjBi8GOwZHBlMGdwanBrMGvwbLBtsG5wbzBv8HCwcXByMHLwc7B0cHUwdfB2sHdweD"
"B48HmgemB9EH8ggWCE8IdgiCCI4ImgjYCOQI8Aj8CQgJFAk7CUwJVwljCW8JewmcCagJtAnACcwJ2AnkCfAJ/AoIChQKIAosCjgK"
"RApQClwKaAp0CooKsQq9CskK1QrhCv0LFgsiCy4LOgtGC1ILXgtqC4ALjAuYC6QLtAvEC9AL3AvoC/gMBAwQDBwMKAw0DEAMTAxY"
"DGgMdAyADIwMxwzTDN8M6wz3DQMNDw0bDScNMw0/DUsNVw1jDW8Neg2GDZINng2pDbUNwQ3NDdgODg4aDiUOMA4/DkoOVQ5gDmsO"
"dg6FDpAOmw6mDrEOvQ7IDtQO3w7rDvcPAg9iD5gPxw/TD94P6Q/0EAAQNhB0EIAQyRD/EQsRFhEhESwRNxFGEVERXBFnEXIRfhGK"
"EZURoRGsEbgRwxHcEiESLBI3EkISThJaEngSgxKPEpoSphKxErwSyBLTEt4S6RL0Ev8TChMYEyMTLxM6E0wTVxNjE3oThhOSE54T"
"sRO8E8gT0xQMFCoUNhRBFE0UWBR/FK8UuxTGFNEU4BTrFPYVARUMFRgVIxUvFTsVRxVTFV4VahV1FYAVixWWFaEVrRXhFhUWSxZl"
"FnAWexaGFsYW0hbdFugW8xb/FzkXUxd0F5YXoResF7YXwhfNF9gX4xfvF/oYBhgSGB4YKhg1GEEYTBhXGGIYbhh6GIUYmhjBGM0Y"
"2RjlGPEZChkoGTQZPxlKGVYZYRltGXgZjhmaGaUZsRm8GccaABoMGhcaIhoxGjwaRxpSGl0aaBp3GoIajRqYGqMarxq6GsYa0Rrd"
"Guka9BsAGw8bGhsmGzIbPhtJG1QbXxtqG3UbgRuQG5sbpxuzG74byhvWG+Ib+hwGHBEcHBwoHDMcPxxRHF0cdhyBHI0cmBypHLQc"
"vxzKHNUc4R0JHTUdYB1+HZsdvR3uHiYeUB5zHo4evx7PHv0fPB9XH4kfyR/dICkgMyA/IEsgVyBjIG8geyCHIJMgnyCsILggxCDQ"
"INwg6CD0IQAhDCEYISUhVSFqIZgh1yHyIiQiYSJ1IsEiyyLuIv4jJiNhI3ojpyPcI/AkOCRCJEskVCRdJGYkbyR4JIEkiiSTJJwk"
"qSS5JMkk2STpJPklCSUZJT8lUCV7Jbgl0iYCJj0mUSaZJqMmrCa1Jr4mxybQJtkm4ibrJvQm/Sb9Jv0nCCcXJyMnLyc/J1QnXieM"
"J5Ynnye1J+coECgdKCsoNSg/KEsoYSh7KIcokyijKMIozCkEKQ4pFykjKS0pNylNKWMpcCl9KYoplimeKaYprinMKdYqAioMKh0q"
"JypFKk8qeyqFKpYqoCqoKrQqvirHKtEq2irmKvAq/ysJKxUrJCssKzgrQitMK1YrXyuCK+MsTixhLGks0C0pLUQtoC35LkYuky68"
"LuIu7i8BLz8vdC+4L/8wMjB1MLsw+TEjMUwxcTGdMcYx2jHnMgAyGTItMkwyYDJqMoQynjK5MwMzEzM7M0wzmTPZM/E0AzQfNDQ0"
"ijUENTE1RDVRNVs1ZTV/NZ010zaVNqc2szbANs024DbxNwI3HDdAN2Y3czeTN6M3tzfDN9M3+TgZOCY4MzhBOE44bTiMOL449DkL"
"OSI5Szl4OYU5kzmgOcA55jn8OhI6GjoiOio6Mjo6OkI6SjpSOlo6YjpqOnI6egAAAAgAMv/1Ay8C4gBXAGAAaQBzAHsAgwCOAJcA"
"AAEiDgIVFBYWFxY2NTUGLgIxJiYxJjY2MR4CMRYWNjc2NjcuAzU0NjcmJjcwNhYXNjYzMhYXNjYWMRYGBxYWFRQOAgcWFhUVFBY3"
"PgI1NC4CATQjJgYVBhcWFzYnJgcGFxYWFzYnJgcGFBcWFhc2JyYHBhcWFzQnJgcUFxY3NCYHIgYXFDM2Ngc0IyIVFBYzNgGwT4tp"
"O0N2TQsOKDMcCwwcEQMPExsOECsoCgMPCCA/Mh4VEwMJEBYuJBgwGBkwGCUtFhEKAxMVHjI/IAoQDwxMdUM7aYv+xAUCBAEEBw4C"
"AgQFAwUCBBMCAgYFAQECBxUDBQUFAwYEIQUIAgUIPgUDBAQBCAMGHwcHBAMHAuI7aYtPVZNrGQMKC0YICxcUIhYMCgIBFRMdDggE"
"EhsHBBMpRzceNBMINigBDxoIBgYIGg8BKDYIEzQeOEcpEgQIJRppCwoDGWuTVU+LaTv92wMDAQICAwIOAQcEAwMFAQIVAwcGAwEH"
"AgICFAMHBQMEBgcHBgIDBgUDAggCAwEFAgQBBAIEBAIHBAACABkAAAMIAtkABwANAAAzMzchFzMBIxc3MxcXIxmtMgEuMrD+/utc"
"EwkUU9aTkwLZ1VdX8v//ABkAAAMIA5kCJgABAAAABwKxARkAwP//ABkAAAMIA5cCJgABAAAABwK1ALIAwP//ABkAAAMIBA8CJgAB"
"AAAABwLEALYAwP//ABn/WQMIA5cCJgABAAAAJwK8ARQAAAAHArUAsgDA//8AGQAAAwgEDwImAAEAAAAHAsUAtwDA//8AGQAAAwgE"
"JwImAAEAAAAHAsYAtgDA//8AGQAAAwgEFQImAAEAAAAHAscAswDA//8AGQAAAwgDlwImAAEAAAAHArMAjwDA//8AGQAAAwgEFAIm"
"AAEAAAAHAsgAmgDA//8AGf9ZAwgDlwImAAEAAAAnArwBFAAAAAcCswCPAMD//wAZAAADCAQUAiYAAQAAAAcCyQCaAMD//wAZAAAD"
"CAQZAiYAAQAAAAcCygCaAMD//wAZAAADCAQVAiYAAQAAAAcCywCbAMD//wAZAAADCAOaAiYAAQAAAAcCrgC5AMD//wAZ/1kDCALZ"
"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"
"AsoAmwDA//8AJP/1AwAEFQImAF4AAAAHAssAnADA//8AJP/1AwADmgImAF4AAAAHAq4AuQDA//8AJP9ZAwAC4wImAF4AAAAHArwB"
"FAAA//8AJP/1AwADmQImAF4AAAAHArAAtADA//8AJP/1AwAD+wImAF4AAAAHArkBCwDA//8AJP/1AwEDLwImAF4AAAAHArsCAwCh"
"//8AJP/1AwEDmQImAGoAAAAHArEBGgDA//8AJP9ZAwEDLwImAGoAAAAHArwBFAAA//8AJP/1AwEDmQImAGoAAAAHArAAtADA//8A"
"JP/1AwED+wImAGoAAAAHArkBCwDA//8AJP/1AwEDsgImAGoAAAAHArcAuQDA//8AJP/1AwADmQImAF4AAAAHArIAxADA//8AJP/1"
"AwADkgImAF4AAAAHArgAmgDA//8AJf/oAwEC8gAmAF4BAAAGAs5B/P//ACT/9QMAA7ICJgBeAAAABwK3ALkAwAACACQAAARJAtkA"
"EQAbAAAhITUhNSE1ITUhNSEiBhUVFBY3IiY1NTQ2MzMRAZICt/53ARH+7wGH/UuyvL20W15fWn6JqoCeiKeZWJqniVhRdlJX/jgA"
"AAIAOAAAAp0C2QAKABQAADMzNTMyNjU0JiMhBTIWFRUUBiMjNTitrXmSjX3+pQFJMDY0Mpz7e3RyfYkuLB0oMdAAAAIAOAAAAnoC"
"2QANABcAADMzNTMyNjY1NCYjIzUjATIWFRUUBiMjNTixhlB4Q5J+gbEBJDA3NDNzgDRpUXR4f/79LCsoKC/WAAIAJP9VAwAC4wAZ"
"ACcAAAUzNSM1PgI1NTQmJiMiBgYVFRQWFhcVFBYTIiY1NTQ2MzIWFRUUBgGo8LlYgkdcpW5tpVtHgVgzGlVlZVVWZWSrbzcNVYdX"
"Y2SRUFCRZGNXh1UNTykuASlWRqVFV1dFpUZWAAIAOAAAAs4C2QANABcAADMzETMTMwM2Nic0JiMhBTIWFRUUBiMjNTitaq7Ryk5g"
"AX56/n8BYS0yMC+0AQr+9gEqDW1WZXqGKycgJizE//8AOAAAAs4DmQImAHgAAAAHArEA8wDA//8AOAAAAs4DlwImAHgAAAAHArQA"
"aADA//8AOP7XAs4C2QImAHgAAAAHAr0A5gAAAAEAH//2ApMC4gApAAAFMjY1NCYmJycmJjU0NjMyFhczJiYjIgYGFRQWFxcWFhUU"
"BiMiJicjFhYBW5CoN2JCdDIzOjs7RgipCpuLWoZKa2GBMjRFO0JPBaoInQpxaEJWNBAaDikiISouNGhzNGJEUl8XIAwrJykoNDtt"
"ff//AB//9gKTA5kCJgB8AAAABwKxAOEAwP//AB//9gKTA5cCJgB8AAAABwK0AFcAwP//AB//FAKTAuICJgB8AAAABwK+AKQAAP//"
"AB//9gKTA5cCJgB8AAAABwKzAFcAwP//AB/+1wKTAuICJgB8AAAABwK9ANQAAAABADgAAALPAtkAGgAAMzMRIQcVMzIWFRUUBiMj"
"FTMyNjU0Jic1NzUhOLABCYVHLDUzM4GgdI5fVoH9nQJPsFsnKR8kLYRnbFVpBQerkQABAB0AAAKeAtkABwAAITMRMzUhFTMBCK3p"
"/X/rAlCJiQD//wAdAAACngLZAiYAgwAAAAYCzGxV//8AHQAAAp4DlwImAIMAAAAHArQAXADA//8AHf8UAp4C2QImAIMAAAAHAr4A"
"qQAA//8AHf7XAp4C2QImAIMAAAAHAr0A2QAAAAEAL//2AsoC2QATAAAFMjY2NREjERQGIyImNREjERQWFgF8ZZZTrlBQT1GtU5YK"
"QYBcAcb+LT5JST4B0/46XIBB//8AL//2AsoDmQImAIgAAAAHArEBBgDA//8AL//2AsoDlwImAIgAAAAHArUAngDA//8AL//2AsoD"
"lwImAIgAAAAHArMAewDA//8AL//2AsoDmgImAIgAAAAHAq4ApQDA//8AL/9ZAsoC2QImAIgAAAAHArwBAAAA//8AL//2AsoDmQIm"
"AIgAAAAHArAAoADA//8AL//2AsoD+wImAIgAAAAHArkA9wDA//8AL//2AzMDQwImAIgAAAAHArsCNQC1//8AL//2AzMDmQImAJAA"
"AAAHArEBBgDA//8AL/9ZAzMDQwImAJAAAAAHArwBAAAA//8AL//2AzMDmQImAJAAAAAHArAAoADA//8AL//2AzMD+wImAJAAAAAH"
"ArkA9wDA//8AL//2AzMDsgImAJAAAAAHArcApADA//8AL//2AsoDmQImAIgAAAAHArIAsADA//8AL//2AsoDkgImAIgAAAAHArgA"
"hgDA//8AL/86AsoC2QImAIgAAAAHAr8BDwAJ//8AL//2AsoD8AImAIgAAAAHArYA2wDA//8AL//2AsoDsgImAIgAAAAHArcApADA"
"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"
"GxkfJSVMXwD//wAV//YCHALZAiYBVQAAAAcCsQCiAAD//wAV//YCHALXAiYBVQAAAAYCtBcA//8AFf8UAhwCIwImAVUAAAAGAr5k"
"AP//ABX/9gIcAtcCJgFVAAAABgKzFwD//wAV/tcCHAIjAiYBVQAAAAcCvQCUAAAAAQAWAAAClwLiACsAADMzETQzMhYVFAYjIxUz"
"MhYVFRQGIyMVMzI2NTQmJzU2NjU0JiMiBgYHIxUzeZ9jKzMwMhsxLjw4OjdQd4JORC83fnFDcEcHZWMB7XAsLSgxYiovGic0e3Fg"
"SmQKBw9NOVZnLFlEeQABABYAAAF9AqsAEAAAMzM1IxEzNSM1IxUjFTMRFBbXpmtoaKVXVzmAASB5kpJ5/sIzLwAAAQAeAAABhQKr"
"ABgAADczFRQWMzM1IzUzNSM1MzUjNSMVIxUzFSMeVzkxpmtoaGhopVdXV9t5My+AW3NSeZKSeVIAAgAWAAAB3gLZAAMAFAAAATM3"
"IwMzNSMRMzUjNSMVIxUzERQWATN+LYh/pmtoaKVXVzkCQZj9J4ABIHmSknn+wjMvAP//ABb/FAGOAqsCJgFcAAAABgK+SwD//wAW"
"/tcBfQKrAiYBXAAAAAYCvXwA//8AKP/3Ak4CGQAPATECfAIZwAD//wAo//cCTgLZAiYBYQAAAAcCsQDKAAD//wAo//cCTgLXAiYB"
"YQAAAAYCtWMA//8AKP/3Ak4C1wImAWEAAAAGArNAAP//ACj/9wJOAtoCJgFhAAAABgKuagD//wAo/1kCTgIZAiYBYQAAAAcCvADF"
"AAD//wAo//cCTgLZAiYBYQAAAAYCsGQA//8AKP/3Ak4DOwImAWEAAAAHArkAvAAA//8AKP/3AqQCgwAmAWEAAAAHArsBpv/1//8A"
"KP/3AqQC2QImAWkAAAAHArEAygAA//8AKP9ZAqQCgwImAWkAAAAHArwAxQAA//8AKP/3AqQC2QImAWkAAAAGArBkAP//ACj/9wKk"
"AzsCJgFpAAAABwK5ALwAAP//ACj/9wKkAvICJgFpAAAABgK3aQD//wAo//cCWgLZAiYBYQAAAAYCsnQA//8AKP/3Ak4C0gImAWEA"
"AAAGArhLAP//ACj/MQJTAhkCJgFhAAAABwK/AWUAAP//ACj/9wJOAzACJgFhAAAABwK2AJ8AAP//ACj/9wJOAvICJgFhAAAABgK3"
"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"
"AnwC5AAfACwAAAUyNjY1NCYjIgYHIzY2NTQ2MzIWFzMmJiMiBgYVFRQWNyImNTU2MzIWFRUUBgFPWYhMeXA9ZR8JAgFLRzJCBp0J"
"jX9fjU2TljpJMV01P0ILOHJVdHgsKREmEkpLKidbcUWLaIyOnYY8QDJIMzIpMDgAAQAjAAACXALZAAkAADMzATUhETM1IRWBvQEe"
"/ceAAQUCTYz+/X0PAAMAIP/1AncC5AAZACcANQAABTI2NTQmJzU2NjU0JiMiBhUUFhcVBgYVFBYTIiY1NTQ2MzIWFRUUBgMiJjU1"
"NDYzMhYVFRQGAUuTmVdBPkaXgYGXRj5BVpmSOTo9Njc8ODs7RD9BPz5DC25gTVoPBw5UPWJjZGE9VA4HEFpMYG4Bti8jFyYrKyYX"
"Iy/+yS8pGSczMycZKS///wAj//UCeALkAA8B1wKfAtnAAP//ACb/4gMFAvcCJgKrAAAABwH5AMkApP//ACb/4gMFAvcCJgKrAAAA"
"BwH6AQAApP//ACb/4gMFAvcCJgKrAAAABwH7ANkApP//ACb/4gMFAvcCJgKrAAAABwH8ANwApP//ACb/4gMFAvcCJgKrAAAABwH9"
"ANQApP//ACb/4gMFAvcCJgKrAAAABwH+ANQApP//ACb/4gMFAvcCJgKrAAAABwH/AM8ApP//ACb/4gMFAvcCJgKrAAAABwIAANoA"
"pP//ACb/4gMFAvcCJgKrAAAABwIBANIApP//ACb/4gMFAvcCJgKrAAAADwH/Al0CNsAA//8AJv/iAwUC9wImAqwAAAAHAfkAyQCk"
"//8AJv/iAwUC9wImAqwAAAAHAfoBAACk//8AJv/iAwUC9wImAqwAAAAHAfsA2QCk//8AJv/iAwUC9wImAqwAAAAHAfwA3ACk//8A"
"Jv/iAwUC9wImAqwAAAAHAf0A1ACk//8AJv/iAwUC9wImAqwAAAAHAf4A1ACk//8AJv/iAwUC9wImAqwAAAAHAf8AzwCk//8AJv/i"
"AwUC9wImAqwAAAAHAgAA2gCk//8AJv/iAwUC9wImAqwAAAAHAgEA0gCk//8AJv/iAwUC9wImAqwAAAAPAf8CXQI2wAAAAwAe//UC"
"aQLkAA0AFgAfAAAFMjY1NTQmIyIGFRUUFhM0NjMyFhUVIxMiJjU1MxUUBgFDh5+ajIafmg1BPT5A/H49QfxAC6amWKGqpqVYoasB"
"2kRJSUQs/tpKQywsQ0oAAQA8AAACSwLZAAsAADMhNSMRIwcjFTMRIzwCD62HFaeiwYYCU3GH/qUAAQAmAAACXgLjAB0AADMhNSEH"
"NTc3NjY1NCYmIyIGBzM2NjMyFhUVFAYHBTECLf7cIRGLU0pAdlOBmwehAzo6LzsmKv7ZhgMGDHQ/c0lDZDiGdDc+MSwQHDwk+QAB"
"ACT/9QJhAuQALAAABTI2NjU0Jic1NjY1NCYjIgYGBzM2NjMyFhUVFAYjIxUzMhYVFRQGIyInIxYWATlXhUxUPzlIj3dXfkYCmgM9"
"Ny88OzI8Qy5GQzh0BZ4CjgsyYERMVwoID1Q+XGc5Z0YwNSgoFSMtcSYvGigvZm17AAABABQAAAJzAtkADwAANyEVMzUzNSM1Iwcj"
"NRMjAxQBUqZnZ4YXouSo9Z6enoeVlQgBrP4yAAABACX/9QJiAtkAIAAABTI2NTQmIyIGByM3ITUhAxc2NjMyFhUVFAYjIiYnIxYW"
"AT2Gn3lyLlEbCw8BYv4JGpQSPy0xQ0M7Nj4EnQWRC4J8bn4bHa2F/lgFHyQyNioxNDErZXoAAgAl//UCZgLkAB0AKgAABTI2NjU0"
"JiMiBgcjNjY1NDMyFhczJiYjIgYVFRQWNyImNTU2MzIWFRUUBgFDV4NJdWs6YR0KAgGKLz4HmgmJeoqkjZM3Ri5YMjs+CzlxVHF8"
"KyoRJhKVKShccJycjI6dhjxAMkgzMikvOQABAB4AAAJuAtkACQAAMzMBNSERMzUhFYi9ASn9sIEBGgJNjP79fQ8AAwAd//UCagLk"
"ABkAJwA1AAAFMjY1NCYnNTY2NTQmIyIGFRQWFxUGBhUUFhMiJjU1NDYzMhYVFRQGAyImNTU0NjMyFhUVFAYBRJCWVUA+RJV+f5VF"
"PUBVlpE4OT00NTs4ODpDPj8+PUILbmBNWg8HDlQ9YmNkYT1UDgcQWkxgbgG2LyMXJioqJhcjL/7KLikZJzMzJxkpLv//ACH/9QJi"
"AuQADwH1AocC2cAAAAIAH//5AXwBmAANABcAABcyNjU1NCYjIgYVFRQWNyI1NTQzMhUVFMxRX1tVUF1aUzU1OQdcXS1aX11cLVhh"
"XT9nPz9nPwABABcAAADlAZEABwAAMzMRIwcjFTNteGIRW1YBkUFbAAEAGQAAAVUBlwAaAAAzITUjBzU3NzY2NTQmIyIGBzM0MzIW"
"FRUUBwcjATKFDggyLClORklYA3IqERYil1sBAgcqIj8pOUdNQS8TEwcZHYAAAQAZ//kBWgGYACsAABcyNjU0Jic1NjY1NCYjIgYV"
"MzY2MzIWFRUUBiMjFTMyFhUVFAYjIiY1IxQWtEheLR4dJE1FSVdsARUUEhYZFSEmEh0ZFBgVb08HPzkpLgcECS4gMjxGOxIXEREI"
"EBRMERQKEBYYEzxHAAEAGAAAAXUBkQAPAAA3MxUzNTM1IzUjByM1NyMHGLV2MjJZET1udX1QUFBcUFAG3/kAAQAg//kBZAGRAB0A"
"ABcyNjU0JiMiBgcHNzM1IQcXNjMyFhUVFCMiJyMWFr5LW0M8FScMBgew/ucQaA0lERwwKwJvAlAHSkQ9RQ0MAUdb8AIeFhcRLSQ3"
"RgAAAgAg//oBbQGXABoAJQAAFzI2NTQmIyIHIzY1NDMyFhczJiYjIgYVFRQWNyI1NTYzMhUVFAbETVxAOj4dBwM6FRkCbgRSR1Fe"
"T1YxECQtGQZHRj5EJhEWORIONT9XUkxOWlwzGhoqERQYAAEAGwAAAV8BkQAJAAAzEzUhFTM1MxUD1on+vFltkAEyX5xACf7UAAAD"
"ABv/+QFtAZgAGQAmADMAABcyNjU0Jic1NjY1NCYjIgYVFBYXFQYGFRQWNyImNTU0MzIWFRUUBgciJjU1NDYzMhYVFRTEU1YtIiAj"
"VElJVCMfIixWUxYXLRUXFxUWGxkYFxkHPzQpMQoFCCwgNTo6NSAsCAUKMig0P/IUEAkjExAJEBSUFBIKERUVEQomAP//AB7/+QFr"
"AZYADwH/AYsBkMAA//8AHwFBAXwC4AIHAfkAAAFI//8AFwFIAOUC2QIHAfoAAAFI//8AGQFIAVUC3wIHAfsAAAFI//8AGQFBAVoC"
"4AIHAfwAAAFI//8AGAFIAXUC2QIHAf0AAAFI//8AIAFBAWQC2QIHAf4AAAFI//8AIAFCAW0C3wIHAf8AAAFI//8AGwFIAV8C2QIH"
"AgAAAAFI//8AGwFBAW0C4AIHAgEAAAFI//8AHgFBAWsC3gIHAgIAAAFIAAH/Nf/SAXIDAAADAAAHMwEjy2IB22MuAy7//wAX/9IC"
"9wMAACYCBAAAACcCDQEOAAAABwH7AaIAAP//ABf/0gLpAwAAJgIEAAAAJwINAQ4AAAAHAf0BdAAA//8AGf/SAz8DAAAmAgYAAAAn"
"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"
"KiozKiozKsMgKiogEjJAQDIAAAUAIf/2Ax0C4wATACMALQA3AE8AAAUyPgI1NC4CIyIOAhUUHgI3IiYmNTQ2NjMyFhYVFAYGAzI1"
"NTQjIhUVFDMyNTU0IyIVFRQDMjY2NzM1IxUzBgYjIiYnMzUjFTMeAgGgU4tmOTlmi1NTjGc5OWeMU12PUFCPXV2OUFCOsCYmJckl"
"JSUtPmVCCRt6Ig1gREReDiR9HApBZAo2ZItUUohkNjZkiFJUi2Q2P0+NXl2LTU2LXV6NTwFSKjMqKjMqKjMqKjMq/vAuUTYfHzdD"
"RDYfHzZRLgABADMAVAMLAoEABQAAJQEnAScHARkB8lX+bpNeVAHHZv6PtFgA//8AMv/1Ay8C4gIGAAAAAAACAB3/mwNBAuIAPQBJ"
"AAAFMjY3JwYGIyImJjU0NjYzMhYWFRQGIyImNzcjByMmJiMiBhUUFjMyNjczFhYzMjY2NTQmJiMiDgIVFBYWEyImNTQ2MzIWFwYG"
"AbhNhyUrImFAXY1ORodhVYFKLSocHgYOQwwHDDgnS1xSRio/DQgLPi46VjBksXVal208YLhsICcnKiAnAwQoZS4iTRohSJBqW5FV"
"Q39aRlYwPcM0HCJ0Y1ZpJyIhLEJ2TnCnXT1wm158vGkBLTUzNEI4NTM+AAMAI//2AuAC5AAlADIAPQAAFzI2NxczJzY2NzM1IwcG"
"BgcnNjY1NTQmIyIGFRUUFwcGBhUVFBYTJiY1NTQ2MzIVFRQGAyImNTU0NjcXBgb3QnEiVMC4CA4Eb88BAQcGakNFaF5gc0sBO0Rz"
"jh8cISFAIzMrMxkfiw42Ci0tUbYSKhZwFBgrFnAfXzUSSlteURdJTgcfYT4YUWMBwyAyGhcdIT4VHTT+lS0lFRwuE48ZHAABAA//"
"aQLoAtkADwAAFzMRMxEzETM1ISIGFRQWN+WceptS/g5wd29nlwLi/R4C4o5kYVZoAQACACH/9gHWAuMALwA/AAAXMjY1NCc2NjU0"
"JicmJjU0NjMyFhczJiYjIgYVFBYXBhUUFhYXFhYVFCMiJicjFhYTJiYnJiY1NDcWFhcWFhUU9WJ1LxoeVVAzNSIfISQBhwRtWVxy"
"GRw8J0UuQS5HJCsChwJwqg0gESYiFAwbDyYmClZLQiwROB9FQhUNHB4XGyAmT1hWSSI2FCpDLDcgDBMdHzYmKFBfATsGCgQLHBkX"
"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"
"MhYVFRQGATI2NTU0JiMiBhUVFBYhMjY1NTQmIyIGFRUUFiUiJjU1NDYzMhYVFRQGISImNTU0NjMyFhUVFAbJVF5eVFNeXhN5Acp6"
"/nccIiIcHCIhAaZUXV5TVF1dAdVUXV1UVF1d/tMcIyMcHCIiAWUcIiIcHCIiAWVbUiRQXFxQJFJb/psC2f7oHx9JIB8fIEkgHv41"
"XFAkUVxcUSRRW1xQJFFcXFEkUVtbHx9JIB8eIUkfHx8fSSAfHiFJHx8AAAMAPwA5AioCZwALAA8AGwAAATI2NTQmIyIGFRQWByE1"
"IRMyNjU0JiMiBhUUFgE2KzM0Kis0NMwB6/4V9yszNCorNDQByyolIyoqIyUquoL+piskJCoqJCQrAAEANQBSAfQCiAAIAAA3MxEX"
"NScHFTfPipvg35pSAW9kl5SUl2T//wA7AIQCcQJDAIcCpv/pAngAAMAAQAAAAP//ADUAVAH0AooADwKmAikC3MAA//8AMACDAmYC"
"QgAPAqcCoQLGwAAAAQAxAIQC9gJCAA0AADczJyEHMzcnIxchNyMHxJZjAThjl5OTl2P+yGOWk4SamuDemZneAAEAJv/iAwUC9wAR"
"AAAFMjY2NTU0JiYjIgYGFRUUFhYBl2ylXVulbm2nXVymHladalxpnFdWnGpcaJ5XAAIAJv/iAwUC9wARACMAAAUyNjY1NTQmJiMi"
"BgYVFRQWFjciJiY1NTQ2NjMyFhYVFRQGBgGXbKVdW6VubaddXKZvW4lMSoldWohMSogeVp1qXGmcV1acalxonlc8R4JYXFaCSUeC"
"WFxXgkgAAAwAMgAyAqgCpwALABcAIwAvADsARwBTAF8AawB3AIMAjwAAATI2NTQmIyIGFRQWFzI2NTQmIyIGFRQWIzI2NTQmIyIG"
"FRQWBTI2NTQmIyIGFRQWITI2NTQmIyIGFRQWBTI2NTQmIyIGFRQWITI2NTQmIyIGFRQWBTI2NTQmIyIGFRQWITI2NTQmIyIGFRQW"
"BTI2NTQmIyIGFRQWIzI2NTQmIyIGFRQWFzI2NTQmIyIGFRQWAW0UGRkUExoamhQZGRQTGhr7FBkZFBMaGgGEFBkZFBMaGv4/FBkZ"
"FBMaGgILFBkZFBMaGv33FBkZFBMaGgILFBkZFBMaGv4/FBkZFBMaGgGEFBkZFBMaGvsUGRkUExoamhQZGRQTGhoCTRoTFBkZFBMa"
"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"
"Au4ACwAAEzI2NTQmIyIGFRQWiiw1NSwsNjYCWCkiIygoIyIpAAEAKP9JAN3/0gALAAAXMjY1NCYjIgYVFBaDKDIyKCkyMrcmHyAk"
"JCAfJgD//wAoAloBiQLaAAYCrgAA//8AKAJdAM0C4QAGAq8AAP//ACgCVgEsAtkABgKwAAD//wAoAlYBLALZAAYCsQAA//8AKAJW"
"AeYC2QAGArIAAP//ACgCVAHaAtcABgKzAAD//wAoAlQB2gLXAAYCtAAA//8AKAJKAZUC1wAGArUAAP//ACgCTAEcAzAABgK2AAD/"
"/wAmAlwBkALyAAYCtwAA//8AKAJfAcQC0gAGArgAAP//ACj/FAFDAAoABgK+AAD//wAo/zEA7gAiAAYCvwAAAAAADwC6AAMAAQQJ"
"AAAAaAAAAAMAAQQJAAEAFABoAAMAAQQJAAIACAB8AAMAAQQJAAMAMgCEAAMAAQQJAAQAHgC2AAMAAQQJAAUAGgDUAAMAAQQJAAYA"
"HADuAAMAAQQJAAgAYgEKAAMAAQQJAAkAGAFsAAMAAQQJAAsAHAGEAAMAAQQJAAwAIAGgAAMAAQQJAQAAGAHAAAMAAQQJAQEAKgHY"
"AAMAAQQJAQIAFgICAAMAAQQJAQMAKgIYAEMAbwBwAHkAcgBpAGcAaAB0ACAAqQAgADIAMAAyADEAIABiAHkAIABHAGkAdABIAHUA"
"YgAuAEkAbgBjAC4AIABBAGwAbAAgAHIAaQBnAGgAdABzACAAcgBlAHMAZQByAHYAZQBkAC4ASAB1AGIAbwB0ACAAUwBhAG4AcwBC"
"AG8AbABkADIALgAwADAAMAA7AE4ATwBOAEUAOwBIAHUAYgBvAHQAUwBhAG4AcwAtAEIAbwBsAGQASAB1AGIAbwB0ACAAUwBhAG4A"
"cwAgAEIAbwBsAGQAVgBlAHIAcwBpAG8AbgAgADIALgAwADAAMABIAHUAYgBvAHQAUwBhAG4AcwAtAEIAbwBsAGQARwBpAHQASAB1"
"AGIALAAgAEkAbgBjAC4ALAAgAFMAdQBiAHMAaQBkAGkAYQByAHkAIABvAGYAIABNAGkAYwByAG8AcwBvAGYAdAAgAEMAbwByAHAA"
"bwByAGEAdABpAG8AbgBEAGUAbgBpACAAQQBuAGcAZwBhAHIAYQB3AHcAdwAuAGcAaQB0AGgAdQBiAC4AYwBvAG0AdwB3AHcALgBk"
"AGUAZwBhAHIAaQBzAG0ALgBjAG8AbQBSAG8AdQBuAGQAZQBkACAAZABvAHQAcwBBAGwAdABlAHIAbgBhAHQAZQAgAGwAbwB3AGUA"
"cgBjAGEAcwBlACAAbABBAGwAdABlAHIAbgBhAHQAZQAgAHIAUwBlAHIAaQBmAGwAZQBzAHMAIAB1AHAAcABlAHIAYwBhAHMAZQAg"
"AEkAAgAAAAAAAP90AEYAAAAAAAAAAAAAAAAAAAAAAAAAAALgAAAAJADJAQIBAwEEAQUBBgEHAMcBCAEJAQoBCwEMAGIBDQCtAQ4B"
"DwEQAGMArgCQACUAJgD9AP8AZAERARIAJwETARQA6QAoAGUBFQEWAMgBFwEYARkBGgEbAMoBHAEdAMsBHgEfASABIQApACoA+AEi"
"ASMBJAElACsBJgEnACwBKADMASkAzQDOAPoBKgDPASsBLAEtAS4ALQEvATAALgExAC8BMgEzATQBNQDiADAAMQE2ATcBOABmATkA"
"MgDQANEBOgE7ATwBPQE+AGcBPwDTAUABQQFCAUMBRAFFAUYBRwFIAJEArwCwADMA7QA0ADUBSQFKAUsANgFMAOQA+wFNAU4BTwA3"
"AVABUQFSAVMAOADUAVQA1QBoAVUA1gFWAVcBWAFZAVoBWwFcAV0BXgFfAWABYQA5ADoBYgFjAWQBZQA7ADwA6wFmALsBZwFoAWkB"
"agA9AWsA5gFsAW0BbgFvAXABcQFyAXMBdAF1AXYBdwF4AXkBegF7AXwBfQF+AX8BgAGBAYIBgwGEAYUBhgGHAYgBiQGKAYsBjAGN"
"AY4BjwGQAZEBkgGTAZQBlQGWAEQAaQGXAZgBmQGaAZsBnABrAZ0BngGfAaABoQBsAaIAagGjAaQBpQBuAG0AoABFAEYA/gEAAG8B"
"pgGnAEcBqAEBAOoASABwAakBqgByAasBrAGtAa4BrwBzAbABsQBxAbIBswG0AbUASQBKAPkBtgG3AbgBuQBLAboBuwBMANcAdAG8"
"AHYAdwG9Ab4AdQG/AcABwQHCAcMATQHEAcUBxgBOAccATwHIAckBygHLAOMAUABRAcwBzQHOAHgBzwBSAHkAewHQAdEB0gHTAdQA"
"fAHVAHoB1gHXAdgB2QHaAdsB3AHdAd4AoQB9ALEAUwDuAFQAVQHfAeAB4QBWAeIA5QD8AeMB5ACJAFcB5QHmAecB6ABYAH4B6QCA"
"AIEB6gB/AesB7AHtAe4B7wHwAfEB8gHzAfQB9QH2AFkAWgH3AfgB+QH6AFsAXADsAfsAugH8Af0B/gH/AF0CAADnAgECAgIDAgQC"
"BQIGAgcCCAIJAgoCCwIMAg0CDgIPAhACEQISAhMCFAIVAhYCFwIYAhkCGgIbAhwCHQIeAh8CIAIhAiICIwIkAiUCJgInAigCKQIq"
"AisCLAItAi4CLwIwAjECMgIzAjQCNQI2AjcCOAI5AjoCOwI8Aj0CPgI/AkACQQJCAkMAwADBAkQCRQCdAJ4CRgCbABMAFAAVABYA"
"FwAYABkAGgAbABwCRwJIAkkCSgJLAkwCTQJOAk8CUAJRAlICUwJUAlUCVgJXAlgCWQJaAlsCXAJdAl4CXwJgAmECYgJjAmQCZQJm"
"AmcCaAJpAmoCawJsAm0CbgJvAnACcQJyAnMCdAJ1AnYCdwJ4ALwA9AD1APYCeQJ6AnsCfAJ9An4CfwKAAoECggKDAoQChQKGAocC"
"iAKJAooCiwKMAo0CjgKPApAAAwKRABEADwAdAB4AqwAEAKMAIgCiAMMAhwANAAYAEgA/ApICkwKUApUClgKXApgCmQKaApsCnAKd"
"Ap4CnwKgAqECogKjABAAsgCzAEICpAKlAqYACwAMAF4AYAA+AEACpwKoAqkCqgKrAqwAxADFALQAtQC2ALcAqQCqAL4AvwAFAAoC"
"rQKuAq8CsAKxArIApgKzArQCtQK2ACMACQCIAIYAiwCKArcAjACDAF8A6AK4ArkCugK7AIQAvQAHArwCvQK+Ar8AhQCWAA4A7wDw"
"ALgAIACPACEAHwCVAJQAkwCnAKQAYQBBAJICwACcAJoAmQClAAgAxgLBAsICwwLEAsUCxgLHAsgCyQLKAssCzALNAs4CzwLQAtEC"
"0gLTAtQC1QLWAtcC2ALZAtoC2wLcAt0C3gLfAuAC4QLiAuMC5ALlAuYC5wLoAukC6gLrAuwC7QLuAI4A3ABDAI0A3wDYAOEA2wDd"
"ANkA2gDeAOAGQWJyZXZlB3VuaTFFQUUHdW5pMUVCNgd1bmkxRUIwB3VuaTFFQjIHdW5pMUVCNAd1bmkxRUE0B3VuaTFFQUMHdW5p"
"MUVBNgd1bmkxRUE4B3VuaTFFQUEHdW5pMUVBMAd1bmkxRUEyB0FtYWNyb24HQW9nb25lawtDY2lyY3VtZmxleApDZG90YWNjZW50"
"BkRjYXJvbgZEY3JvYXQGRWJyZXZlBkVjYXJvbgd1bmkxRUJFB3VuaTFFQzYHdW5pMUVDMAd1bmkxRUMyB3VuaTFFQzQKRWRvdGFj"
"Y2VudAd1bmkxRUI4B3VuaTFFQkEHRW1hY3JvbgdFb2dvbmVrB3VuaTFFQkMGR2Nhcm9uC0djaXJjdW1mbGV4B3VuaTAxMjIKR2Rv"
"dGFjY2VudARIYmFyC0hjaXJjdW1mbGV4AklKBklicmV2ZQd1bmkxRUNBB3VuaTFFQzgHSW1hY3JvbgdJb2dvbmVrBkl0aWxkZQt1"
"bmkwMDRBMDMwMQtKY2lyY3VtZmxleAd1bmkwMTM2BkxhY3V0ZQZMY2Fyb24HdW5pMDEzQgRMZG90Bk5hY3V0ZQZOY2Fyb24HdW5p"
"MDE0NQNFbmcHdW5pMUVEMAd1bmkxRUQ4B3VuaTFFRDIHdW5pMUVENAd1bmkxRUQ2B3VuaTFFQ0MHdW5pMUVDRQVPaG9ybgd1bmkx"
"RURBB3VuaTFFRTIHdW5pMUVEQwd1bmkxRURFB3VuaTFFRTANT2h1bmdhcnVtbGF1dAdPbWFjcm9uBlJhY3V0ZQZSY2Fyb24HdW5p"
"MDE1NgZTYWN1dGULU2NpcmN1bWZsZXgHdW5pMDIxOAd1bmkxRTlFBFRiYXIGVGNhcm9uB3VuaTAxNjIHdW5pMDIxQQZVYnJldmUH"
"dW5pMUVFNAd1bmkxRUU2BVVob3JuB3VuaTFFRTgHdW5pMUVGMAd1bmkxRUVBB3VuaTFFRUMHdW5pMUVFRQ1VaHVuZ2FydW1sYXV0"
"B1VtYWNyb24HVW9nb25lawVVcmluZwZVdGlsZGUGV2FjdXRlC1djaXJjdW1mbGV4CVdkaWVyZXNpcwZXZ3JhdmULWWNpcmN1bWZs"
"ZXgHdW5pMUVGNAZZZ3JhdmUHdW5pMUVGNgd1bmkxRUY4BlphY3V0ZQpaZG90YWNjZW50DHVuaTFFQjYuc3MwMQx1bmkxRUFDLnNz"
"MDEOQWRpZXJlc2lzLnNzMDEMdW5pMUVBMC5zczAxD0Nkb3RhY2NlbnQuc3MwMQx1bmkxRUM2LnNzMDEORWRpZXJlc2lzLnNzMDEP"
"RWRvdGFjY2VudC5zczAxDHVuaTFFQjguc3MwMQ9HZG90YWNjZW50LnNzMDEOSWRpZXJlc2lzLnNzMDEPSWRvdGFjY2VudC5zczAx"
"DHVuaTFFQ0Euc3MwMQlMZG90LnNzMDEMdW5pMUVEOC5zczAxDk9kaWVyZXNpcy5zczAxDHVuaTFFQ0Muc3MwMQx1bmkxRUUyLnNz"
"MDEGUS5zczAxDlVkaWVyZXNpcy5zczAxDHVuaTFFRTQuc3MwMQx1bmkxRUYwLnNzMDEOV2RpZXJlc2lzLnNzMDEOWWRpZXJlc2lz"
"LnNzMDEMdW5pMUVGNC5zczAxD1pkb3RhY2NlbnQuc3MwMQZJLnNzMDQHSUouc3MwNAtJYWN1dGUuc3MwNAtJYnJldmUuc3MwNBBJ"
"Y2lyY3VtZmxleC5zczA0DklkaWVyZXNpcy5zczA0D0lkb3RhY2NlbnQuc3MwNAx1bmkxRUNBLnNzMDQLSWdyYXZlLnNzMDQMdW5p"
"MUVDOC5zczA0DEltYWNyb24uc3MwNAxJb2dvbmVrLnNzMDQLSXRpbGRlLnNzMDQTSWRpZXJlc2lzLnNzMDEuc3MwNBRJZG90YWNj"
"ZW50LnNzMDEuc3MwNBF1bmkxRUNBLnNzMDEuc3MwNAZhYnJldmUHdW5pMUVBRgd1bmkxRUI3B3VuaTFFQjEHdW5pMUVCMwd1bmkx"
"RUI1B3VuaTFFQTUHdW5pMUVBRAd1bmkxRUE3B3VuaTFFQTkHdW5pMUVBQgd1bmkxRUExB3VuaTFFQTMHYW1hY3Jvbgdhb2dvbmVr"
"C2NjaXJjdW1mbGV4CmNkb3RhY2NlbnQGZGNhcm9uBmVicmV2ZQZlY2Fyb24HdW5pMUVCRgd1bmkxRUM3B3VuaTFFQzEHdW5pMUVD"
"Mwd1bmkxRUM1CmVkb3RhY2NlbnQHdW5pMUVCOQd1bmkxRUJCB2VtYWNyb24HZW9nb25lawd1bmkxRUJEBmdjYXJvbgtnY2lyY3Vt"
"ZmxleAd1bmkwMTIzCmdkb3RhY2NlbnQEaGJhcgtoY2lyY3VtZmxleAZpYnJldmUJaS5sb2NsVFJLB3VuaTFFQ0IHdW5pMUVDOQdp"
"bWFjcm9uB2lvZ29uZWsGaXRpbGRlAmlqB3VuaTAyMzcLdW5pMDA2QTAzMDELamNpcmN1bWZsZXgHdW5pMDEzNwZsYWN1dGUGbGNh"
"cm9uB3VuaTAxM0MEbGRvdAZuYWN1dGUGbmNhcm9uB3VuaTAxNDYDZW5nB3VuaTFFRDEHdW5pMUVEOQd1bmkxRUQzB3VuaTFFRDUH"
"dW5pMUVENwd1bmkxRUNEB3VuaTFFQ0YFb2hvcm4HdW5pMUVEQgd1bmkxRUUzB3VuaTFFREQHdW5pMUVERgd1bmkxRUUxDW9odW5n"
"YXJ1bWxhdXQHb21hY3JvbgZyYWN1dGUGcmNhcm9uB3VuaTAxNTcGc2FjdXRlC3NjaXJjdW1mbGV4B3VuaTAyMTkEdGJhcgZ0Y2Fy"
"b24HdW5pMDE2Mwd1bmkwMjFCBnVicmV2ZQd1bmkxRUU1B3VuaTFFRTcFdWhvcm4HdW5pMUVFOQd1bmkxRUYxB3VuaTFFRUIHdW5p"
"MUVFRAd1bmkxRUVGDXVodW5nYXJ1bWxhdXQHdW1hY3Jvbgd1b2dvbmVrBXVyaW5nBnV0aWxkZQZ3YWN1dGULd2NpcmN1bWZsZXgJ"
"d2RpZXJlc2lzBndncmF2ZQt5Y2lyY3VtZmxleAd1bmkxRUY1BnlncmF2ZQd1bmkxRUY3B3VuaTFFRjkGemFjdXRlCnpkb3RhY2Nl"
"bnQPdW5pMUVDQi5kb3RsZXNzD2lvZ29uZWsuZG90bGVzcwZhLnNzMDELYWFjdXRlLnNzMDELYWJyZXZlLnNzMDEMdW5pMUVBRi5z"
"czAxDHVuaTFFQjcuc3MwMQx1bmkxRUIxLnNzMDEMdW5pMUVCMy5zczAxDHVuaTFFQjUuc3MwMRBhY2lyY3VtZmxleC5zczAxDHVu"
"aTFFQTUuc3MwMQx1bmkxRUFELnNzMDEMdW5pMUVBNy5zczAxDHVuaTFFQTkuc3MwMQx1bmkxRUFCLnNzMDEOYWRpZXJlc2lzLnNz"
"MDEMdW5pMUVBMS5zczAxC2FncmF2ZS5zczAxDHVuaTFFQTMuc3MwMQxhbWFjcm9uLnNzMDEMYW9nb25lay5zczAxCmFyaW5nLnNz"
"MDELYXRpbGRlLnNzMDEPY2RvdGFjY2VudC5zczAxDHVuaTFFQzcuc3MwMQ5lZGllcmVzaXMuc3MwMQ9lZG90YWNjZW50LnNzMDEM"
"dW5pMUVCOS5zczAxD2dkb3RhY2NlbnQuc3MwMQZpLnNzMDEOaWRpZXJlc2lzLnNzMDEOaS5sb2NsVFJLLnNzMDEMdW5pMUVDQi5z"
"czAxBmouc3MwMQlsZG90LnNzMDEMdW5pMUVEOS5zczAxDm9kaWVyZXNpcy5zczAxDHVuaTFFQ0Quc3MwMQx1bmkxRUUzLnNzMDEO"
"dWRpZXJlc2lzLnNzMDEMdW5pMUVFNS5zczAxDHVuaTFFRjEuc3MwMQ53ZGllcmVzaXMuc3MwMQZ5LnNzMDELeWFjdXRlLnNzMDEQ"
"eWNpcmN1bWZsZXguc3MwMQ55ZGllcmVzaXMuc3MwMQx1bmkxRUY1LnNzMDELeWdyYXZlLnNzMDEPemRvdGFjY2VudC5zczAxBmwu"
"c3MwMgtsYWN1dGUuc3MwMgtsY2Fyb24uc3MwMgx1bmkwMTNDLnNzMDIJbGRvdC5zczAyC2xzbGFzaC5zczAyBnIuc3MwMwtyYWN1"
"dGUuc3MwMwtyY2Fyb24uc3MwMwx1bmkwMTU3LnNzMDMUdW5pMUVDQi5kb3RsZXNzLnNzMDEObGRvdC5zczAxLnNzMDIIZl9mLmxp"
"Z2EKZl9mX2kubGlnYQpmX2ZfbC5saWdhB2ZsLnNzMDIPZl9mX2wubGlnYS5zczAyB3VuaTAzQkMHdW5pMjRGRgd1bmkyNzc2B3Vu"
"aTI3NzcHdW5pMjc3OAd1bmkyNzc5B3VuaTI3N0EHdW5pMjc3Qgd1bmkyNzdDB3VuaTI3N0QHdW5pMjc3RQd1bmkyNEVBB3VuaTI0"
"NjAHdW5pMjQ2MQd1bmkyNDYyB3VuaTI0NjMHdW5pMjQ2NAd1bmkyNDY1B3VuaTI0NjYHdW5pMjQ2Nwd1bmkyNDY4B3plcm8udGYG"
"b25lLnRmBnR3by50Zgh0aHJlZS50Zgdmb3VyLnRmB2ZpdmUudGYGc2l4LnRmCHNldmVuLnRmCGVpZ2h0LnRmB25pbmUudGYJemVy"
"by5kbm9tCG9uZS5kbm9tCHR3by5kbm9tCnRocmVlLmRub20JZm91ci5kbm9tCWZpdmUuZG5vbQhzaXguZG5vbQpzZXZlbi5kbm9t"
"CmVpZ2h0LmRub20JbmluZS5kbm9tCXplcm8ubnVtcghvbmUubnVtcgh0d28ubnVtcgp0aHJlZS5udW1yCWZvdXIubnVtcglmaXZl"
"Lm51bXIIc2l4Lm51bXIKc2V2ZW4ubnVtcgplaWdodC5udW1yCW5pbmUubnVtcglvbmVlaWdodGgMdGhyZWVlaWdodGhzC2ZpdmVl"
"aWdodGhzDHNldmVuZWlnaHRocwd1bmkyMDgwB3VuaTIwODEHdW5pMjA4Mgd1bmkyMDgzB3VuaTIwODQHdW5pMjA4NQd1bmkyMDg2"
"B3VuaTIwODcHdW5pMjA4OAd1bmkyMDg5B3VuaTIwNzAHdW5pMDBCOQd1bmkwMEIyB3VuaTAwQjMHdW5pMjA3NAd1bmkyMDc1B3Vu"
"aTIwNzYHdW5pMjA3Nwd1bmkyMDc4B3VuaTIwNzkHdW5pMDBBMA9leGNsYW1kb3duLmNhc2URcXVlc3Rpb25kb3duLmNhc2UWcGVy"
"aW9kY2VudGVyZWQubG9jbENBVAtwZXJpb2Quc3MwMQpjb21tYS5zczAxCmNvbG9uLnNzMDEOc2VtaWNvbG9uLnNzMDENZWxsaXBz"
"aXMuc3MwMQtleGNsYW0uc3MwMQ9leGNsYW1kb3duLnNzMDENcXVlc3Rpb24uc3MwMRFxdWVzdGlvbmRvd24uc3MwMRNwZXJpb2Rj"
"ZW50ZXJlZC5zczAxG3BlcmlvZGNlbnRlcmVkLmxvY2xDQVQuY2FzZRRleGNsYW1kb3duLmNhc2Uuc3MwMRZxdWVzdGlvbmRvd24u"
"Y2FzZS5zczAxG3BlcmlvZGNlbnRlcmVkLmxvY2xDQVQuc3MwMSBwZXJpb2RjZW50ZXJlZC5sb2NsQ0FULmNhc2Uuc3MwMQtoeXBo"
"ZW4uY2FzZQtlbmRhc2guY2FzZQtlbWRhc2guY2FzZQ5wYXJlbmxlZnQuY2FzZQ9wYXJlbnJpZ2h0LmNhc2UOYnJhY2VsZWZ0LmNh"
"c2UPYnJhY2VyaWdodC5jYXNlEGJyYWNrZXRsZWZ0LmNhc2URYnJhY2tldHJpZ2h0LmNhc2UTcXVvdGVzaW5nbGJhc2Uuc3MwMRFx"
"dW90ZWRibGJhc2Uuc3MwMRFxdW90ZWRibGxlZnQuc3MwMRJxdW90ZWRibHJpZ2h0LnNzMDEOcXVvdGVsZWZ0LnNzMDEPcXVvdGVy"
"aWdodC5zczAxB3VuaTI2MzkJc21pbGVmYWNlB3VuaTI3MTMHdW5pRjhGRgd1bmkyMTE3B3VuaTIxMTMJZXN0aW1hdGVkB3VuaTIx"
"MTYHdW5pMjBCRgRFdXJvB3VuaTIwQkEHdW5pMjBCOQd1bmkyMEFBCGVtcHR5c2V0C2RpdmlkZS5zczAxB2Fycm93dXAKYXJyb3dy"
"aWdodAlhcnJvd2Rvd24JYXJyb3dsZWZ0CWFycm93Ym90aAd1bmkyNUNGBmNpcmNsZQd1bmkyNUNDB3VuaTAzMDgHdW5pMDMwNwln"
"cmF2ZWNvbWIJYWN1dGVjb21iB3VuaTAzMEIHdW5pMDMwMgd1bmkwMzBDB3VuaTAzMDYHdW5pMDMwQQl0aWxkZWNvbWIHdW5pMDMw"
"NA1ob29rYWJvdmVjb21iB3VuaTAzMTIHdW5pMDMxQgxkb3RiZWxvd2NvbWIHdW5pMDMyNgd1bmkwMzI3B3VuaTAzMjgHdW5pMDMz"
"NQd1bmkwMzM2B3VuaTAzMzcHdW5pMDMzOAt1bmkwMzA2MDMwMQt1bmkwMzA2MDMwMAt1bmkwMzA2MDMwOQt1bmkwMzA2MDMwMwt1"
"bmkwMzAyMDMwMQt1bmkwMzAyMDMwMAt1bmkwMzAyMDMwOQt1bmkwMzAyMDMwMwx1bmkwMzM1LmNhc2UMdW5pMDMzNy5jYXNlDHVu"
"aTAzMzguY2FzZQl1bmkwMzI4LmUMdW5pMDMwOC5zczAxDHVuaTAzMDcuc3MwMRFkb3RiZWxvd2NvbWIuc3MwMQABAAIADgAAAKIA"
"AADyAAIAGAABAFwAAQBeAHUAAQB3AIEAAQCDAO0AAQDvAPgAAQD6ATUAAQE3AU4AAQFQAVoAAQFcAcUAAQHGAcwAAgHbAe4AAQIr"
"AiwAAQIuAi4AAQI9Aj4AAQJAAkAAAQJfAnAAAQJ6AnoAAQJ8AnwAAQKEAoUAAQKHAogAAQKNAo0AAQKSApIAAQKrAq0AAQKuAtIA"
"AwASAAcAHAAkAEIAMgA6ADoAQgACAAEBxgHMAAAAAQAEAAEA7gACAAYACgABANAAAQGhAAEABAABAM0AAQAEAAEA4QACAAYACgAB"
"AN4AAQG7AAEAAQAAAAgAAgADAq4CugAAAsQCywANAtAC0QAVAAEAAAAKAGIAiAACREZMVAAObGF0bgASAD4AAAA6AAlBWkUgADpD"
"QVQgADpDUlQgADpLQVogADpNT0wgADpOTEQgADpST00gADpUQVQgADpUUksgADoAAP//AAMAAAABAAIAA2tlcm4AFG1hcmsAGm1r"
"bWsAIAAAAAEAAAAAAAEAAQAAAAEAAgADAAinzMDEAAIACAACAAo6fgABAsIABAAAAVwFWgYkBr4GUgZYBoYT0AaQBpAGkAaWBrAG"
"vgbEBtoG8Ab+BwwHFgdAB3IHpAf2B/wIBghsCJoI1AkKCRAJRglMCWIJfAmyCcAKVgpcCw4LsAu6C9AL5gwUDB4MKAw2DDwNbAzG"
"DMwM6g0EDSYNRA1aDWwNcg2ADcIObA6ODuAPKg9gEO4RKBE2EUwRYhHQEdoSiBLKExATmhPQE9oT7BP6FKwUshTAFMYUzBTSFNwU"
"6hTwFR4VChUUFR4VKBUuFTwVQhVIFUgVThVgFX4VmBWeFaQVzhX8FoIWvBbCFuQW6ihIFvAW+hcsF04XVBdaF2QXcheEF7IX0Bfe"
"F+gYOhhAGEYYUBkGGRgZVhl8GaoZsBnaGhAaHhooGnIalBrGGswa0hsUGxobRBtKG4QbrhvUHAYcPBxiHGgcch0IHSYdTB2OHbge"
"Dh5AHk4eVB7KHvgfBh+EH5IfnB+qH7Afvh/UH/YgDCA6IHwgliCwIL4g0CDWIOAg4CDmIOYg7CD2IPwhCiEQIRYhJCFCIVQhYiFs"
"Icoh4CHqIfgiJiJkIo4iZCKOIqwirCLSIuAi9iL8IzojuCPaJCgkbiUIJYIl0CYKJkQmfiasJtIm9CceJ1AnaieUJ7In3CgCKAgo"
"DihIKE4oWCh2KIwouijIKNoo6CkKKSgpPilUKWopmCmuKcQqAiosKj4qTCqOKqwqwiswK2oroCwKLKwsyi0YLSItKC02LXgthi2Q"
"Lbot0C5uLpguxi7ULvYvBC8OMEAwijDIMOIxMDF6MYQxkjHQMgIyQDJuMogywjL0MxozYDNyM6Qz6jQYNC40VDRmNHw0jjS4NOo1"
"CDUeNUA1SjVwNZ41pDWyNdA2BjYoNmo2dDaONsw26jdQN7Y32DgWOCw4bjh8OKY4sDjaOQw5ZjmAOZI5oDm+OcQ56jocOkoAAgBu"
"AAEABAAAAAkADwAEABEAGQALAB8AHwAUACMAJAAVADMAMwAXADUANgAYADwAPwAaAEQARAAeAEoASgAfAEwAUQAgAFMAVAAmAFYA"
"XAAoAF4AXwAvAGcAZwAxAGoAbwAyAHEAcgA4AHUAeAA6AHwAfAA+AIIAiQA/AJsAnABHAKEAogBJAKoAqgBLAK8AsABMAL8AwABO"
"AMgAyABQAMoAzQBRANIA0gBVANQA1QBWANgA2ABYANsA3wBZAOMA5gBeAOoA6wBiAO8A8ABkAPIA8wBmAPYA9gBoAPgA+gBpAP0A"
"/QBsAQIBAgBtAQQBBABuAQcBBwBvAQkBCgBwAQwBDgByARABEwB1ARYBFgB5ARgBHQB6AR8BIgCAASQBJACEASYBKACFASoBKgCI"
"ASwBLQCJAS8BMQCLATMBMwCOATYBOACPAT0BPQCSAT8BPwCTAUMBSwCUAU4BTgCdAVABUwCeAVUBVQCiAVcBWACjAVsBYQClAWUB"
"ZQCsAW8BbwCtAXEBcQCuAXQBdQCvAXoBewCxAX8BfwCzAYMBgwC0AYUBhQC1AYkBiQC2AY0BkAC3AZQBlgC7AZwBnAC+AaUBpgC/"
"AagBqQDBAa4BrgDDAbMBswDEAbcBtwDFAboBugDGAbwBvADHAb8BwgDIAcYB2gDMAfkCAgDhAgQCBADrAgYCBgDsAg0CDQDtAhUC"
"HADuAh8CIAD2AiMCKAD4AisCMAD+AjICMwEEAjYCOQEGAjsCOwEKAj0CQgELAkQCRQERAkkCSQETAkwCVwEUAlkCWwEgAl0CXQEj"
"Al8CcAEkAnYCdwE2AnoCfgE4AoECgQE9AoMCgwE+AoUChQE/AocCigFAAowCnQFEAp8CnwFWAqECpQFXADIAPf/aAE4ABgBd//QA"
"dv/0AIT/eQCI/8sApf9fAKb/XwCn/18Axf9fAMb/XwD5/+ABG//6AS//5AFb/74BXf/OAbr/7QG//9gBzv+KAdH/zwHT//0B1v/f"
"Adf/1QHY/7kB2f/kAdr/2wIw//QCNv+DAjf/2gI5/1QCU//iAlb/3QJZ/9MCY/+dAmT/owJq/6sCbf+LAm7/jAJw/50Cdv/YAnv/"
"jwJ9/2sCh//TApD/sQKS/7sCk/+0ApT/2wKZ/64Cmv+UApv/kAALAHb/9ACE/3kA+f/gAS//5AG6/+0Bv//YAjb/gwJq/6sCbv+M"
"Anv/jwJ9/2sAAQCD/3kACwCD/4MAh/+DAJv/gQCi/4MApf+EAKb/gwDF/4QAxv+DAmT/owJq/6sCcP+dAAIAg/+DAKL/gQABAKL/"
"gQAGAIP/ewCb/2oApf9vAmr/qwJ7/48Cff9vAAMCNv+DAmr/qwJu/4wAAQJu/4wABQCD/38Am/91AKL/eAJq/6sCbv+MAAUCLAAR"
"Ajb/gwJUAAgCY/+dAm7/jAADAKX/YADF/2ACNv+DAAMBzf+SAjb/gwJu/4wAAgD5/+kBdP/WAAoBFAATARsAHwHWAAYB2P/3AdkA"
"CAHaAAMCOf/SAlb/0wJ9/90ClP/3AAwAdAAAAdMABwHWAAQB2P/7AdkACAHaAAYCOf/KAlb/wAJe/88CcP/vAn3/2QKU//kADABO"
"/9ABJAABAS8ABwHT//YB1wAHAdoAAgI5/70CVv+1Alz/uQJe/7wCff/PApT/7wAUAPn/6QEbADEBJP//AScANgEv//EBTv/6AVv/"
"2QG6AAAB0f/pAdf/7AHa//gCN//qAlP/7wJ2/+UCe//XApD/wQKS/88ClP/oApr/jgKb/4YAAQFO//oAAgIsAA8CVAAIABkAdP/p"
"ARj/7AEbACYBZf/sAaUAAQHR/+wB0//nAdb/9AHX/+4B2f/uAdr/9QIX/9ACGP/NAhn/nQIa/9ECG//GAh3/ywI3/+4CP//PAkD/"
"1QJB/2cCU//qAnv/6AKS/9kClP/iAAsBFAAKARsAFAEnACkBLwAEAdMAAwHY//MB2gABAjn/uwJW/9ICff/QApT/9gAOADwAAABm"
"//wAd//8AIgAAQEZABoBJwA1AdoAAAIw//4CP//9AkIAAQJqAAACcP/8ApT/8AKb/8kADQAB/9oAPQAHAEz/3wCD//sAof/lANj/"
"4wD2/+MA+v/jARL/4wE3/+MBVf/iAWH/9wGJ/+IAAQAB//MADQB0/94A+f/pAScANwFb/9oB0f/mAdf/6gI3/+oCU//vAnb/5gJ7"
"/9YCkv/PApr/fwKb/3kAAQEbADMABQEhABEBJAAmAU4AAQIsAA0CVAAHAAYAGf/+AF7//gBf//4AiAACAdoAAAKU//IADQAP/+gA"
"IwAAAC0ACgAyAAwASQANAMwALwDQAC0A0gBKAaUAAQHaAAACVP/1Alr/+gKU//IAAwAB/+UAXv/+AScAHgAlAHT/rQCnAAAA6v/G"
"AQT/wQEJ/8oBL//iAT//wQFK/8gBUwALAWH/ygGA/8ABgv/CAZf/3wGs/8YBuP+ZAbr/9gG//9sB0f+5AdP/8AHW/+EB1/+/Adn/"
"1wHa/80CN/+6Aj//5wJT/9UCWf/GAnb/vgJ7/6ECh/+9ApH/bAKS/5kCk/+gApT/1gKa/2ECm/9nAqX/dwABAQn/ygAsACn/9wAs"
"//cAMf/3ADL/9wA0//cAPf/dAHT/zgB2//cAhP97AKX/SACm/0kAp/9IAMX/SADG/0kBJP//Ac3/WgHO/1oB0f/WAdb/6wHX/9wB"
"2P+0Adn/8AHa/+cCNv92Ajf/3gI5/2YCU//uAlb/1QJZ/98CY/+UAmT/lAJp/1UCbv8+Am//lAJw/5QCdv/jAnv/agJ9/w4Ch//j"
"ApD/ugKS/7kClP/fApr/UwKb/2MAKAABAAcAGAANABn/4QAb/+EAHwANADb/4wA8AA0ATwANAFcADQBYAA0AWgANAF7/4QBg/+EA"
"eAANAHz//QB+//0Ag//WAIj/7wCJ/+8Am//VANj/6wFh//kBYv/5AXT/swF1/8gBif/3AiD/ywIh/8ECIv++AiP/sgIk/70CJf/D"
"Aib/yAIn/8ACKP/FAjL/uAJM/7ECUP+BAlT/6QJh/7EAAgAy//gCbv8+AAUApf9IAMX/SAEv/+4CZP+cAm7/WQAFAGb//ACIAAEB"
"GwAfAdoAAAKU//AACwAc//wAZv/8AHf//ACIAAEBJwA1Ac4AAAHaAAACfv/1ApD/2AKU//ACm//JAAIAGf/8AXv/9gACAAH/8wBe"
"//wAAwAB//MAE//zASAAKwABAF7//AAiABj/+wAf//sAI//7ADX/+wA8//sAPf/yAE7/0ABP//sAUf/7AFf/+wBY//sAXP/7AHX/"
"+wB4//sAgv/7AIT/0gCb/8sApf+0AMX/tADvAAEBEwABARQACgEbABMBKAABASoAAQG6AAIB0//1AdoAAQI5/70CUwAGAlb/tQJe"
"/7wCff/NApT/7QABASQAAAAHAD//+gBYAAQAg//6Aiv/zwIs/88CPf/CAlT//wAGABkABwA///oAVwAEAFgABAB1AAQAg//6AAgA"
"GQAHAD//+gBYAAQAdQAEAIP/+gCIAAcCK//PAiz/zwAHAD//+gBYAAQCK//PAiz/zwI9/8ICPv/IAlT//wAFAD//+gBYAAQCK//P"
"Aiz/zwI9/8IABAA///oAWAAEAiv/zwIs/88AAQD5AAEAAwCD/9UAm//QAKL/ywAQAE7/lgEbACABL//yAVP//QHT//0B2AAJAdoA"
"BwIX/8QCGP/EAhn/iQI5/9YCQf9QAlb/yQJe/8gCff/oApT/8AAqAAH/wQAC/8EAE//BABf/wQAiAC8AP//FAEH/xQBJ/8UATP+3"
"AF4ABwBfAAcAZgAHAIP/sQCIAAEAiQABAJv/wQCi/5kAo/+ZANgAAwDZAAMA6gADAO7//AD6AAMA+wADAQkAAwEW//0BJP/9ATcA"
"AwE4AAMBPwADAVH//QFhAAIBYgACAXT/8gF7/+sBfP/rAbT/6wIg/7sCK/+6Aiz/ugI9/6kCVP+yAAgB0//1AdoAAQI5/70CT//F"
"AlT/wAJW/74Cff/NApT/7QAUADH/9gB2//YApf/JAMX/yQEnADMB0wABAdb/6gHX/+4B2P/0Adn/6gHa//ICOf/FAlP/8AJW/+QC"
"bv/tAn3/0wKH/+YCkv/aApT/6QKb/6YAEgEUABABGQAPARsAGwEvAAIBTv//AdP//wHY//MB2QAIAdoAAAI5/8gCVv/IAl7/2wJu"
"/+wCcP/uAn3/0gKHAAIClP/3Apv/xQANAAH/5AA2//wAP//1AHwAAACD/+EAm//cAJz/4QDYAAYCI//PAkwABAJU/9ECYf/SAmP/"
"0gBjAAn/hAAK/4IAC/+EAAz/gwAW/34ATv+1AHT/zwDa/6sA2/+oANz/qwDd/6gA4P+zAOH/pADi/7MA4/+jAOT/pADl/6sA5v+s"
"AOj/nwDp/5cA6v+8AOz/ngDt/6kA+/+FAP3/vwEE/60BBf+JAQf/nQEJ/8IBF//HARj/4gEZACABGwAmAR//8gEk//gBL//jATj/"
"hQE6/6kBPf+pAT//qwFB/5sBRv+bAUn/kwFK/78BTP+mAVL/ygFTAAwBV//UAWP/0QFk/8wBZf/QAWf/ywFs/8sBbf/FAXD/1wFy"
"/8wBff/fAYD/3AGB/9gBif+QAYr/kgGO/7MBlf+0AZj/kAGZ/6wBmv+aAZv/zAGc/5ABnf+jAaX/+AGv/80Btf/eAb//4gHR/9gB"
"0//mAdb/8AHX/9oB2AAHAdn/5AHa/+cCFf9WAhf/WQI3/+ACP//BAkD/xQJB/1MCU//XAmX/gQJ2/7wCe//cAof/2wKQ/74Ckf93"
"ApL/vgKU/+ICmf+hApr/ZQKb/2YCpf9yAA4AAf95AAL/eQBy/9AAhAAHAUv/ogFd/9kCK/+XAiz/lwIt/9cCLv/XAjj/awI+/5YC"
"Zf+YAmf/mAADAWX/0AGJ/5ACP//BAAUA2v+rAOD/tADq/7wBcP/XAYn/kQAFANr/qwDg/7MA6v+8AYn/kAGL/7YAGwAYAAEAGQAC"
"AB8AAQAjAAEAJAABADUAAQA2AAIAPAABAE7/2wBPAAEAUQABAFcAAQBYAAEAXgACAHUAAQB4AAEAiAAEAO8AAwETAAMBFAAVAScA"
"IQEoAAMBKgADAboABAHaAAEClP/0Apv/zwACASQAAQFTAAsAKwAJ/4EACv9/AAv/gQAO/38AE/92ACb/8wAp//MATv+2AHT/zADa"
"/7IA5v+rAOr/uwDy/8gA/f/FAQf/qgEJ/8IBGP/YARkAIwEbACoBJP/xAT//qwFM/6UBV//YAYv/wQGW/7IBl//AAZv/zAGl//QB"
"0f/QAdP/2wHW/+sB1//SAdgADAHZ/9oB2v/dAhf/iwI3/9oCP//AAkD/xgJT/8oCdv+4Anv/0AKS/7sAEADm/8sBL//nAZf/0wGl"
"AAEBv//mAdP/5gHX/+UB2AANAdr/7QIY/7QCP//XAlP/3gJ2/9kCkv/RApT/5AKb/5wAEQB0/68B0f+6Adb/3QHX/8AB2f/YAdr/"
"zgI2/9UCN/+6AlP/1QJ2/74Ce/+kApD/mAKS/5wCk/+hApT/1wKa/2MCm/9nACIAKf/yACv/8gAs//IA5v+kAOj/ngDq/7gA/v+Z"
"AP//iwEC/4sBB/+mARj/ywE5/5cBSv++AWX/swFw/8EBm//GAdH/vwHT/88B1//BAdn/0gHa/9ECF/9UAjf/xQI//58CQP+lAkH/"
"PQJT/7sCdv+WAnv/wQKQ/54Ckv+kApT/0gKa/3MCm/9XAA0BGQAoAS//9gFTAA0Bv//qAdH/5QHX/+oB2v/2Ajf/8AJT//ACdv/m"
"Anv/2QKS/88Cm/92AAIAg/+DAKL/gwAEAMX/ZwJu/4wCe/+PAn3/awADABkABwA///oAg//6ACwAAQAVABgADQAZAAsAHwANACEA"
"NgAjAA0ANQANADwADQA/ABEAQwARAEwAEwBPAA0AUQANAFcADQBYAA0AdQANAHgADQB8AAgAg//PAIgABwCb/8sAnP/iAKEAEACi"
"/7QAqgAVALQADQD6ABABEwARARcAEQEaACIBIAAlASoAEQE3ABABUQARAVUAEwFhAAwBgwAdAYkAEgGhABABpQARAacAEQHTABYC"
"PQALAj4AEQABAScANQADAAH/8wAiAB0A0AAtAAEA0gBXAAEAzABTAAEAzQBXAAIAywBXANIAbAADAM0AVADUAFkA1QBVAAEA1QBi"
"AAYBJwAAAdj/7wHaAAACkv/sApP/3wKa/9QAAgIg/7wCVP/JAAICIP+6AlT/yQACAiD/uQJU/8kAAQIg/7oAAwF7//wCIP+9AlT/"
"yAABAXv//AABAiD/vgABAlT/ygAEASQABgIsAAUCVP/uAlj/9AAHAEz/6QF2/+sBugABAdP/7AHY/8cCe//qAo//3AAGAdj/ywJ7"
"/+8Cj//aApL/6QKT/9sClP/pAAECVP/GAAECVP+9AAoBGgAKARsADQEeAAQBIAANASIABwEnABEB2gABApL/7QKU//QCmv/UAAsA"
"/wAAAQEAAAEWAAEBHQABAR4ABwEiAAwBPAAAAWEAAAFoAAABaQAAAWoAAAAhANgACgDZAAoA9gAKAPkABgD6AAkBDP/0AQ0ACAE3"
"AAkBPwAJAVUAAQFc//QBYQAFAXT/5AF7/98Bs//eAcb/9AHH//QByP/0Acn/9AHK//QCK//rAiz/7QIy/9UCOP/NAj3/1wI+/98C"
"TAAHAlT/xwJY/8oCYf/oAmP/6AJp/+oCbf/lAA4ATP/tAIP/iACG/4gAh/+IAb8ABwHT/+8B2P/FAkD/+QJTAAYCYf/ZAnv/6gKP"
"/90Ckv/sApr/3wABAlT/xQAIAWEAAgIr//ACLP/wAj3/4QI+/+oCVAAGAmL//AJp//8AAQJU/8EAAQCD/4gAAgG/AAcCVP/GAAwA"
"TP+yARoADAEbABEBHgAGASAAEQEqAAABzgATAdX/yAHaAAYCd//dAo//0gKV/+kACAEkAAQBqQAEAiv/+QIs//kCOP/5AlT/1AJW"
"/94CWP/cAAECVP/UAAECIP/FAAICIP+2Aib/vwADASQABAIg/7YCJv+/AAQBjwABAdj/0QJ7/+oCj//ZAAsBGgAJARsADQEnAA8B"
"2gAAAlT/7QJh//UCYv/8AmT//AJp//4Cav/+Apr/1AAHAR4ACgFPAAQBUwAJAVcAAQGFAAQCOP/zAlQADgADAIMAHwIhACECVAAd"
"AAIBGgAbAlMADgAUAEQAMwDvAAwBDAAFARMADAEWAAwBGwAjASgADAEqAAwBXAAFAboADQHGAAoBxwAKAcgACgHJAAoBygAKAiEA"
"IwIlACgCMgAgAlQAHwJpACsAAQEbAA0AAQIsAAQAAgJiAAgCaQAKAC0APwA1AFgAKwB1ACsAmwAvAOoABwDvAA0A8gAHARMADQEg"
"ACUBJAANASgADQEpAA0BKgANAS0ADQFPAA0BVwAKAVwABgF0//wBhQANAakAEAG6AA0BvQANAcYAFgHHABYByAAWAckAFgHKABYB"
"ywAWAcwAFgIhACkCJAAyAiUANQInADQCKAA1AjAAKgIyACkCPf/wAlQAHAJhACcCYgAzAmMAJwJkADMCaQA2AmoANgJuADAABAEk"
"AAYBdP/8AiwABQI9//EADwETAAcBIgAYASgABwIhACQCJAAkAiUAJwImACQCJwArAjAAIAIyABoCVAAeAmIAIwJkACMCaQAsAmoA"
"LAAJARoACQEeAAQBIAANASQABQHaAAACLP/+AjgACQJPAAYCVP/6AAsBFAAHARoADAEeAAoBIAAZASEABQFXAAEBqQAFAdgAFQHa"
"AAICLP/+Aj7//AABAScAMAAKAbr/+wG//+AB1f/BAkAABAJT//ACd//gAo//oQKS/9oClf/DApr/mwANARkABAEaAAoBGwANAR4A"
"BAEgAA0BIgAHAScAEQHaAAECMAAAAlMAAAJ2AAAClP/0Apr/1AADAVcANgGpAFcCQgCxAAIBIAANAiwABAASANj//wDr//8A8P/9"
"APb//wD6//0BCv/9AQ0AAAE3//0BOP/9AVUAAwFhAAIBdQAEAYb//wIr/+MCLP/kAj3/0wI+/9sCVP/XAAgBef/qAc7/3gHT//sB"
"2P/RAnv/6QKP/9kCkP/ZApr/1wAMACEAJgCG/5oAh/+aAc7/3QHY/9ECQAABAnYABQJ7/+oCfv/NAo//2QKS/+kCmv/XAAEAo//B"
"AAECWP/uABAATP/oAKX/dgDF/3YBMQAAAV0ABAG6AAIBvwAGAdP/6QHY/8MCQP/xAlMABgJi/+MCe//oAo//3AKU/+wCmv/dAAEB"
"vwAGAAoBFgABAiv/6wIs/+0CMv/HAj3/1wI+/+ACVAAEAmL/+QJm/94Caf/9AAEAIgArAA4BFgAbARwAGwEwABoBMQAaAVwADQFh"
"ACABpQAbAacAGwIr//QCLP/1Aj3/3QI+/+UCVP/zAmkAHQAKAPAAEwEWABsBHAAbATAAGgExABoBTgAaAVwADQFhACABpQAbAacA"
"GwAJAPAAEwEWABsBHAAbATAAGgExABoBTgAaAVwADQFhACACVP/zAAwBFgAbARwAGwEwABoBMQAaAaUAGwGnABsCK//0Aiz/9QI9"
"/90CPv/lAlT/8wJpAB0ADQEWABsBHAAbATAAGgExABoBpQAbAacAGwIr//QCLP/1Ai0AGQI9/90CPv/lAlT/8wJpAB0ACQEWABsB"
"HAAbATEAGgGlABsCK//0Aiz/9QI9/90CPv/lAlT/9AABAlT/2AACAIP/vQJU/8EAJQDYABIA7wAJAPYAEgD5AA8A+gAPAQwAAAEN"
"ABABJAAJASgACQEqAAkBMAAJATEACQE3AA8BSwAPAU4ACQFRAAkBVQAIAVwAAAFhAA4BdAAAAXv//QG6AAsBwAAMAcYAAAHHAAAB"
"yAAAAckAAAHKAAACIP/KAiv/9gIs//gCOP/WAj3/3wI+/+cCTAAHAlT/yAJY/74ABwBM/+oBugABAdP/7AHY/8cCQP/1Anv/6wKP"
"/9wACQEkAAUB2gAAAiwABAI4AAoCPv/9Ak8ABwJU//MCVv/5Alj/+AAQAEz/kAGO//QBv//3AdX/zAHaAAMCFv+tAhf/vQIY/70C"
"Gf+eAhr/0QIb/7MCQAAEAnf/2AKP/9MClf/pApr/zQAKAPL/6wD2/+0BVf/2AVf/+gFcAAUCK/+WAiz/lwI9/44CPv+VAkz/4wAV"
"ANj/7ADZ/+0A8P/rAPL/7AD6/+sA/f/rARYAAAE3/+sBVf/2AVwABQFhAAMBcgADAYn/9AGK//UCK/+WAiz/lwIv/4QCPf+OAj7/"
"lQJB/4ACTP/jAAwBKgAAAXb/6gGQAAQB2P/OAi0AAQJAAAACUwABAnv/6QKP/9ICkv/sApT/8wKa/88AAwEgAAoCVP/VAlj/2AAB"
"AlT/wwAdANgABgDwAAcA9gAGAPoABwEM/+oBDQAHATcABwFVAAIBXP/oAWEAAwF0/+UBdf/tAcb/6wHH/+sByP/rAcn/6wHK/+sB"
"y//rAcz/6wIr//MCLP/1Aj3/6AI+//ICTAAEAlT/vgJY/8kCYf/fAmP/3wJq/+YACwEaAAIBIAAFASEAAgG///YB1f/cAdoAAwIu"
"AA0CQAAQAo//ygKS/+sClf/gAAMBXQADAiD/uwIm/74AHwDY//YA2f/2AO8AHgD2//YBDAALARMAHgEWAB4BJAAgASgAHgEqAB4B"
"N//1AVwADwHGABoBxwAaAcgAGgHJABoBygAaAisABQIsAAUCLQAOAjAAMAIyABoCTP/YAlQAIQJhACICYgA0AmMAIgJl/9MCZ//T"
"AmkANAJqADQAAwCG/9UCLAAWAlQACwACAIf/0QJU/+YAAwHaAAACQv//Apr/1AABAIP/ywADAXT//AI9//ACVP/jAAUBJAAGAakA"
"BgIsAAUCVP/tAlj/9AAIAEz/lwBO/5cBHv/8AZb/3gHV/8YB2gAEAnf/1wKP/8gABQBM/7UB1f/XAdoABAJ3/94Cj//RAAsB1P/x"
"AdX/vgHW/+kB2f/uAdr/7gJT/+sCd//bAo//owKS/9cClf/EApr/ngAQAEz/igCl/7cBGv/0AVP/9AG//+UBwv/mAdX/twHa//wC"
"Ff+kAhf/rgJT//ICd//QAo//wAKU/94Clf/bApr/vQAGAQD/0gIg/7sCJv+mAiv/twIsAAcCVAAHAAYBv//wAdX/3gHaAAQCQAAP"
"Ao//zQKV/+IAAwEWAAABIAAQAlT/4QAEAIP/jgGm//wB2P/LAkD//gABAVz/6QACATD//AEx//wAAQEx//wAAQGz/9IAAgEx//wB"
"s//SAAECVP/tAAMBpgAQAlT/6QJY//cAAQEqAA0AAQI9//EAAwEgABABqQAFAj7//AAHAPAAEwExABoBTgAaAVwADQFhACABpQAb"
"Aj3/3QAEAEz/igDF/7cBqf/0AdX/tQADAj3/kgI+/88CVP/pAAICPP/YApL/zwAXANgAEADvAEEA8gAXARMAQQEWADQBJABBASgA"
"QQEwACUBMQAlATMAJwE3AAYBUQAlAVUAGQFXACoBXAAdAWEAIgFiACIBdAAdAkz/4wJUAFUCYQBlAmkAgQJqAIEABQDY//kA+v/3"
"AQr/9wE3//cBOP/3AAIATP+aAhn/oQADAVwABwIr/6ECLP+iAAsA2P/tANn/7QD6/+kBFgAJASgACQE3/+sCK/+hAiz/ogI9/5kC"
"Pv+hAkz/4wAPAEz/sgDu//AA+f/jAUv/6AFPAAcBqQALAc4AEwHV/8gB2gAGAi//qwIwAAgCNgASAk//tQKP/9ICm/+/AAoAg//0"
"AVMACgF6//0BqQAAAboAAQJE/+0CWP/9Apr/1AKb/80CnP/FAAcBTwAAAakAAAHaAAICWP/9ApT/9AKb/80CnP/KAAkAg//SAjz/"
"2AJE/8sCSv/QAlj/5wJu/9cCcP/XApv/oQKc/6IAAwI9/4MCPv+JAlT/4wAFAjj/fQI9/4MCPv+JAkz/twJU/+MAAQHPAAMADwHP"
"AAYB0AAEAiD/vwIm/78CKwACAiwAAgItAA0COP/5Akz/5QJU/88CVv/QAlj/1AJq//wCff/DAo7/0AAfAAH/zwAZAAYAP//mAEz/"
"2QB8//0Ag//YAJv/0ACc/+QAof+6AKL/vwCj/78A2AAEAPAABAD2AAQA+gAEAQ0ABAEaABQBVf//AVwAAAF6/+IBzQAEAc7//wIo"
"//cCL//RAk//nQJW/74CXv/KAo//3QKQ/9wCm//XApz/ywAIAAH/8wEaABsBVf/9Ac4AAAHTAAACj//SApD/2AKb/8kAEwAZ//cA"
"Nv/3AF7/9wCD/+MAm//ZAJz/5gCi/9EA2P/zAPD/8QD2//QA+v/xATH//wHNAAEBzgADAlb/5AKP/8UCkP/YApv/rwKc/8sAEQAB"
"/+EAg//lAJv/2wCh/9QAov/UANgABAD6AAUBGgAfAVz/8wF6/+8Bzf/7Ac4AAAJW/80CXv/iAo//ygKQ/+UCm//DACYBzf+pAgP/"
"swIE/64CBv+8Agf/qQII/7oCCf+2Agr/ugIL/70CDP+5Ah//lAIg/44CIf+3AiL/pAIj/6ACJP+fAiX/lwIm/6ICJ/+jAij/ngIv"
"/+ACOf+HAj//2AJA/+ACRP+OAk//tgJW/6wCXv+7AmL/ogJp/6wCbv+XAnD/ogJ7/8ICff96Ao//ygKQ/9oCm//JApz/fQAeAAH/"
"3wAZAAEANgABAIP/7QCh/+IA2AAFAPAABwD2AAUA+gAHAQz/4wENAAUBXP/fAXT/3QF6/9YBe//UAcb/4wHH/+MByP/jAcn/4wHK"
"/+MBzf/sAc7/7gI//+cCQP/wAk//sgJW/+MCj//XApD/3AKb/9ICnP+bABMAAf/cAIP/5wCb/9sAof/MAKL/0gDYAAUA9gAFAPoA"
"BQEaABkBXP/wAXr/6AHO//wCP//xAk//rwJW/8kCXv/gAo//1QKQ/+ICnP+5AA4BGgAgAc//4gIv/2cCP//fAkD/5gJP/1YCU//k"
"Aoj/zgKP/6cCkP/PApP/yAKV/8ECmP+6Apv/jAAOAAH/5ACD/+MAm//ZAJz/4gCi/9IA2AAFAPoABgFc//MBzv/+Alb/0AJe/+MC"
"j//IApD/5QKb/8IADgHNAAUCIP/WAib/2gIv/9QCOf/IAj///gJAAAECT/+fAlMABgJW/8ECXv/SAn3/2QKP/9wCkP/fAAsCMv+B"
"AkT/gwJU/7oCYf+tAmL/sgJk/74Caf+2Amr/uAJt/5oCbv+oAn7/ggAJAfn//QH6//oCMv+FAkT/hQJU/8QCYf/LAmL/1wJk/9sC"
"fv+uAAgCMv+EAmH/sgJi/7gCZP/CAmn/ugJq/7oCbf+iAn7/jAAKAjL/gwJE/4YCVP+/AmH/tQJi/7wCZP/GAmn/uwJq/7wCbf+l"
"An7/kAAMAjL/ggJU/8ICYf+VAmL/mwJk/6kCaf+SAmr/ogJt/40Cbv+PAn7/eAKO/6UCj/+mAAYCMv+GAlT/vgJh/8QCYv/MAmT/"
"0wJ+/64ACgIy/4ECRP+EAlT/vAJh/7MCYv+6AmT/xQJp/7wCav+9Am3/pAJ+/44ABwIy/38COP+2AkT/fAJU/7ICYf/dAmL/5QJ+"
"/7gACgIy/4MCRP+GAlT/wAJh/7MCYv+6AmT/xQJp/7sCav+7Am3/pAJ+/48ACQIy/4ECVP+7AmH/rwJi/7QCZP/AAmn/uAJq/7oC"
"bf+dAn7/hgABAg3/+wABAg3/7gAOAfn/4wH7/+0B/f+/AgH/7AIV/9MCFv/fAhf/3QIY/90CGf+wAhr/6wIb/9QCHAAFAh3/3AIe"
"/9wAAQJU/8QAAgIV//0CFv/7AAcAg/9SAJv/igCc/7EAov9TAVz/zQF1/9ACVP/bAAUAg/9WAJv/iwCc/7IAov9WAlT/zgALABn/"
"1AA2/9gAXv/UAIP/VwCI/9oAm/9xAJz/nwIW/9QCTP/FAlT/0QJY/8oAAwCD/1cAnP+7AlT/zQAEAIP/VgCc/7MCVP/KAlj/zAAD"
"AD//ywIZ/9oCVP+yAAgAAf+BAg3/ygIr/40CLP+NAjj/dgI9/4MCVP/mAmX/sAAHAAH/kgIN/+cCK/+NAiz/jQI4/4cCPf+FAj7/"
"iQAFAg3/3AIr/40CLP+NAjj/ggI9/4MABQIN/9cCK/+NAiz/jQI4/38CPf+DAAUCDf/VAiv/jQIs/40COP99Aj3/gwALAAH/WwAZ"
"/70CDf+rAiv/jQIs/40CLf/BAi7/wQI4/00CPf+DAmX/eAJn/3wABQIN/9wCK/+NAiz/jQI4/4ECPf+DAAUCDf/MAiv/jQIs/40C"
"OP93Aj3/gwAPAc3/jQIg/40CIf+NAiL/jQIj/40CJP+NAiX/jQIm/40CJ/+NAij/jQIrAAACU//yAlb/1QJZ/+QCav+eAAoCIP+N"
"AiH/jQIi/40CI/+NAiT/jQIl/40CJv+NAif/jQIo/40Cav+eAAQBzwAJAlMAAQJW/9UCWQABAAMCIP+/Aib/wQJU/98AEACE/3AB"
"Xf/OAiD/cQIh/zgCIv83AiP/LQIk/zQCJf8uAib/NQIn/zACKP8uAlP/6gJZ/9wCY/+NAmT/jQJq/54ABwIw//8CVP/qAmH/9wJl"
"/9sCZv/7Amf/2wJpAAAABQIw//oCM/+gAjv/oAJW/9QCXv/TABsAAf/lABn/6wBe/+sAdf/3AHf/6wB8AAMAg/+HAJv/jQCc/68A"
"ov+FAPAAAgEM/8oBUAAEAVz/xgF0/64Bdf/GAXv/ogHG/8oBx//KAcj/ygHJ/8oByv/KAdL/iwHY/44CVP+4AmH/fAJp/4UADgAB"
"/4MATP+EAKH/1gDY/8EA8P+6APb/wQD6/7oBDf/DATf/uwFO//IBUP/BAVX/ygFcAAMBif/DAA0AAf/ZAD//6wBM/+IAg//hAJv/"
"2gCh/7oAov/FAdL//gHaAAUCK//jAiz/5AI9/9ICVP/IABoAcv+8AO7/mgD5/64BGQAfASAALAFL/5UBz//CAhb/igIZ/2QCHf+B"
"Ai//YQI3/9ECT/9XAlP/wgJg/2wCbP9qAoX/qwKH/8cCiP+wAon/yQKM/5gCj/+QApz/mgKd/7ACn/+NAqL/nwAoABn/uAA2/7oA"
"Xv+4AHf/uAB8/84Ag/9qAIj/uQCb/1EAnP+LAKL/TQDY/9EA8P/OAPb/0QD6/84BDP/CATf/zgFc/60BdP+CAXX/mgHG/8IBx//C"
"Acj/wgHJ/8IByv/CAdH/vgHS/4kB1//EAdj/qwI2/3kCOf9CAmH/ggJi/4gCY/+XAmT/lwJl/6sCZ/+rAmn/fgJq/6QCbf+AAm7/"
"gQAHABn/6wB3/+oAg/+FAJv/jACi/4QCYf97Amn/hAATAKL/iQGp//kBzf+DAiD/hQIh/4MCIv+DAiP/gwIk/4MCJf+DAib/gwIn"
"/4MCKP+DAkT/kAJT/+ECVv+8Aln/zwJp/4MCbv+DAnD/iQACAm7/iQJw/4kAAQJT//wAAwJM/88CVP/YAmn/9AAQAIT/ZgIg/3EC"
"If83AiL/NgIj/ywCJP8zAiX/LQIm/zQCJ/8vAij/LQJE/4ECU//hAmn/NAJt/xUCbv8VAnD/iQADAkIABwJU/+wCZf/cAAICRf+j"
"Am4AAQAKABn/5QCD/4gAm/+KAKL/gwDA/+UBXP/AAXT/qgGz/5YCaf+FAm3/fQAFAIP/iACb/4oAov+DAmn/hQJt/30AJwAhABoA"
"Pf/fAFYABQByAAAAdv/2AIb/ZgCk/3cApf93AKb/dwCn/3cAxf93AMb/dwEvAAoBSwAGAc///wIH/9kCIP+sAiL/yQIj/4ICJP/F"
"AiX/vgIm/8ACJ//JAij/xQI//88CQP/VAkT/fgJM//sCUwADAlb/mQJf/74CYP+pAmP/2QJk/+gCav/GAmz/pAJu/7sCcP/PAof/"
"7AAKAIb/XAIg/64CI/+GAiT/xwIl/8ECKP/HAkT/fgJNAAACYP+rAmz/pAALAiD/rgIj/4YCJP/HAiX/wQIo/8cCQP/WAkT/fgJg"
"/6sCZP/oAmz/pAJu/74AAwFOAAcCTwAaAm7/SQAIACEAJgA9/+AAdv/2AIb/cgCk/44CXv+fAmD/WgJs/2MAAwCG/3ICYP9cAmz/"
"ZQACAmD/XAJs/2UATAAh//MAPf/fAFb/wQBm/78Acv/BAHT/uAB2/+gAzAAeAOb/vgDo/7kA7v+/APL/xAD5/70BFQAeARkAHgEa"
"AAsBIAAdASEAEQEnAEUBL//VAT//vwFL/9ABTv/zAU8AAAFX/9gBW//CAV3/wAFl/8ABdv/CAXn/wgGF/+cBpf/rAakAHwG//9MB"
"z//wAgf/ugIuAAoCL//MAjP/tgI3/8kCP//JAkT/ygJF/7YCU/+6AmAACgJs//4Cbv/qAnD/5wJ2/7YCd/+5Ann/xgJ6/7oCfP+6"
"AoH/tgKD/+cChf+vAof/vwKI/60Cif+7Aoz/yQKP/40CkP+cApH/kgKT/5sClP/AApX/mgKW/9wCl/+uApj/rQKZ/4oCmv+MApv/"
"fQKc/4gCnf+0AqL/swKl/50AEgAB/+IAg//XAIT/2QCb/8sAnP/eAKL/vACj/7wA2AAGAPYABgD6AAYBNwAGAXT/9gF7//MCP//8"
"AkAAAAJTAAYCVv/WApz/xQAPAU7/+QHR/74B0v/QAdP/5AHU/8oB1f+iAdf/vgIr/9MCTP+ZAlP/1QJl/4wCZv+kAo7/gAKP/4MC"
"nP+NAAYCK//OAiz/1AI9/74CVP/CAlb/zAKc/5UAEwBy/74A7v+4APn/uQEVABsBJwBFAUv/1wFO//gBV//YAakALAIv/84CM/+r"
"Ajf/wwJF/6sCU//VAnb/sAKP/4ICm/93Apz/igKd/6gAEgBW/8cAcv/OAHT/vwI3/9MCO//OAln/xAJg//QCbP/uAnb/xwJ5/9AC"
"h//GAoj/twKP/5MClf+jApj/ywKZ/5ICm/+EApz/igACAIP/4AJe/94AAwAZ/7kB0v/AAo7/fAAPABn/ugAd/7sANv+9ADn/vQBe"
"/7oAd/+6AHz/1wHS/8YB1P/dAdX/tAHX/8oCUP+dAo7/fAKS/6oCm/9zAAwAVv/JAHL/0gB2//IAg/+VAIX/lQCb/5gAnP+mAKL/"
"jgF0/50Bdf+3Akz/vgKP/40ADwBW/8cAcv/SAHb/8gCG/10BIQADAU7/+QFb/7gCN//eAlP/7gJh/xsCYv8bAoj/pQKP/1gCkf9r"
"Apn/sgALACEABgEgADQBJwAVAc//9gIv/xsCM/+nAjv/pwJP/0cCYP8bAo//vwKb/7EABgDu/7YBS/+pAV3/6QIv/xsCU//hApv/"
"hgAOAAH/nQAR/50AE/+eABX/nQAX/50ATP+bASAANAFL/9cCL/+NAjP/sgI7/7ICTP/ZAk7/2gJg/40ADAB0/+MA6P+5AO7/uAD+"
"/8cBFAAOARoAHwEeABEBIAAtASIAIwFL/7ACL/+NAmD/jQAJACEABQBW/9UAhv/HAUv/3wIg/7ECJv+aAi//8AIz/+gCVv+uABEA"
"IQAPAIP/gAIg/5sCIv/BAiP/uQIk/7wCJf+0Aib/sQIn/8MCKP+6Ai//tQI//8YCQP/MAkT/mwJW/4wCXv+gAl//uQAEAIb/zAIg"
"/7ECJv+aAjP/6AAMAiD/mwIi/8ECI/+6AiT/vAIl/7QCJv+xAif/wwIo/7oCL/+1Aj//xgJA/8wCX/+5ABEAIQAIAFb/3ADu/9oB"
"FAAaARoAJAEgADQBJwAkAUv/1AHP//cCL/80AjP/qgI7/6oCQf80AkX/rwJP/0cCU//zApv/rAALAO7/2gEUABoBGgAkARsAKgEe"
"ABIBIAA0ASIALgIv/54CM/+uAjv/rgJF/7MABQCD/5UAm/+ZAJz/owCi/48BdP+aAAkAVv/EAHL/zgB2//IAhv9lAm3/FQJu/xUC"
"cP+JAo//XgKl/4wABAJB/xUCRf+cAk//SQJs/xUABQFL/6QCP//UAkD/2QJB/xUCm/9/AAQAAf+dAEz/nAJF/6cCbP+JAAoAdP/e"
"ARoAIAHV/5oCPf+JAj7/iQJB/4kCTP+sAlT/5AJl/5oCZ/+aAAwAAf++AD//1gBM/78Ag//GAJv/wwCc/94Aof+ZAKL/owCq/9QA"
"9gADAQ0AAwJU/7cABwHS/54B2P+uAlT/wAJh/6oCYv+uAmT/vwJp/6YABQBM/84Ag//MAKH/pQCi/6oCVP+3AAgCK/+NAiz/jQI4"
"/4MCPf+DAj7/iQJU/7sCWv+/An3/2wACAKL/qgJU/7cACQIr/40CLP+NAjj/ggI9/4MCPv+JAkz/vAJU//ACZf/AAmf/wAALAAH/"
"fAAZ//AAI//1ADX/9QBM/34AWP/1ANj/xgDw/74A9v/GAQ3/xwE3/74AAQJU/7oAAwHV/+cB2gACAlT/ywAHAiD/uwIm/7QCK//A"
"Aiz/wAI4/68CVP+yAlj/ogANAdL/5wHT//kB1P//AdX//AHW//0B1//9Adj/6wHa//oCK//qAjj/zQJU/70CWP/DAlr/ygAIAdL/"
"8wIr/9sCLP/cAjj/vwI9/8kCPv/PAlT/uwJa/8UAEAHS/4kB0//CAdj/fgIg/6YCIv+6AiP/fAIk/7cCJf+yAib/uQIn/7kCKP+3"
"AjL/gQI4/7ACVP+kAmn/vQJq/8IAAgHV/7ECOP+/AAYB0v/vAdX/9QHX//UB2P/uAdr//AJU/8wADwHR/6kB0v/CAdP/sgHU/7cB"
"1f+fAdb/1AHX/6oB2f+4Adr/tAIj/7kCK/+bAiz/mwIt/6gCLv+nAjj/hQAHAgT/nQJW/4ACXP99Al7/fQJu/7kCh/+5Ao3/kAAZ"
"AAH/kAAY/8sAGf/aADz/ywA//3gATP9yAFj/ywB8/7oAg/9jAJv/kgCh/1sAov9vAKr/ggDY/9gBKv/QAXX/yQF6/58Be/+6Ac//"
"1QHQ/80CBP+ZAgr/pgKH/7ICi//FAo3/iwAZAAH/qwAY/9MANf/TADz/0wA//8IAWP/TAHX/0wB8/98Ag/+1AJv/qgCi/5YBMP/X"
"ATH/1wFO/9cBVf/OAdL/1AHT/9gB1P/fAdX/1wHW/9wB1//aAdj/0wHZ/98CVP+UAlr/nAAIAD//eACi/3QB0v+7AdP/tAHU/6QB"
"2P+4AlT/iQJa/5IADwAB/7oAGf/xADb/8QA//88ATP+/AF7/8QCD/74Am/+7AJz/0QCh/5sAov+lAKr/0AFV/+oBev/YAo3/pgAF"
"AAH/rQCi/6UA7//fAdH/4gJU/5wAEAAB/6YAP/+lAEz/nACD/48Am/+mAJz/xQCh/3gAov+GAKr/rQF6/8QBg//YAdL/yQHT/8kB"
"2P/FAlT/mgKU/8EAAwHU//kCVP/AApX/wQAKAIP/gAHR/8MB0v+rAdP/xQHU/7UB1f+1Adj/qgHZ/7gCU//EAlT/kAACATH/2gJU"
"/7oACgHR/90B0v/BAdP/4AHU/9EB1f/QAdb/3gHY/8MCBP+tAgr/rAJU/6cADAAB/5AB0f/SAdL/ywHT/8gB1P/NAdX/0AHW/88B"
"2P/JAdn/0AJT/9MCVP+JAlr/jwAWAAH/rAAY/8gAdf/IAIP/VwCb/4YAof+WAKL/YQD2/9YBDP/BASr/zgEw/84BMf/OAVH/zgFV"
"/9IBXP/BAXr/mwF7/64Bg//DAdL/pgHT/7wB2P+lAlT/hQAGAjD/xAJC/8QCRP+xAlP/1AJe/3QCbv+0AAQBz//CAjD/xAJT/74C"
"Xv+DAAMCVP+0Alj/pwJa/74ABwAB/50A2P+tAPb/rQD6/6sBVf+uAYn/qwKf/7QAAQJT/+oACQAB/3IA2P+yAPD/rgD2/7IBDf+y"
"AVX/tgF6/8YB0P/cAdX/mAAMAiD/qgIh/8cCIv+rAiP/gQIk/6YCJf+jAib/rgIn/6kCKP+rAkT/igJu/6gCcP+rAAsCMv+BAjb/"
"bwJE/4QCVP+8Alr/2AJh/5ECYv+ZAmP/ogJk/6oCbf9+Am7/hgAKAD//dgCi/00B0v+ZAdP/hgHU/6IB2P+TAlT/dwJa/38Cbf+e"
"Am7/nQACYrQABAAAZEpoVgBrAHYAAP/9AAAAAP/2AAAAAAAA//7//v/4AAAAAP/8//8AAAAB//QAAP/bAAAAAAAA//0AAP+m//8A"
"AP/5//D/8f/x//P/8AAA//3/9P/3AAP/twAAAAD//f/8////8gAA/7n/8QAA//L/9AAA/8QAAAAA/+r/6P/k/+3/1gAAAAD/+wAA"
"/8MAAAAA/7j/7f/vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/+gAA//MAAAAA//v//gAA//X/+QAAAAD/+//+/8r/"
"x/+9//L/zf/EAAAAAAAA/+3/xAAAAAAAAAAAAAAAAAAA//T/yv/aAAT/3P/Z/9//y//sAAD/9v/2/8H/7v/H/83/jv/o/5T/3QAE"
"//YAB/+4/1//of+2/8z/lf+d/4z/if/1AAD/6v+4//v///94//kAAAAB/40ACf+ZAAAAAP+M/+H/9/+EAAD/fwAA//oAAAAA/4r/"
"jf+WAAAAAAAE/+r/zAAAAAD/gv+a/4kAAP+YAAD/pgAAAAD/9v/7//YAAAAA//oAAAAAAAAAAP+O/93/igAA/8cAAAAAAAD//v+N"
"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"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA4AAAAAABEAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/jQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/jQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACwAAAAAADAAAAAD/+QAAAAAAAwAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+NAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+NAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//b/9v/8//f/9gAA/+z//P/6//H/"
"9P//AAAAAAAAAAAAAAAAAAAAAAAAAAD//P/vAAAAAAAA//0AAAAAAAAAAP/3/9EAAAAA//b/9f/oAAAAAAAA//oAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/+gAAAAAAAAAAAAD/6QAAAAAAAP/1//YAAP/3AAAAAP/8AAAAAAAAAAAAAAAAAAAA"
"AAAAAAAAAAAAAAAAAAAAAAcABP/RAAQABAADAAIAAP/rAAAAAP/9AAMABAAH//3//v/m////+wAA/+kABP/G//8ABQACAAD//f/6"
"//r/yf/9//T//P/P////3gAAAAb/5f/+AAAAAP/8AAAAAP/8/8AAAAAFAAD/+gAAAAAAAAAA//P/3gADAAD/2//E/70AAAACAAD/"
"/AAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAgAEAAAAAP/zAAAAAAAC//b/2gAA/8AAAAAA//4AAAAA"
"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"
"AAAAAP9bAAUAAAAA/40AAP/HAAAAAAAAAAD/0v/d/+7/1f+8/+D/6v/qAAH/+QAA/5UAAP/8/+j/4P+h/+D/3//rAAH/1wAE/+T/"
"///q/+D/6P/o/+r/2gAF/+7/z//+//r/5gAF/+7/5//fAAP/9P/3AAT/iQAA/9z/1f+P/90ABgAQAAD/1P/r/1YAAAAAAAD/9//w"
"/4oAAAAAAAAAAP/aAAAAAP/u//T/vgAAAAD/kv/v/+7/3wAAAAH/+AAAAAD/vwAA/9cAAAAAAAAAKQAVAAAAAAAZAAAAAAAAAAD/"
"6//T//0AAP/oAAAAAAAA/3D//AAAAAD/kgAA//wAAAAAAAAAAP+z/9b/1QAA/+sABQAGAAb/5//lAAD/pwAAAAD//QAG/+QABQAG"
"AAIAAQAB//v//wAB/+0AAv/z//7/7AAC/+UACP///////v/y/9X/8f/u//r/8v/0//L/9//nAAD/9v/x/+4AAf/nAA4AAP/v/+7/"
"v//qAAAAAP/rAAj/2f/2AAD/2QAA//0AAAAA/+//8//JAAAAAP/y/9T/yAAFAAD/3P/3//EAAP/JAAD/5AAAAAAAHwAqAAMAAAAA"
"ACEAAAAAAAAAAP/2AAn/8gAA//MAAAAAAAD/7v/1AAAAAP/zAAD/0AAAAAAAAAAA/8EABQAG/9X/2P/c/+f/5//7//MAAP/xAAIA"
"QwABADwAAAA/AE0APABPAFIASwBUAFQATwBWAFgAUABcAFwAUwBeAGkAVABwAHUAYAB3AIEAZgCDAIMAcQCFALoAcgC8AL4AqADB"
"AMkAqwDYANoAtADgAOIAtwDmAPcAugD6AQEAzAEDARgA1AEaARoA6gEcARwA6wEeAR4A7AEjASQA7QEmASoA7wEsASwA9AEwATwA"
"9QE+AUIBAgFJAUoBBwFMAVEBCQFUAVoBDwFcAVwBFgFfAW4BFwFwAX4BJwGAAYYBNgGJAYwBPQGRAZMBQQGXAaMBRAGlAaUBUQGn"
"AacBUgGpAakBUwGrAa0BVAGvAbYBVwG4AbsBXwG9Ab0BYwHAAcABZAHDAcMBZQHGAc8BZgHRAdoBcAIIAggBegIKAgoBewIhAiIB"
"fAIrAi8BfgIyAjIBgwI2AjYBhAI4AjgBhQI9Aj8BhgJBAkEBiQJEAkQBigJMAlUBiwJXAlcBlQJZAloBlgJfAnABmAJ3AncBqgJ+"
"An4BqwKOAo8BrAKSApIBrgKbApwBrwKjAqMBsQACAKwAAQAWAAEAFwAXAAIAGAAYAGoAGQAeABEAHwAiAB0AIwA0AAIANQA1AGkA"
"NgA7ABAAPAA8ABgAPwA/AAgAQABAABwAQQBLAAgATABNABwATwBQADQAUQBSABsAVABUABsAVgBWABsAVwBYABgAXABcABgAXgBp"
"AAQAcABzAAQAdAB0AAIAdQB1AGgAdwB3AAQAeAB7ABoAfACBABUAgwCDABkAhQCHABkAiACPAAcAkACVAA8AlgCaAAcAmwCbAGcA"
"nACgABQAoQChAGYAogCpAAsAqgCtABcArgCxAAEAsgCyABEAswC2AAIAtwC3ABAAuAC6AAgAvAC+AAQAwQDCAAcAwwDDAA8AxADE"
"ABQAxQDGAAsAxwDHABcAyADIABgAyQDJABwA7gDuAAMA7wDvACMA8AD1AA4A9gD2AAwA9wD3AF0A+gEBAAMBAwELAAMBDAEMAFgB"
"EwEVAAoBFgEWAAwBGAEYAC0BGgEaACwBHAEcAAwBIwEkAAwBJgEmAC0BJwEnACwBKAEpACsBKgEqAAwBLAEsAFMBMAE2AAoBNwE8"
"AAUBPgFCAAUBSQFKAAUBTAFMAAUBTQFNAAMBTgFPACMBUQFRACUBVAFUACUBVQFaABMBXAFcAB4BXwFgAB4BaQFuAA0BdAF0ADcB"
"dQF5ABIBegF6ADYBewF+AAkBgAGCAAkBgwGGABYBiQGMAAYBkQGTAAYBlwGeAAYBnwGfAA4BoAGjAAMBpQGlAAwBpwGnAAwBqQGp"
"AAwBqwGtAAUBsQGxAA0BsgGyABIBswG2AAkBuAG4AAkBuQG5ABYBugG7AB8BvQG9AB8BwAHAACQBwwHDACQBxgHGAFcBxwHHADIB"
"yAHIADEByQHJADIBygHKADEBywHMADABzQHNAE8BzgHOAE4B0QHRADUB0gHSAFAB0wHTADoB1AHUADwB1QHVAFQB1gHWAFYB1wHX"
"AD4B2AHYAEAB2QHZAFsB2gHaAFECCAIIAFUCCgIKAD8CIQIhADkCIgIiADsCKwIrAEgCLAIsAF4CLQIuADMCLwIvAFoCMgIyACkC"
"NgI2AGICOAI4AD0CPQI9ACoCPgI+ACICPwI/AF8CQQJBACoCRAJEACkCTAJOACECTwJPADgCUAJSACACUwJTAE0CVAJUAEsCVQJV"
"AGECVwJXAGACWQJZAEwCWgJaAEoCXwJgACYCYQJhACgCYgJiAEUCYwJjACgCZAJkAEMCZQJlAC8CZgJmAC4CZwJnAC8CaAJoAC4C"
"aQJpAEYCagJqAEECawJsACICbQJtACcCbgJuAEQCbwJvACcCcAJwAEICdwJ3AGUCfgJ+AFwCjgKOAEcCjwKPAFICkgKSAFkCmwKb"
"AGMCnAKcAGQCowKjAEkAAgDSAAEAFwAEABgAGAABABkAHgACAB8AIAABACEAIgAoACMAJAABACcAKAABACoAKgABAC0AMAABADMA"
"MwABADUANQABADYAOwAQADwAPAABAD4APgABAD8ASwAKAEwATAB1AE4ATgB0AE8AUQABAFMAVQABAFYAVgBzAFcAXAABAF4AcQAC"
"AHIAcgByAHMAcwACAHUAdQABAHcAdwACAHgAeAABAHoAegABAHwAgQAUAIIAggABAIMAgwAnAIUAhQAnAIYAhgBxAIcAhwBwAIgA"
"mgAIAJsAmwBvAJwAoAATAKEAoQBuAKIAowAZAKQApABtAKgAqQAZAKoArQAXAK4AsQAEALIAsgACALcAtwAQALgAugAKALsAuwAB"
"ALwAwAACAMEAwwAIAMQAxAATAMcAxwAXAMgAygABANgA7QAFAO4A7gBsAO8A7wAMAPAA8QAGAPIA8gADAPMA8wAGAPQA9AADAPUA"
"9QAGAPYA+AAFAPkA+QBdAPoA+wAGAPwBBAADAQUBBgAGAQcBBwADAQgBCAAGAQkBCQADAQoBCgAGAQsBCwADAQwBDABbAQ0BEgAO"
"ARMBEwAMARQBFABUARYBFgAWARcBGAALARkBGQBTARoBGgBSARsBGwBRARwBHQAWAR4BHgBPASABIABOASIBIgBNASQBJABMASYB"
"JgALAScBJwBLASgBKAAMASoBKgAMASwBLAAMAS4BLgAMAS8BLwBJATABNgALATcBOAAGATkBPwADAUABQAAGAUEBQQADAUIBRQAG"
"AUYBRgADAUcBRwAGAUgBSAADAUkBSQAGAUoBSgADAUsBSwBCAUwBTAADAU0BTQAGAU4BTgALAVABUAAFAVEBUgALAVUBWgASAVsB"
"WwBVAVwBXAAYAV4BYAAYAWEBcwAHAXQBdAArAXUBdQAaAXcBeAAaAXoBegAqAXsBggANAYMBhgAVAYkBjQAJAZEBlAAJAZcBngAJ"
"AZ8BnwAGAaABoQADAaIBowAGAaQBpAAOAaUBpQAWAaYBpgBQAacBpwAWAaoBqgAMAasBrAADAa0BrgAGAa8BsQAHAbMBuAARAbkB"
"uQAVAboBugAMAbwBvAAMAb4BvgAMAcABwAALAcEBwQA3AcUBxQAMAcYBzAAPAc4BzgBDAdAB0AA9AdEB0QApAdIB0gBFAdMB0wAu"
"AdQB1AAxAdUB1QBYAdYB1gBaAdcB1wA0AdgB2AA2AdkB2QBhAdoB2gBHAg0CDQBWAiACIABEAiECIQAtAiICIgAwAiMCIwBXAiQC"
"JABZAiUCJQAzAiYCJgA1AicCJwBgAigCKABGAisCKwA/AiwCLABjAi0CLgAmAi8CLwBfAjACMABcAjICMgA7AjYCNgBoAjgCOAAy"
"AjkCOQBnAj0CPQAhAj4CPgAlAj8CPwBkAkECQQAhAkQCRAA6AkoCSgA+AkwCTgAcAk8CTwAsAlACUgAbAlQCVABBAlYCVgBmAlgC"
"WABlAloCWgBAAmECYQAfAmICYgAdAmMCYwAfAmQCZAAdAmUCZQAkAmYCZgAjAmcCZwAkAmgCaAAjAmkCagAgAmsCawAlAm0CbQAe"
"Am4CbgA5Am8CbwAeAnACcAA4AncCdwBrAn0CfQAvAn4CfgBiAo4CjgA8Ao8CjwBIApICkgBeApUClQBKApsCmwBpApwCnABqAqMC"
"pAAiAAQAAAABAAgAAQAMABYABQCwAZoAAgABAq4C0gAAAAIAGQABAFwAAABeAHUAXAB3AIEAdACDAO0AfwDvAPgA6gD6ATUA9AE3"
"AU4BMAFQAVoBSAFcAcUBUwHbAe4BvQIrAiwB0QIuAi4B0wI9Aj4B1AJAAkAB1gJfAl8B1wJjAmQB2AJrAmsB2gJvAnAB2wJ6AnoB"
"3QJ8AnwB3gKEAoUB3wKHAogB4QKNAo0B4wKSApIB5AKrAq0B5QAlAAAY0gAAGNgAABkgAAAY3gAAGOQAABjqAAAY6gAAGPAAABj2"
"AAAY/AAAGQIAABkIAAAZDgABAJYAAgCcAAIAogACAKgAAwCuAAQAtAAEALoABADAAAQAxgAAGRQAABkaAAAZGgAAGSAAABkmAAAZ"
"JgAAGSYAABksAAQAzAAEANIABADYAAMA3gAAGTIAABk4AAIA5AABACgCJAABAH0AAAABAIQAAAABALUAAAABAOkAAAABAN0CcAAB"
"AbQBGQABAK8BbgABAUQBFQABAPIBBwABAM8BbQABAVIBcQABAN0AAAABAIMAAAHoFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoU"
"IAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQU"
"AAAUGhQgAAAUFAAAFBoUIAAAExIAABQaFCAAABMYAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoU"
"IAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAATHgAAEyQAAAAAFGIAABQmAAAAABRi"
"AAAUJgAAAAAUYgAAFCYAAAAAFGIAABQmAAAAABRiAAAUJgAAAAAUYgAAFCYAAAAAEyoAABMwAAATNhMqAAATMAAAEzYTKgAAEzAA"
"ABM2EyoAABMwAAATNhQsAAAVcBQyAAAULAAAFXAUMgAAFCwAABVwFDIAABQsAAAVcBQyAAAULAAAFXAUMgAAFCwAABVwFDIAABQs"
"AAAVcBQyAAAULAAAFXAUMgAAEzwAABVwFDIAABNCAAAVcBQyAAAULAAAFXAUMgAAFCwAABVwFDIAABQsAAAVcBQyAAAULAAAFXAU"
"MgAAFCwAABVwFDIAABQsAAAVcBQyAAAULAAAFXAUMgAAFCwAABVwFDIAABNIAAATTgAAAAAUOAAAFD4AAAAAFDgAABQ+AAAAABQ4"
"AAAUPgAAAAAUOAAAFD4AAAAAFDgAABQ+AAAAABQ4AAAUPgAAAAATZgAAFCYAABNsE1QAABNaAAATYBNmAAAUJgAAE2wURAAAFEoU"
"UAAAAAAAAAAAFFAAABREAAAUShRQAAAURAAAFEoUUAAAFEQAABRKFFAAABREAAAUShRQAAAURAAAFEoUUAAAFEQAABRKFFAAABRE"
"AAAUShRQAAAURAAAFEoUUAAAFEQAABRKFFAAABREAAAUShRQAAAURAAAFEoUUAAAE3IAABN4AAAAABNyAAATeAAAAAATcgAAE3gA"
"AAAAE34AABOEAAAAABN+AAAThAAAAAAWfhRWFV4AABRcFn4UVhVeAAAUXBZ+FFYVXgAAFFwWfhRWFV4AABRcFn4UVhVeAAAUXBOK"
"E5ATlgAAE5wTogAAE6gAAAAAE64AABO0AAAAABOuAAATtAAAAAATrgAAE7QAAAAAE64AABO0AAAAABOuAAATtAAAAAAUYhRoFG4U"
"dBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwUYhRoFG4UdBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwTuhRoFG4UdBb8E8AUaBRuFHQW/BRi"
"FGgUbhR0FvwUYhRoFG4UdBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwUYhRoFG4UdBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwUYhRoFG4U"
"dBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwUYhRoFG4UdBb8FGIUaBRuFHQW/BPGE8wT0hPYE94UYhRoFG4UdBb8E+QAABPqE/AAABSq"
"AAAUsAAAAAAUYhRoFG4UdBb8FwIAABcIAAAAABcCAAAXCAAAAAAXAgAAFwgAAAAAFwIAABcIAAAAABSqAAAUsAAAAAAUqgAAFLAA"
"AAAAFKoAABSwAAAAABSqAAAUsAAAAAAUqgAAFLAAAAAAFKoAABSwAAAAABP2AAAT/AAAFAIT9gAAE/wAABQCE/YAABP8AAAUAhP2"
"AAAT/AAAFAIT9gAAE/wAABQCFHoUgBSGFIwAABR6FIAUhhSMAAAUehSAFIYUjAAAFHoUgBSGFIwAABR6FIAUhhSMAAAUehSAFIYU"
"jAAAFHoUgBSGFIwAABR6FIAUhhSMAAAUehSAFIYUjAAAFHoUgBSGFIwAABR6FIAUhhSMAAAUehSAFIYUjAAAFHoUgBSGFIwAABR6"
"FIAUhhSMAAAUehSAFIYUjAAAFHoUgBSGFIwAABR6FIAUhhSMAAAUehSAFIYUjAAAFHoUgBSGFIwAABRiAAAUbgAAAAAUkgAAFJgA"
"AAAAFJIAABSYAAAAABSSAAAUmAAAAAAUkgAAFJgAAAAAFJIAABSYAAAAABQIAAAUDgAAAAAUngAAFKQAAAAAFJ4AABSkAAAAABSe"
"AAAUpAAAAAAUngAAFKQAAAAAFJ4AABSkAAAAABSeAAAUpAAAAAAUngAAFKQAAAAAFJ4AABSkAAAAABSqAAAUsAAAFLYUqgAAFLAA"
"ABS2FKoAABSwAAAUthSqAAAUsAAAFLYUFAAAFBoUIAAAFBQAABQaFCAAABQUAAAUGhQgAAAUFAAAFBoUIAAAFGIAABQmAAAAABQs"
"AAAVcBQyAAAULAAAFXAUMgAAFCwAABVwFDIAABQsAAAVcBQyAAAUOAAAFD4AAAAAFEQAABRKFFAAABREAAAUShRQAAAURAAAFEoU"
"UAAAFn4UVhVeAAAUXBRiFGgUbhR0FvwUYhRoFG4UdBb8FGIUaBRuFHQW/BRiFGgUbhR0FvwUYhRoFG4UdBb8FHoUgBSGFIwAABR6"
"FIAUhhSMAAAUehSAFIYUjAAAFJIAABSYAAAAABSeAAAUpAAAAAAUngAAFKQAAAAAFKoAABSwAAAUthZ+AAAUvBTCAAAAAAAAAAAU"
"wgAAFn4AABS8FMIAABZ+AAAUvBTCAAAWfgAAFLwUwgAAFn4AABS8FMIAABZ+AAAUvBTCAAAWfgAAFLwUwgAAFn4AABS8FMIAABZ+"
"AAAUvBTCAAAWfgAAFLwUwgAAFn4AABS8FMIAABZ+AAAUvBTCAAAWfgAAFLwUwgAAFn4AABS8FMIAABZ+AAAUvBTCAAAVagAAFNQU"
"2gAAFWoAABTUFNoAABVqAAAU1BTaAAAVagAAFNQU2gAAFWoAABTUFNoAABVqAAAU1BTaAAAVagAAFNQU2gAAFWoAABTUFNoAABVq"
"AAAU1BTaAAAVagAAFNQU2gAAFWoAABTUFNoAABVqAAAU1BTaAAAUyAAAFNQU2gAAFM4AABTUFNoAABVqAAAU1BTaAAAVagAAFNQU"
"2gAAFWoAABTUFNoAABVqAAAU1BTaAAAVagAAFNQU2gAAFWoAABTUFNoAABVqAAAU1BTaAAAVagAAFNQU2gAAFOAAABZIAAAAABXo"
"AAAV7gAAAAAV6AAAFe4AAAAAFegAABXuAAAAABXoAAAV7gAAAAAV6AAAFe4AAAAAFegAABXuAAAAABTmFOwVcAAAFPIU5hTsFXAA"
"ABTyFOYU7BVwAAAU8hYAAAAV9BX6AAAWAAAAFfQV+gAAFgAAABX0FfoAABYAAAAV9BX6AAAWAAAAFfQV+gAAFgAAABX0FfoAABYA"
"AAAV9BX6AAAWAAAAFfQV+gAAFPgAABX0FfoAABT+AAAV9BX6AAAWAAAAFfQV+gAAFgAAABX0FfoAABYAAAAV9BX6AAAWAAAAFfQV"
"+gAAFgAAABX0FfoAABYAAAAV9BX6AAAWAAAAFfQV+gAAFgAAABX0FfoAABUEAAAVCgAAAAAWAAAAFgYAAAAAFgAAABYGAAAAABYA"
"AAAWBgAAAAAWAAAAFgYAAAAAFgAAABYGAAAAABYAAAAWBgAAAAAWDAAAFUYAABUQFgwAABVGAAAVEBYMAAAVRgAAFRAWogAAFqgW"
"rgAAFqIAABaoFq4AABaiAAAWqBauAAAWogAAFqgWrgAAFqIAABaoFq4AABaiAAAWqBauAAAWogAAFqgWrgAAFqIAABaoFq4AABai"
"AAAWqBauAAAWogAAFqgWrgAAFqIAABaoFq4AABaiAAAWqBauAAAWogAAFqgWrgAAAAAAABaoFq4AABaiAAAAAAAAAAAWogAAAAAA"
"AAAAFqIAAAAAAAAAABaiAAAAAAAAAAAVFgAAFV4AAAAAFRYAABVeAAAAABYMFhIWqAAAFhgWDBYSFqgAABYYFgwWEhaoAAAWGBYM"
"FhIWqAAAFhgWDBYSFqgAABYYFRwVIhUoAAAVLhU0AAAVOgAAAAAVQAAAFUYAAAAAFUAAABVGAAAAABVAAAAVRgAAAAAVQAAAFUYA"
"AAAAFUAAABVGAAAAABYeFiQWKhYwFjYWHhYkFioWMBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWHhYkFioWMBY2Fh4WJBYqFjAWNhVM"
"FiQWKhYwFjYVUhYkFioWMBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWHhYkFioWMBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWHhYkFioW"
"MBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWHhYkFioWMBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWHhYkFioWMBY2FVgWJBVeFjAVZBYe"
"FiQWKhYwFjYAABYkAAAAABY2FjwAABZIAAAAABVqAAAVcAAAAAAVdgAAFqgAAAAAFXYAABaoAAAAABV2AAAWqAAAAAAVdgAAFqgA"
"AAAAFXwAABWCAAAAABV8AAAVggAAAAAVfAAAFYIAAAAAFXwAABWCAAAAABV8AAAVggAAAAAVfAAAFYIAAAAAFZoVoBWmAAAVrBfo"
"FYgVjgAAFZQVmhWgFaYAABWsFZoVoBWmAAAVrBWaFaAVpgAAFawWPBZCFkgWTgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWPBZCFkgW"
"TgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWPBZCFkgWTgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWPBZCFkgWTgAAFjwWQhZIFk4AABY8"
"FkIWSBZOAAAWPBZCFkgWTgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWPBZCFkgWTgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWPBZCFkgW"
"TgAAFjwAABZIAAAAABZUAAAWWgAAAAAWVAAAFloAAAAAFlQAABZaAAAAABZUAAAWWgAAAAAWVAAAFloAAAAAFbIAABW4AAAAABW+"
"AAAVxAAAAAAVvgAAFcQAAAAAFb4AABXEAAAAABW+AAAVxAAAAAAVvgAAFcQAAAAAFb4AABXEAAAAABW+AAAVxAAAAAAVvgAAFcQA"
"AAAAFmwAABZyAAAWeBZsAAAWcgAAFngWbAAAFnIAABZ4FmwAABZyAAAWeBaiAAAWqBauAAAWogAAFqgWrgAAFdYAABXcFeIAABXW"
"AAAV3BXiAAAV1gAAFdwV4gAAFdYAABXcFeIAABXWAAAV3BXiAAAV1gAAFdwV4gAAFdYAABXcFeIAABXWAAAV3BXiAAAV1gAAFdwV"
"4gAAFdYAABXcFeIAABXWAAAV3BXiAAAV1gAAFdwV4gAAFcoAABXcFeIAABXQAAAV3BXiAAAV1gAAFdwV4gAAFdYAABXcFeIAABXW"
"AAAV3BXiAAAV1gAAFdwV4gAAFdYAABXcFeIAABXWAAAV3BXiAAAV1gAAFdwV4gAAFdYAABXcFeIAABXoAAAV7gAAAAAWAAAAFfQV"
"+gAAFgAAABX0FfoAABYAAAAV9BX6AAAWAAAAFfQV+gAAFgAAABYGAAAAABaiAAAWqBauAAAWogAAFqgWrgAAFqIAABaoFq4AABai"
"AAAWqBauAAAWogAAAAAAAAAAFgwWEhaoAAAWGBYeFiQWKhYwFjYWHhYkFioWMBY2Fh4WJBYqFjAWNhYeFiQWKhYwFjYWPBZCFkgW"
"TgAAFjwWQhZIFk4AABY8FkIWSBZOAAAWVAAAFloAAAAAFmAAABZmAAAAABZgAAAWZgAAAAAWYAAAFmYAAAAAFmAAABZmAAAAABZg"
"AAAWZgAAAAAWYAAAFmYAAAAAFmwAABZyAAAWeBa0FroWwAAAFsYWtBa6FsAAABbGFrQWuhbAAAAWxha0FroWwAAAFsYWtBa6FsAA"
"ABbGFn4WhBaKAAAWkBaWAAAWnAAAAAAWlgAAFpwAAAAAFpYAABacAAAAABaWAAAWnAAAAAAWogAAFqgWrgAAFrQWuhbAAAAWxgAA"
"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"
"A6oAAkRGTFQADmxhdG4APAAEAAAAAP//ABIAAAABAAIABAAFAAYAEAARABIAEwAUABUAFgAXABgAGQAaABsAOgAJQVpFIABkQ0FU"
"IACQQ1JUIAC8S0FaIADoTU9MIAEUTkxEIAFAUk9NIAFsVEFUIAGYVFJLIAHEAAD//wASAAAAAQADAAQABQAGABAAEQASABMAFAAV"
"ABYAFwAYABkAGgAbAAD//wATAAAAAQACAAQABQAGAAcAEAARABIAEwAUABUAFgAXABgAGQAaABsAAP//ABMAAAABAAIABAAFAAYA"
"CAAQABEAEgATABQAFQAWABcAGAAZABoAGwAA//8AEwAAAAEAAgAEAAUABgAJABAAEQASABMAFAAVABYAFwAYABkAGgAbAAD//wAT"
"AAAAAQACAAQABQAGAAoAEAARABIAEwAUABUAFgAXABgAGQAaABsAAP//ABMAAAABAAIABAAFAAYACwAQABEAEgATABQAFQAWABcA"
"GAAZABoAGwAA//8AEwAAAAEAAgAEAAUABgAMABAAEQASABMAFAAVABYAFwAYABkAGgAbAAD//wATAAAAAQACAAQABQAGAA0AEAAR"
"ABIAEwAUABUAFgAXABgAGQAaABsAAP//ABMAAAABAAIABAAFAAYADgAQABEAEgATABQAFQAWABcAGAAZABoAGwAA//8AEwAAAAEA"
"AgAEAAUABgAPABAAEQASABMAFAAVABYAFwAYABkAGgAbABxhYWx0AKpjYXNlALJjY21wALhjY21wAMJkbm9tAM5mcmFjANRsaWdh"
"AN5sb2NsAORsb2NsAOpsb2NsAPBsb2NsAPZsb2NsAPxsb2NsAQJsb2NsAQhsb2NsAQ5sb2NsARRudW1yARpvcmRuASBwbnVtAShz"
"YWx0AS5zaW5mATRzczAxATpzczAyAURzczAzAU5zczA0AVhzdWJzAWJzdXBzAWh0bnVtAW4AAAACAAAAAQAAAAEAJAAAAAMAAgAF"
"AAgAAAAEAAIABQAIAAgAAAABABkAAAADABoAGwAcAAAAAQAlAAAAAQAJAAAAAQAQAAAAAQAKAAAAAQALAAAAAQAPAAAAAQATAAAA"
"AQAOAAAAAQAMAAAAAQANAAAAAQAYAAAAAgAfACEAAAABACIAAAABACYAAAABABYABgABACcAAAEAAAYAAQAoAAABAQAGAAEAKQAA"
"AQIABgABACoAAAEDAAAAAQAVAAAAAQAXAAAAAQAjACsAWALWA/gEfAR8BKIE2gTaBPgFVgVWBVYFVgVWBWoFagWMBcIF0AXkBhoG"
"NAY0BkIGcgZQBl4GcgaABr4GvgbWBxQHNgdYB3AHiAfWCBoIGgm8CfIKCgABAAAAAQAIAAIBPACbAc0ArgCvALAAsQCyALMAtAC1"
"ALYAtwDIAMkAygDLAMwA0ADRANIA0wDUAE0AuwHOALwAvQC+AL8AwACBAIcAwQDCAMMAxADFAMYAxwDVANYA1wGKAYsBjAGNAY4B"
"jwGQAZEBkgGTAZQBlQGWAZcBmAGZAZoBmwGcAZ0BngGfAaABoQGiAaMBpAGmAacBqAG6AbsBvAG9Ab8BzgGrAawBrQGuAcABwQHC"
"AcMBWgFgAa8BsAGxAbIBswG0AbUBtgG3AbgBuQHEAcUBzAHLAdEB0gHTAdQB1QHWAdcB2AHZAdoB+QH6AfsB/AH9Af4B/wIAAgEC"
"AgI9Aj4CPwJAAkECQgJEAg0CSAJJAksCUAJRAlICWQJaAlsCXAJdAl4CawJsAm0CbgJvAnACpQLQAtEC0gLMAs0CzgABAJsAAQAF"
"AAsADwAQAB4AKQAtAC4ALwA7AD8AQABBAEIAQwBHAEgASQBKAEsATABVAF4AYgBmAGcAbAB3AH8AhgCMAI0AkgCfAKUApgCtALgA"
"uQC6ANkA2gDbANwA3QDeAN8A4ADhAOIA4wDkAOUA5gDnAOgA6QDqAOsA7ADtAPUBAAEEAQUBBgESARsBHAEdASoBKwEsAS0BLwE3"
"ATsBPwFAAUUBUQFSAVMBVAFYAV8BZQFmAWsBeAF7AXwBfQF+AX8BgAGGAYcBqgHIAcoB7wHwAfEB8gHzAfQB9QH2AfcB+AIDAgQC"
"BQIGAgcCCAIJAgoCCwIMAisCLAItAi4CLwIwAjICOAI6AjsCRwJMAk0CTgJTAlQCVQJWAlcCWAJfAmACYQJiAmMCZAKRAq4CrwK8"
"AsACwgLDAAMAAAABAAgAAQDsABUAMAA2ADwAQgBIAE4AVABaAGYAcgB+AIoAlgCiAK4AugDGANIA2ADeAOYAAgC4AM0AAgC5AM4A"
"AgC6AM8AAgGJAc0AAgEcAaUAAgEmAakAAgGqAb4ABQHvAfkCAwIVAh8ABQHwAfoCBAIWAiAABQHxAfsCBQIXAiEABQHyAfwCBgIY"
"AiIABQHzAf0CBwIZAiMABQH0Af4CCAIaAiQABQH1Af8CCQIbAiUABQH2AgACCgIcAiYABQH3AgECCwIdAicABQH4AgICDAIeAigA"
"AgI6AkMAAgI7AkUAAwI8AkYCRwACAkcCSgABABUARABFAEYA2AEWASQBLgHRAdIB0wHUAdUB1gHXAdgB2QHaAjECMwI0AjwABgAA"
"AAQADgAgAFYAaAADAAAAAQAmAAEAPgABAAAAAwADAAAAAQAUAAIAHAAsAAEAAAAEAAEAAgEWASQAAgACArsCvAAAAr4CwwACAAIA"
"AQKuAroAAAADAAEAoAABAKAAAAABAAAAAwADAAEAEgABAI4AAAABAAAABAACAAEAAQDXAAAAAQAAAAEACAACABAABQEXASUCzALN"
"As4AAQAFARYBJALAAsICwwAGAAAAAgAKABwAAwAAAAEAQgABACQAAQAAAAYAAwABABIAAQAwAAAAAQAAAAcAAQADAswCzQLOAAEA"
"AAABAAgAAgAMAAMCzALNAs4AAQADAsACwgLDAAQAAAABAAgAAQBOAAIACgAsAAQACgAQABYAHALIAAICsQLJAAICsALKAAICuQLL"
"AAICtwAEAAoAEAAWABwCxAACArECxQACArACxgACArkCxwACArcAAQACArMCtQABAAAAAQAIAAEABgAGAAEAAQEWAAEAAAABAAgA"
"AgAOAAQAgQCHAVoBYAABAAQAfwCGAVgBXwAGAAAAAQAIAAEASgABAAgAAgAGABYAAQEqAAEAAQEqAAEAAAARAAEAUQABAAEAUQAB"
"AAAAEgABAAAAAQAIAAEAFAAIAAEAAAABAAgAAQAGABMAAQABAjQABgAAAAEACAABAEAAAgAKABwAAQAEAAEAQQABAAAAAQAAABQA"
"AQAEAAEBGAABAAAAAQAAABQAAQAAAAEACAACAAoAAgBNASYAAQACAEwBJAABAAAAAQAIAAEBQgBEAAEAAAABAAgAAQE0AE4AAQAA"
"AAEACAABASYAKAABAAAAAQAIAAEABv/VAAEAAQI4AAEAAAABAAgAAQEEADIABgAAAAIACgAiAAMAAQASAAEAQgAAAAEAAAAdAAEA"
"AQINAAMAAQASAAEAKgAAAAEAAAAeAAIAAQH5AgIAAAABAAAAAQAIAAEABv/2AAIAAQIDAgwAAAAGAAAAAgAKACQAAwABAJ4AAQAS"
"AAAAAQAAACAAAQACAAEA2AADAAEAhAABABIAAAABAAAAIAABAAIAXgE3AAEAAAABAAgAAgAOAAQBzQHOAc0BzgABAAQAAQBeANgB"
"NwAEAAAAAQAIAAEAFAABAAgAAQAEAoMAAwE3AisAAQABAFgAAQAAAAEACAABAAb/4gACAAEB7wH4AAAAAQAAAAEACAABAAYAHgAC"
"AAEB0QHaAAAAAQAAAAEACAACACQADwI6AjsCRwJQAlECUgJZAloCWwJcAl0CXgLMAs0CzgABAA8CMQIzAjwCTAJNAk4CUwJUAlUC"
"VgJXAlgCwALCAsMABAAIAAEACAABADYAAQAIAAUADAAUABwAIgAoAccAAwEMARYByAADAQwBKgHGAAIBDAHJAAIBFgHKAAIBKgAB"
"AAEBDAABAAAAAQAIAAIAzgBkAK4ArwCwALEAsgCzALQAtQC2ALcAuAC5ALoAuwC8AL0AvgC/AMAAwQDCAMMAxADFAMYAxwGJAYoB"
"iwGMAY0BjgGPAZABkQGSAZMBlAGVAZYBlwGYAZkBmgGbAZwBnQGeAZ8BoAGhAaIBowGkAaUBpgGnAagBqQGqAasBrAGtAa4BrwGw"
"AbEBsgGzAbQBtQG2AbcBuAG5AcQCPQI+Aj8CQAJBAkICQwJEAkUCRgJIAkkCSgJLAmsCbAJtAm4CbwJwAqUC0ALRAtIAAQBkAAUA"
"CwAPABAAHgApAC0ALgAvADsARABFAEYAVQBiAGYAZwBsAHcAjACNAJIAnwClAKYArQDYANkA2gDbANwA3QDeAN8A4ADhAOIA4wDk"
"AOUA5gDnAOgA6QDqAOsA7ADtAPUBAAEEAQUBBgESARYBGwEcAR0BJAEuATsBPwFAAUUBZQFmAWsBeAF7AXwBfQF+AX8BgAGGAYcC"
"KwIsAi0CLgIvAjACMQIyAjMCNAI6AjsCPAJHAl8CYAJhAmICYwJkApECrgKvArwAAQAAAAEACAACABgACQG6AbsBvAG9Ab4BvwHF"
"AcwBywABAAkBKgErASwBLQEuAS8BqgHIAcoAAQAAAAEACAABAAYAbwACAAEBUQFUAAAAAQAAAAEACAACACYAEADIAMkAygDLAMwA"
"zQDOAM8A0ADRANIA0wDUANUA1gDXAAIAAgA/AEsAAAC4ALoADQAA"
)


def _materialize_hubot_font_files ():
    tmp_dir =os .path .join (tempfile .gettempdir (),"revolt_fonts")
    try :
        os .makedirs (tmp_dir ,exist_ok =True )
    except Exception :
        pass 
    reg_path =os .path .join (tmp_dir ,"HubotSans-Regular.ttf")
    bold_path =os .path .join (tmp_dir ,"HubotSans-Bold.ttf")
    try :
        with open (reg_path ,"wb")as f :
            f .write (base64 .b64decode (_FONT_HUBOT_REGULAR_B64 ))
    except Exception :
        reg_path =None 
    try :
        with open (bold_path ,"wb")as f :
            f .write (base64 .b64decode (_FONT_HUBOT_BOLD_B64 ))
    except Exception :
        bold_path =None 
    return [p for p in (reg_path ,bold_path )if p ]

_HUBOT_FONT_PATHS :list =[]
_HUBOT_FONT_LOADED =False 

def _register_hubot_sans_font ():
    # loads the bundled Hubot Sans TTFs as private fonts, no system install needed
    global _HUBOT_FONT_PATHS ,_HUBOT_FONT_LOADED 
    _HUBOT_FONT_PATHS =_materialize_hubot_font_files ()
    if not _HUBOT_FONT_PATHS :
        return 
    if os .name =="nt":
        try :
            FR_PRIVATE =0x10 
            added =0 
            for path in _HUBOT_FONT_PATHS :
                n =ctypes .windll .gdi32 .AddFontResourceExW (path ,FR_PRIVATE ,0 )
                added +=n 
            if added :
                _HUBOT_FONT_LOADED =True 
                try :
                    HWND_BROADCAST =0xFFFF 
                    WM_FONTCHANGE =0x001D 
                    ctypes .windll .user32 .SendMessageW (HWND_BROADCAST ,WM_FONTCHANGE ,0 ,0 )
                except Exception :
                    pass 

                def _cleanup_hubot_fonts ():
                    for path in _HUBOT_FONT_PATHS :
                        try :
                            ctypes .windll .gdi32 .RemoveFontResourceExW (path ,FR_PRIVATE ,0 )
                        except Exception :
                            pass 
                atexit .register (_cleanup_hubot_fonts )
        except Exception :
            _HUBOT_FONT_LOADED =False 
    elif sys .platform =="darwin":
        try :
            user_fonts_dir =os .path .expanduser ("~/Library/Fonts")
            os .makedirs (user_fonts_dir ,exist_ok =True )
            for path in _HUBOT_FONT_PATHS :
                dest =os .path .join (user_fonts_dir ,os .path .basename (path ))
                if not os .path .exists (dest ):
                    shutil .copyfile (path ,dest )
            _HUBOT_FONT_LOADED =True 
        except Exception :
            _HUBOT_FONT_LOADED =False 
    else :
        try :
            user_fonts_dir =os .path .expanduser ("~/.local/share/fonts")
            os .makedirs (user_fonts_dir ,exist_ok =True )
            copied =False 
            for path in _HUBOT_FONT_PATHS :
                dest =os .path .join (user_fonts_dir ,os .path .basename (path ))
                if not os .path .exists (dest ):
                    shutil .copyfile (path ,dest )
                    copied =True 
            if copied :
                try :
                    subprocess .run (["fc-cache","-f",user_fonts_dir ],
                    stdout =subprocess .DEVNULL ,stderr =subprocess .DEVNULL ,timeout =5 )
                except Exception :
                    pass 
            _HUBOT_FONT_LOADED =True 
        except Exception :
            _HUBOT_FONT_LOADED =False 

_register_hubot_sans_font ()

try :
    import pystray 
    from PIL import Image ,ImageDraw 
    _TRAY_AVAILABLE =True 
except Exception :
    _TRAY_AVAILABLE =False 

# system notification backends - tries winotify, then plyer, then pystray tray bubble
_WINOTIFY_AVAILABLE =False 
if os .name =="nt":
    try :
        from winotify import Notification as _WiNotification ,audio as _wn_audio 
        _WINOTIFY_AVAILABLE =True 
    except Exception :
        _WINOTIFY_AVAILABLE =False 

_PLYER_AVAILABLE =False 
try :
    from plyer import notification as _plyer_notification 
    _PLYER_AVAILABLE =True 
except Exception :
    _PLYER_AVAILABLE =False 

def is_admin ()->bool :
    try :
        return bool (ctypes .windll .shell32 .IsUserAnAdmin ())if os .name =="nt"else os .getuid ()==0 
    except Exception :
        return False 

def elevate_windows ():

    args =[os .path .abspath (sys .argv [0 ])]+sys .argv [1 :]
    params =" ".join (f'"{a }"'for a in args )
    workdir =os .path .dirname (os .path .abspath (sys .argv [0 ]))or None 
    ctypes .windll .shell32 .ShellExecuteW (
    None ,"runas",sys .executable ,params ,workdir ,1 )

def set_always_admin_windows ():
    if os .name !="nt":
        return 
    if not getattr (sys ,"frozen",False ):
        return 
    try :
        key_path =r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
        with winreg .CreateKeyEx (winreg .HKEY_CURRENT_USER ,key_path ,
        0 ,winreg .KEY_SET_VALUE )as k :
            winreg .SetValueEx (k ,sys .executable ,0 ,winreg .REG_SZ ,"~ RUNASADMIN")
    except Exception :
        pass 

def ensure_admin ():
    if is_admin ():
        set_always_admin_windows ()
        return True 
    if os .name =="nt":
        elevate_windows ()
        return False 
    return True 

def flush_dns ():
    try :
        if os .name =="nt":
            si =subprocess .STARTUPINFO ()
            si .dwFlags |=subprocess .STARTF_USESHOWWINDOW 
            si .wShowWindow =0 
            subprocess .run (["ipconfig","/flushdns"],startupinfo =si ,capture_output =True )
        else :
            for s in ("systemd-resolved","nscd","dnsmasq"):
                subprocess .run (["systemctl","restart",s ],capture_output =True ,timeout =4 )
    except Exception :
        pass 

def flush_ip ():
    try :
        if os .name =="nt":
            si =subprocess .STARTUPINFO ()
            si .dwFlags |=subprocess .STARTF_USESHOWWINDOW 
            si .wShowWindow =0 
            subprocess .run (["ipconfig","/release"],startupinfo =si ,capture_output =True )
            subprocess .run (["ipconfig","/renew"],startupinfo =si ,capture_output =True )
        else :
            try :
                subprocess .run (["dhclient","-r"],capture_output =True ,timeout =8 )
                subprocess .run (["dhclient"],capture_output =True ,timeout =8 )
            except Exception :
                subprocess .run (
                ["nmcli","networking","off"],capture_output =True ,timeout =8 )
                subprocess .run (
                ["nmcli","networking","on"],capture_output =True ,timeout =8 )
    except Exception :
        pass 

def clean_domain (raw :str )->str :
    raw =raw .strip ().lower ()
    for p in ("https://","http://","//"):
        if raw .startswith (p ):raw =raw [len (p ):]
    return raw .split ("/")[0 ].strip ()

def mask_domain (d :str )->str :
    if not d :return d 
    parts =d .split (".")
    tld =parts [-1 ]
    body =".".join (parts [:-1 ])
    if len (body )<=2 :masked ="●"*len (body )
    elif len (body )<=4 :masked =body [0 ]+"●"*(len (body )-1 )
    else :masked =body [0 ]+"●"*(len (body )-2 )+body [-1 ]
    return f"{masked }.{tld }"

def _startup_cmd ()->str :
    exe =sys .executable 
    if getattr (sys ,"frozen",False ):return f'"{exe }"'
    return f'"{exe }" "{os .path .abspath (__file__ )}"'

def get_startup_enabled ()->bool :
    if os .name =="nt":
        try :
            with winreg .OpenKey (winreg .HKEY_CURRENT_USER ,_REG_KEY )as k :
                winreg .QueryValueEx (k ,_APP_NAME )
                return True 
        except Exception :
            return False 
    return os .path .exists (_DESK_FILE )

def set_startup_enabled (enable :bool ):
    if os .name =="nt":
        with winreg .OpenKey (winreg .HKEY_CURRENT_USER ,_REG_KEY ,
        0 ,winreg .KEY_SET_VALUE )as k :
            if enable :
                winreg .SetValueEx (k ,_APP_NAME ,0 ,winreg .REG_SZ ,_startup_cmd ())
            else :
                try :winreg .DeleteValue (k ,_APP_NAME )
                except FileNotFoundError :pass 
    else :
        if enable :
            os .makedirs (os .path .dirname (_DESK_FILE ),exist_ok =True )
            with open (_DESK_FILE ,"w")as f :
                f .write (f"[Desktop Entry]\nName={_APP_NAME }\n"
                f"Exec={_startup_cmd ()}\nType=Application\n"
                "X-GNOME-Autostart-enabled=true\n")
        else :
            try :os .remove (_DESK_FILE )
            except FileNotFoundError :pass 

def _create_desktop_shortcut ():
    try :
        desktop =os .path .join (os .path .expanduser ("~"),"Desktop")
        if not os .path .isdir (desktop ):
            return 
        if os .name =="nt":
            lnk =os .path .join (desktop ,f"{_APP_NAME }.lnk")
            if os .path .exists (lnk ):
                return 
            exe =sys .executable 
            script =os .path .abspath (__file__ )
            args =""if getattr (sys ,"frozen",False )else script 
            workdir =os .path .dirname (script )
            icon_ref =ICON_PATH if os .path .exists (ICON_PATH )else f"{exe },0"
            ps =(
            "$s = (New-Object -COM WScript.Shell).CreateShortcut('{lnk}'); "
            "$s.TargetPath = '{exe}'; "
            "$s.Arguments = '\"{args}\"'; "
            "$s.WorkingDirectory = '{workdir}'; "
            "$s.IconLocation = '{icon_ref}'; "
            "$s.Save()"
            ).format (lnk =lnk ,exe =exe ,args =args ,workdir =workdir ,icon_ref =icon_ref )
            si =subprocess .STARTUPINFO ()
            si .dwFlags |=subprocess .STARTF_USESHOWWINDOW 
            si .wShowWindow =0 
            subprocess .run (["powershell","-NoProfile","-Command",ps ],
            startupinfo =si ,capture_output =True ,timeout =10 )
        else :
            desk_file =os .path .join (desktop ,"Revolt.desktop")
            if os .path .exists (desk_file ):
                return 
            icon_line =f"Icon={ICON_PATH }\n"if os .path .exists (ICON_PATH )else ""
            with open (desk_file ,"w")as f :
                f .write (f"[Desktop Entry]\nName={_APP_NAME }\n"
                f"Exec={_startup_cmd ()}\nType=Application\n"
                f"{icon_line }Terminal=false\n")
            os .chmod (desk_file ,0o755 )
            try :
                subprocess .run (["gio","set",desk_file ,"metadata::trusted","true"],
                capture_output =True ,timeout =4 )
            except Exception :
                pass 
    except Exception :
        pass 

def _mark_shortcut_prompt_done ():
    try :
        with open (_SHORTCUT_MARKER ,"w")as f :
            f .write ("1")
    except Exception :
        pass 

def prompt_desktop_shortcut_once (parent =None ):
    if os .path .exists (_SHORTCUT_MARKER ):
        return 
    try :
        add_it =messagebox .askyesno (
        "Add Desktop Shortcut?",
        "Add Revolt as a shortcut on your Desktop for quick access?",
        parent =parent ,
        )
    except Exception :
        add_it =False 
    if add_it :
        _create_desktop_shortcut ()
    _mark_shortcut_prompt_done ()

def _mark_onboarding_done ():
    try :
        with open (_ONBOARDING_MARKER ,"w")as f :
            f .write ("1")
    except Exception :
        pass 

def _h2r (h :str ):
    h =h .lstrip ("#")
    return int (h [:2 ],16 ),int (h [2 :4 ],16 ),int (h [4 :],16 )

def _r2h (r ,g ,b )->str :
    return f"#{int (max (0 ,min (255 ,r ))):02x}{int (max (0 ,min (255 ,g ))):02x}{int (max (0 ,min (255 ,b ))):02x}"

def lerp_col (a :str ,b :str ,t :float )->str :
    r1 ,g1 ,b1 =_h2r (a );r2 ,g2 ,b2 =_h2r (b )
    return _r2h (r1 +(r2 -r1 )*t ,g1 +(g2 -g1 )*t ,b1 +(b2 -b1 )*t )

def lighten (c :str ,a :float =.12 )->str :
    r ,g ,b =_h2r (c );return _r2h (r +(255 -r )*a ,g +(255 -g )*a ,b +(255 -b )*a )

def darken (c :str ,a :float =.12 )->str :
    r ,g ,b =_h2r (c );return _r2h (r *(1 -a ),g *(1 -a ),b *(1 -a ))

BG ="#07090f"
SIDEBAR ="#0d1322"
CARD ="#141c34"
TOOLBAR ="#1c2648"
ACCENT ="#4d79ff"
ACCENT2 ="#c44dff"
ACCENT_DIM ="#202d5c"
DANGER ="#ff2d55"
WARN ="#ffac2f"
TEXT ="#ffffff"
MUTED ="#b7c3e6"
BORDER ="#46579e"
BORDER_HI ="#7f92e0"
BORDER_LO ="#1b2244"
GLASS_TINT ="#1a2340"
ENTRY ="#161f3a"
SEL_BG ="#324690"
SEL_FG ="#c8d6ff"
BADGE_BG ="#20295a"
ROW_ALT ="#101830"
SCROLL_BG1 ="#4d79ff"
SCROLL_BG2 ="#5c70b8"

FONT_FAMILY ="Arial"
MONO_FAMILY ="Consolas"

TOPICS_DATABASE :dict [str ,list [str ]]={

"Ad Blocking":[
"audio-sp.spotify.com",
"ads-fa.spotify.com","pagead.l.doubleclick.net",
"video-stats.l.google.com",
"googleadservices.com","googlesyndication.com","doubleclick.net",
"adservice.google.com","pagead2.googlesyndication.com",
"tpc.googlesyndication.com","ads.google.com","google-analytics.com",
"analytics.google.com","ssl.google-analytics.com","googletagmanager.com",
"googletagservices.com","g.doubleclick.net","stats.g.doubleclick.net",
"ad.doubleclick.net","fundingchoicesmessages.google.com","adsense.google.com",
"connect.facebook.net","an.facebook.com","pixel.facebook.com",
"static.ads-twitter.com","ads-api.twitter.com","analytics.twitter.com",
"ads.instagram.com","amazon-adsystem.com","aax.amazon-adsystem.com",
"aax-eu.amazon-adsystem.com","c.amazon-adsystem.com","fls-na.amazon.com",
"ads.pubmatic.com","outbrain.com","widgets.outbrain.com","taboola.com",
"cdn.taboola.com","trc.taboola.com","criteo.com","dis.criteo.com",
"static.criteo.net","rubiconproject.com","openx.net","appnexus.com",
"ib.adnxs.com","secure.adnxs.com","tremorhub.com","advertising.com",
"adsrvr.org","casalemedia.com","sharethrough.com","sovrn.com",
"indexexchange.com","smartadserver.com","33across.com","spotxchange.com",
"spotx.tv","adcolony.com","mediavine.com","adthrive.com","undertone.com",
"adroll.com","rlcdn.com","moatads.com","ezoic.com","popads.net",
"popcash.net","propellerads.com","revcontent.com","mgid.com",
"exoclick.com","juicyads.com","trafficjunky.com","trafficstars.com",
"clickadu.com","adcash.com","zedo.com","adzerk.com","districtm.io",
"contextweb.com","nexac.com","bidswitch.net","scorecardresearch.com",
"quantserve.com","hotjar.com","mouseflow.com","fullstory.com",
"logrocket.com","clarity.ms","c.clarity.ms","mixpanel.com",
"api.mixpanel.com","amplitude.com","api2.amplitude.com","segment.com",
"api.segment.io","cdn.segment.com","heap.io","heapanalytics.com",
"chartbeat.com","newrelic.com","bam.nr-data.net","statcounter.com",
"crazyegg.com","luckyorange.com","optimizely.com","braze.com",
"intercom.com","api.intercom.io","drift.com","marketo.com",
"hubspot.com","js.hs-analytics.net","pardot.com","klaviyo.com",
"mailchimp.com","omtrdc.net","adobedtm.com","demdex.net","addthis.com",
"sharethis.com","skimresources.com","viglink.com","narrativ.com",
"bat.bing.com","c.bing.com","ct.pinterest.com","analytics.tiktok.com",
"ads.tiktok.com","analytics.snapchat.com","tr.snapchat.com",
"px.ads.linkedin.com","snap.licdn.com","nielsen.com","imrworldwide.com",
"acxiom.com","liveramp.com","epsilon.com","thetradedesk.com",
"id5-sync.com","id5.io",
"adform.net","adition.com","admedo.com","adnxs-simple.com",
"adtech.de","adtechus.com","adtelligent.com","adyoulike.com",
"affiliatly.com","affinity.com","agkn.com","aidata.io",
"aniview.com","apester.com","atedra.net","audiencescience.com",
"beachfrontmedia.com","bidtellect.com","bttrack.com","bnmla.com",
"brightline.tv","btrll.com","c3metrics.com","cedato.com",
"channeladvisor.com","clickagy.com","clickfuse.com","clicktale.net",
"cognitivematch.com","conversantmedia.com","crwdcntrl.net",
"dataxu.com","decenterads.com","dianomi.com","digitru.st",
"districtmapps.io","dotomi.com","doubleverify.com",
"eyeota.net","exelator.com","exponential.com","flashtalking.com",
"gammaplatform.com","gumgum.com","hlserve.com","impactradius.com",
"improvedigital.com","innovid.com","insticator.com","ipredictive.com",
"jivox.com","kargo.com","krxd.net","lijit.com","liveintent.com",
"lkqd.net","loopme.com","mantisadnetwork.com","mathtag.com",
"media.net","mediaforge.com","meetrics.net","mfadsrvr.com",
"monetate.net","mookie1.com","narrative.io","netmng.com",
"nrelate.com","onaudience.com","onetag.com","optad360.com",
"pathtopurchase.com","permutive.com","pippio.com","pixel.watch",
"placeiq.net","postrelease.com","pro-market.net","pubmine.com",
"pubnative.net","quantcast.com","reklama.com","richaudience.com",
"rlets.com","rtbsrvr.com","salesforceliveagent.com","semasio.net",
"sift.com","simpli.fi","smaato.net","smartclip.net","spoutable.com",
"springserve.com","stackadapt.com","summetrix.com","supersonicads.com",
"supperads.com","tapad.com","teads.tv","technoratimedia.com",
"themoneytizer.com","tidaltv.com","triplelift.com","trustx.org",
"turn.com","tynt.com","unrulymedia.com","vdna-assets.com",
"verizonmedia.com","videoplaza.com","viewability.mookie1.com",
"vindicosuite.com","vidible.tv","vungle.com","w55c.net",
"widespace.com","yldbt.com","yieldlab.net","yieldmo.com",
"zemanta.com","zeotap.com","adblade.com","admanmedia.com",
"adnium.com","adpone.com","adpushup.com","adsafeprotected.com",
"adspeed.net","adtdp.com","adtrue.com","advertserve.com",
"aim4media.com","anymind360.com","bidgear.com","boldapps.net",
"bounceexchange.com","cheq.ai","clickcertain.com","content.ad",
"contextual.media.net","crosspixel.net","distroscale.com",
"engageya.com","freewheel.tv","gnezdo.net","impact.com",
"index.wp.com","keywee.co","lucidmoment.com",
"marketgid.com","nend.net","perfectmarket.com",
"pgpartner.com","pubgalaxy.com","runative-syndicate.com",
"smartyads.com","spotim.market","stroeermediabrands.de",
"voicefive.com","xad.com","yieldbot.com","zergnet.com",
"adcolony.io","adikteev.com","admixer.net","adotmob.com",
"adpone.net","adprime.com","adservme.com","adsymptotic.com",
"adzcentral.com","alenty.com","aralego.com","attentiontrust.com",
"avocarrot.com","between.us","blismedia.com","brand-metrics.com",
"bridgetrack.com","bucksense.com","c6dt.com","catapultx.com",
"connatix.com","contentspread.net","convertro.com","crimtan.com",
"criteo.net","datonics.com","digitalarbitrage.com","doceree.com",
"dstillery.com","emxdgt.com","engine.adzerk.net","fout.jp",
"gravity.com","greystripe.com","gumgum.net","hyprmx.com",
"ingage.tech","inmobi.com","inskinmedia.com","instreamatic.com",
"ipromote.com","jampp.com","kayzen.io","kubient.com",
"leadbolt.com","liftoff.io","lotame.com","m6r.eu",
"madvertise.com","mediamath.com","meetrics.com","mfadsrvr.net",
"minutemedia.com","mobfox.com","mobupps.com","moloco.com",
"nativo.com","navdmp.com","netseer.com","nexage.com",
"onclickads.net","onclusive.com","openweb.com","opera-mediaworks.com",
"otm-r.com","outbrainimg.com","pflexads.com","platform161.com",
"pmc.io","pointroll.com","postquantum.com","pubfuture.com",
"pubgears.com","pubwise.io","quantumdigital.com","reklamup.com",
"rezonence.com","rocketfuel.com","rockyou.com","ru4.com",
"run-syndicate.com","scoota.com","semasio.com","sizmek.com",
"smadex.com","smartclip.com","sonobi.com","spotx.com",
"steelhousemedia.com","stickyadstv.com","stroeer.de","swoop.com",
"synacor.com","targetspot.com","teadsplayer.com","technorati.com",
"theadex.com","thetradedesk.net","tinypass.com","triplelift.net",
"tubemogul.com","undertone.net","valuecommerce.com","varick.com",
"vertamedia.com","videoamp.com","viralize.com","vizury.com",
"voicefive.net","yellowblue.io","yieldpartners.com","yieldstar.com",
"zeta.com","zetaglobal.com","ziffdavis.com","zypmedia.com",
"6sense.com","adalyser.com","adcash.net","addapptr.com",
"adhese.com","adition.net","adloox.com","admanager.net",
"adnetik.com","adocean.pl","adpredictive.com","adrta.com",
"adsafe.com","adspirit.de","adswizz.com","adtiger.de",
"adventive.com","affinitiveworks.com","agof.de","aidapipe.com",
"aidsads.com","aim.com","aja-kk.jp","akaads.com",
"albacross.com","alkemics.com","aniview.co","apester.co",
"aps.amazon.com","atwola.com","audienceproject.com","axonix.com",
"bannerflow.com","batch.com","beeswax.com","between-digital.com",
"bidr.io","bilendi.com","blueconic.com","brainlabsdigital.com",
"brightcove.com","browsi.com","captify.co","catchpoint.com",
"channelmix.com","chartboost.com","clickky.biz","clickio.com",
"colossusssp.com","conativ.com","contentexchange.com",
"converge-digital.com","criteo-syndication.com","cxense.com",
"d.adroll.com","datablogo.com","decisiontreelabs.com",
"digitalcontrolroom.com","digiseg.io","dmp.acxiom.com",
"e-planning.net","effectivemeasure.net","ensighten.com",
"evolok.com","exchangewire.com","exponea.com","eyeview.com",
"fastclick.net","flowplayer.com","forensiq.com","freshrelevance.com",
"friendbuy.com","funnelenvy.com","geoedge.com","glimr.io",
"goldbach.com","gravitympacts.com","grow.com","hivestack.com",
"iabtechlab.com","impact-ad.jp","in-page-push.com",
"influencive.com","insightexpressai.com","instapage.com",
"invocacdn.com","ipinyou.com","jscache.com","jwpcdn.com",
"kaizenplatform.net","keyade.com","kruxdigital.com",
"kwikmotion.com","leadscore.io","liftigniter.com",
"listrak.com","livevideo.com","logly.co.jp","lunametrics.com",
"madtech.com","marketingcloud.com","mecomcorp.com",
"metaffiliation.com","mmismm.com","mobclix.com","mobtrics.com",
"mookie1.net","moburst.com","motigo.com","nano-interactive.com",
"netshelter.net","nex8.net","onaudience.net","opencalais.com",
"openstat.net","optim.al","otonomy.io","peer39.net",
"personyze.com","piano.io","plista.com","polar.me",
"poweradspy.com","predicline.com","pressboard.ca",
"programmatic.com","promoted-content.com","pulse360.io",
"quintly.com","reachlocal.com","real-time-bidder.com",
"remerge.io","rntrack.com","rockabox.co","rovion.com",
"s2s.io","salesloft.com","sailthru.com","scupio.com",
"seedtag.com","selectmedia.asia","semcasting.com",
"servedbyadbutler.com","sharedcount.com","showheroes.com",
"sift-science.com","similarweb.com","site-analytics.com",
"sizmek.net","smartology.io","socialtoaster.com",
"spinbackup.com","spyfu.com","stealthbanner.com",
"storygize.net","strossle.com","supponor.com",
"surveymonkey.net","survicate.com","tapfiliate.com",
"tapjoy.com","targetingedge.com","tealium.com","telaria.com",
"the-ozone-project.com","thetrainline-ads.com","tradelab.fr",
"trafficfactory.biz","trafficroots.com","travelaudience.com",
"trendemon.com","trueanthem.com","truex.com","trustarc.com",
"tvsquared.com","tvtag.com","unbounce.com","upfluence.com",
"usemax.de","userreport.com","valueclick.com","vamoos.com",
"vdopia.com","viafoura.com","videoreach.com","viewthrough.com",
"vindico.com","visualdna.com","voicebase.com","vwo.com",
"webengage.com","webgains.com","webtrends.com","weborama.com",
"wisepops.com","wootag.com","xg4ken.com","xtremepush.com",
"yieldkit.com","yieldoptimizer.com","zapr.in","zoomrx.com",
],

"Evil Companies":[
"anthropic.com","claude.ai","console.anthropic.com",
"nestle.com","nespresso.com","nescafe.com","kitkat.com","gerber.com",
"perrier.com","sanpellegrino.com","purina.com","maggi.com",
"palantir.com","gotham.palantir.com","foundry.palantir.com",
"tesla.com","teslamotors.com","shop.tesla.com",
"spacex.com","starlink.com","starshield.spacex.com",
"x.com","twitter.com","t.co","twimg.com","tweetdeck.com",
"xai.com","x.ai","grok.com","grok.x.ai",
"neuralink.com","boringcompany.com","theboringcompany.com",
"disney.com","disneyplus.com","go.com","abc.com","espn.com",
"marvel.com","starwars.com","hulu.com","pixar.com",
"oracle.com","netsuite.com","java.com","mysql.com","oraclecloud.com",
"eloqua.com","bluekai.com",
"mspy.com","mspyonline.com","my.mspyonline.com",
"amazon.com","amazon.co.uk","amazon.de","amazon.fr","amazon.co.jp",
"amazon.ca","amazon.com.au","amazon.in","amazon.es","amazon.it",
"aws.amazon.com","amazonaws.com","twitch.tv","ring.com","imdb.com",
"audible.com","goodreads.com","zappos.com","woot.com",
"primevideo.com","mgm.com",
"baidu.com","baidu.cn","tieba.com","pan.baidu.com",
],

"Social":[
"x.com","twitter.com","t.co","twimg.com","abs.twimg.com","pbs.twimg.com",
"telegram.org","telegram.me","t.me","web.telegram.org",
],

"Adult & OnlyFans":[
"porn.com","pornhub.com","xvideos.com","xnxx.com","xhamster.com",
"redtube.com","youporn.com","tube8.com","beeg.com","spankbang.com",
"eporner.com","hclips.com","sunporno.com","tnaflix.com",
"upornia.com","txxx.com","hqporner.com","heavy-r.com",
"drtuber.com","nuvid.com","winporn.com","pornone.com",
"hdsex.net","iceporn.com","pornoxo.com","alphaporno.com",
"empflix.com","xxxbunker.com","slutload.com","yuvutu.com",
"porndig.com","pornrabbit.com","bravotube.net","cliphunter.com",
"definebabe.com","fapvid.com","fapster.xxx","fapnado.com",
"jizzbunker.com","porndoe.com","tubegalore.com","pornheed.com",
"sextube.com","homemoviestube.com","hellporno.com","fullporner.com",
"theyarehuge.com","fuqer.com","pornjk.com","porntry.com",
"amateurporn.net","homegrownfreaks.net","tubedupe.com",
"hdporn.net","3movs.com","pornhubpremium.com","thumbzilla.com",
"anyporn.com","yourporn.sexy","daftsex.com","netporn.com","porndude.com",
"porn300.com","4tube.com","91porn.com","analdin.com","babesvid.com",
"biguz.net","cumlouder.com","dirtytube.tv","epornin.com",
"faphouse.com","freeporn.com","hdzog.com","heresex.com","hotmovs.com",
"iwank.tv","jizz.com","melonstube.com","milfzr.com",
"noodlemagazine.com","nudevista.com","pervzilla.com","pichunter.com",
"pinflix.com","playvids.com","pornflip.com","porngo.com",
"pornhat.com","pornhd.com","pornid.xxx","pornlib.com","pornmd.com",
"pornolab.net","pornon.com","pornq.com","pornrox.com","pornxs.com",
"proporn.com","r18.com","reallifecam.com","redporno.com",
"royalporntube.com","sexhd.tv","sexvid.xxx","spankwire.com",
"streamporn.to","tubecup.com","tubepatrol.porn","tubewolf.com",
"viewpornfree.tv","viptube.com","voyeurweb.com","voyeurhit.com",
"vporn.com","watchporn.to","worldsex.com","xbabe.com",
"xlxx.com","xtapes.to","yes-porn.com","youjizz.com","yobt.tv",
"chaturbate.com","cam4.com","livejasmin.com","stripchat.com",
"myfreecams.com","bongacams.com","streamate.com","imlive.com",
"flirt4free.com","cams.com","camster.com","jerkmate.com",
"dirtyroulette.com","shagle.com","camfuze.com","camonster.com",
"bazoocam.org","luckycrush.live","omegle.com","camwithher.com",
"onlyfans.com","fansly.com","brazzers.com","vixen.com",
"blacked.com","bangbros.com","realitykings.com","mofos.com",
"naughtyamerica.com","digitalplayground.com","kink.com",
"wicked.com","vivid.com","erome.com","motherless.com",
"playboy.com","penthouse.com","hustler.com","femjoy.com",
"hegre.com","suicidegirls.com","dogfart.com","evilangel.com",
"teamskeet.com","mylf.com","twistys.com","babes.com",
"21sextury.com","21naturals.com","puretaboo.com","manyvids.com",
"modelhub.com","loyalfans.com",
"hentaihaven.xxx","nhentai.net","rule34.xxx","rule34.paheal.net",
"gelbooru.com","e621.net","danbooru.donmai.us","sankakucomplex.com",
"hentai2read.com","fakku.net","hentaifox.com","hentaiera.com",
"hentai.tv","doujins.com","luscious.net","tsumino.com","hanime.tv",
"hentaiworld.tv","asmhentai.com","hitomi.la","novelai.net",
"adultfriendfinder.com","ashleymadison.com","seeking.com",
"adultwork.com","skipthegames.com","eros.com","tryst.link",
"adultsearch.com","bedpage.com","listcrawler.com",
"gaytube.com","xgaytube.com","xtube.com","ashemaletube.com",
"shemale.xxx","gaydemon.com","dudesnude.com","manhunt.net",
"adam4adam.com","scruff.com","grindr.com","men.com",
"camsoda.com","xcams.com","cams.org","sexcams.com","joyourself.com",
"youporngay.com","gayporn.com","boyfriendtv.com","gaymaletube.com",
"xvideos2.com","xvideos3.com","xvideos.es","xvideos.jp",
"pornhub.net","pornhubthbnails.com","pornhublive.com",
"xhamsterlive.com","xhamster2.com","xhamster3.com","xhamster.desi",
"xnxx1.com","xnxx2.com","xnxx-cdn.com",
"eroprofile.com","spankbang.party",
"camwhores.tv","camwhorestv.com","camvault.com","camarads.com",
"recon.com","squirt.org","sniffies.com","cruisingforsex.com",
"literotica.com","asstr.org","fictionmania.tv","sexstories.com",
"adultdvdtalk.com","freeones.com","boobpedia.com","iafd.com",
"fetlife.com","kinkbomb.com","bdsmtube.tv","clips4sale.com",
"iwantclips.com","onlyfans.gallery","fapello.com","simpcity.su",
"coomer.party","coomer.su","kemono.party","kemono.su",
"thothub.to","thothub.tv","leakedzone.com","fapachi.com",
"influencersgonewild.com","fapinfo.com","viralpornhub.com",
"adultimefans.com","reallovedolls.com","doublelist.com",
"adulttime.com","reality-kings.com","teamskeetnetwork.com",
"score.com","xlgirls.com","xlvideos.com","bigtitscream.com",
"youjizz.tv","youjizz.net","upskirt-collection.com",
"voyeur-house.tv","voyeurstyle.com","publicagent.com",
"hookuphotshot.com","fakehub.com","fakeagent.com",
"vixenmedia.com","tushy.com","deeper.com","slayed.com",
"blackedraw.com","blacked-raw.com","exotic4k.com","tiny4k.com",
"passion-hd.com","nubilefilms.com","nubiles.net","nubilesporn.com",
"sextronix.com","sexyhub.com","povlife.com","povperv.com",
"hentaicity.com","hentaigasm.com","hanime1.me","9hentai.com",
"e-hentai.org","exhentai.org","doujindesu.tv","comicsporn.xxx",
"myhentaicomics.com","hentai-foundry.com","hentaifreak.org",
"chochox.com","hentai2read.net","simply-hentai.com",
"cam4free.com","xcamodels.com","livecams.com","webcamfree.com",
"cammodels.com","adultfriendmatch.com","xdating.com",
"benaughty.com","onenightfriend.com","flirt.com","sudy.com",
"fuckbook.com","instantfuck.com","milfaholic.com","fling.com",
"cougarlife.com","xmatch.com","alt.com","bookofsex.com",
"shemaletube.com","tgirl.com","transangels.com","allporn.com",
"javhd.com","javfor.me","javmost.com","javlibrary.com","av01.tv",
"onejav.com","missav.com","supjav.com","jable.tv",
"xxxfiles.com","tktube.com","hclips.net","txxx.tube",
"gotporn.com","xbabe.tv","pornktube.tv","hotgvibe.com",
"camgirl.com","cherry.tv","xmodels.com","chaturbate.tv",
"myvidster.com","gayvid.com","pornhive.tv","porntrex.com",
"eporner.tv","pornvideoq.com","cliphunter.tv","mrskin.com",
"watchmygf.tv","gfrevenge.com","dirtyshack.com","exgfmovies.com",
"trueamateurs.com","yanks.com","abbywinters.com","only3x.com",
"xart.com","metart.com","joymii.com","watch4beauty.com",
"eternaldesire.com","stunning18.com","errotica-archives.com",
"domai.com","femjoyhunter.com","hegre-art.com","zishy.com",
"cherrynudes.com","goddessnudes.com","photodromm.com",
"pmatehunter.com","teenpornstorage.com","teensdotv.com",
"18onlygirls.com","18tokyo.com","sextvx.com","pornstarbyface.com",
"pornstartube.com","tubxporn.com","4kporn.xxx","voyeurfrance.net",
"voyeurflash.com","dinotube.com","alohatube.com","mangovideo.tv",
"18andabused.com","bbwtube.com","chubbyloving.com","xtubeuncensored.com",
"milfnut.tv","milfmovs.com","milfporntoy.com","matureclub.com",
"matureshare.com","maturenl.com","granny-porn.com","oldnanny.com",
"sexvideos.host","sexu.com","sexfury.com","sexywebcamgirls.com",
"camplace.com","camwhorez.tv","camrips.tv","chatterbate.com",
"myfreepaysite.com","clips4salecdn.com","modelcentro.com",
"myclubxxx.com","onlyleaks.com","onlyfinder.com","onlyfans.pics",
"leakedmodels.com","celebjihad.com","celebgate.cc","fappenist.com",
"thefappening.pm","fappeninblog.com","celeb.gate.cc",
"boundhub.com","kink.tube","bdsmvidz.com","restrainedelegance.com",
"whippedass.com","sexandsubmission.com","publicdisgrace.com",
"devicebondage.com","hogtied.com","fuckingmachines.com",
"wiredpussy.com","menonedge.com","boundgods.com","dungeonsex.com",
"sexyandfunny.com","camarads.tv","stripcamfun.com","imlivefree.com",
"cam.com","xcamz.com","camzap.com","camstreams.tv",
"myfreewebcam.com","cam4ultimate.com","seancody.com","corbinfisher.com",
"randyblue.com","nextdoorstudios.com","chaosmen.com","raunchybastards.com",
"falconstudios.com","hotguysfuck.com","gaycest.com","boyfun.com",
"spankbang.tube","fuq.com","porndish.com","4kpornhd.com",
"pornktub.com","xxxstreams.tv","cliphunter.net","fullhdxxx.com",
"sexvidxxx.com","adultism.com","milffox.com","milftrip.com",
"milfed.com","momxxx.com","momvids.com","mommysgirl.com",
"familyhookups.com","familystrokes.com","stepsiblingscaught.com",
"girlsway.com","truelesbian.com","allgirlmassage.com",
"sisloves.me","brattysis.com","daughterswap.com",
"povd.com","povwatchers.com","teamskeetselects.com",
],

"Gore & Shock":[
"theync.com","kaotic.com","crazyshit.com","documentingreality.com",
"hoodsite.com","bestgore.com","goregrish.com","seegore.com",
"watchpeopledie.tv","leakreality.com","shockmansion.com",
"effedupmovies.com","rotten.com","ogrish.com","deepgoretube.com",
"goresee.com","bestgore.net","gorecenter.com","deathaddict.co",
"scat-tube.org","shock-video.com","gore2gasm.com","cute-dead-guys.net",
"liveleak.com","efukt.com","worldstarhiphop.com","sickgore.com",
"gorezone.net","shockgore.com","splatball.com","goregrish.net",
"deathscenes.net","goresplatter.com","goretastic.com","gore-video.com",
"shockdump.com","morbidreality.com","autopsyvault.com","bestgore.org",
"gorenography.com","shockument.com","sickvideos.net","shockingvideos.com",
"funker530.com","combatfootage.com","liveleak.cc",
"meatspin.com","goatse.cx","lemonparty.org","tubgirl.ca",
"ratemypoo.com","ratemypoo.net","ratemypoop.com",
"scatbook.com","scat-video.com","scat-tube.com","scattube.org",
"scatforum.net","shit-fan.com","browntube.com","scatqueens.com",
"shiteaters.com","coprophilia.net",
"nsfl.co","nsfl.net","bestgore.cc","theyync.com",
"gorewire.com","violentvideo.net","deathworld.net",
"hacksaw.cx","crazyvids.net","deadlyvideo.com","gorelovers.com",
"shockumentary.com","corpseflesh.com","deadvid.com","snuffx.com",
"realsnuff.com","gorechannel.net","goregrind.net","morbidforum.net",
"killervideos.com","deathvideos.net","brutalvideo.net",
"morbidamusement.com","offensivecommunity.net","goreworld.com",
"pro-ana.com","proanorexia.com","thinspiration.com",
"pro-mia.com","selfharm.co.uk","suicide-forum.com","sanctioned-suicide.net",
"documentedreality.net","fullgore.com","gorelife.net","gorereality.com",
"shockedmonkeys.com","lastbreath.tv","gorenography.net","hardgore.net",
"worldofdeath.net","realdeathvideos.com","crimescenevideos.com",
"goredump.net","gorehub.net","deathclique.com","goretube.tv",
"cnn.gorebase.net","liveleaked.com","documentingdeath.com",
"kaotic.net","real-gore.com","goreforall.com","sadico.net",
"b4rd.com","bestgore.fun","gorestation.com","the-yuck.com",
"deathvids.net","cartelvideos.com","narcovideos.net","elblogdelnarco.net",
"extremevideos.net","brutalgore.net","goreupload.com","gorevault.net",
"gorefeed.com","gorepost.net","shockingpics.com","disturbingpics.net",
"crimelibrary.net","forensicfiles.tv","autopsyphotos.net",
"warvideos.net","executionvideos.net","beheadingvideo.net",
"isisvideos.net","jihadwatch.tv","combatgore.net",
"roadaccidents.net","fatalcrash.net","carcrashvideos.net",
"morguefile.net","deathrow.tv","cartelexecution.net",
"gorevideos.net","goreclips.net","shockingvids.net","fataltube.net",
"documentingtruth.net","dailymotiongore.net","rawgore.net",
"extremegorevids.net","brutaldeath.net","deathmedia.net",
"graphicvideos.net","mangledbodies.net","carnagevids.net",
"atrocityvideos.net","warcrimesvideos.net","cartelbeheading.net",
"narcoworld.net","gruesomevideos.net","fatalinjuryvideos.net",
"sadisticvideos.net","tortureclips.net","snufffilms.net",
"corpsevideos.net","deathgallery.net","gorewatch.net",
"reddituncensored.net","liveleakarchive.com","bestgorearchive.com",
"theync.net","kaotic.org","crazyshit.net","documentingreality.org",
"ultimategore.com","gorevault.com","gorepost.com","gorehub.com",
"gorechan.net","4gore.com","gorearchive.net","nsflchan.com",
"shockvid.net","fatalityclips.net","autopsyworld.net",
"warzonevids.net","battlefieldvideos.net","executiongore.net",
"gruesomegallery.net","carnageclips.net","deathrealm.net",
"morbidgallery.net","goreuncensored.net","rawexecution.net",
"brutalclips.net","fatalfootage.net","gorezone.org",
],

"Conspiracy & Fringe":[
"infowars.com","prisonplanet.com","banned.video",
"naturalnews.com","beforeitsnews.com","thegatewaypundit.com",
"breitbart.com","newsmax.com","oann.com","epochtimes.com",
"rebelnews.com","worldnetdaily.com","wnd.com","theblaze.com",
"dailywire.com","pjmedia.com","frontpagemag.com",
"americanthinker.com","thefederalist.com",
"qanon.pub","8kun.top","greatawakening.win","voat.co",
"godlikeproductions.com","abovetopsecret.com","vigilantcitizen.com",
"rense.com","whatreallyhappened.com","thetruthseeker.co.uk",
"aim4truth.org","bitchute.com","brighteon.com","rumble.com",
"frankspeech.com","gab.com","parler.com","gettr.com","truthsocial.com",
"mercola.com","greenmedinfo.com","activistpost.com",
"wakeupworld.com","collective-evolution.com","globalresearch.ca",
"veteranstoday.com","lewrockwell.com","chemtrailsplanet.net",
"geoengineeringwatch.org","flatearth.ws","tfes.org",
"theflatearthsociety.org","in5d.com","zerohedge.com",
"dailyexpose.uk","expose-news.com","ukcolumn.org","off-guardian.org",
"rt.com","sputniknews.com","tass.com","xinhuanet.com",
"cgtn.com","press.tv","almayadeen.net",
],

"Crypto & Gambling":[
"binance.com","coinbase.com","kraken.com","kucoin.com",
"okx.com","crypto.com","bybit.com","gate.io","mexc.com",
"bitfinex.com","bitstamp.net","gemini.com","poloniex.com",
"bittrex.com","huobi.com","bitget.com","phemex.com",
"deribit.com","bitmex.com","luno.com","bitvavo.com",
"lbank.com","hashkey.com","whitebit.com","coinstore.com",
"uniswap.org","pancakeswap.finance","sushiswap.org",
"curve.fi","aave.com","compound.finance","makerdao.com",
"dydx.exchange","gmx.io","1inch.io","balancer.fi",
"yearn.finance","synthetix.io","thorchain.org","jupiter.ag",
"raydium.io","orca.so","dexscreener.com","coingecko.com",
"coinmarketcap.com","coincap.io","messari.io","glassnode.com",
"tradingview.com","etherscan.io","bscscan.com","solscan.io","birdeye.so",
"bet365.com","draftkings.com","fanduel.com","betmgm.com",
"caesarssportsbook.com","pointsbet.com","williamhill.com",
"paddypower.com","ladbrokes.com","coral.co.uk","skybet.com",
"betfair.com","betway.com","unibet.com","bwin.com",
"1xbet.com","22bet.com","bovada.lv","mybookie.ag",
"sportsbetting.ag","bookmaker.eu","betvictor.com","888sport.com",
"melbet.com","parimatch.com","sportybet.com","bet9ja.com",
"kalshi.com","polymarket.com",
"888casino.com","pokerstars.com","stake.com","roobet.com",
"rollbit.com","jackpot.com","casumo.com","leovegas.com",
"casino.com","jackpotcity.com","spinpalace.com",
"slotocash.com","ignitioncasino.eu","bitstarz.com",
"cloudbet.com","sportsbet.io","primedice.com","bc.game",
"metaspins.com","fortunejack.com","wolfbet.com","chips.gg",
"shuffle.com","duelbits.com","betfury.io","bustabit.com",
"gamdom.com","vave.com","7bitcasino.com",
"cake.io","biconomy.com","htx.com","upbit.com","bithumb.com",
"coinex.com","xt.com","bitrue.com","p2b.com","latoken.com",
"ascendex.com","bitpanda.com","paribu.com","btcturk.com",
"raboo.io","apex.exchange","hyperliquid.xyz","vertex.trade",
"pump.fun","moonshot.money","dextools.io","dexview.com",
"poocoin.app","geckoterminal.com","defillama.com","zapper.fi",
"debank.com","zerion.io","phantom.app","metamask.io",
"trustwallet.com","exodus.com","ledger.com","trezor.io",
"888poker.com","partypoker.com","ggpoker.com","wsop.com",
"borgata.com","tropicana.net","virgin-bet.com","betuk.com",
"grosvenorcasinos.com","genesiscasino.com","royalvegascasino.com",
"spinsamurai.com","wildz.com","playamo.com","betchain.com",
"fairspin.io","1win.com","22bet.ng","betwinner.com",
"linebet.com","4rabet.com","dafabet.com","fun88.com",
"w88.com","m88.com","12bet.com","sbobet.com","maxbet.com",
"10cric.com","rajabets.com","pin-up.com","mostbet.com",
"casinodays.com","luckydays.com","slots.lv","cafecasino.lv",
"wildcasino.ag","betonline.ag","xbet.ag","gtbets.eu",
"polybet.io","zeusbet.com","novibet.com","betano.com",
],

"AI & Chatbots":[
"chat.openai.com","openai.com","chatgpt.com","api.openai.com",
"platform.openai.com","labs.openai.com",
"claude.ai","anthropic.com","console.anthropic.com",
"gemini.google.com","bard.google.com","aistudio.google.com",
"deepmind.com","labs.google.com",
"copilot.microsoft.com","sydney.bing.com",
"meta.ai","llama.meta.com","ai.meta.com","grok.com","x.ai",
"mistral.ai","chat.mistral.ai","console.mistral.ai",
"perplexity.ai","labs.perplexity.ai",
"character.ai","c.ai","beta.character.ai","crushon.ai",
"janitor.ai","spicychat.ai","chai-research.com","replika.com",
"kindroid.ai","venus.chub.ai","pygmalion.chat",
"midjourney.com","stability.ai","dreamstudio.ai",
"playgroundai.com","leonardo.ai","firefly.adobe.com",
"ideogram.ai","nightcafe.studio","tensor.art","civitai.com",
"seaart.ai","getimg.ai","dezgo.com","lexica.art",
"arthub.ai","pixai.art","novelai.net","waifulabs.com",
"runway.ml","runwayml.com","sora.com","pika.art","luma.ai",
"klingai.com","invideo.io","synthesia.io","heygen.com",
"d-id.com","fliki.ai","elevenlabs.io","murf.ai",
"play.ht","suno.ai","udio.com",
"jasper.ai","copy.ai","writesonic.com","rytr.me","sudowrite.com",
"quillbot.com","wordtune.com","grammarly.com","hyperwriteai.com",
"anyword.com","longshot.ai",
"cursor.sh","cursor.com","tabnine.com","codeium.com",
"sourcegraph.com","continue.dev",
"huggingface.co","replicate.com","together.ai","groq.com",
"fireworks.ai","cohere.com","ai21.com","inflection.ai",
"nat.dev","poe.com","flowgpt.com","ora.ai","deepseek.com",

"replit.com","manus.im","devin.ai","windsurf.com",
"v0.dev","bolt.new","lovable.dev","augmentcode.com",

"pi.ai","you.com","phind.com","forefront.ai","ai.com",
"ca.ai","chub.ai","notion.ai","labs.google",

"otter.ai","descript.com","chatpdf.com","humata.ai",

"voiceflow.com","botpress.com","chatbase.co",

"adcreative.ai","copysmith.ai","taskade.com","galaxy.ai","remaker.ai",

"ollama.com","lmstudio.ai",

"kimi.moonshot.cn","moonshot.cn","qwen.ai","tongyi.aliyun.com",
"zhipuai.cn","chatglm.cn","baichuan-ai.com",
"yiyan.baidu.com","sensetime.com","01.ai","minimax.chat",
"hailuoai.com","doubao.com","xinghuo.xfyun.cn",

"candy.ai","dreamgf.ai","girlfriendgpt.com","secretdesires.ai",
"sakura.fm","dopple.ai",

"wombo.ai","craiyon.com","deepai.org","artbreeder.com",
"starryai.com","photoroom.com","cutout.pro","reface.ai","deepswap.ai",

"capcut.com","vidyo.ai",

"resemble.ai","wellsaidlabs.com","voicemod.net",

"fireflies.ai","fathom.video","rev.com",

"felo.ai","komo.ai",

"fixie.ai","imbue.com","multion.ai",

"aider.chat","cline.bot","sweep.dev",

"writer.com",

"gptzero.me","originality.ai","copyleaks.com",

"gamma.app","tome.app","beautiful.ai",
],

"Tor & Dark Web":[
"torproject.org","www.torproject.org","dist.torproject.org",
"blog.torproject.org","forum.torproject.org","gitlab.torproject.org",
"community.torproject.org","tb-manual.torproject.org",
"check.torproject.org","metrics.torproject.org",
"bridges.torproject.org","onionservices.torproject.org",
"support.torproject.org","people.torproject.org",
"onion.ly","onion.to","onion.cab","onion.pet","onion.ws",
"onion.sh","onion.link","onion.city","tor2web.org","tor2web.io",
"onion.rip","onion.direct","notevil.link",
"ahmia.fi","darksearch.io","onionlandsearchengine.com",
"tails.net","tails.boum.org","whonix.org","geti2p.net",
"i2p2.de","freenetproject.org","hyphanet.org",
"guardianproject.info","orbot.app",
"torbrowser.net","torproject.net",
],
}

REMOTE_SOURCES :dict [str ,list [str ]]={

"Ad Blocking":[

"https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling-porn-social/hosts",

"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/light.txt",
],
"Adult & OnlyFans":[

"https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts",
],

}

def load_custom_feeds ()->list [dict ]:
    if os .path .exists (CUSTOM_FEEDS_FILE ):
        try :
            with open (CUSTOM_FEEDS_FILE )as f :
                data =json .load (f )
            feeds =data .get ("feeds",[])
            out =[]
            for f_ in feeds :
                if not isinstance (f_ ,dict ):continue 
                url =str (f_ .get ("url","")).strip ()
                cat =str (f_ .get ("category","")).strip ()
                if not url or not cat :continue 
                out .append ({
                "label":str (f_ .get ("label","")).strip ()or url ,
                "url":url ,
                "category":cat ,
                "enabled":bool (f_ .get ("enabled",True )),
                })
            return out 
        except Exception :
            pass 
    return []

def save_custom_feeds (feeds :list [dict ]):
    if not _atomic_write_json (CUSTOM_FEEDS_FILE ,{"feeds":feeds }):
        messagebox .showerror ("Save Error",
        "Could not save your custom feeds. Check the log for details:\n"+APP_LOG_FILE )

SUGGESTED_FEEDS :list [dict ]=[
{
"label":"HaGeZi Threat Intelligence Feed",
"url":"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/tif.txt",
"category":"Malware & Phishing",
"desc":"Actively-updated malware, phishing, and scam-domain feed.",
},
{
"label":"HaGeZi Gambling Blocklist",
"url":"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/gambling.txt",
"category":"Crypto & Gambling",
"desc":"Broader coverage of online casinos, betting, and lottery sites.",
},
{
"label":"HaGeZi Social Media (Extended)",
"url":"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/social-extended.txt",
"category":"Social",
"desc":"Adds regional and lesser-known social platforms beyond the built-in list.",
},
{
"label":"HaGeZi Anti-Piracy Feed",
"url":"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/anti.piracy.txt",
"category":"Piracy & Torrents",
"desc":"Torrent trackers, stream-ripping sites, and pirated-media portals.",
},
{
"label":"StevenBlack Fake News",
"url":"https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-only/hosts",
"category":"Conspiracy & Fringe",
"desc":"Known misinformation and disinformation-focused domains.",
},
{
"label":"HaGeZi Dynamic DNS Blocklist",
"url":"https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/dyndns.txt",
"category":"Evil Companies",
"desc":"Dynamic-DNS hostnames commonly abused for scams and malware C2.",
},
]

def build_combined_sources (custom_feeds :list [dict ],
base :dict [str ,list [str ]]=None )->dict [str ,list [str ]]:
    base =base if base is not None else REMOTE_SOURCES 
    combined :dict [str ,list [str ]]={k :list (v )for k ,v in base .items ()}
    for feed in custom_feeds :
        if not feed .get ("enabled",True ):
            continue 
        cat =feed .get ("category","").strip ()
        url =feed .get ("url","").strip ()
        if not cat or not url :
            continue 
        bucket =combined .setdefault (cat ,[])
        if url not in bucket :
            bucket .append (url )
    return combined 

def relative_time (ts_iso :str )->str :
    if not ts_iso :
        return "unknown time"
    import datetime 
    try :
        then =datetime .datetime .fromisoformat (ts_iso )
    except Exception :
        return ts_iso 
    hours =max (0.0 ,(datetime .datetime .now ()-then ).total_seconds ()/3600 )
    if hours <1 :
        return "less than an hour ago"
    if hours <24 :
        return f"{int (hours )}h ago"
    return f"{int (hours //24 )}d ago"

def feed_health (url :str ,feed_status :dict ,stale_hours :float =26 )->dict :
    entry =feed_status .get (url )
    if not entry :
        return {"state":"unknown","label":"Not yet fetched",
        "detail":"This feed hasn't been fetched yet — hit "
        "\"Update Blocklists\" to check it."}

    import datetime 
    last_checked =entry .get ("last_checked")
    age_hours =None 
    if last_checked :
        try :
            then =datetime .datetime .fromisoformat (last_checked )
            age_hours =(datetime .datetime .now ()-then ).total_seconds ()/3600 
        except Exception :
            age_hours =None 

    if not entry .get ("ok",False ):
        err =entry .get ("error")or "Unknown error"
        return {"state":"failed","label":"Failed",
        "detail":f"Last attempt {relative_time (last_checked )}: {err }"}

    if age_hours is not None and age_hours >stale_hours :
        age_txt =relative_time (last_checked )
        return {"state":"stale",
        "label":f"Stale ({age_txt })",
        "detail":f"Last successful fetch was {age_txt } "
        f"({entry .get ('domain_count',0 )} domains) — "
        "hasn't been re-checked recently."}

    n =entry .get ("domain_count",0 )
    return {"state":"ok","label":f"OK · {n :,} domains",
    "detail":f"Last checked {relative_time (last_checked )}, {n :,} domains found."}

def load_config ()->tuple [dict [str ,set [str ]],bool ,dict ]:
    result :dict [str ,set [str ]]={k :set ()for k in TOPICS_DATABASE }
    lifetime =False 
    theme ={"accent":ACCENT ,"bg_img":None ,"titlebar_color":None }
    if os .path .exists (CONFIG_FILE ):
        try :
            with open (CONFIG_FILE )as f :
                data =json .load (f )
            for k ,v in data .get ("topics",{}).items ():
                if k =="_block_all_tor":
                    result [k ]=bool (v )
                    continue 
                result .setdefault (k ,set ())
                result [k ]=set (v )
            lifetime =bool (data .get ("lifetime",False ))
            theme .update (data .get ("theme",{}))
        except Exception :
            pass 
    return result ,lifetime ,theme 

def save_config (topics :dict [str ,set [str ]],lifetime :bool ,theme :dict =None ):
    try :
        ser_topics ={}
        for k ,v in topics .items ():
            if k =="_block_all_tor":
                ser_topics [k ]=bool (v )
            else :
                ser_topics [k ]=sorted (v )
        ok =_atomic_write_json (CONFIG_FILE ,{
        "topics":ser_topics ,
        "lifetime":lifetime ,
        "theme":theme or {"accent":ACCENT ,"bg_img":None }
        })
        if not ok :
            messagebox .showerror ("Save Error",
            "Could not save your settings. Check the log for details:\n"+APP_LOG_FILE )
    except Exception as e :
        messagebox .showerror ("Save Error",str (e ))

_LOCK_DEFAULT ={"enabled":False ,"salt":"","hash":"","cooldown_min":0 }

_PBKDF2_ITERATIONS =200_000 

def hash_password (password :str ,salt :str ,iterations :int =_PBKDF2_ITERATIONS )->str :
    dk =hashlib .pbkdf2_hmac ("sha256",password .encode ("utf-8"),
    salt .encode ("utf-8"),iterations )
    return f"pbkdf2${iterations }${dk .hex ()}"

def verify_password (password :str ,salt :str ,stored_hash :str )->tuple [bool ,str |None ]:
    if stored_hash .startswith ("pbkdf2$"):
        try :
            _ ,iters_s ,_ =stored_hash .split ("$",2 )
            return hash_password (password ,salt ,int (iters_s ))==stored_hash ,None 
        except Exception :
            return False ,None 

    legacy =hashlib .sha256 ((salt +password ).encode ("utf-8")).hexdigest ()
    if legacy ==stored_hash :
        return True ,hash_password (password ,salt )
    return False ,None 

def load_lock ()->dict :
    lock =dict (_LOCK_DEFAULT )
    if os .path .exists (LOCK_FILE ):
        try :
            with open (LOCK_FILE )as f :
                data =json .load (f )
            for k in _LOCK_DEFAULT :
                if k in data :
                    lock [k ]=data [k ]
        except Exception :
            pass 
    return lock 

def save_lock (lock :dict ):
    if not _atomic_write_json (LOCK_FILE ,lock ):
        messagebox .showerror ("Save Error",
        "Could not save the lock settings. Check the log for details:\n"+APP_LOG_FILE )

def load_remote_cache ()->dict :
    if os .path .exists (REMOTE_CACHE_FILE ):
        try :
            with open (REMOTE_CACHE_FILE )as f :
                data =json .load (f )
            data .setdefault ("categories",{})
            data .setdefault ("last_updated",None )
            data .setdefault ("feed_status",{})
            return data 
        except Exception :
            pass 
    return {"categories":{},"last_updated":None ,"feed_status":{}}

def save_remote_cache (cache :dict ):
    _atomic_write_json (REMOTE_CACHE_FILE ,cache )

def _parse_hosts_text (text :str )->set [str ]:
    out :set [str ]=set ()
    skip ={"localhost","localhost.localdomain","local","broadcasthost",
    "ip6-localhost","ip6-loopback","0.0.0.0"}
    for line in text .splitlines ():
        line =line .split ("#",1 )[0 ].strip ()
        if not line :
            continue 
        parts =line .split ()
        if len (parts )<2 :
            continue 
        if parts [0 ]not in ("0.0.0.0","127.0.0.1"):
            continue 
        d =parts [1 ].strip ().lower ()
        if d and d not in skip :
            out .add (d )
    return out 

def fetch_remote_updates (sources :dict [str ,list [str ]]=REMOTE_SOURCES ,
timeout :int =20 
)->tuple [dict [str ,set [str ]],list [str ],dict [str ,dict ]]:
    import datetime 
    results :dict [str ,set [str ]]={}
    errors :list [str ]=[]
    feed_status :dict [str ,dict ]={}
    now =datetime .datetime .now ().isoformat (timespec ="seconds")
    for category ,urls in sources .items ():
        merged :set [str ]=set ()
        for url in urls :
            try :
                req =urllib .request .Request (url ,headers ={"User-Agent":"Revolt-Shield/1.0"})
                with urllib .request .urlopen (req ,timeout =timeout )as resp :
                    text =resp .read ().decode ("utf-8",errors ="replace")
                domains =_parse_hosts_text (text )
                merged |=domains 
                feed_status [url ]={
                "ok":True ,"last_checked":now ,
                "error":None ,"domain_count":len (domains ),
                }
            except Exception as e :
                errors .append (f"{category }: {e }")
                feed_status [url ]={
                "ok":False ,"last_checked":now ,
                "error":str (e ),"domain_count":0 ,
                }
        if merged :
            results [category ]=merged 
    return results ,errors ,feed_status 

def update_remote_blocklists_async (on_done ,sources :dict [str ,list [str ]]=None ):
    if sources is None :
        sources =REMOTE_SOURCES 
    def worker ():
        results ,errors ,feed_status =fetch_remote_updates (sources )
        cache =load_remote_cache ()
        added =0 
        for category ,domains in results .items ():
            existing =set (cache ["categories"].get (category ,[]))
            added +=len (domains -existing )

            cache ["categories"][category ]=sorted (domains )
        cache .setdefault ("feed_status",{}).update (feed_status )
        import datetime 
        cache ["last_updated"]=datetime .datetime .now ().isoformat (timespec ="seconds")
        save_remote_cache (cache )
        on_done (added ,errors )
    threading .Thread (target =worker ,daemon =True ).start ()

def remote_cache_domain_count ()->int :
    cache =load_remote_cache ()
    return sum (len (v )for v in cache ["categories"].values ())

DNS_PORT =53 
LOCAL_DNS_IP ="127.0.0.1"
UPSTREAM_DNS =("1.1.1.1",53 )
_SINKHOLE_TTL =60 

_custom_dns_ip :str |None =None 

def is_valid_ipv4 (ip :str )->bool :
    try :
        socket .inet_aton (ip .strip ())
        return ip .strip ().count (".")==3 
    except Exception :
        return False 

def load_custom_dns ()->str |None :
    if os .path .exists (CUSTOM_DNS_FILE ):
        try :
            with open (CUSTOM_DNS_FILE )as f :
                data =json .load (f )
            ip =str (data .get ("ip","")).strip ()
            if is_valid_ipv4 (ip ):
                return ip 
        except Exception :
            pass 
    return None 

def save_custom_dns (ip :str |None ):
    if not _atomic_write_json (CUSTOM_DNS_FILE ,{"ip":ip or ""}):
        messagebox .showerror ("Save Error",
        "Could not save the custom DNS setting. Check the log for details:\n"+APP_LOG_FILE )

def set_custom_dns_ip (ip :str |None ):
    global _custom_dns_ip 
    _custom_dns_ip =ip if ip and is_valid_ipv4 (ip )else None 

def get_upstream_dns ()->tuple [str ,int ]:
    if _custom_dns_ip :
        return (_custom_dns_ip ,53 )
    return UPSTREAM_DNS 

def load_allowlist ()->set [str ]:
    if os .path .exists (ALLOWLIST_FILE ):
        try :
            with open (ALLOWLIST_FILE )as f :
                data =json .load (f )
            return {clean_domain (d )for d in data .get ("domains",[])if clean_domain (d )}
        except Exception :
            pass 
    return set ()

def save_allowlist (domains :set [str ]):
    if not _atomic_write_json (ALLOWLIST_FILE ,{"domains":sorted (domains )}):
        messagebox .showerror ("Save Error",
        "Could not save the allowlist. Check the log for details:\n"+APP_LOG_FILE )

_dns_server =None 
_dns_state ={"active":False ,"adapters":{}}

_blocked_count =0 
_blocked_lock =threading .Lock ()

_BLOCKED_RECENT_MAX =300 
_blocked_recent :deque =deque (maxlen =_BLOCKED_RECENT_MAX )

def get_blocked_count ()->int :
    with _blocked_lock :
        return _blocked_count 

def _bump_blocked_count ():
    global _blocked_count 
    with _blocked_lock :
        _blocked_count +=1 

def _record_blocked (domain :str ):
    with _blocked_lock :
        _blocked_recent .appendleft ({"domain":domain ,"ts":time .time ()})

def get_recent_blocked (limit :int =60 )->list [dict ]:
    with _blocked_lock :
        return list (_blocked_recent )[:limit ]

def _reset_blocked_count ():
    global _blocked_count 
    with _blocked_lock :
        _blocked_count =0 
        _blocked_recent .clear ()

def _expand_domain_variants (domains :set [str ])->set [str ]:
    out :set [str ]=set ()
    for site in domains :
        d =clean_domain (site )
        if not d :
            continue 
        bare =d [4 :]if d .startswith ("www.")else d 
        if not bare :
            continue 
        out .add (bare )
        out .add (f"www.{bare }")
    return out 

def _combined_blocklist (topics :dict [str ,set [str ]])->set [str ]:
    combined :dict [str ,set [str ]]={k :set (v )for k ,v in TOPICS_DATABASE .items ()}
    for k ,v in topics .items ():
        if k =="_block_all_tor":continue 
        combined .setdefault (k ,set ()).update (v )

    if topics .get ("_block_all_tor"):
        combined .setdefault ("Tor & Dark Web",set ()).update ([
        "onion.ly","onion.to","onion.cab","onion.pet","onion.ws",
        "onion.sh","onion.link","onion.city","tor2web.org","tor2web.io",
        "onion.rip","onion.direct","onion.dog","onion.casa","onion.plus",
        "onion.foundation","onion.re","onion.services","onion.xyz"
        ])
    remote_cache =load_remote_cache ()
    for k ,v in remote_cache .get ("categories",{}).items ():
        combined .setdefault (k ,set ()).update (v )
    all_domains :set [str ]=set ()
    for v in combined .values ():
        all_domains |=v 
    return _expand_domain_variants (all_domains )

def _parse_dns_qname (data :bytes )->str :
    idx =12 
    labels =[]
    try :
        while True :
            length =data [idx ]
            if length ==0 :
                break 
            idx +=1 
            labels .append (data [idx :idx +length ].decode ("ascii",errors ="replace"))
            idx +=length 
    except IndexError :
        pass 
    return ".".join (labels )

def _domain_matches (qname :str ,domains :set [str ])->bool :
    if qname in domains :
        return True 
    parts =qname .split (".")
    for i in range (1 ,len (parts )):
        if ".".join (parts [i :])in domains :
            return True 
    return False 

def _dns_is_blocked (qname :str ,blocked :set [str ],topics :dict =None ,
allowlist :set [str ]=None )->bool :
    qname =qname .rstrip (".").lower ()
    if not qname :
        return False 

    if allowlist and _domain_matches (qname ,allowlist ):
        return False 
    if topics and topics .get ("_block_all_tor"):
        if qname .endswith (".onion")or ".onion."in qname :
            return True 
    if qname in blocked :
        return True 
    parts =qname .split (".")
    for i in range (1 ,len (parts )):
        if ".".join (parts [i :])in blocked :
            return True 
    return False 

def check_site_status (domain :str ,topics :dict [str ,set [str ]],
allowlist :set [str ]=None )->dict :
    d =clean_domain (domain )
    if not d :
        return {"valid":False ,"domain":domain .strip ()}

    allowlist =allowlist or set ()
    if allowlist and _domain_matches (d ,_expand_domain_variants (allowlist )):
        return {"valid":True ,"domain":d ,"blocked":False ,
        "allowlisted":True ,"source":None ,"origin":None }

    if topics .get ("_block_all_tor")and (d .endswith (".onion")or ".onion."in d ):
        return {"valid":True ,"domain":d ,"blocked":True ,
        "allowlisted":False ,"source":"Tor & Dark Web",
        "origin":"Block-all-Tor rule"}

    remote_cache =load_remote_cache ().get ("categories",{})

    ordered :list [tuple [str ,str ,set [str ]]]=[]
    for cat ,doms in topics .items ():
        if cat .startswith ("_"):
            continue 
        ordered .append ((cat ,"Your list",set (doms )))
    for cat ,doms in TOPICS_DATABASE .items ():
        ordered .append ((cat ,"Built-in",set (doms )))
    for cat ,doms in remote_cache .items ():
        ordered .append ((cat ,"Subscribed feed",set (doms )))

    for cat ,origin ,doms in ordered :
        if not doms :
            continue 
        if _domain_matches (d ,_expand_domain_variants (doms )):
            return {"valid":True ,"domain":d ,"blocked":True ,
            "allowlisted":False ,"source":cat ,"origin":origin }

    return {"valid":True ,"domain":d ,"blocked":False ,
    "allowlisted":False ,"source":None ,"origin":None }

def ping_site (domain :str ,timeout :float =4.0 )->dict :
    d =clean_domain (domain )
    if not d :
        return {"valid":False ,"domain":domain .strip ()}

    ips =_resolve_domain_ips (d )
    if not ips :
        return {"valid":True ,"domain":d ,"resolved":False ,
        "up":False ,"latency_ms":None ,"ips":[]}

    up ,latency_ms =False ,None 
    for port in (443 ,80 ):
        try :
            t0 =time .time ()
            with socket .create_connection ((d ,port ),timeout =timeout ):
                latency_ms =int ((time .time ()-t0 )*1000 )
                up =True 
                break 
        except Exception :
            continue 

    return {"valid":True ,"domain":d ,"resolved":True ,"up":up ,
    "latency_ms":latency_ms ,"ips":ips }

def _dns_sinkhole_response (query :bytes )->bytes :
    header =query [:2 ]+b"\x81\x80"+query [4 :6 ]+b"\x00\x01\x00\x00\x00\x00"
    question =query [12 :]
    answer =(b"\xc0\x0c\x00\x01\x00\x01"+struct .pack (">I",_SINKHOLE_TTL )
    +b"\x00\x04"+socket .inet_aton (REDIRECT_IP ))
    return header +question +answer 

class _DNSSinkhole (threading .Thread ):

    def __init__ (self ,blocked :set [str ],topics :dict =None ,allowlist :set [str ]=None ):
        super ().__init__ (daemon =True )
        self .blocked =blocked 
        self .topics =topics 
        self .allowlist =allowlist or set ()
        self ._stop_evt =threading .Event ()
        self .sock =None 
        self .ready =threading .Event ()
        self .bind_error =None 

    def update_blocklist (self ,blocked :set [str ],topics :dict =None ,
    allowlist :set [str ]=None ):
        self .blocked =blocked 
        self .topics =topics 
        if allowlist is not None :
            self .allowlist =allowlist 

    def run (self ):
        try :
            self .sock =socket .socket (socket .AF_INET ,socket .SOCK_DGRAM )
            self .sock .setsockopt (socket .SOL_SOCKET ,socket .SO_REUSEADDR ,1 )
            self .sock .bind ((LOCAL_DNS_IP ,DNS_PORT ))
            self .sock .settimeout (1.0 )
        except Exception as e :
            self .bind_error =e 
            self .ready .set ()
            return 
        self .ready .set ()
        while not self ._stop_evt .is_set ():
            try :
                data ,addr =self .sock .recvfrom (512 )
            except socket .timeout :
                continue 
            except OSError :
                break 
            threading .Thread (target =self ._handle ,args =(data ,addr ),daemon =True ).start ()
        try :
            self .sock .close ()
        except Exception :
            pass 

    def _handle (self ,data :bytes ,addr ):
        try :
            qname =_parse_dns_qname (data )
            if _dns_is_blocked (qname ,self .blocked ,self .topics ,self .allowlist ):
                self .sock .sendto (_dns_sinkhole_response (data ),addr )
                _bump_blocked_count ()
                _record_blocked (qname )
                return 
            up =socket .socket (socket .AF_INET ,socket .SOCK_DGRAM )
            up .settimeout (3.0 )
            try :
                up .sendto (data ,get_upstream_dns ())
                resp ,_ =up .recvfrom (1024 )
                self .sock .sendto (resp ,addr )
            finally :
                up .close ()
        except Exception :
            pass 

    def stop (self ):
        self ._stop_evt .set ()
        try :
            if self .sock :
                self .sock .close ()
        except Exception :
            pass 

def _si_hidden ():
    if os .name !="nt":
        return None 
    si =subprocess .STARTUPINFO ()
    si .dwFlags |=subprocess .STARTF_USESHOWWINDOW 
    si .wShowWindow =0 
    return si 

def _win_active_adapters ()->list [str ]:
    try :
        out =subprocess .run (["netsh","interface","ipv4","show","interfaces"],
        capture_output =True ,text =True ,startupinfo =_si_hidden (),
        timeout =8 ).stdout 
    except Exception :
        return []
    names =[]
    for line in out .splitlines ():
        m =re .match (r"\s*\d+\s+\d+\s+\d+\s+(\S+)\s+(.+)",line )
        if m and m .group (1 ).lower ()=="connected":
            name =m .group (2 ).strip ()
            if name and "loopback"not in name .lower ():
                names .append (name )
    return names 

def _win_get_dns (name :str )->list [str ]:
    try :
        out =subprocess .run (["netsh","interface","ip","show","dns",name ],
        capture_output =True ,text =True ,startupinfo =_si_hidden (),
        timeout =8 ).stdout 
    except Exception :
        return []
    if "dhcp"in out .lower ():
        return []
    return re .findall (r"\b\d{1,3}(?:\.\d{1,3}){3}\b",out )

def _win_set_dns_static (name :str ,ip :str ,secondary :str |None =None ):
    subprocess .run (["netsh","interface","ip","set","dns",f"name={name }","static",ip ,"primary"],
    capture_output =True ,startupinfo =_si_hidden (),timeout =8 )
    if secondary :
        subprocess .run (["netsh","interface","ip","add","dns",f"name={name }",secondary ,"index=2"],
        capture_output =True ,startupinfo =_si_hidden (),timeout =8 )

def _win_restore_dns (name :str ,original_ips :list [str ]):
    if not original_ips :
        subprocess .run (["netsh","interface","ip","set","dns",f"name={name }","dhcp"],
        capture_output =True ,startupinfo =_si_hidden (),timeout =8 )
        return 
    subprocess .run (["netsh","interface","ip","set","dns",f"name={name }","static",
    original_ips [0 ],"primary"],
    capture_output =True ,startupinfo =_si_hidden (),timeout =8 )
    for i ,ip in enumerate (original_ips [1 :],start =2 ):
        subprocess .run (["netsh","interface","ip","add","dns",f"name={name }",ip ,f"index={i }"],
        capture_output =True ,startupinfo =_si_hidden (),timeout =8 )

def _mac_active_services ()->list [str ]:
    try :
        out =subprocess .run (["networksetup","-listallnetworkservices"],
        capture_output =True ,text =True ,timeout =8 ).stdout 
    except Exception :
        return []
    return [l for l in out .splitlines ()[1 :]if l .strip ()and not l .startswith ("*")]

def _mac_get_dns (service :str )->list [str ]:
    try :
        out =subprocess .run (["networksetup","-getdnsservers",service ],
        capture_output =True ,text =True ,timeout =8 ).stdout 
    except Exception :
        return []
    if "aren't any"in out .lower ():
        return []
    return [l .strip ()for l in out .splitlines ()if l .strip ()]

def _mac_set_dns (service :str ,ip :str |list [str ]):
    ips =ip if isinstance (ip ,list )else [ip ]
    subprocess .run (["networksetup","-setdnsservers",service ]+ips ,
    capture_output =True ,timeout =8 )

def _mac_restore_dns (service :str ,original :list [str ]):
    args =original if original else ["empty"]
    subprocess .run (["networksetup","-setdnsservers",service ]+args ,
    capture_output =True ,timeout =8 )

_RESOLV_BACKUP ="/tmp/.revolt_resolv_conf.bak"

def _linux_apply_dns ():
    try :
        if os .path .exists ("/etc/resolv.conf")and not os .path .exists (_RESOLV_BACKUP ):
            with open ("/etc/resolv.conf")as f :
                with open (_RESOLV_BACKUP ,"w")as bak :
                    bak .write (f .read ())

        lines =["nameserver 127.0.0.1\n"]
        if _custom_dns_ip :
            lines .append (f"nameserver {_custom_dns_ip }\n")
        with open ("/etc/resolv.conf","w")as f :
            f .writelines (lines )
    except Exception :
        pass 

def _linux_restore_dns ():
    try :
        if os .path .exists (_RESOLV_BACKUP ):
            with open (_RESOLV_BACKUP )as f :
                backup =f .read ()
            with open ("/etc/resolv.conf","w")as f :
                f .write (backup )
            os .remove (_RESOLV_BACKUP )
    except Exception :
        pass 

def _persist_dns_recovery_state (adapters :dict ):
    _atomic_write_json (DNS_STATE_FILE ,{
    "platform":"nt"if os .name =="nt"else sys .platform ,
    "adapters":adapters ,
    })

def _clear_dns_recovery_state ():
    try :
        if os .path .exists (DNS_STATE_FILE ):
            os .remove (DNS_STATE_FILE )
    except Exception :
        pass 

def recover_dns_from_previous_session ():
    if os .name !="nt"and sys .platform !="darwin":
        return 
    if not os .path .exists (DNS_STATE_FILE ):
        return 
    try :
        with open (DNS_STATE_FILE )as f :
            saved =json .load (f )
        adapters =saved .get ("adapters",{})
        if os .name =="nt":
            for name ,ips in adapters .items ():
                _win_restore_dns (name ,ips )
        elif sys .platform =="darwin":
            for svc ,ips in adapters .items ():
                _mac_restore_dns (svc ,ips )
        if adapters :
            pass 
    except Exception :
        pass 
    finally :
        _clear_dns_recovery_state ()

def _point_dns_to_sinkhole ():
    try :
        if os .name =="nt":

            adapter_names =set (_win_active_adapters ())

            ha =_win_hosted_adapter_name ()
            if ha :adapter_names .add (ha )

            saved ={name :_win_get_dns (name )for name in adapter_names }
            _persist_dns_recovery_state (saved )
            for name in saved :
                _win_set_dns_static (name ,LOCAL_DNS_IP ,secondary =_custom_dns_ip )
            _dns_state ["adapters"]=saved 
        elif sys .platform =="darwin":
            saved ={svc :_mac_get_dns (svc )for svc in _mac_active_services ()}
            _persist_dns_recovery_state (saved )
            for svc in saved :
                _mac_set_dns (svc ,[LOCAL_DNS_IP ,_custom_dns_ip ]if _custom_dns_ip else LOCAL_DNS_IP )
            _dns_state ["adapters"]=saved 
        else :
            _linux_apply_dns ()
            _dns_state ["adapters"]={}
    except Exception :
        pass 

def _restore_system_dns ():
    try :
        if os .name =="nt":
            for name ,ips in _dns_state .get ("adapters",{}).items ():
                _win_restore_dns (name ,ips )
        elif sys .platform =="darwin":
            for svc ,ips in _dns_state .get ("adapters",{}).items ():
                _mac_restore_dns (svc ,ips )
        else :
            _linux_restore_dns ()
    except Exception :
        pass 
    _dns_state ["adapters"]={}
    _clear_dns_recovery_state ()

def _refresh_sinkhole_secondary_dns ():

    if not _dns_state .get ("active"):
        return 
    ip =_custom_dns_ip 
    try :
        if os .name =="nt":
            for name in list (_dns_state .get ("adapters",{}).keys ()):
                _win_set_dns_static (name ,LOCAL_DNS_IP ,secondary =ip )
        elif sys .platform =="darwin":
            for svc in list (_dns_state .get ("adapters",{}).keys ()):
                _mac_set_dns (svc ,[LOCAL_DNS_IP ,ip ]if ip else LOCAL_DNS_IP )
        else :
            _linux_apply_dns ()
    except Exception as e :
        log .debug ("refresh secondary dns failed: %s",e )

_custom_dns_state ={"adapters":set ()}

def apply_direct_custom_dns ():

    if _dns_state .get ("active"):
        _refresh_sinkhole_secondary_dns ()
        return 

    ip =_custom_dns_ip 
    try :
        if os .name =="nt":
            names =set (_win_active_adapters ())
            ha =_win_hosted_adapter_name ()
            if ha :names .add (ha )
            if ip :
                for n in names :
                    _win_set_dns_static (n ,ip )
                _custom_dns_state ["adapters"]=names 
            else :
                for n in names |_custom_dns_state .get ("adapters",set ()):
                    _win_restore_dns (n ,[])
                _custom_dns_state ["adapters"]=set ()
        elif sys .platform =="darwin":
            svcs =set (_mac_active_services ())
            if ip :
                for s in svcs :
                    _mac_set_dns (s ,ip )
                _custom_dns_state ["adapters"]=svcs 
            else :
                for s in svcs |_custom_dns_state .get ("adapters",set ()):
                    _mac_restore_dns (s ,[])
                _custom_dns_state ["adapters"]=set ()
        else :
            if ip :
                try :
                    if os .path .exists ("/etc/resolv.conf")and not os .path .exists (_RESOLV_BACKUP ):
                        with open ("/etc/resolv.conf")as f :
                            with open (_RESOLV_BACKUP ,"w")as bak :
                                bak .write (f .read ())
                    with open ("/etc/resolv.conf","w")as f :
                        f .write (f"nameserver {ip }\n")
                except Exception :
                    pass 
            else :
                _linux_restore_dns ()
    except Exception as e :
        log .debug ("apply_direct_custom_dns failed: %s",e )

def apply_direct_custom_dns_async ():
    threading .Thread (target =apply_direct_custom_dns ,daemon =True ).start ()

atexit .register (lambda :_restore_system_dns ()if _dns_state .get ("active")else None )

def load_vpn_config ()->dict :
    if os .path .exists (VPN_CONFIG_FILE ):
        try :
            with open (VPN_CONFIG_FILE )as f :
                data =json .load (f )
            if isinstance (data ,dict ):
                return data 
        except Exception :
            pass 
    return {}

def save_vpn_config (data :dict ):
    try :
        with open (VPN_CONFIG_FILE ,"w")as f :
            json .dump (data ,f )
    except Exception as e :
        messagebox .showerror ("Save Error",str (e ))

def _detect_vpn_tool (kind :str )->str |None :
    if kind =="wireguard":
        exe =shutil .which ("wg-quick")or shutil .which ("wireguard")
        if exe :
            return exe 
        if os .name =="nt":
            for p in (r"C:\Program Files\WireGuard\wireguard.exe",
            r"C:\Program Files (x86)\WireGuard\wireguard.exe"):
                if os .path .exists (p ):
                    return p 
        return None 
    else :
        exe =shutil .which ("openvpn")
        if exe :
            return exe 
        if os .name =="nt":
            for p in (r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe"):
                if os .path .exists (p ):
                    return p 
        return None 

def _load_vpn_state ()->dict :
    try :
        with open (VPN_STATE_FILE )as f :
            data =json .load (f )
        return data if isinstance (data ,dict )else {}
    except Exception :
        return {}

def _save_vpn_state (data :dict ):
    try :
        with open (VPN_STATE_FILE ,"w")as f :
            json .dump (data ,f )
    except Exception :
        pass 

def _clear_vpn_state ():
    try :
        if os .path .exists (VPN_STATE_FILE ):
            os .remove (VPN_STATE_FILE )
    except Exception :
        pass 

def vpn_is_active ()->bool :
    state =_load_vpn_state ()
    if not state .get ("active"):
        return False 
    iface =state .get ("iface")
    live =any_vpn_interface_active ()
    still_up =(iface in live )if iface else bool (live )
    if not still_up :
        _clear_vpn_state ()
        return False 
    return True 

_VPN_IFACE_MARKERS =(
"wireguard","wg","tun","tap","utun","openvpn","ppp","nordlynx",
"protonvpn","expressvpn","surfshark","windscribe","mullvad",
"cisco anyconnect","globalprotect","fortinet","pulse secure",
"l2tp","pptp","ipsec","tailscale","zerotier",
)

def _windows_active_vpn_interfaces ()->list [str ]:
    found =[]
    try :
        out =subprocess .run (["ipconfig","/all"],capture_output =True ,text =True ,
        startupinfo =_si_hidden (),timeout =8 ).stdout 
    except Exception :
        return found 

    blocks =re .split (r"\r?\n\r?\n",out )
    for block in blocks :
        header =block .strip ().splitlines ()[0 ].lower ()if block .strip ()else ""
        if not any (m in header for m in _VPN_IFACE_MARKERS ):
            continue 
        if re .search (r"IPv[46] Address[.\s]*:\s*[0-9a-fA-F:.]+",block ):
            name =block .strip ().splitlines ()[0 ].rstrip (":").strip ()
            found .append (name )
    return found 

def _posix_active_vpn_interfaces ()->list [str ]:
    found =[]
    try :
        if shutil .which ("ip"):
            out =subprocess .run (["ip","-o","link","show","up"],
            capture_output =True ,text =True ,timeout =8 ).stdout 
        else :
            out =subprocess .run (["ifconfig"],capture_output =True ,text =True ,
            timeout =8 ).stdout 
    except Exception :
        return found 
    for line in out .splitlines ():
        low =line .lower ()
        if any (m in low for m in ("tun","tap","utun","wg","ppp","tailscale",
        "zerotier")):
            m =re .match (r"\s*\d*:?\s*([A-Za-z0-9_.]+)[:\s]",line )
            if m :
                found .append (m .group (1 ))
    return found 

def any_vpn_interface_active ()->list [str ]:
    try :
        return _windows_active_vpn_interfaces ()if os .name =="nt"else _posix_active_vpn_interfaces ()
    except Exception :
        return []

def force_down_interface (name :str )->bool :
    try :
        if os .name =="nt":
            r =subprocess .run (["netsh","interface","set","interface",
            name ,"admin=disable"],
            capture_output =True ,startupinfo =_si_hidden (),
            timeout =10 )
            return r .returncode ==0 
        else :
            r =subprocess .run (["ifconfig",name ,"down"]if shutil .which ("ifconfig")
            else ["ip","link","set",name ,"down"],
            capture_output =True ,timeout =10 )
            return r .returncode ==0 
    except Exception :
        return False 

def _tail (path :str ,max_bytes :int =4000 )->str :
    try :
        with open (path ,"rb")as f :
            f .seek (0 ,os .SEEK_END )
            size =f .tell ()
            f .seek (max (0 ,size -max_bytes ))
            return f .read ().decode ("utf-8",errors ="replace")
    except Exception :
        return ""

def _wg_tunnel_name (config_path :str )->str :
    return os .path .splitext (os .path .basename (config_path ))[0 ]

def _iface_has_address (name :str )->bool :
    try :
        if os .name =="nt":
            out =subprocess .run (["ipconfig","/all"],capture_output =True ,
            text =True ,startupinfo =_si_hidden (),
            timeout =8 ).stdout 
            for block in re .split (r"\r?\n\r?\n",out ):
                lines =block .strip ().splitlines ()
                if not lines or name .lower ()not in lines [0 ].lower ():
                    continue 
                if re .search (r"IPv[46] Address[.\s]*:\s*[0-9a-fA-F:.]+",block ):
                    return True 
            return False 
        else :
            r =subprocess .run (["ip","-o","addr","show",name ]if shutil .which ("ip")
            else ["ifconfig",name ],
            capture_output =True ,text =True ,timeout =8 )
            return r .returncode ==0 and bool (re .search (r"inet6?\s+[0-9a-fA-F:.]+",r .stdout ))
    except Exception :
        return False 

def _wait_for (predicate ,timeout :float ,interval :float =0.5 ):
    deadline =time .time ()+timeout 
    result =False 
    while time .time ()<deadline :
        result =predicate ()
        if result :
            return result 
        time .sleep (interval )
    return result 

_OVPN_FAIL_MARKERS =(
"auth_failed","tls error","tls handshake failed","cannot resolve host",
"connection refused","auth-failure","exiting due to fatal error",
"options error",
)

def connect_vpn (config_path :str ,kind :str )->tuple [bool ,str ]:
    if not config_path or not os .path .exists (config_path ):
        return False ,"That config file doesn't exist — pick one again."
    tool =_detect_vpn_tool (kind )
    if not tool :
        name ="WireGuard"if kind =="wireguard"else "OpenVPN"
        return False ,(f"{name }'s official client isn't installed. Install "
        f"it, then try again — Revolt drives it but doesn't "
        f"install it for you.")
    try :
        if kind =="wireguard":
            tunnel_name =_wg_tunnel_name (config_path )
            if os .name =="nt":
                r =subprocess .run ([tool ,"/installtunnelservice",config_path ],
                capture_output =True ,text =True ,
                startupinfo =_si_hidden (),timeout =20 )
                if r .returncode !=0 :
                    return False ,(r .stderr or r .stdout or 
                    "Failed to start the tunnel.").strip ()
            else :
                r =subprocess .run (["wg-quick","up",config_path ],
                capture_output =True ,text =True ,timeout =20 )
                if r .returncode !=0 :
                    return False ,(r .stderr or "Failed to bring the tunnel up.").strip ()

            up =_wait_for (lambda :_iface_has_address (tunnel_name ),timeout =12 )
            if not up :
                disconnect_vpn (config_path ,kind )
                return False ,("The tunnel service started, but the network "
                "interface never came up with an address — "
                "double-check the config's endpoint/keys and "
                "that the peer is reachable.")
            _save_vpn_state ({"active":True ,"kind":kind ,"iface":tunnel_name ,
            "config_path":config_path })
            return True ,"Connected — tunnel interface is verified up with an address."

        else :
            try :
                if os .path .exists (VPN_LOG_FILE ):
                    os .remove (VPN_LOG_FILE )
            except Exception :
                pass 

            pid =None 
            if os .name =="nt":
                proc =subprocess .Popen (
                [tool ,"--config",config_path ,"--log",VPN_LOG_FILE ],
                startupinfo =_si_hidden (),creationflags =subprocess .CREATE_NO_WINDOW )
                pid =proc .pid 
            else :
                subprocess .Popen (["openvpn","--config",config_path ,"--daemon",
                "--writepid",VPN_PID_FILE ,"--log",VPN_LOG_FILE ])
                _wait_for (lambda :os .path .exists (VPN_PID_FILE ),timeout =5 ,interval =0.25 )
                if os .path .exists (VPN_PID_FILE ):
                    try :
                        with open (VPN_PID_FILE )as f :
                            pid =int (f .read ().strip ())
                    except Exception :
                        pid =None 

            def check ():
                text =_tail (VPN_LOG_FILE )
                if "Initialization Sequence Completed"in text :
                    return "ok"
                low =text .lower ()
                if any (m in low for m in _OVPN_FAIL_MARKERS ):
                    return "fail"
                return None 

            _wait_for (lambda :check ()is not None ,timeout =25 ,interval =0.5 )
            status =check ()

            if status !="ok":

                if os .name =="nt"and pid :
                    subprocess .run (["taskkill","/PID",str (pid ),"/F"],
                    capture_output =True ,startupinfo =_si_hidden (),timeout =8 )
                elif pid :
                    try :os .kill (pid ,15 )
                    except Exception :pass 
                if os .path .exists (VPN_PID_FILE ):
                    try :os .remove (VPN_PID_FILE )
                    except Exception :pass 
                tail_lines =_tail (VPN_LOG_FILE ,800 ).strip ().splitlines ()
                last_line =tail_lines [-1 ]if tail_lines else ""
                if status =="fail":
                    return False ,f"OpenVPN reported an error: {last_line or 'connection failed'}"
                return False ,("Timed out waiting for OpenVPN to finish connecting "
                "— check the server address and your credentials."
                +(f" Last log line: {last_line }"if last_line else ""))

            _save_vpn_state ({"active":True ,"kind":kind ,"iface":None ,
            "config_path":config_path ,"pid":pid })
            return True ,"Connected — OpenVPN confirmed the tunnel handshake completed."
    except Exception as e :
        return False ,str (e )

def disconnect_vpn (config_path :str ,kind :str )->tuple [bool ,str ]:
    tool =_detect_vpn_tool (kind )
    try :
        if kind =="wireguard":
            if os .name =="nt"and tool :
                tunnel_name =_wg_tunnel_name (config_path )
                subprocess .run ([tool ,"/uninstalltunnelservice",tunnel_name ],
                capture_output =True ,startupinfo =_si_hidden (),timeout =20 )
            else :
                subprocess .run (["wg-quick","down",config_path ],
                capture_output =True ,timeout =20 )
        else :
            if os .name =="nt":
                subprocess .run (["taskkill","/IM","openvpn.exe","/F"],
                capture_output =True ,startupinfo =_si_hidden (),timeout =8 )
            elif os .path .exists (VPN_PID_FILE ):
                with open (VPN_PID_FILE )as f :
                    pid =int (f .read ().strip ())
                os .kill (pid ,15 )
        if os .path .exists (VPN_PID_FILE ):
            try :os .remove (VPN_PID_FILE )
            except Exception :pass 
        _clear_vpn_state ()
        return True ,"Disconnected."
    except Exception as e :
        return False ,str (e )

HOTSPOT_CONFIG_FILE =os .path .join (os .path .expanduser ("~"),"revolt_hotspot_config.json")

_hotspot_state ={"engine":None ,"disabled_adapters":[]}

def load_hotspot_config ()->dict :
    try :
        with open (HOTSPOT_CONFIG_FILE )as f :
            return json .load (f )
    except Exception :
        return {}

def save_hotspot_config (cfg :dict ):
    try :
        with open (HOTSPOT_CONFIG_FILE ,"w")as f :
            json .dump (cfg ,f )
    except Exception :
        pass 

def _run_ps (script :str ,timeout :float =15.0 )->str :
    if os .name !="nt":
        return ""
    try :
        out =subprocess .run (
        ["powershell","-NoProfile","-NonInteractive","-Command",script ],
        capture_output =True ,text =True ,startupinfo =_si_hidden (),timeout =timeout )
        return (out .stdout or "").strip ()
    except Exception :
        return ""

def _run_ps_file (script_text :str ,args :list [str ],timeout :float =20.0 )->str :
    if os .name !="nt":
        return ""
    tmp_path =None 
    try :
        fd ,tmp_path =tempfile .mkstemp (suffix =".ps1")
        with os .fdopen (fd ,"w",encoding ="utf-8")as f :
            f .write (script_text )
        out =subprocess .run (
        ["powershell","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass",
        "-File",tmp_path ]+list (args ),
        capture_output =True ,text =True ,startupinfo =_si_hidden (),timeout =timeout )
        return (out .stdout or "").strip ()
    except Exception :
        return ""
    finally :
        if tmp_path :
            try :
                os .remove (tmp_path )
            except Exception :
                pass 

def hotspot_supported ()->bool :
    if os .name !="nt":
        return False 
    out =_run_ps (
    "try { "
    "[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,"
    "Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null; "
    "Write-Output MODERN_OK } catch { }")
    if "MODERN_OK"in out :
        return True 
    try :
        legacy =subprocess .run (["netsh","wlan","show","drivers"],
        capture_output =True ,text =True ,startupinfo =_si_hidden (),
        timeout =8 ).stdout 
    except Exception :
        return False 
    return re .search (r"hosted network supported\s*:\s*yes",legacy ,re .I )is not None 

def list_wifi_adapters ()->list [dict ]:
    if os .name !="nt":
        return []
    out =_run_ps (
    "Get-NetAdapter -Physical -ErrorAction SilentlyContinue | "
    "Where-Object { $_.PhysicalMediaType -match '802.11' -or "
    "$_.InterfaceDescription -match 'Wireless|Wi-Fi|WiFi|802\\.11' } | "
    "Select-Object Name, InterfaceDescription, Status | ConvertTo-Json -Compress")
    if not out :
        return []
    try :
        data =json .loads (out )
    except Exception :
        return []
    if isinstance (data ,dict ):
        data =[data ]
    adapters =[]
    for d in data :
        name =d .get ("Name","")
        if not name :
            continue 
        adapters .append ({
        "name":name ,
        "description":d .get ("InterfaceDescription",""),
        "enabled":str (d .get ("Status","")).lower ()=="up",
        })
    return adapters 

def _set_adapter_enabled (name :str ,enabled :bool ):
    verb ="Enable-NetAdapter"if enabled else "Disable-NetAdapter"
    _run_ps (f"{verb } -Name '{name }' -Confirm:$false -ErrorAction SilentlyContinue")

def _apply_broadcast_selection (selected :list [str ])->tuple [bool ,str ]:
    all_wifi =list_wifi_adapters ()
    _hotspot_state ["disabled_adapters"]=[]
    if not selected or len (selected )>=len (all_wifi ):
        return True ,""
    to_disable =[a ["name"]for a in all_wifi if a ["name"]not in selected ]
    if not to_disable :
        return True ,""
    for name in to_disable :
        _set_adapter_enabled (name ,False )
    _hotspot_state ["disabled_adapters"]=to_disable 
    time .sleep (1.5 )
    return True ,f"broadcasting only on {', '.join (selected )}"

def _restore_broadcast_selection ():
    for name in _hotspot_state .get ("disabled_adapters",[]):
        _set_adapter_enabled (name ,True )
    _hotspot_state ["disabled_adapters"]=[]

_MOBILE_HOTSPOT_PS =r'''
param(
    [string]$Action,
    [string]$Ssid = "",
    [string]$Passphrase = ""
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

try {
    [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
    [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
} catch {
    Write-Output "ERROR:WINRT_UNAVAILABLE"
    exit 1
}

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and !$_.IsGenericMethod
})[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
Function AwaitAction($WinRtAction) {
    $netTask = $asTaskAction.Invoke($null, @($WinRtAction))
    $netTask.Wait(-1) | Out-Null
}

$connProfile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if (-not $connProfile) {
    Write-Output "ERROR:NO_INTERNET_PROFILE"
    exit 1
}
$manager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($connProfile)

switch ($Action) {
    'start' {
        try {
            if ($Ssid -or $Passphrase) {
                $config = New-Object Windows.Networking.NetworkOperators.NetworkOperatorTetheringAccessPointConfiguration
                if ($Ssid) { $config.Ssid = $Ssid }
                if ($Passphrase) { $config.Passphrase = $Passphrase }
                AwaitAction($manager.ConfigureAccessPointAsync($config))
            }
        } catch {
            Write-Output "ERROR:CONFIG_FAILED:$($_.Exception.Message)"
            exit 1
        }
        try {
            $result = Await ($manager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            if ($result.Status -eq [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success -or
                [string]$manager.TetheringOperationalState -eq 'On') {
                Write-Output "OK:STARTED"
            } else {
                Write-Output "ERROR:START_FAILED:$($result.Status)"
            }
        } catch {
            Write-Output "ERROR:START_EXCEPTION:$($_.Exception.Message)"
        }
    }
    'stop' {
        try {
            Await ($manager.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]) | Out-Null
            Write-Output "OK:STOPPED"
        } catch {
            Write-Output "ERROR:STOP_EXCEPTION:$($_.Exception.Message)"
        }
    }
    'status' {
        $state = "Unknown"
        try { $state = [string]$manager.TetheringOperationalState } catch { }
        $clients = 0
        try { $clients = [int]$manager.ClientCount } catch { }
        $ssidOut = ""
        try { $ssidOut = $manager.GetCurrentAccessPointConfiguration().Ssid } catch { }
        Write-Output "STATE:$state"
        Write-Output "CLIENTS:$clients"
        Write-Output "SSID:$ssidOut"
    }
}
'''

def _modern_hotspot (action :str ,ssid :str ="",password :str ="")->str :
    return _run_ps_file (_MOBILE_HOTSPOT_PS ,[
    "-Action",action ,"-Ssid",ssid ,"-Passphrase",password ])

def _win_hosted_adapter_name ()->str |None :
    out =_run_ps (
    "Get-NetAdapter | Where-Object { $_.InterfaceDescription -match "
    "'Hosted Network Virtual|Wi-Fi Direct Virtual|Microsoft Wi-Fi Direct' } | "
    "Select-Object -First 1 -ExpandProperty Name")
    return out .splitlines ()[0 ].strip ()if out .strip ()else None 

def _win_hosted_adapter_ip ()->str |None :
    name =_win_hosted_adapter_name ()
    if not name :
        return None 
    out =_run_ps (
    f"(Get-NetIPAddress -InterfaceAlias '{name }' -AddressFamily IPv4 "
    f"-ErrorAction SilentlyContinue).IPAddress")
    lines =[l .strip ()for l in out .splitlines ()if l .strip ()]
    return lines [0 ]if lines else None 

def _win_public_adapter_name (exclude :str |None =None )->str |None :
    for name in _win_active_adapters ():
        if name !=exclude :
            return name 
    return None 

def _enable_ics_to_hosted_network ()->tuple [bool ,str ]:
    private_name =_win_hosted_adapter_name ()
    if not private_name :
        return False ,"couldn't find the hosted network's virtual adapter"
    public_name =_win_public_adapter_name (exclude =private_name )
    if not public_name :
        return False ,"couldn't find an active internet connection to share"
    script =f"""
$ErrorActionPreference = 'SilentlyContinue'
$share = New-Object -ComObject HNetCfg.HNetShare
foreach ($conn in $share.EnumEveryConnection) {{
    $p = $share.NetConnectionProps($conn)
    $c = $share.INetSharingConfigurationForINetConnection($conn)
    if ($p.Name -eq '{public_name }')  {{ $c.EnableSharing(0) }}
    if ($p.Name -eq '{private_name }') {{ $c.EnableSharing(1) }}
}}
Write-Output DONE
"""
    out =_run_ps (script ,timeout =20 )
    if "DONE"in out :
        return True ,f"sharing '{public_name }' with '{private_name }'"
    return False ,"Windows blocked the automatic sharing step"

def _disable_ics_from_hosted_network ():
    private_name =_win_hosted_adapter_name ()
    if not private_name :
        return 
    script =f"""
$ErrorActionPreference = 'SilentlyContinue'
$share = New-Object -ComObject HNetCfg.HNetShare
foreach ($conn in $share.EnumEveryConnection) {{
    $p = $share.NetConnectionProps($conn)
    $c = $share.INetSharingConfigurationForINetConnection($conn)
    if ($p.Name -eq '{private_name }') {{ $c.DisableSharing() }}
}}
"""
    _run_ps (script ,timeout =15 )

def _start_hotspot_legacy (ssid :str ,password :str )->tuple [bool ,str ]:
    try :
        out1 =subprocess .run (
        ["netsh","wlan","set","hostednetwork","mode=allow",
        f"ssid={ssid }",f"key={password }"],
        capture_output =True ,text =True ,startupinfo =_si_hidden (),timeout =10 )
        if out1 .returncode !=0 :
            return False ,(out1 .stdout +out1 .stderr ).strip ()or "Could not configure the hosted network."

        out2 =subprocess .run (["netsh","wlan","start","hostednetwork"],
        capture_output =True ,text =True ,
        startupinfo =_si_hidden (),timeout =10 )
        combined =(out2 .stdout +out2 .stderr )
        if "started"not in combined .lower ():
            return False ,combined .strip ()or (
            "The hosted network couldn't be started. This adapter/driver "
            "doesn't seem to support either hotspot method Revolt can "
            "drive — try Windows Settings → Mobile hotspot directly.")

        ok ,msg =_enable_ics_to_hosted_network ()
        if not ok :

            for _ in range (5 ):
                time .sleep (1.2 )
                ok ,msg =_enable_ics_to_hosted_network ()
                if ok :
                    break 
        if not ok :

            return True ,"ICS_PENDING:"+msg 
        _hotspot_state ["engine"]="legacy"
        return True ,"Hotspot is on — nearby devices can now connect, and the Shield covers them too."
    except Exception as e :
        return False ,str (e )

def start_hotspot (ssid :str ,password :str ,broadcast_adapters :list [str ]|None =None )->tuple [bool ,str ]:
    if os .name !="nt":
        return False ,"Hotspot creation is only supported on Windows right now."
    if not ssid .strip ():
        return False ,"Give the hotspot a name."
    if not password or len (password )<8 :
        return False ,"Choose a password of at least 8 characters (WPA2 needs it)."

    _apply_broadcast_selection (broadcast_adapters or [])
    save_hotspot_config ({"ssid":ssid ,"password":password ,
    "broadcast_adapters":broadcast_adapters or []})

    out =_modern_hotspot ("start",ssid ,password )
    if "OK:STARTED"in out :
        _hotspot_state ["engine"]="modern"

        if _dns_state .get ("active"):
            ha =_win_hosted_adapter_name ()
            if ha :
                _dns_state .setdefault ("adapters",{})[ha ]=_win_get_dns (ha )
                _win_set_dns_static (ha ,LOCAL_DNS_IP )
        return True ,"Hotspot is on — nearby devices can now connect, and the Shield covers them too."

    ok ,msg =_start_hotspot_legacy (ssid ,password )
    if not ok :
        _restore_broadcast_selection ()
        modern_lines =out .splitlines ()
        reason =(modern_lines [0 ].replace ("ERROR:","")if modern_lines 
        else "modern hotspot API unavailable")
        return False ,f"{msg } (also tried the newer Mobile Hotspot API: {reason })"

    if _dns_state .get ("active"):
        ha =_win_hosted_adapter_name ()
        if ha :
            _dns_state .setdefault ("adapters",{})[ha ]=_win_get_dns (ha )
            _win_set_dns_static (ha ,LOCAL_DNS_IP )
    return ok ,msg 

def stop_hotspot ()->tuple [bool ,str ]:
    if os .name !="nt":
        return False ,"Hotspot creation is only supported on Windows right now."
    try :
        engine =_hotspot_state .get ("engine")
        if engine =="legacy":
            _disable_ics_from_hosted_network ()
            subprocess .run (["netsh","wlan","stop","hostednetwork"],
            capture_output =True ,startupinfo =_si_hidden (),timeout =10 )
        else :
            _modern_hotspot ("stop")

            subprocess .run (["netsh","wlan","stop","hostednetwork"],
            capture_output =True ,startupinfo =_si_hidden (),timeout =10 )
        _hotspot_state ["engine"]=None 
        _restore_broadcast_selection ()
        _device_first_seen .clear ()
        return True ,"Hotspot turned off."
    except Exception as e :
        return False ,str (e )

def hotspot_status ()->dict :
    result ={"running":False ,"ssid":None ,"clients":0 }
    if os .name !="nt":
        return result 

    out =_modern_hotspot ("status")
    lines =out .splitlines ()if out else []
    if lines and not lines [0 ].startswith ("ERROR:"):
        state =ssid =clients =""
        for line in lines :
            if line .startswith ("STATE:"):
                state =line [len ("STATE:"):].strip ()
            elif line .startswith ("CLIENTS:"):
                clients =line [len ("CLIENTS:"):].strip ()
            elif line .startswith ("SSID:"):
                ssid =line [len ("SSID:"):].strip ()
        if state :
            running =state .lower ()=="on"
            if running :
                result ["running"]=True 
                result ["ssid"]=ssid or None 
                try :
                    result ["clients"]=int (clients )
                except Exception :
                    result ["clients"]=0 
                return result 

    try :
        legacy_out =subprocess .run (["netsh","wlan","show","hostednetwork"],
        capture_output =True ,text =True ,
        startupinfo =_si_hidden (),timeout =8 ).stdout 
    except Exception :
        return result 
    m =re .search (r'SSID name\s*:\s*"(.+?)"',legacy_out )
    if m :
        result ["ssid"]=m .group (1 )
    m =re .search (r"^\s*Status\s*:\s*(\S+)",legacy_out ,re .M )
    if m :
        result ["running"]=m .group (1 ).strip ().lower ()=="started"
    m =re .search (r"Number of clients\s*:\s*(\d+)",legacy_out )
    if m :
        result ["clients"]=int (m .group (1 ))
    return result 

def _resolve_hostname (ip :str )->str :
    try :
        socket .setdefaulttimeout (0.6 )
        return socket .gethostbyaddr (ip )[0 ]
    except Exception :
        return "Unknown device"
    finally :
        socket .setdefaulttimeout (None )

def _ping_host (ip :str ,timeout_ms :int =450 )->bool :
    try :
        if os .name =="nt":
            out =subprocess .run (["ping","-n","1","-w",str (timeout_ms ),ip ],
            capture_output =True ,text =True ,startupinfo =_si_hidden (),
            timeout =(timeout_ms /1000 )+2 )
            return out .returncode ==0 and "TTL="in out .stdout .upper ()
        out =subprocess .run (["ping","-c","1","-W","1",ip ],
        capture_output =True ,timeout =2 )
        return out .returncode ==0 
    except Exception :
        return False 

def _arp_delete (ip :str ):
    try :
        subprocess .run (["arp","-d",ip ],capture_output =True ,
        startupinfo =_si_hidden (),timeout =3 )
    except Exception :
        pass 

_MAC_VENDOR_PREFIXES ={
"3C:22:FB":"Apple","F0:18:98":"Apple","AC:DE:48":"Apple","D8:BB:2C":"Apple",
"00:1B:63":"Apple","28:CF:E9":"Apple","F0:99:BF":"Apple","A4:83:E7":"Apple",
"00:1A:11":"Google","F4:F5:D8":"Google","3C:5A:B4":"Google","94:EB:2C":"Google",
"5C:AD:CF":"Samsung","E8:50:8B":"Samsung","CC:07:AB":"Samsung","8C:71:F8":"Samsung",
"A4:5E:60":"Xiaomi","64:CC:2E":"Xiaomi","F0:B4:29":"Xiaomi","78:11:DC":"Xiaomi",
"B0:BE:76":"Huawei","00:E0:FC":"Huawei","48:7B:5E":"Huawei",
"DC:A6:32":"Raspberry Pi","B8:27:EB":"Raspberry Pi","E4:5F:01":"Raspberry Pi",
"3C:8B:FE":"Sony","AC:9B:0A":"Sony","FC:0F:E6":"Sony",
"00:50:56":"VMware","08:00:27":"VirtualBox","00:15:5D":"Hyper-V",
"74:C2:46":"Amazon","F0:27:2D":"Amazon","68:37:E9":"Amazon",
"7C:D1:C3":"Microsoft","00:50:F2":"Microsoft","28:18:78":"Microsoft",
"3C:97:0E":"Intel","00:1B:77":"Intel","94:65:2D":"Intel",
}

def _mac_vendor (mac :str )->str :
    return _MAC_VENDOR_PREFIXES .get (mac .upper ()[:8 ],"")

_device_first_seen :dict [str ,float ]={}

def _hotspot_blocked_macs ()->set [str ]:
    cfg =load_hotspot_config ()
    return {m .upper ()for m in cfg .get ("blocked_macs",[])}

def _save_hotspot_blocked_macs (macs :set [str ]):
    cfg =load_hotspot_config ()
    cfg ["blocked_macs"]=sorted (macs )
    save_hotspot_config (cfg )

def _device_block_rule_name (mac :str )->str :
    return "Revolt-Hotspot-Block-"+mac .upper ().replace (":","")

def block_hotspot_device (ip :str ,mac :str )->tuple [bool ,str ]:
    if os .name !="nt":
        return False ,"Device blocking is only supported on Windows right now."
    try :
        macs =_hotspot_blocked_macs ()
        macs .add (mac .upper ())
        _save_hotspot_blocked_macs (macs )
        name =_device_block_rule_name (mac )
        for suffix ,direction in ((""," in"),("-out","out")):
            subprocess .run (["netsh","advfirewall","firewall","delete","rule",
            f"name={name }{suffix }"],capture_output =True ,startupinfo =_si_hidden ())
            subprocess .run (["netsh","advfirewall","firewall","add","rule",
            f"name={name }{suffix }",f"dir={direction .strip ()}","action=block",
            f"remoteip={ip }"],capture_output =True ,check =True ,
            startupinfo =_si_hidden ())
        _arp_delete (ip )
        _device_first_seen .pop (mac .upper (),None )
        return True ,"Device blocked — it no longer has network access through this hotspot."
    except Exception as e :
        return False ,str (e )

def unblock_hotspot_device (mac :str )->tuple [bool ,str ]:
    if os .name !="nt":
        return False ,"Not supported on this platform."
    try :
        macs =_hotspot_blocked_macs ()
        macs .discard (mac .upper ())
        _save_hotspot_blocked_macs (macs )
        name =_device_block_rule_name (mac )
        for suffix in ("","-out"):
            subprocess .run (["netsh","advfirewall","firewall","delete","rule",
            f"name={name }{suffix }"],capture_output =True ,startupinfo =_si_hidden ())
        return True ,"Device unblocked."
    except Exception as e :
        return False ,str (e )

def list_blocked_hotspot_devices ()->list [dict ]:
    return [{"mac":m }for m in sorted (_hotspot_blocked_macs ())]

def list_hotspot_devices ()->list [dict ]:
    if os .name !="nt":
        return []
    host_ip =_win_hosted_adapter_ip ()or "192.168.137.1"
    try :
        out =subprocess .run (["arp","-a"],capture_output =True ,text =True ,
        startupinfo =_si_hidden (),timeout =8 ).stdout 
    except Exception :
        return []
    subnet_prefix =".".join (host_ip .split (".")[:3 ])+"."
    candidates ,in_block =[],False 
    for line in out .splitlines ():
        if line .strip ().lower ().startswith ("interface:"):
            in_block =host_ip in line 
            continue 
        if not in_block :
            continue 
        m =re .match (r"\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F-]{17})\s+(\w+)",line )
        if not m :
            continue 
        ip ,mac ,_kind =m .groups ()
        mac =mac .upper ().replace ("-",":")
        if ip ==host_ip or not ip .startswith (subnet_prefix )or ip .endswith (".255"):
            continue 
        candidates .append ((ip ,mac ))

    if not candidates :
        _device_first_seen .clear ()
        return []

    blocked =_hotspot_blocked_macs ()
    live :dict [str ,str ]={}
    lock =threading .Lock ()

    def probe (ip :str ,mac :str ):
        if _ping_host (ip ):
            with lock :
                live [mac ]=ip 
        else :

            _arp_delete (ip )
            _device_first_seen .pop (mac ,None )

    threads =[threading .Thread (target =probe ,args =(ip ,mac ),daemon =True )
    for ip ,mac in candidates ]
    for t in threads :t .start ()
    for t in threads :t .join (timeout =3.0 )

    for seen_mac in list (_device_first_seen .keys ()):
        if seen_mac not in live :
            _device_first_seen .pop (seen_mac ,None )

    now =time .time ()
    devices =[]
    for mac ,ip in live .items ():
        if mac in blocked :
            continue 
        first =_device_first_seen .setdefault (mac ,now )
        devices .append ({
        "ip":ip ,"mac":mac ,
        "hostname":_resolve_hostname (ip ),
        "vendor":_mac_vendor (mac ),
        "since":first ,
        })
    devices .sort (key =lambda d :d ["since"])
    return devices 

def get_hotspot_bandwidth ()->dict :
    name =_win_hosted_adapter_name ()
    if not name :
        return {"sent":0 ,"received":0 }
    out =_run_ps (
    f"$s = Get-NetAdapterStatistics -Name '{name }' -ErrorAction SilentlyContinue; "
    f"if ($s) {{ \"$($s.SentBytes),$($s.ReceivedBytes)\" }}")
    try :
        sent ,recv =out .strip ().split (",")
        return {"sent":int (sent ),"received":int (recv )}
    except Exception :
        return {"sent":0 ,"received":0 }

atexit .register (lambda :stop_hotspot ()
if _hotspot_state .get ("engine")or _hotspot_state .get ("disabled_adapters")
else None )

VPNGATE_API_URL ="http://www.vpngate.net/api/iphone/"
VPNGATE_CACHE_DIR =os .path .join (os .path .expanduser ("~"),".revolt_vpngate")

def fetch_vpngate_relays (timeout :float =10.0 )->list [dict ]:
    try :
        req =urllib .request .Request (VPNGATE_API_URL ,
        headers ={"User-Agent":"Revolt/1.0"})
        with urllib .request .urlopen (req ,timeout =timeout )as resp :
            text =resp .read ().decode ("utf-8",errors ="replace")
    except Exception :
        return []

    relays :list [dict ]=[]
    for line in text .splitlines ():
        if not line or line .startswith ("*")or line .startswith ("#"):
            continue 
        parts =line .split (",")
        if len (parts )<15 :
            continue 
        try :
            relays .append ({
            "host":parts [0 ],
            "ip":parts [1 ],
            "score":int (parts [2 ])if parts [2 ].isdigit ()else 0 ,
            "ping_ms":int (parts [3 ])if parts [3 ].isdigit ()else None ,
            "speed_mbps":round (int (parts [4 ])/1_000_000 ,1 )if parts [4 ].isdigit ()else None ,
            "country_long":parts [5 ]or "Unknown",
            "country_short":parts [6 ]or "XX",
            "sessions":parts [7 ],
            "config_b64":parts [14 ],
            })
        except Exception :
            continue 
    relays .sort (key =lambda r :r ["score"],reverse =True )
    return relays 

def save_vpngate_config (relay :dict )->str |None :
    try :
        text =base64 .b64decode (relay .get ("config_b64","")).decode (
        "utf-8",errors ="replace")
        if "remote "not in text :
            return None 
        os .makedirs (VPNGATE_CACHE_DIR ,exist_ok =True )
        fname =re .sub (r"[^A-Za-z0-9_.\-]","_",
        f"{relay .get ('country_short','XX')}_{relay .get ('ip','relay')}.ovpn")
        path =os .path .join (VPNGATE_CACHE_DIR ,fname )
        with open (path ,"w")as f :
            f .write (text )
        return path 
    except Exception :
        return None 

def detect_shield ()->bool :
    return _dns_state .get ("active",False )

def apply_blocking (topics :dict [str ,set [str ]],allowlist :set [str ]=None )->int :
    global _dns_server 
    blocked =_combined_blocklist (topics )

    if allowlist is None :
        allowlist =load_allowlist ()

    if _dns_server is None :
        srv =_DNSSinkhole (blocked ,topics ,allowlist )
        srv .start ()
        srv .ready .wait (timeout =5 )
        if srv .bind_error is not None :
            raise PermissionError (
            "Could not start the local DNS sinkhole on 127.0.0.1:53 "
            f"({srv .bind_error }). Make sure no other DNS service, VPN, "
            "or ad-blocker is already using port 53, then try again.")
        _dns_server =srv 
    else :
        _dns_server .update_blocklist (blocked ,topics ,allowlist )

    if not _dns_state ["active"]:
        _point_dns_to_sinkhole ()
        _dns_state ["active"]=True 
        _reset_blocked_count ()

    flush_dns ()
    return len (blocked )

def remove_blocking ():
    global _dns_server 
    _restore_system_dns ()
    _dns_state ["active"]=False 
    if _dns_server is not None :
        _dns_server .stop ()
        _dns_server =None 
    flush_dns ()

LIFETIME_HOSTS_BEGIN ="# >>> Revolt lifetime block — do not edit between these lines >>>"
LIFETIME_HOSTS_END ="# <<< Revolt lifetime block <<<"

def get_system_hosts_path ()->str :
    if os .name =="nt":
        root =os .environ .get ("SystemRoot",r"C:\Windows")
        return os .path .join (root ,"System32","drivers","etc","hosts")
    return "/etc/hosts"

def _has_hosts_write_access ()->bool :
    if os .name =="nt":
        return is_admin ()
    try :
        return os .getuid ()==0 
    except Exception :
        return False 

def _backup_hosts_once (path :str ):
    backup =path +".revolt_original"
    try :
        if os .path .exists (path )and not os .path .exists (backup ):
            shutil .copy2 (path ,backup )
    except Exception as e :
        log .warning (f"Could not back up hosts file: {e }")

def _strip_lifetime_block (lines :list [str ])->list [str ]:
    out =[]
    skipping =False 
    for line in lines :
        stripped =line .rstrip ("\n")
        if stripped ==LIFETIME_HOSTS_BEGIN :
            skipping =True 
            continue 
        if stripped ==LIFETIME_HOSTS_END :
            skipping =False 
            continue 
        if not skipping :
            out .append (line )
    while out and not out [-1 ].strip ():
        out .pop ()
    return out 

def _atomic_write_hosts (path :str ,lines :list [str ])->bool :
    directory =os .path .dirname (path )or "."
    fd ,tmp_path =tempfile .mkstemp (prefix =".revolt_hosts_",dir =directory )
    try :
        with os .fdopen (fd ,"w",encoding ="utf-8")as f :
            f .writelines (lines )
            f .flush ()
            os .fsync (f .fileno ())
        os .replace (tmp_path ,path )
        return True 
    except Exception :
        try :os .remove (tmp_path )
        except Exception :pass 
        raise 

def write_lifetime_hosts (domains :set [str ])->tuple [bool ,str ]:
    path =get_system_hosts_path ()
    if not _has_hosts_write_access ():
        return False ,("Administrator privileges are required to write to the "
        "system hosts file." if os .name =="nt"else 
        "Root privileges are required to write to /etc/hosts.")
    try :
        _backup_hosts_once (path )
        try :
            with open (path ,"r",encoding ="utf-8",errors ="ignore")as f :
                existing =f .readlines ()
        except FileNotFoundError :
            existing =[]
        base_lines =_strip_lifetime_block (existing )
        block =[LIFETIME_HOSTS_BEGIN +"\n"]
        for d in sorted (domains ):
            block .append (f"0.0.0.0 {d }\n")
        block .append (LIFETIME_HOSTS_END +"\n")
        new_content =base_lines +["\n"]+block 
        _atomic_write_hosts (path ,new_content )
        flush_dns ()
        log .info (f"Lifetime mode: wrote {len (domains )} domains to {path }")
        return True ,f"{len (domains )} domains written to the system hosts file."
    except Exception as e :
        log .warning (f"Failed to write lifetime hosts block: {e }")
        return False ,str (e )

def clear_lifetime_hosts ()->tuple [bool ,str ]:
    path =get_system_hosts_path ()
    if not _has_hosts_write_access ():
        return False ,("Administrator privileges are required to edit the "
        "system hosts file." if os .name =="nt"else 
        "Root privileges are required to edit /etc/hosts.")
    try :
        try :
            with open (path ,"r",encoding ="utf-8",errors ="ignore")as f :
                existing =f .readlines ()
        except FileNotFoundError :
            return True ,"Nothing to clear."
        base_lines =_strip_lifetime_block (existing )
        new_content =[l if l .endswith ("\n")else l +"\n"for l in base_lines ]
        _atomic_write_hosts (path ,new_content )
        flush_dns ()
        log .info ("Lifetime mode: cleared hosts file block")
        return True ,"Lifetime hosts entries removed."
    except Exception as e :
        log .warning (f"Failed to clear lifetime hosts block: {e }")
        return False ,str (e )

def _resolve_domain_ips (domain :str )->list [str ]:
    ips :set [str ]=set ()
    try :
        for res in socket .getaddrinfo (domain ,None ,socket .AF_INET ):
            ips .add (res [4 ][0 ])
    except Exception :
        pass 
    return sorted (ips )

def _test_domain_reachable (domain :str ,timeout :float =3.0 )->bool :
    for port in (443 ,80 ):
        try :
            with socket .create_connection ((domain ,port ),timeout =timeout ):
                return True 
        except Exception :
            continue 
    return False 

def _firewall_rule_name (domain :str )->str :
    return f"Revolt-Allow-{domain }"

def open_ports_for_domain (domain :str )->tuple [bool ,str ]:
    ips =_resolve_domain_ips (domain )
    if not ips :
        return False ,(f'"{domain }" was added to the allowlist, but it '
        "couldn't be resolved right now — double check the "
        "spelling or your internet connection.")

    fw_note =""
    if os .name =="nt":
        try :
            name =_firewall_rule_name (domain )

            subprocess .run (
            ["netsh","advfirewall","firewall","delete","rule",f"name={name }"],
            capture_output =True ,startupinfo =_si_hidden ())
            subprocess .run (
            ["netsh","advfirewall","firewall","add","rule",
            f"name={name }","dir=out","action=allow",
            f"remoteip={','.join (ips )}","protocol=TCP",
            "remoteport=80,443"],
            capture_output =True ,check =True ,startupinfo =_si_hidden ())
            fw_note =" An outbound firewall rule for it was added too."
        except Exception as e :
            fw_note =f" (Couldn't add a firewall rule for it: {e })"

    if _test_domain_reachable (domain ):
        return True ,(f'"{domain }" is allowlisted and reachable '
        f"({', '.join (ips )}).{fw_note }")
    return True ,(f'"{domain }" is allowlisted and resolves to '
    f"{', '.join (ips )}, but a live connection couldn't be "
    f"confirmed just now (it may still work fine).{fw_note }")

def close_ports_for_domain (domain :str ):
    if os .name !="nt":
        return 
    try :
        subprocess .run (
        ["netsh","advfirewall","firewall","delete","rule",
        f"name={_firewall_rule_name (domain )}"],
        capture_output =True ,startupinfo =_si_hidden ())
    except Exception :
        pass 

def _fmt_ago (ts :float )->str :
    d =max (0.0 ,time .time ()-ts )
    if d <1.5 :
        return "just now"
    if d <60 :
        return f"{int (d )}s ago"
    if d <3600 :
        return f"{int (d //60 )}m ago"
    return f"{int (d //3600 )}h ago"

def draw_rrect (cv :tk .Canvas ,x1 ,y1 ,x2 ,y2 ,r =8 ,**kw ):
    r =max (0 ,min (r ,(x2 -x1 )//2 ,(y2 -y1 )//2 ))
    if r ==0 :
        cv .create_rectangle (x1 ,y1 ,x2 ,y2 ,**kw )
        return 
    pts =[
    x1 +r ,y1 ,x2 -r ,y1 ,
    x2 ,y1 ,x2 ,y1 +r ,
    x2 ,y2 -r ,x2 ,y2 ,
    x2 -r ,y2 ,x1 +r ,y2 ,
    x1 ,y2 ,x1 ,y2 -r ,
    x1 ,y1 +r ,x1 ,y1 ,
    x1 +r ,y1 ,
    ]
    cv .create_polygon (pts ,smooth =True ,**kw )

# Iconoir icons (https://iconoir.com), rasterized at runtime via cairosvg + Pillow.
# falls back to the old hand-drawn canvas glyphs if those libs aren't installed
_IOR_SVG ={
"app-window":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M2 19V5C2 3.89543 2.89543 3 4 3H20C21.1046 3 22 3.89543 22 5V19C22 20.1046 21.1046 21 20 21H4C2.89543 21 2 20.1046 2 19Z\" stroke=\"currentColor\"/> <path d=\"M2 7L22 7\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M5 5.01L5.01 4.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M8 5.01L8.01 4.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M11 5.01L11.01 4.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"chat-bubble":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M17 12.5C17.2761 12.5 17.5 12.2761 17.5 12C17.5 11.7239 17.2761 11.5 17 11.5C16.7239 11.5 16.5 11.7239 16.5 12C16.5 12.2761 16.7239 12.5 17 12.5Z\" fill=\"currentColor\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 12.5C12.2761 12.5 12.5 12.2761 12.5 12C12.5 11.7239 12.2761 11.5 12 11.5C11.7239 11.5 11.5 11.7239 11.5 12C11.5 12.2761 11.7239 12.5 12 12.5Z\" fill=\"currentColor\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7 12.5C7.27614 12.5 7.5 12.2761 7.5 12C7.5 11.7239 7.27614 11.5 7 11.5C6.72386 11.5 6.5 11.7239 6.5 12C6.5 12.2761 6.72386 12.5 7 12.5Z\" fill=\"currentColor\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 13.8214 2.48697 15.5291 3.33782 17L2.5 21.5L7 20.6622C8.47087 21.513 10.1786 22 12 22Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"check":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M5 13L9 17L19 7\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"city":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M7 9.01L7.01 8.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M11 9.01L11.01 8.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7 13.01L7.01 12.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M11 13.01L11.01 12.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7 17.01L7.01 16.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M11 17.01L11.01 16.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M15 21H3.6C3.26863 21 3 20.7314 3 20.4V5.6C3 5.26863 3.26863 5 3.6 5H9V3.6C9 3.26863 9.26863 3 9.6 3H14.4C14.7314 3 15 3.26863 15 3.6V9M15 21H20.4C20.7314 21 21 20.7314 21 20.4V9.6C21 9.26863 20.7314 9 20.4 9H15M15 21V17M15 9V13M15 13H17M15 13V17M15 17H17\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"cpu":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 14 14\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M6.035 2.507c-0.653 1.073 -0.204 2.73 1.344 3 0.545 0.095 0.978 0.51 1.096 1.05l0.02 0.092c0.454 2.073 3.407 2.086 3.878 0.017l0.025 -0.108a1.4 1.4 0 0 1 0.04 -0.139v5.791c0 0.941 -0.764 1.704 -1.705 1.704H1.734A1.704 1.704 0 0 1 0.03 12.21V4.211c0 -0.941 0.763 -1.704 1.704 -1.704h4.3Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M3.08 7.797a0.625 0.625 0 1 0 -0.883 0.884L3.255 9.74l-1.058 1.058a0.625 0.625 0 0 0 0.884 0.884l1.5 -1.5a0.625 0.625 0 0 0 0 -0.884l-1.5 -1.5Zm2.559 2.817a0.625 0.625 0 1 0 0 1.25h1.5a0.625 0.625 0 0 0 0 -1.25h-1.5Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M6.035 2.507c-0.653 1.073 -0.204 2.73 1.344 3 0.318 0.055 0.598 0.22 0.8 0.454H0.028V4.21c0 -0.941 0.764 -1.704 1.705 -1.704h4.3Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M11.233 0.721C11.04 -0.13 9.825 -0.125 9.638 0.728l-0.007 0.035 -0.015 0.068A2.53 2.53 0 0 1 7.58 2.772c-0.887 0.154 -0.887 1.428 0 1.582a2.53 2.53 0 0 1 2.038 1.952l0.02 0.093c0.187 0.852 1.401 0.858 1.595 0.007l0.025 -0.108a2.546 2.546 0 0 1 2.046 -1.942c0.889 -0.155 0.889 -1.43 0 -1.585A2.546 2.546 0 0 1 11.26 0.844l-0.018 -0.082 -0.01 -0.041Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> </svg>",
"dice-five":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M13.75 13.25a2 2 0 0 1 -2 2h-0.88a0.75 0.75 0 1 1 0 -1.5h0.88a0.5 0.5 0 0 0 0 -1H11a0.76 0.76 0 0 1 -0.75 -0.75V9.5a0.76 0.76 0 0 1 0.75 -0.75h2a0.75 0.75 0 0 1 0 1.5h-1a0.25 0.25 0 0 0 -0.25 0.25v0.5a0.25 0.25 0 0 0 0.22 0.25 2 2 0 0 1 1.78 2Z\" fill=\"currentColor\" stroke-width=\"1\"/> <path d=\"M12 0a12 12 0 1 0 12 12A12 12 0 0 0 12 0Zm4.83 3.57a0.23 0.23 0 0 1 0.17 -0.14 0.3 0.3 0 0 1 0.21 0 10.18 10.18 0 0 1 3.36 3.36 0.3 0.3 0 0 1 0 0.21 0.23 0.23 0 0 1 -0.14 0.15l-2.81 1.21a0.27 0.27 0 0 1 -0.3 -0.09 6.32 6.32 0 0 0 -1.59 -1.59 0.27 0.27 0 0 1 -0.09 -0.3ZM12 2.5a1 1 0 1 1 -1 1 1 1 0 0 1 1 -1Zm-5.19 1a0.3 0.3 0 0 1 0.21 0 0.23 0.23 0 0 1 0.15 0.14l1.19 2.74a0.27 0.27 0 0 1 -0.09 0.3 6.32 6.32 0 0 0 -1.59 1.59 0.27 0.27 0 0 1 -0.3 0.09L3.57 7.17A0.23 0.23 0 0 1 3.43 7a0.3 0.3 0 0 1 0 -0.21 10.18 10.18 0 0 1 3.38 -3.34ZM2.5 12a1 1 0 1 1 1 1 1 1 0 0 1 -1 -1Zm4.67 8.43a0.23 0.23 0 0 1 -0.15 0.14 0.3 0.3 0 0 1 -0.21 0 10.18 10.18 0 0 1 -3.36 -3.36 0.3 0.3 0 0 1 0 -0.21 0.23 0.23 0 0 1 0.14 -0.15l2.81 -1.19a0.27 0.27 0 0 1 0.3 0.09 6.32 6.32 0 0 0 1.59 1.59 0.27 0.27 0 0 1 0.09 0.3ZM12 21.5a1 1 0 1 1 1 -1 1 1 0 0 1 -1 1Zm0 -5a4.5 4.5 0 1 1 4.5 -4.5 4.51 4.51 0 0 1 -4.5 4.5Zm5.19 4.05a0.3 0.3 0 0 1 -0.21 0 0.23 0.23 0 0 1 -0.15 -0.14l-1.19 -2.81a0.27 0.27 0 0 1 0.09 -0.3 6.32 6.32 0 0 0 1.59 -1.59 0.27 0.27 0 0 1 0.3 -0.09l2.81 1.19a0.23 0.23 0 0 1 0.14 0.15 0.3 0.3 0 0 1 0 0.21 10.18 10.18 0 0 1 -3.38 3.38ZM20.5 13a1 1 0 1 1 1 -1 1 1 0 0 1 -1 1Z\" fill=\"currentColor\" stroke-width=\"1\"/> </svg>",
"download-circle":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" d=\"M5 21c-1.10457 0 -2 -0.8954 -2 -2h2zm4 0H7v-2h2zm4 0h-2v-2h2zm4 0h-2v-2h2zm4 -2c0 1.1046 -0.8954 2 -2 2v-2zM5 17H3v-2h2zm16 0h-2v-2h2zm-9 -9c0.5523 0.00002 1 0.44773 1 1v3.5859l1.043 -1.0429c0.3905 -0.3905 1.0235 -0.3905 1.414 0s0.3905 1.0235 0 1.414l-2.75 2.75 -0.0761 0.0684c-0.3928 0.3203 -0.9718 0.2977 -1.3379 -0.0684l-2.75003 -2.75c-0.39046 -0.3905 -0.39046 -1.0235 0 -1.414 0.39051 -0.3905 1.02354 -0.3905 1.41406 0L11 12.5859V9c0 -0.55225 0.4478 -0.99995 1 -1m-7 5H3v-2h2zm16 0h-2v-2h2zM5 9H3V7h2zm16 0h-2V7h2zM5 5H3c0 -1.10457 0.89543 -2 2 -2zm4 0H7V3h2zm4 0h-2V3h2zm4 0h-2V3h2zm2 -2c1.1046 0 2 0.89543 2 2h-2z\" stroke-width=\"1\"/> </svg>",
"erase":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M21 21L9 21\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M15.889 14.8891L8.46436 7.46448\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M2.8934 12.6066L12.0858 3.41421C12.8668 2.63317 14.1332 2.63317 14.9142 3.41421L19.864 8.36396C20.645 9.14501 20.645 10.4113 19.864 11.1924L10.6213 20.435C10.2596 20.7968 9.76894 21 9.25736 21C8.74577 21 8.25514 20.7968 7.8934 20.435L2.8934 15.435C2.11235 14.654 2.11235 13.3877 2.8934 12.6066Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"eye":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M3 13C6.6 5 17.4 5 21 13\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 17C10.3431 17 9 15.6569 9 14C9 12.3431 10.3431 11 12 11C13.6569 11 15 12.3431 15 14C15 15.6569 13.6569 17 12 17Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"globe":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M2.5 12.5L8 14.5L7 18L8 21\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M17 20.5L16.5 18L14 17V13.5L17 12.5L21.5 13\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M19 5.5L18.5 7L15 7.5V10.5L17.5 9.5H19.5L21.5 10.5\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M2.5 10.5L5 8.5L7.5 8L9.5 5L8.5 3\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"import":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M4 13V19C4 20.1046 4.89543 21 6 21H18C19.1046 21 20 20.1046 20 19V13\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 3L12 15M12 15L8.5 11.5M12 15L15.5 11.5\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"infinite":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M14 9L13.75 9.375M10 9C9.08779 7.78565 7.63574 7 6 7C3.23858 7 1 9.23858 1 12C1 14.7614 3.23858 17 6 17C7.63582 17 9.08816 16.2144 10.0004 15L10.3337 14.5\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M10 9L13.9996 15C14.9118 16.2144 16.3642 17 18 17C20.7614 17 23 14.7614 23 12C23 9.23858 20.7614 7 18 7C16.3642 7 14.9118 7.78555 13.9996 9\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"info-circle":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M12 11.5V16.5\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 7.51L12.01 7.49889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"leaf":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 14 14\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M10.8432.0915544c.2237-.080771.4632-.1090357.6997-.08248853.2439.02736203.4777.11217513.6824.24749913.2047.135326.3743.317305.4949.530999.1189.210856.1868.446616.1981.688366.0859 1.13094.1495 2.88623-.0523 4.70345-.2007 1.80796-.6703 3.74107-1.698 5.17302-1.0651 1.5438-2.58577 2.2296-3.9997 2.4971-1.40454.2658-2.73237.126-3.48875-.0038-.20984-.0319-.4125-.0983-.59991-.1961 1.12918-3.0219 3.24835-6.3452 6.38216-9.23269.25385-.2339.27002-.62929.03612-.88314-.23389-.25385-.62929-.27003-.88314-.03613C5.54313 6.32785 3.38757 9.5729 2.14192 12.6165c-.37095-.6848-.83477-1.7162-1.03818-2.90587-.240922-1.40907-.11891-3.06421.97743-4.60844 1.01257-1.43082 2.69274-2.52722 4.34145-3.33603C8.07402.956028 9.75312.406239 10.8432.0915544Z\" clip-rule=\"evenodd\"/> </svg>",
"link":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M14 11.9976C14 9.5059 11.683 7 8.85714 7C8.52241 7 7.41904 7.00001 7.14286 7.00001C4.30254 7.00001 2 9.23752 2 11.9976C2 14.376 3.70973 16.3664 6 16.8714C6.36756 16.9525 6.75006 16.9952 7.14286 16.9952\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M10 11.9976C10 14.4893 12.317 16.9952 15.1429 16.9952C15.4776 16.9952 16.581 16.9952 16.8571 16.9952C19.6975 16.9952 22 14.7577 22 11.9976C22 9.6192 20.2903 7.62884 18 7.12383C17.6324 7.04278 17.2499 6.99999 16.8571 6.99999\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"media-image":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M21 3.6V20.4C21 20.7314 20.7314 21 20.4 21H3.6C3.26863 21 3 20.7314 3 20.4V3.6C3 3.26863 3.26863 3 3.6 3H20.4C20.7314 3 21 3.26863 21 3.6Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M3 16L10 13L21 18\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M16 10C14.8954 10 14 9.10457 14 8C14 6.89543 14.8954 6 16 6C17.1046 6 18 6.89543 18 8C18 9.10457 17.1046 10 16 10Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"palette":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M20.5096 9.54C20.4243 9.77932 20.2918 9.99909 20.12 10.1863C19.9483 10.3735 19.7407 10.5244 19.5096 10.63C18.2796 11.1806 17.2346 12.0745 16.5002 13.2045C15.7659 14.3345 15.3733 15.6524 15.3696 17C15.3711 17.4701 15.418 17.9389 15.5096 18.4C15.5707 18.6818 15.5747 18.973 15.5215 19.2564C15.4682 19.5397 15.3588 19.8096 15.1996 20.05C15.0649 20.2604 14.8877 20.4403 14.6793 20.5781C14.4709 20.7158 14.2359 20.8085 13.9896 20.85C13.4554 20.9504 12.9131 21.0006 12.3696 21C11.1638 21.0006 9.97011 20.7588 8.85952 20.2891C7.74893 19.8194 6.74405 19.1314 5.90455 18.2657C5.06506 17.4001 4.40807 16.3747 3.97261 15.2502C3.53714 14.1257 3.33208 12.9252 3.36959 11.72C3.4472 9.47279 4.3586 7.33495 5.92622 5.72296C7.49385 4.11097 9.60542 3.14028 11.8496 3H12.3596C14.0353 3.00042 15.6777 3.46869 17.1017 4.35207C18.5257 5.23544 19.6748 6.49885 20.4196 8C20.6488 8.47498 20.6812 9.02129 20.5096 9.52V9.54Z\" stroke=\"currentColor\" stroke-width=\"1.5\"/> <path d=\"M8 16.01L8.01 15.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M6 12.01L6.01 11.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M8 8.01L8.01 7.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M12 6.01L12.01 5.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M16 8.01L16.01 7.99889\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"plus":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M6 12H12M18 12H12M12 12V6M12 12V18\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"refresh":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M12 3.25c-4.83249 0 -8.75 3.91751 -8.75 8.75 0 3.3529 1.88543 6.2673 4.65975 7.7374l-1.17054 2.209C3.17946 20.0602 0.75 16.3148 0.75 12 0.75 5.7868 5.7868 0.75 12 0.75c2.2104 0 4.2723 0.63813 6.011 1.73905L19.5 1l1 1v4.5H16l-1 -1 1.186 -1.18597C14.9425 3.63525 13.5165 3.25 12 3.25Zm-0.0001 17.5001c1.1406 0 2.2273 -0.2175 3.2231 -0.6123l0.9213 2.324c-1.2842 0.5091 -2.6832 0.7883 -4.1444 0.7883 -1.0274 0 -2.02463 -0.138 -2.9731 -0.3973l0.65929 -2.4115c0.73561 0.2011 1.51111 0.3088 2.31381 0.3088Zm7.5435 -4.3137c-0.7203 1.2217 -1.7294 2.2538 -2.9329 3.0016l1.3195 2.1235c1.546 -0.9607 2.8414 -2.2855 3.767 -3.8554l-2.1536 -1.2697Zm0.7019 -1.4998c0.3264 -0.9163 0.5046 -1.9043 0.5046 -2.9366h2.5c0 1.3222 -0.2286 2.5937 -0.6495 3.7754l-2.3551 -0.8388Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> </svg>",
"refresh-double":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M21.1679 8C19.6247 4.46819 16.1006 2 11.9999 2C6.81459 2 2.55104 5.94668 2.04932 11\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M17 8H21.4C21.7314 8 22 7.73137 22 7.4V3\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M2.88146 16C4.42458 19.5318 7.94874 22 12.0494 22C17.2347 22 21.4983 18.0533 22 13\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7.04932 16H2.64932C2.31795 16 2.04932 16.2686 2.04932 16.6V21\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"sea-waves":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M3 10C5.48276 10 7.34483 7 7.34483 7C7.34483 7 9.2069 10 11.6897 10C14.1724 10 16.6552 7 16.6552 7C16.6552 7 19.1379 10 21 10\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M3 17C5.48276 17 7.34483 14 7.34483 14C7.34483 14 9.2069 17 11.6897 17C14.1724 17 16.6552 14 16.6552 14C16.6552 14 19.1379 17 21 17\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"search":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M17 17L21 21\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M3 11C3 15.4183 6.58172 19 11 19C13.213 19 15.2161 18.1015 16.6644 16.6493C18.1077 15.2022 19 13.2053 19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11Z\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"shield":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 14 14\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M7.41215 0.216928C7.32078 0.0838935 7.17082 0.00314212 7.00946 0.0000896752 6.8481 -0.00296277 6.69518 0.0720591 6.59885 0.201543 5.9697 1.04718 5.12412 1.70747 4.15119 2.11285c-0.97293 0.40539 -2.03718 0.54086 -3.08064 0.39215 -0.143471 -0.02044 -0.288752 0.02236 -0.398214 0.11733S0.5 2.85508 0.5 3v2.78113c0.003853 1.70548 0.52066 3.37037 1.48325 4.77827 0.96258 1.4079 2.32643 2.4936 3.91425 3.1161l0.0009 0.0004 0.59 0.23 -0.00002 0 0.00609 0.0023c0.32594 0.1222 0.68512 0.1222 1.01106 0l0.00002 0 0.00605 -0.0023 0.59 -0.23L7.92 13.21l0.1825 0.4655c1.58782 -0.6225 2.9517 -1.7082 3.9143 -3.1161 0.9625 -1.4079 1.4793 -3.07279 1.4832 -4.77827l0 -0.00113V3c0 -0.13843 -0.0574 -0.27066 -0.1585 -0.36521 -0.1011 -0.09454 -0.2369 -0.14294 -0.375 -0.13367 -2.5491 0.17121 -4.42764 -0.64371 -5.55435 -2.284192Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> </svg>",
"smartphone-device":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M12 16.01L12.01 15.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7 19.4V4.6C7 4.26863 7.26863 4 7.6 4H16.4C16.7314 4 17 4.26863 17 4.6V19.4C17 19.7314 16.7314 20 16.4 20H7.6C7.26863 20 7 19.7314 7 19.4Z\" stroke=\"currentColor\" stroke-width=\"1.5\"/> </svg>",
"trash":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 48 48\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M15.8636 5.59514C17.3559 2.51719 20.4954 0.5 24.0003 0.5c3.5048 0 6.6444 2.01718 8.1367 5.09515 3.5856 0.08467 6.3585 0.2085 8.0519 0.29735 1.4211 0.07456 2.9633 0.68745 3.7693 2.14119 0.3614 0.6517 0.724 1.48029 0.955 2.46071 0.0644 0.2735 0.0868 0.5408 0.0868 0.788 0 1.4401 -0.8014 2.7219 -2.0236 3.3449 -0.095 10.521 -0.458 19.6681 -0.7144 25.0089 -0.1851 3.8571 -3.1424 7.026 -7.0416 7.3522 -3.0364 0.2541 -7.1202 0.5115 -11.2196 0.5115 -4.0997 0 -8.1843 -0.2574 -11.2212 -0.5115 -3.89933 -0.3262 -6.8567 -3.4952 -7.04184 -7.3524 -0.25636 -5.3407 -0.61939 -14.4879 -0.71438 -25.0088C3.80133 14.0041 3 12.7224 3 11.2824c0 -0.2472 0.02236 -0.5145 0.08682 -0.788 0.23102 -0.98041 0.59362 -1.80901 0.95495 -2.46071 0.80602 -1.45374 2.34822 -2.06663 3.76932 -2.14119 1.69351 -0.08886 4.46661 -0.2127 8.05251 -0.29736ZM9.02877 15.1742c0.10225 10.2085 0.45442 19.0624 0.70439 24.2701 0.09141 1.9044 1.53104 3.4033 3.37984 3.558 2.9757 0.249 6.94 0.4976 10.8878 0.4976 3.9475 0 7.911 -0.2486 10.8861 -0.4975 1.8488 -0.1547 3.2883 -1.6536 3.3797 -3.558 0.25 -5.2076 0.6022 -14.0616 0.7044 -24.2701 -3.2307 0.167 -8.1059 0.3257 -14.9702 0.3257 -6.865 0 -11.7409 -0.1587 -14.97203 -0.3258ZM19.999 21.4375c-0.0345 -1.104 -0.9574 -1.971 -2.0615 -1.9365 -1.104 0.0345 -1.971 0.9574 -1.9365 2.0615l0.5 16c0.0345 1.104 0.9574 1.971 2.0615 1.9365 1.104 -0.0345 1.971 -0.9574 1.9365 -2.0615l-0.5 -16Zm10.0635 -1.9365c-1.1041 -0.0345 -2.027 0.8325 -2.0615 1.9365l-0.5 16c-0.0345 1.1041 0.8325 2.027 1.9365 2.0615 1.1041 0.0345 2.027 -0.8325 2.0615 -1.9365l0.5 -16c0.0345 -1.1041 -0.8325 -2.027 -1.9365 -2.0615Z\" clip-rule=\"evenodd\" stroke-width=\"1\"/> </svg>",
"undo":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" stroke-width=\"1.5\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M4.5 8C8.5 8 11 8 15 8C15 8 15 8 15 8C15 8 20 8 20 12.7059C20 18 15 18 15 18C11.5714 18 9.71429 18 6.28571 18\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> <path d=\"M7.5 11.5C6.13317 10.1332 5.36683 9.36683 4 8C5.36683 6.63317 6.13317 5.86683 7.5 4.5\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"warning-triangle":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M20.0429 21H3.95705C2.41902 21 1.45658 19.3364 2.22324 18.0031L10.2662 4.01533C11.0352 2.67792 12.9648 2.67791 13.7338 4.01532L21.7768 18.0031C22.5434 19.3364 21.581 21 20.0429 21Z\" stroke=\"currentColor\" stroke-linecap=\"round\"/> <path d=\"M12 9V13\" stroke=\"currentColor\" stroke-linecap=\"round\"/> <path d=\"M12 17.01L12.01 16.9989\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"xmark":"<svg width=\"24\" height=\"24\" stroke-width=\"1.5\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M6.75827 17.2426L12.0009 12M17.2435 6.75736L12.0009 12M12.0009 12L6.75827 6.75736M12.0009 12L17.2435 17.2426\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/> </svg>",
"angry":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M2 12a10 10 0 1 0 20 0 10 10 0 1 0 -20 0\" stroke-width=\"2\"/> <path d=\"M16 16s-1.5 -2 -4 -2 -4 2 -4 2\" stroke-width=\"2\"/> <path d=\"M7.5 8 10 9\" stroke-width=\"2\"/> <path d=\"m14 9 2.5 -1\" stroke-width=\"2\"/> <path d=\"M9 10h0\" stroke-width=\"2\"/> <path d=\"M15 10h0\" stroke-width=\"2\"/> </svg>",
"blood-drop":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"M12.84 0.45a1 1 0 0 0 -1.68 0C11.09 0.56 4 11.73 4 16a8 8 0 0 0 16 0C20 11.74 12.91 0.56 12.84 0.45ZM12 21.24A5.26 5.26 0 0 1 6.75 16a0.75 0.75 0 0 1 1.5 0A3.76 3.76 0 0 0 12 19.74a0.75 0.75 0 0 1 0 1.5Z\" fill=\"currentColor\" stroke-width=\"1\"/> </svg>",
"hash":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" xmlns=\"http://www.w3.org/2000/svg\"> <path d=\"m4 9 16 0\" stroke-width=\"2\"/> <path d=\"m4 15 16 0\" stroke-width=\"2\"/> <path d=\"M10 3 8 21\" stroke-width=\"2\"/> <path d=\"m16 3 -2 18\" stroke-width=\"2\"/> </svg>",
"tracking":"<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" d=\"M12.0001 12.975c-1.1 0 -2 -0.35 -2.7 -1.05 -0.7 -0.7 -1.05 -1.6 -1.05 -2.7s0.35 -2 1.05 -2.7c0.7 -0.7 1.6 -1.05 2.7 -1.05s2 0.35 2.7 1.05c0.7 0.7 1.05 1.6 1.05 2.7s-0.35 2 -1.05 2.7c-0.7 0.7 -1.6 1.05 -2.7 1.05Zm-8 8.025v-2.35c0 -0.63335 0.15833 -1.17085 0.475 -1.6125 0.316665 -0.44165 0.725 -0.7875 1.225 -1.0375 0.85 -0.43335 1.85415 -0.79165 3.0125 -1.075 1.15835 -0.28335 2.25415 -0.425 3.2875 -0.425s2.125 0.14165 3.275 0.425 2.15 0.64165 3 1.075c0.5 0.25 0.9125 0.59585 1.2375 1.0375 0.325 0.44165 0.4875 0.97915 0.4875 1.6125V21h-16Zm1.5 -1.5h13v-0.85c0 -0.27185 -0.07085 -0.519 -0.2125 -0.7415 -0.14165 -0.22235 -0.34585 -0.4085 -0.6125 -0.5585 -0.8 -0.45 -1.70835 -0.7875 -2.725 -1.0125 -1.01665 -0.225 -2 -0.3375 -2.95 -0.3375 -0.95 0 -1.9375 0.12085 -2.9625 0.3625 -1.025 0.24165 -1.9375 0.57085 -2.7375 0.9875 -0.23335 0.11665 -0.425 0.29585 -0.575 0.5375 -0.15 0.24165 -0.225 0.49585 -0.225 0.7625V19.5Zm6.5 -8.025c0.65 0 1.1875 -0.2125 1.6125 -0.6375 0.425 -0.425 0.6375 -0.9625 0.6375 -1.6125s-0.2125 -1.1875 -0.6375 -1.6125c-0.425 -0.425 -0.9625 -0.6375 -1.6125 -0.6375s-1.1875 0.2125 -1.6125 0.6375c-0.425 0.425 -0.6375 0.9625 -0.6375 1.6125s0.2125 1.1875 0.6375 1.6125c0.425 0.425 0.9625 0.6375 1.6125 0.6375Zm-11.025 -6.95v-1.5c0.28333 0 0.541665 -0.054835 0.775 -0.1645 0.23333 -0.109665 0.441665 -0.257335 0.625 -0.443 0.18333 -0.185665 0.325 -0.396585 0.425 -0.63275 0.1 -0.236335 0.15 -0.497915 0.15 -0.78475h1.525c0 0.483335 -0.09117 0.938085 -0.2735 1.36425 -0.18217 0.426335 -0.43367 0.801165 -0.7545 1.1245 -0.320835 0.323335 -0.69275 0.576915 -1.11575 0.76075 -0.422835 0.183665 -0.87492 0.2755 -1.35625 0.2755Zm0 3.5v-1.5c0.766665 0 1.48508 -0.1449 2.15525 -0.43475 0.670165 -0.29 1.25175 -0.68675 1.74475 -1.19025 0.5 -0.5 0.89165 -1.083415 1.175 -1.75025 0.28335 -0.666665 0.425 -1.38325 0.425 -2.14975h1.525c0 0.966665 -0.18335 1.879165 -0.55 2.7375 -0.36665 0.858335 -0.86665 1.60415 -1.5 2.2375 -0.63335 0.63335 -1.37525 1.13335 -2.22575 1.5 -0.850335 0.36665 -1.76675 0.55 -2.74925 0.55Zm22.025 0c-0.96665 0 -1.87915 -0.18335 -2.7375 -0.55 -0.85835 -0.36665 -1.60415 -0.86665 -2.2375 -1.5 -0.63335 -0.63335 -1.13335 -1.378915 -1.5 -2.23675 -0.36665 -0.857665 -0.55 -1.770415 -0.55 -2.73825h1.525c0 0.766665 0.14275 1.48225 0.42825 2.14675 0.28535 0.664665 0.6759 1.249085 1.17175 1.75325 0.50465 0.49585 1.08965 0.8864 1.755 1.17175 0.66535 0.2855 1.38035 0.42825 2.145 0.42825v1.525Zm0 -3.525c-0.48335 0 -0.93625 -0.091165 -1.35875 -0.2735 -0.42235 -0.182335 -0.79375 -0.433915 -1.11425 -0.75475 -0.3205 -0.320835 -0.57175 -0.692665 -0.75375 -1.1155 -0.18215 -0.423 -0.27325 -0.875085 -0.27325 -1.35625h1.5c0 0.283335 0.05415 0.541665 0.1625 0.775 0.10835 0.233335 0.25415 0.441665 0.4375 0.625 0.18335 0.183335 0.39165 0.329165 0.625 0.4375 0.23335 0.108335 0.49165 0.1625 0.775 0.1625v1.5Z\" stroke-width=\"0.5\"/> </svg>",
}

# custom PNG icons - alpha channel used as a stencil, filled with theme color
_IOR_PNG ={
"shield":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACO0lEQVR42u2ZvU4bQRDHfxx2ZIIiBykUkUBKk0ipIhrk5AFc5eMZ0qOkQjQUfoTQpaHmBSjdRCC4PEGgIF0kiGIRCwV/xHdHway0Ot3ZrLn1ra0baXWn292Z/392dmd3DwoppBBb8g5oA2+nEfwLIAJ68lydJvDPBPR/rbSBpWkAv6aBD+RdPVvAiqvA54HPCeCjGIkIeA/MuQLcA94Ap7GYTyqBkIuAb8Ar6Z+Lt58CHzXgo8BHKe1+ABvAc2BhnJFJ61ADPgG/gD/ybRl4CawDT7S2faBk6M0BEAIPYt/PgJ/ABdAVZz0EvgC+CYFoBIC+BuA+YRCKLi+BzJ2wphG4AipiIB7znsXYDTWboWanCzxK6lBKUVQaUmd7UfAMcOazCmTNuCBQECgIzCCBrmM4r00JnGvJJE9R9n+bEjhxjMCJKYHvjhHwTQkcODYHDk07PE44SeVRAilV0xH4CxxJ/SAnrw/Evi+XAsZ54KvEYJ4EQsExllS1Q3oe4aPsVsfNxG1gT9r0J+x9dUrbGxY+d5EVwwN7VkXZy+QeaXfCJJSd3ayGc1GWss4EllXdzmKWMVkXA/8sE1D66zYm1o4o71gCr/Tu2Nx6Ny2RUPqats8oZcmMWZJQenzRb13KwL5mPLjnhI1EX3mSicYDGphf7Ca1b+R5tK0Bl1rq7w0ZkUDq1RbhEnjtwl69AmwneDiIAdfrt6WfU7IEbHL7KylpBFrAFlPwr6zC7W+kY0lMPvDBRY8XUsgsyA0do7wst30rGAAAAABJRU5ErkJggg==",
"tracking":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAADUUlEQVR42u2YT0gVURTGf2+elWZCkWY9/IslJf2VFkURGSVEhbjIVhGBZOCiFkW0aRO1ixBqFbVx2aKQWhhtxF1IUSKSuIj+iBWBJWL60Nfme3AZ5s3MmzcTr5gPLgNzz3z3nnvP/e45AzFixIhRzNgMzKk1G+8TwCtgHrhbAP9NcYwBlvG+zhi3yY3A8hjgJLBa7ZvtuyagFJgpwIEZcTQASeP9D2PcrqDkW4AlIA0M2frWAxn1dxTgwFFxZIBNtr4Bo681H9JGoFcfzunZYLM5o/cZIFWAA5UGzwVbX7Xez+t5A9jhhzRja+0OYTep1RnXeSgEI+KatoURwD6H+Xgiu21PHFYe4JxBdiIEoThs8F126K8GHgILfh2oAdbk6GsWSVq7YIXgQAJ4K84MsCuHXamcCYxt2p1ZDVQXolxvFOdskEPrhRKg23aoj3nYtwF9wCDwArgPHAdWunx30DbGVa163rCAVUCtlOGz7RC1eSjYB4eDl23fgZ0u3++32f8Eril0y4EVfhx4Y0iX2YY8JLPGZv8ReAQ80HnJGALR4sJTpZ1zWoDpIDL6THKW8DiIE8ZBPGuTRAs4pb4F3bQlHnx7gMdBZPS8LqrdQIXPsGsxBrjkYtdl2B3yyV2usDsN9ESV9PUqPOY9Dl4S+Crb22EMbIXkQJ24JhQibpfka9nWFpMD2Un7Cbm1eqaLyYExYFkyusHFrgLYK9t3xVT4VBopxmCOhUkA/YaUNhZb9XbPUJhhYLsKkjJdRANG/9NiLD9LdNmZmr1krHi2jQdNEf4GksAVI/W1O3PLIx8KlMpGgVL9EKjXGJ+UTszF/0n+N4QZQpZ0PqVSNAWsU98v4ItS7SmlycvFsADlSsr6gPcudYC9TarIOeJSvkaKFhXa6RwTzP5lmFCbyqFMWdt+ZZyJqCdeBbx0mMQIcB04oPq2TJJqqSWlTJXK83uA5w48wwX+Z3JFtUPF1S2ngq5cBdAJjNq466M47KPGlnd5VFRBBKBDIbmkkLPCdCBlTP5ihCHaaaQeW8MkbjWIqyJWtexCtYdZD1iG7UKEDqSN8ZJ+M8h8sAjc0YWU8PuXIE+hWFTCl4jCgWUpT5T4nW8OT4BdiCoNsIgRI0aMfwp/AP3aGX5OTHvNAAAAAElFTkSuQmCC",
"hash":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACKElEQVR42u2Zz2sTQRTHP7OGjWCwgmBJDprWFDzZQ/8hT576F/VU/5P25q0HsS02SX8cFBvEbhVpQ816ecFh6JKdzXsxwn5hmEzyIex3Z+a9t7NQq1YtLa0C76WtGvDm2gNyafsGvKkeAD+A39I+Ak6RL1SiZCAFWsCd/Oex3Fkt3txAS/qx9CfKvLmBp9LfSd9X5s0NtIPxmTJvbmAtGH9W5s0N9KRvSP9NmTc3sOFFF4CfyvzCZiAFroEbZb5QjRLMrASTAl1vfCEx3SnxedWL6wA7wIuCmUqACdAEXnrf3wBDBR7hz4G3VTb6yKtV/nUbVdkD6RJVummVPfAaeAc8n7GEVoAn8jkBroDM+70qP11CF8CbedwnsleSe5oDtmWaM+m3lHhXJkqWiUKTGdGgHSzHc2/tzsvnZe7uvHoVrNNfyry5gfUgKd0q8+ZPYpm3BA6UefMZaAKPvQeToTJvbuBR8GR1qMyr1EJJQa2SS47wI9VX4VxBRInl3T25oXQt1AV2CxLZIpJYmMjOYg1ksl6XQddiPmoPjJeoFhpX2QObM8rp6YOJX2gNJK4XLYlY3i+nK8sVtAT44MX07xImtXhX9bTuv0li8+aBh0FS6ivz5gbC48FPyry5gfB4cKDMmxvoBONTZd7cQDcYf1HmzQ1sRB4PxvLmBnqRx4OxvKkccMTfV0SZxHkt3nwGcuDSO0E4kAvT4heiZ8S9Jo3la9WqVUJ/AMdY65jLCm9FAAAAAElFTkSuQmCC",
"angry":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAADrUlEQVR42u2Zz0tUURTHPzMj6gglUWYLCTcRiZTRJsnJal3kuC5koD9BqZW4EQrc+i9EBDYtCkGiiBDbtCjohyWDiIhjiegwmYzDtOg8OF7ee/Pem3nq0Bx48ObNOeeee++53/u950Jd6vJ/S6SKvo4CF4DrwBXgDHBc/lsHfgCzwBvgI7B1GAagAegH0kARKBlPQR7zexGYEtuGgwg8CiSBrApqB8jbBGs+edG1fmfFV3S/Uug08Ay4JL+3JH0syQJzwFfgp3xrA84BvUC70tW2H4BBYCnMkU+qkdtU7/PAkAQXc7GPAadEd97B10BYwY9IA9sqVRaAvoDTHxXbjEqtbXkfrnbw98VxTuXvgyotwAbxZa2jnLyPVDttdPB9Icxwn00nkpU67bCZ3u4Q11i3TZp2VAKVnwXH8yGOvCkJNWgFiSHQhjtoIMSoQycr2c0jDgAwarQ96NdxDNiQfCwAizbweBFYFnpwC4j78B8Hbortsvgy21+StneEisT8dOCaMQJ2qbNiQxseAZ0ufjuBhzb0YsVlUVsx9PvpwEvFWRYc0mTSoBE6oAkb/QlDR9tMOqRXRnGsF16DPyJGFuoMuSzy28A7CaZoQGDcSBkNxZburOy8ThthSqFSUWIrK1dVYyXgZBn9JmBVGrDQ6qkxaxH5ZqFLUWyayvhuN2JJeOnAmEqfrAea0KpGyeIyEYeUGDB0Wz1AeVal0ZiXDsyo3Ex7hEIrv5+UgdUI8FitEy8QnFbxzHjpwJIyGPex8JtD0h1X8SzaTZEpx4Bdef/lo6E/IelaMeyqI6prB7SUDvuh3q4DG4omt1XgOybwGfe7ixpyQtHudS8d+Kbeu3w2FhekeQ6sAb/lWZNvSZ+Uw4zhexgwaqHLHQWPJbUv5I2KxTZw1yMCBYJRvxtZXEFvwTjfms+m4kGvPMxGoI3MpBIpF90WdabNqUDngHtSheiV9zn1f07BYouL/0BUwiRzGZfpnjYY4zLQ47IT94iOtpl2SctAZM4rnY4a6fHW4wbVLLraNupyMgtEp2MCWW4HGoAbQsrSQKMP/41isyo+qPaBxuuREgKWBMvYmkfKQNWJiM2hPkH4kjBod+BDfc2XVfa7sJUIo7Bl1kVrsrRoybDN9GaokeKuJQM4l9dT/Cudeymvp6hSeT2sC473wBf2XnB0AZc54AsOPf1J2YgqvWJaLVNaCVWsS74pDuiSr9rXrOeFGvQCZ9l7zTovjPQ18IlDcs1al7rUuvwFNnzMJjdwBtcAAAAASUVORK5CYII=",
"blood-drop":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACiklEQVR42u2Yz2sTQRTHP60VGgupN/+CQuMpYg9FvIl4Ea01omC92Gtpe6gnlf4nXkTwKF5ES0/9E6QVQk49FHIqVUKy3eyulzcwDLvdbDKzu4H9wjCbzLzZ93veW6hQoYIrbAF9macOS0AE9GRemibmZ4EO4AOezB35fyqwKVrvG/PbaWC+Lsx6MkfG73rZBfiSIsDnMjPfSGDeFGK5jMzPAMcSsH6CAGrtt+wvFZ4YAZs01PrjMjF/HTgX7QYpAgSy71zoSoHdFN9PioWdMjC/oGk1yjBUPCzYuDUnwUc5I8xIFwJzwPsitX8zo+skudJiURbYt6SI/SK174+p/cigX8zbAu80X54Ein4vT+3fGDPzpGWkWl4W2BC6oSWFDCUjvc6rWemKBQJLFlBndfNoeu6MWPNkHeq8pmsX2pHAm3Vg2RDYdqn9mgPNx1mi5soCK8A8cKn9N5BhA5dy/l1XArRiaOZl2HIjgOeuXOiPkTUugAfAK0tZSdEfuxKgZ2SMD9rad0ulRQT8c+VCg5gLSKEtWSS0oKiBKwHaBs19be1wzL4gri7quBLgQHtJCDzUAvhQNDdJiTGUc3+6ioGm5ucqDl4YaVYFYz/lE8tVDU7TlQDXgDOtEvUlE+kXz6oW7GZ2GaUeOpP3OMMbLRMp7f4yXLEGPAM+AUcZa6EN18XcnFSNntET/JA+IQ73UnrnQNa6cn5u30B7Ru6/AJ7G3My3UgRQ5zTy7Mpa2svN7swDvsoHr01Jv3GxEGjMt4po7NcNH/ZHrFYDY996kd+GGsCp0d96MvoyAiNzqb2nebvNVYH9UnOVtNGW/VYCdsayILeBNeCRPNeBv8CJ3LDf5HlIhQoVrOA/qe3cKu9SRLoAAAAASUVORK5CYII=",
"dice-five":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAEZElEQVR42u2Zz4vVVRTAP/MrRjRiUioRhKlhpECF2uVqdGYkF1EGwWOsRUQ16MKFeyVoJcyuTSLkYgZRTBfKYIogZsVgT2YxhCL+ASkNw0NfX75+57k5Fw+Hc7/v+34W9A5c3uN77zn33Ht+nws96MH/G/raSOtV4D1gEngfGAe2yNxj4D7wK3ANKAN//xcu4CVgP7AI1Boci8C00Og6DAAzwJphKgFSIJNfPcK3xOCsASWh2RV4C1iRzTOgKow1KoHU4K4I7Y7CjGLgiTqEZSwDbgKbZdxUEvAOU1X/ZzrF/AnZoGL0OMbMqMIddRgN4wejTjXgeKeYX5XfP4GtMrdobjcwOaHwJ8xcIjgLMr8FuGP2ONEu5g8ZwheBITW/yzCXKduYkVFV32vKkHcYxzBv9jrUKvOjRrQXgH4nljyI2EPMeIPR9jm0Fsyeo80y3w88VLe3AgxG1n7s6HiQQtUcLKz5MMdFL6u1D51LKwSfKW+zJt4kBoNKrzPlIvVI1XyScxkhqq8qT9ewKg2Jt0mUp8iDb1SQSnLUJ1HB7us6NE8rnIqxu7rwgRJhUIUfgbcdvZ1z1Od34BhwQMYx+WbVaM6xgZ3AOSXRsHZ/Iwe4YQxOj7Lo7zAwa7xGWZK4GIwDdw3OLLAB+Ejpvmf0N4oyP5ITYZOcwHVW5TNDcpO7ZexUOj8ga2OBLXEuLvAyUuQA08ZX1xxiVbPZsknGzjl4PzueRl9KNccNhzVTnqu0MGXmngH/yFiX78PGAx2UzQNsVziPgb+An9R8BnxiPNGw0F5XuM8ML9NFJPBbwaAUxLzk0Lguc1/J5jEPspRja54K3S4igTH5XZffXyTk7wWeyvd1dTtnci7jDdkjjcyfUVIOdJ/KXjtkb83LeBEJZOZWtOGUlL4GO5h0aJQVfgp8Gdlr0qFXMgFN85IVkUA76uZrSr8HgVMmO+0oPDKnviWim5DQnhlPdDhy6JeBVySKJ8BlZ90R44Ey2WNC9rxleHnULSMO0u0HvpW1V501d1o1Yg9OGqJpJKvU/nnM3P68JIC6evvUicq6uPGy2NTwcrKdgSyLBLJBB2fO2NKApOc2kKWNBrJOpRKbJIXYBbzupN7nnRLTZqxNpxL1krn7UiZulDRaJ2Z3c3x1n8wtG5wvpLk1JTrecjKHpK41oyqXgHcd1+ul00smnT4aSae/cw75JvC92E/T6bQtaBbqrJ9toqD5vA7NU60UNLakrACv1Wk1VhosKfMY2io4TZeUuqgPbu5eTh27r4mi/mCO9B8oiTZd1HttlUsRYuWCAUl7lHtOmtKvun0tt1Vija0LRvxjxhXqVKNUp7H1jmnVX2l3YyvWWlxW/n1e6XXR1mKwh/Myv03cc0daiwGOG9HWlKdopbm7oP5XOtXc9drr1Zwkr9H2+hP1v9TNB460DQ8cWTcfOLTfLyl9beWJabXbT0wYzzHNv/jI185n1hFePLPuwX9mvS0diz/k5nvQgx60CM8BrQc0rKsWXO8AAAAASUVORK5CYII=",
"cpu":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACkUlEQVR42u2Zv2sUQRTHP7cuSdSAIv5sDETPQgTBSjEWBsVKJRAIolUsBEFtrMTKTuzsBCsLEQv/ASGdaKegoAZRtLA7Qorzctnb3RS+gWGYvZvd22P3YL4w7O2y++b7fe/NzJs58PDwqBoLQAv4DMyMG/kDQApEcv0LBHkMBBULmAcSYBPYAA4B+8YpAh+0CHTk951xIX9GCHflqgvZWXfye4G2kI8NASmwAmwrq7NGzjZoXB0H1oW4Tt4mYrcLuSwcAe4DcxLSQcR6QAisApeEhMIOoAncBZblWdLHprIF8AB4DfwRcU5YtHjGtd0ybN2weDh2sBMZ9y3ghAv5pnzQ0XLUpbXlelKztV1sxWIvKuCQrjZDtUyyoUXAUy2EYc41JTBSRw3EzSHGYCDp1gOmXT6ICqaO8tKSYe+hxaMu9mILl3kXAUVzX3X23mLzIHAFeKeRc83/F8A5YJdryNIhmvLuxT6z3oUBg1k9+wnMFsm5tCQRZ/v0cTQjnSJp32UCoAoBuhdfAqczwn81o5RIgf3DrLxpSc307mNj4WoAXzXB6v1Hw5YOcYkiVHHWySB3U4i3tXcO10mAbZqd0vqaMVInNoq4Rt02NAlwTLv/DdwG/gG/gFMiQt+x1SYCysuvLH2GFmdOA9fqFIFQSool4Lyl+kyMZ8+BPXWKgDk7LWQ4cAp4klGW4FLMjRoT4vE3wDfgGfAFmJSS4Z6I6BXlN+oIuBR163K9XscI6JFIjFI7EE4TeQZWlQiMdaGQgbGGF+AFeAFegBdQuoCNmnBLXM5CbQLeSiHVq4FzPxX5cFYrtoqe0pWx9fzosqXMwuUKiOttNc9JXBaacq6zph04jbJ1gR/8/09iEg8PDydsAegnLYnLU7ksAAAAAElFTkSuQmCC",
"wifi":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAFVElEQVR4AdXBfWwcdAEA0Hcfm8cytEsabLChN5XRaClLOSuEZlzmTNANUkSlMc2sY2KVTVxC/GODMIQlJowMNhadODJws8OBq7HijDhuswuBbAx0MYBjO0uFs1Rp4rl18yyS/EjOs7e2xOs1vhcx/WpxFAkMYhA5vIheDPofxFVHHLWoxUJFW/ACnsBuHPceRVRPLepRj3qksRRzBQU8iA0YNkURMyuBNDpxI+IYwX34LgomETOzCjiOn2IvGtCMxViEX+CUCcRURxMWIIoR5Q3hxziAJWjG5/BrDDuHiOlXizcQV3QMP0MvDhuvDr34JPL4DPqVETP9zmIe/oW3UYMLsAg3ox0vI6soj524GC34IvZi2H+JqL440mjHDagT9OGryCm1GzfiOK7EsP8QU31jOIEnsRVn0IJmdOBp5BT14dNoRit2Ycy7YmZWAQfxCK5EEzrxe7wiKKAPHWjGafR7V0x1dOPzaMRsDCiVx6NoQCuuwy+RE+RxFF1IYTtOeUdMdTyDRfgsVqAb5+E5FARj6MV8tGIZepAXZPEJNON92OcdMdXxNE7ij5iHi7AYXXgGg4r68Ck0oRE9in6Hm9GKHvwtpjoGcBB92IwDuBSN6MTL+INgDE9iJZpxAFnBEC7BQryJgzEzI4uH8UFcgevwGwwK8piFxWjCQ4pOoRMfwA+iZk4B3diGBPYgoWgjckhhoaIM8rgc9TEzbx+WohFncFBQwHy04q/YLyjgMjThZMzUJJDGGnwb63Ev7sAKtCOFf+J1FEzdGF5BFxZgk6KzWI73Y5uiWizDa3ETq8G3cCtqlJdEEmmswggewEbkTU0Gr+IjaEO/ICNYqNSgoD7m3DrwcyxDAkewB5fgPBzCa7gIb+FhxPBhpLECf8YxU9OMFhzFc4IxfAU1eAQjgjnoxum48u7G7YIDuB392Il5eBHXCPpxGWqQQhvuwdXowcdxh8llBXVK5dCAemQFg4IPxZSK4zF0o4BbsAoDWIJ7kcfVGMJZ7MNKpHAIGezAX3AN0mjCHhMbw3LswvOKmpDCfRgWnMJKFGJKfQfdGMFSPK7oMVyIO9GnaARvYwk+hocEh/FbtKMFs7DfuQ3gbjyv1FPYigGlfoRtUUUdWIcCrkdGURop5HC/8e5HDimkFWVwPQpYhw7vXQHDxhvGcFRQg02C1cgo1SnYhlHjjWK7oFOpDFYLNmGuCooINmO16tiCb6qQKBLoUj1dSKiQONpwPo4gZbz1uBNbscrEHsQtuAvrjXcYl6MNT6mAKNoFfcprFGRMrl/QqLx9gnYVEkWTIKO8OsGwyeUEdcrLCJpUSBRJQVZ5SUHW5LKCpPKOC5IqJIIzmK26TmOOCoj6PxfHG2jAfGSNl0UD5iNrYkmcxJ+QNF4SJzGkQqIYFCSVlxUkTS4pyCrvo4KsConiBUFaeTlBncnVCXLKSwuOqZAoegXLlPeSoM3k0oKXlLdU0KtCIkhgCOerjr/jAoyqgChGsUP17MCoCokL1uILqMPX8X2lfoibcBfWK+8erMN2rFSqG99DDmtVUFSQxxrBFqSV2in4GhLGS+AmwU6l0tgiWIO8CoopOoZZSKMdzyIryOJaLMA/0K/UbWjHEaxVlMZezMEGbFZhMaX241K0oBNv4rDgBJbjCvRgRJDEHsTxZZwQdKMHc/AEuk2DmPF+gllIYxnSeBUZXIwU0tiF2fgV6rELG9GGXfgGotiAbtMk4tw6sAl1gsN4Fl/CPBwSXIW38CiuQkqQwxrsNo0iJjYXt+FW1JiaETyAjcibZhFTk0Ab2tGEJC4UvI4sjqEX/RhVJf8GGD5jQGg6apoAAAAASUVORK5CYII=",
"private-wifi":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAGCUlEQVR4Ab3BD4jdBR0A8M9+96MedcRjPNqTjvWSwmteeMzTDh15yYkTrnbkkGXilv+6QNgtKDUEoWattOYIzXLixOkxNsna0FkKt7jBmQg3eGeTrjhl4DPOOvTQlz3OBl/hfL7fr5vz6eejjUpaHcRBrUraJNEe2/Ey+jUbwpBm/XgZ27VBoj1SpBi2vGGkSLVBoj3GhQHLGxDGtUGiPSaEc1CQr4BzhQltkGiPBUyjgB75epBiGgvaINE+k0KffH3CpDZJtE9V6JavW6hqk0T7VIUu+SpCVZsk2mdWKMlXFGa1SaI9erFDSISCJQUhEX6KXm3Q4fSl+AZ+g59gjfAgxnEzLhb+gz/jc7gIazCCQfwbM1h0Gjq8fymuxj6MYLUwhy24G13Yj1Q4Hw/h93geX8UnsBqbcCVeRxWL3ocOpy7F1diHa7DSkqO4BJPCb9GLfZjGWnwGB/A8xvBlrBZWYhhX4nVUsegUdDg16/A7jGAl3kCKFXgYw5gXBvEzLGAD/ogbsBZHMIvX8Ai+gB68jTexCsP4OqbxkmV0+P9KuB+/RBmzuA/n4WPYhRuwaMk9+Dxuw+N4DW9jEGdgr9DAAZyBPryFO7Aa3bgG3TiCN+TokG8d/oQLsIAfYzO2YzUexQ1YtKQLd6OOb6IuVDGKbtyP1yw5jLNxDj6F8/AmzsdaXIln8ZIMHbJtxEEUcRSX4A/4ITZhBpehrtn3MIB9eMSSOr6EHryOcUsW8TiuwBr8Fz/CGM5DD67GX/G890i02ogxpLgdA5hFEVuFb2NBq83Cbq12C5u1WsD1wlYUMYsB3I4UY9joPRLNhjGGFNtwKxrCCIo4ggmtBlHBixjX6im8iAoGtRrHERSxRWjgVtyCFGMY9i6JJUXchxS7cJdmm4Xtsq0TDsh3QOiXbYdwrWY7sAsp7kPROxJLdqCEpzGqWQXdmMe4bL3CpHyTQp9sT2EBPejSbBRPo4Qd3pEIffgOGrhRqyHhSTRkO1eYkm9KOFe2Bp4UhrS6EQ1ciz4nJcKI8Asc16pPGJethC7MY0a+GcyjCyXZxoVerY5jF1KMOClBig3Cbtm6haps/cJzlndM6JetKvTIdq+wAWmCAZRwDDOynSUcl60knLC8WaEk23HhLNlm8AJKGEgwIByWrYAiFjDnw1cTSvIdEtYl6BKOy1YWXvXReVGoyFYVKgm6hBNOX0moWd6c0On01YRygpIwJ1tRmJevU6hb3oJQkq8uFGSrCeUEBaEg24LQ6aNTEOqyFYQ0QU3okq0ufFy+OaFoeWWhJt8nhQXZKsJcglmhItsJoUu+BaFoeQWhLl9JmJOtS5hJMCX0yzcvlH34KsKr8vUL1QSHhA0oy/aMMCBbTeiyvIpwQrYBYUK2MjYIhxLM4Dmk2CLbuDAgW00oW15JmJOtXxiXbQtSPIeZRNghbEVJq3HhUqRa1YRVlrdKqGmV4lJhXKsStgrbnZQIj+EZlPGAVpP4OyoY1qqGeZRQkq+MEuZR02ojKngBU1o9hDKewSEnJUIDI2hgCKNa3SncJNu00Cdfr3BMtpuEO7UaxXrUcR0aTkosmcL1wh0Y1WwPaujDVVpNCb3y9QpVra5CL2rYq9ko7hC+i6p3JJrtwTak2ImdSIU6bhF+hYpmE8KgfIPChGYV/Fr4PupCip3YiRTbsMe7JFrdhW1oYBQHURH24FEUMYZOSw4LF6KgVQEXCoct6cR+dGIf9goVHMQoGtiGu7xHh2yTeBZD6MEIVuAveBxXYQ2+gv14C3VcgjMxjapmm3AFjuIeoRNPoB+z+JpwM/ahG/O4HHtl6JBvBg/iDKzFxdiEN7EL69GDi3EUc1jEMMp4QLO7sRq3YQrdeBQXYAbfwno8iI1I8TA2YEqOFU7NOtyLs4U6juBCdKKO23Ev/oYiLsNhYT2ewBy+iBtxEwpYwFFchIIwjRFMWMYKpy7FMK7DpbLV8Qo+ixp+IPwcZZxACQXZnsRuPIaGU7DC6enCdRjCOUidngaO4RB244T3aYUProBe9KMHn8aZWIWVwr/wCv6Bf6KKSUyh7gP4H4iIeoXFvZDMAAAAAElFTkSuQmCC",
"lock":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACe0lEQVR4Ae3BMWhcZQAA4O/+e8QOGerkgQ/MEJwCUhB1yFhMkA6iJ5S22EIzVBfTQajg5mC2dCg0ko4FDSXiUGgLDi0c4hAspSoWTugQtTeZ4YYOxTjc8Pg5m+Z/7/XKk36f556xlvocwTo69raNj3BVDYL6rKPjyXJcVJOgPh37l6tJ0HAt9dkVa4nt2p+WBEHDBZMz8BQEk7OEP9QsMzlXkRu3q4Kg4YKGCxouMzlHcBG5GmUmZx0dNQsmp+MpCBou8+y01CBouKDhgoYLGi6oRy5drgZBdV3cle4uuioKqlnGFRwUu2fc72IHcQXLKmgr7yjWjbuDE3gg9gPeREdsEb/gVyW0lTODa5hSGOITLOGBcX9iDQMcRqbwNjawI1FbOefxhsJDLOBbT7aFWziGzMgBvIjvJArS5TgudhY9+9fDp2LHkUuUSXcKmcIdrInN4kssGrmOz9BXuIAlvGYkwwmsSBCke0tsTWwWt9HFNKbRxW3Mil0Sm5coSDcn1hNbwbRx01gRuyk2J1GQ7hWx38QWPN6CWF/sZYmC6g4oLxPLJArSDcRysRse74bYjNhAoiDdz2KLYucwNG6Ic2KHxbYkCtJ9L3YamUIfh7CJIYbYxCH0FTKcFutJlEn3Db5AZmQOZ3BBoY+uvZ3BnMIjXJYoSHcfm2KrmLd/81gV28C2RG3lbGEJU0YCPsTf+An/+G8ZPsbXyBSG+AA7ErWVs4O/8K5CwDt4Dy9gBw8xhVdxDF/hFILYSfSU0FLNMlZVcxbnldRWzY+4h0VMSTPESVxSQUs9ZrCC95HZ2yNs4HPcV1FLvWZwFPN4HS8ZGWALPVzGtuf+J/4FN1xzd9NXwTQAAAAASUVORK5CYII=",
"prohibition":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAACo0lEQVR4Ae3BMc6kZAAA0LdASeUBvsoDbL8EGk3YnoY7WNh4Dm+gJQlMz25htyRbegAPYGViQvVlCssvxH/+n2FmYkzmPU9PT0//qXduU2JG5Zgv+IjVQbnjSsyoHBdQY0J0QO6YEjMqtwuoMSG6Uu56JWZU7iegxoToCu9cp8SMytaCFqt9SnzCB1tf8BGrnXL7lZhR2VrQYrVfxIgGQRJQY0K0Q26fEjMqWwtarK4XMaJBkATUmBC9Ife2EjMqWwtarI6LGNEgSAJqTIhekXtdiRmVrQUtVreLGNEgSAJqTIguyF1WYkZla0GL1XHv8ackYkSDIAmoMSF6Qe6y31DZWtBidVyHz/gGnyURIxoESUCNX70gc1lla0GL1XEdBhT4ET/bWtFisVW5ILNfi9VxHQYUkh/w3taK1k6Z/VbHdRhQSM7o8bt/W+2UebwOAwrJGT1ObpR5rA4DCskZPU7uIPM4HQYUkjN6nNxJ5jE6DCgkZ/Q4uaPM/XUYUEjO6HFyZ5n76jCgkJzR4+QBMvfTYUAhOaPHyYNk7qPDgEJyRo+TB8rcrsOAQnJGj5MHy+xX+rdvMaCQnNHj5LjSTpn9ZpS2/sBPkjN6nBxXYrZT7rLvESQBNSZEyVf8je/Q4+S4EjMqWwt+8YLcZSMaBElAjQlR8hUDvjiuxIzK1oIW0Qtyl0WMaBAkATUmRMlfjisxo7K1oMXqgtzrIkY0CJKAGhOi25SYUdla0GL1itzbIkY0CJKAGhOiY0rMqGwtaLF6Q26fiBENgiSgxoToOiVmVLYWtFjtkNsvYkSDIAmoMSHap8SMytaCFqud3rleiU/44L4WtFhdIXe9iBENgvtY0GJ1pdwxESMaBLdZ0GJ1QO64iBENgmMWtFg9PT09/S/9A2xTs6eMhSwfAAAAAElFTkSuQmCC",
"no-adult":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAEsElEQVR4Ae3BT2hb9wEA4E9P7yCCD5orGo0FmtERchibt/qQQ9hMMbSQQI0ojRN7I9sO3SEBj4TapTP1oRCNDJIto6SUshRs4pFA8RbDBju4NAwfvJFDkDxowGUJKKBDDmLRQXF3+B1enyT/VZYd5u+zZ8//uYyn5wiG8BIOo4CioIY6VvF3LGHZU5DRmyImMIYDduY+5nAZNbuUsTsFXMA4cnrTxCzeRt0OZezcKK6g4Omq4yzm7UDG9sW4gp/rroEFLOEO1lAXFHEAgxjCMfTp7irOomUbMranD9dxXKd7KGMWTduTwzim8KJOt3ASDVvI2lqMGzgurYlpnMIKWravhX/gfTzGUcQSh/Ad3MC6TWRt7X2c0mkaZazbvXXcxiKG0S9xCPtxyyayNjeKC7obQhUVvavhBl7F8xKD+Cfu2kDWxgpYxD7dRSihioreNfAJRtAvMYQP0dRF1sZ+i6MSTUxjCJEgQglVVPSugc9wGrFgH76GW7rI6q6IjxFJTKOMKkqIBBFKqKKidzU8wbDEt/ERGtpkdfdL/EDiHk5hHRVUUUIkiFBCFRW9W8YY+gUxnuCv2sS6G5NWRkviJm7672mhjA8lxjClTaTTERyQaGDWszeLhsQBHNEm1mlI2gKagj6cF6xiHnlMCFZwEAU0URZMII861jAouIoaRjAg+DUaaGIRJySGsOwrYp0GpS1JNDCA19DEEiYwKfgevoV3Bato4pLgF7iPPwnyKOP3yGMBDYklnJAY1CbW6bC0O9KmcAw5XMKIYA53sIozeBHvStzDVTQxhzG8if3Io4UpaSvSDmsT6fSctDVpq5gTjCKHFmYETbwnGMCA4D00BTNoIYdRwRxWpdWkPadNpFNRWl2nGWlz+FziGr6Q+ALXJD7HnLQZne5LK2oT2Z0Raa8gJzGAFyRewIBEDq9IG7ELkU4PpRWl5fGOYE1QxHmJi4JHeCS4KHEeRcGa4B3kpRWkPdQm0qku7YC08ygIfoRPBeeQxzCGBb/CbwTDGEIe5wR/wU8EBUxIOyitrk2k06q0QYkizgkWcBsTgjxmcFFQw2WUURNcwgzygiksYUEwiaLEoLRVbTI6TeGCxB8w6n9jHick3kbZV0Q6LUk7hpxnL4dj0pa0iXRaxgOJPox79sbRJ/EAy9rEupvFpMQkrqGld6/jOmKJFk7ipiDGpLRZXWR1dxdnEAv68Ri39a6CKkqIBBFKqKKCt/CGRBMn0dAmq7sGvonvSxzFImp6V0EVJUSCCCV8iWnEEh9hXhdZG/sbfop9ghjDuIGG3lVQRQmRIMLLiCXqeA1NXWRt7N/4F16X6Mer+AQNvaugihIi3f0MKzaQtbm7+DoGJZ7HCD5DTe8q+BIv6/QByjaRtbU/4yUckujHaTzBMtbtToy3MI1Y2iJ+jHWbyNraOv6I7+KQRIxhnMJjVNCyPTmcxnW8gVjaIkbRtIWM7YvxO7ypuwZu4VOs4D5qggIOYhA/xHH06e4DnEHLNmTs3CiuoODpquMs5u1Axu4UUMYYcnrTxMeYwiM7lNGbIiYwjm/YmQeYxWXU7FLG03MEQxjEYRSwX/AQdaxiBUtYtmfPnp79B5xbJmSrP/izAAAAAElFTkSuQmCC",
"settings":"iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAEyElEQVR4Ae3Bf2hcdwEA8E/ePcMJQa5dmIXVWrRidcGepYxZ6vBHptmo2xhZ16FgJWUV7aCOSFtURKUEJdjOZc7IatPp2EYPJi602Va1UFcRCp6YuQ47YSPVMga7P052ps/DP+6Pb17evcsV7x+xn49rrvk/16d3hvGC7nwSZ/RApHeGdK+sRyK9U9a9sh6J9E5Z98p6JNYbMW6Utgo1LSW8JbgRMRL/pUh3RlGSbwix4DXUBDVcEsQYkm8Ao7oQW9l2nEADc3gCs2hoKWGvtKqs87hBsBfjqGkpYjs+jxEU8TnM6iDWWYzDWoq4C3ehjgr+hG9gUFpV1jzuFIzhThzCJoxiQNphzCGRI9bZODbIGsAu+aqyzssaxGH5NmAfJuUoyLcGT6KoezVMYwYNaZfxTmxEUfduwnHUtVGQ7wi2CmqYxnvwLmkJvof78Es0ZDUwh2n8C9sQSbuEY9iIopYiVuFX2ihobwseRiT4Or6LH+EsruB9WMCteAoNK2vgDJ7FMCI8gf3Yh5P4J24XfASn8HfL9GnvLLYJXsEQEmlFxKgLyvgiRrBWywLmcBTzggEkaEiLMY8PCn6Hj1umIGsnHpR2COdkJVjUEuMh/BRbMYh+9GMQN+N+XI8X0MQiEllNxBgRrMMrmLdEQdY3MSRtG17GBe3F+C1GEckX4SZ8Cj9HU3ujeAj90v6NiiUKsmbxAQwJ+jGKt3FO1o9xt+6tw3U4KesAptEv7WnsQmKJgqwEFbwDtwgifAZr8ByaWsp4FJHgIvZgDBP4IzZjtWAznsEbWmI8ggOyDuErSCxTkO83uITbEQm24Cz+puUAtgou4qOoYhGL+AuOYQdWa4lwBXNabsGUtARj+KEckc4ew22yLghGpB1EXVYdB6UNCy7Kug0zOois7LSsBcEN0ubkm5P2XsGCrNNWEPkfF1nZsKy1gkvSRuQbkfaaYK2sYSuIdLYbp2RtEMxJm8CArAFMSDst2CjrFHbroCDfBH6ASNo0foKmlgXcj0jLauzAP/A6+nEHTmCDIMEevKHldbwbWwQR7kARv9ZGn6wBHMOotAQHMSlrCl91dR7BXlnjmEAsrYIvoW6JgqzHsUNaHffhZ9p7Hp/GOt15ETvRlHUOf8Z29As+jPejYomCrBij0vZjRr4mHsd12IxIewkexU4k8l3A2xiRdgjzlijImsetWCdYj2k0pRVRxCKaOIlncAWrUMQi/oonsQczaGoZQIREWoyjGBS8iAct06e9Lfg9YsEDmEKMT+Be7MRl3IOqq1PGCazBU3gaZ5BgLx4WJPgYzlumT77HMCaoYQajWCstwfcxiZrOShjHfsTSFlDBLpQER7FbG33yrcHLKOleDTP4DmrSSvg2dqGkezV8CJe1UZCvjj4M614RN+MPuCBtBEdQdHW+hefliHQ2iVdl1XEcX8ObssqyyrLexAM4jrqsV3FEB7HOEuzDs2jgOfwCs2homcEkxgRlWWVpRzGOmpYvYzu+gM+iiH1IdBBb2SzuwRzqsmqYwphgk6xN0qZQEzRQQQUDGMGsFUS6U0FdvnkkgvUoCUpYL0gwL18dFV2I9UaCl7BJ8JZ8LyHRA5HeqepeVY9Eeqeqe1U9Eumdqu7Nu+aaa3riP2EvKOAXjvMRAAAAAElFTkSuQmCC",
}

_ICON_IMG_CACHE ={}

def _quantize_hex (color :str ,step :int =10 )->str :
    try :
        h =color .lstrip ("#")
        if len (h )!=6 :
            return color 
        r ,g ,b =int (h [0 :2 ],16 ),int (h [2 :4 ],16 ),int (h [4 :6 ],16 )
        q =lambda v :max (0 ,min (255 ,(v //step )*step +step //2 ))
        return f"#{q (r ):02x}{q (g ):02x}{q (b ):02x}"
    except Exception :
        return color 

def _render_png_icon (slug :str ,size :int ,color :str ):
    b64 =_IOR_PNG .get (slug )
    if not b64 :
        return None 
    try :
        raw =base64 .b64decode (b64 )
        src =_PILImage .open (io .BytesIO (raw )).convert ("RGBA")
        h =color .lstrip ("#")
        r ,g ,b =int (h [0 :2 ],16 ),int (h [2 :4 ],16 ),int (h [4 :6 ],16 )
        solid =_PILImage .new ("RGBA",src .size ,(r ,g ,b ,255 ))
        solid .putalpha (src .split ()[3 ])

        target_px =max (8 ,int (round (size )))

        hi_res =max (512 ,target_px *8 )
        solid =solid .resize ((hi_res ,hi_res ),_PILImage .LANCZOS )
        solid =solid .resize ((target_px ,target_px ),_PILImage .LANCZOS )
        return _PILImageTk .PhotoImage (solid )
    except Exception :
        return None 

def _render_iconoir_image (slug :str ,size :int ,color :str ):
    if not _PIL_AVAILABLE :
        return None 
    size =max (8 ,int (round (size )))
    qcolor =_quantize_hex (color )
    key =(slug ,size ,qcolor )
    img =_ICON_IMG_CACHE .get (key )
    if img is not None :
        return img 
    if slug in _IOR_PNG :
        tk_img =_render_png_icon (slug ,size ,qcolor )
        if tk_img is None :
            return None 
        _ICON_IMG_CACHE [key ]=tk_img 
        return tk_img 
    if not _SVG_ICONS_AVAILABLE :
        return None 
    svg_src =_IOR_SVG .get (slug )
    if not svg_src :
        return None 
    try :
        svg =svg_src .replace ("currentColor",qcolor )
        png_bytes =_cairosvg .svg2png (bytestring =svg .encode ("utf-8"),
        output_width =size *5 ,output_height =size *5 )
        pil_img =_PILImage .open (io .BytesIO (png_bytes )).convert ("RGBA")
        pil_img =pil_img .resize ((size ,size ),_PILImage .LANCZOS )
        tk_img =_PILImageTk .PhotoImage (pil_img )
    except Exception :
        return None 
    _ICON_IMG_CACHE [key ]=tk_img 
    return tk_img 

_IOR_SVG ["discord"]=("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" "
"xmlns=\"http://www.w3.org/2000/svg\"> <path fill=\"currentColor\" d=\"M20.317 4.3698a19.7913 "
"19.7913 0 0 0 -4.8851 -1.5152 0.0741 0.0741 0 0 0 -0.0785 0.0371c-0.211 0.3753 -0.4447 0.8648 "
"-0.6083 1.2495 -1.8447 -0.2762 -3.68 -0.2762 -5.4868 0 -0.1636 -0.3933 -0.4058 -0.8742 -0.6177 "
"-1.2495a0.077 0.077 0 0 0 -0.0785 -0.037 19.7363 19.7363 0 0 0 -4.8852 1.515 0.0699 0.0699 0 0 0 "
"-0.0321 0.0277C0.5334 9.0458 -0.319 13.5799 0.0992 18.0578a0.0824 0.0824 0 0 0 0.0312 0.0561 "
"c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a0.0777 0.0777 0 0 0 0.0842 -0.0276c0.4616 -0.6304 "
"0.8731 -1.2952 1.226 -1.9942a0.076 0.076 0 0 0 -0.0416 -0.1057c-0.6528 -0.2476 -1.2743 -0.5495 "
"-1.8722 -0.8923a0.077 0.077 0 0 1 -0.0076 -0.1277c0.1258 -0.0943 0.2517 -0.1923 0.3718 -0.2914 "
"a0.0743 0.0743 0 0 1 0.0776 -0.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a0.0739 0.0739 0 0 1 "
"0.0785 0.0095c0.1202 0.099 0.246 0.1981 0.3728 0.2924a0.077 0.077 0 0 1 -0.0066 0.1276 12.2986 "
"12.2986 0 0 1 -1.873 0.8914a0.0766 0.0766 0 0 0 -0.0407 0.1067c0.3604 0.698 0.7719 1.3628 1.225 "
"1.9932a0.076 0.076 0 0 0 0.0842 0.0286c1.961 -0.6067 3.9495 -1.5219 6.0023 -3.0294a0.077 0.077 "
"0 0 0 0.0313 -0.0552c0.5004 -5.177 -0.8382 -9.6739 -3.5485 -13.6604a0.061 0.061 0 0 0 -0.0312 "
"-0.0286ZM8.02 15.3312c-1.1825 0 -2.1569 -1.0857 -2.1569 -2.419 0 -1.3332 0.9555 -2.4189 2.157 "
"-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332 -0.9555 2.4189 -2.1569 2.4189Zm7.9748 0 "
"c-1.1825 0 -2.1569 -1.0857 -2.1569 -2.419 0 -1.3332 0.9554 -2.4189 2.1569 -2.4189 1.2108 0 "
"2.1757 1.0952 2.1568 2.419 0 1.3332 -0.946 2.4189 -2.1568 2.4189Z\"/> </svg>")

def _icon_discord_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.08 )
    bw ,bh =size *0.66 ,size *0.42 
    x0 ,y0 =cx -bw /2 ,cy -bh /2 -size *0.04 
    x1 ,y1 =cx +bw /2 ,cy +bh /2 -size *0.04 
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.2 ,outline =color ,fill ="",width =w )
    er =size *0.075 
    ey =cy +size *0.02 
    cv .create_oval (cx -bw *0.2 -er ,ey -er ,cx -bw *0.2 +er ,ey +er ,outline =color ,fill =color )
    cv .create_oval (cx +bw *0.2 -er ,ey -er ,cx +bw *0.2 +er ,ey +er ,outline =color ,fill =color )
    for dx in (-1 ,1 ):
        lx =cx +dx *bw *0.42 
        cv .create_line (lx ,y1 -size *0.03 ,lx +dx *size *0.05 ,y1 +size *0.12 ,
        fill =color ,width =w ,capstyle ="round")


def _icon_discord (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"discord",size ,color ,bg =bg ,fallback =_icon_discord_fallback )

def _icon_swatch (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.2 ,size *0.08 )
    r =size *0.16 
    for dx ,dy in ((-0.16 ,-0.1 ),(0.16 ,-0.1 ),(0 ,0.18 )):
        px ,py =cx +dx *size ,cy +dy *size 
        cv .create_oval (px -r ,py -r ,px +r ,py +r ,outline =color ,width =w ,fill ="")

def _icon_pictures (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.2 ,size *0.08 )
    bw ,bh =size *0.5 ,size *0.38 
    ox ,oy =size *0.09 ,size *0.09 
    bx0 ,by0 =cx -bw /2 -ox ,cy -bh /2 -oy 
    bx1 ,by1 =bx0 +bw ,by0 +bh 
    draw_rrect (cv ,bx0 ,by0 ,bx1 ,by1 ,r =size *0.08 ,outline =color ,fill =bg if bg else BG ,width =w )
    fx0 ,fy0 =bx0 +ox *2 ,by0 +oy *2 
    fx1 ,fy1 =fx0 +bw ,fy0 +bh 
    draw_rrect (cv ,fx0 ,fy0 ,fx1 ,fy1 ,r =size *0.08 ,outline =color ,fill =bg if bg else BG ,width =w )
    cv .create_line (fx0 +bw *0.12 ,fy1 -bh *0.28 ,fx0 +bw *0.4 ,fy1 -bh *0.62 ,
    fx0 +bw *0.62 ,fy1 -bh *0.32 ,fx1 -bw *0.14 ,fy1 -bh *0.7 ,
    fill =color ,width =w ,joinstyle ="round",smooth =False )
    sr =size *0.045 
    sx ,sy =fx0 +bw *0.22 ,fy0 +bh *0.28 
    cv .create_oval (sx -sr ,sy -sr ,sx +sr ,sy +sr ,outline =color ,fill =color )

def _icon_image_off (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.2 ,size *0.08 )
    bw ,bh =size *0.6 ,size *0.42 
    x0 ,y0 =cx -bw /2 ,cy -bh /2 
    x1 ,y1 =cx +bw /2 ,cy +bh /2 
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.1 ,outline =color ,fill ="",width =w )
    cv .create_line (x0 +bw *0.14 ,y1 -bh *0.22 ,x0 +bw *0.4 ,y1 -bh *0.55 ,
    x0 +bw *0.58 ,y1 -bh *0.28 ,x1 -bw *0.14 ,y1 -bh *0.65 ,
    fill =color ,width =w ,joinstyle ="round")
    cv .create_line (x0 -size *0.02 ,y0 -size *0.02 ,x1 +size *0.02 ,y1 +size *0.02 ,
    fill =color ,width =w +0.6 ,capstyle ="round")

def _draw_iconoir (cv ,cx ,cy ,slug :str ,size ,color ,bg =None ,fallback =None ):
    img =_render_iconoir_image (slug ,size ,color )
    if img is not None :
        if not hasattr (cv ,"_icon_img_refs"):
            cv ._icon_img_refs =[]
        cv ._icon_img_refs .append (img )
        cv .create_image (cx ,cy ,image =img ,anchor ="center")
        return 
    if fallback is not None :
        fallback (cv ,cx ,cy ,size ,color ,bg =bg )

def _icon_generic_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    r =size *0.42 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,outline =color ,
    width =max (1.3 ,size *0.09 ),fill ="")


def _icon_globe_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    r =size *0.42 
    w =max (1.3 ,size *0.075 )
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,fill =color ,outline ="")
    cv .create_oval (cx -r *0.42 ,cy -r *0.98 ,cx +r *0.42 ,cy +r *0.98 ,
    outline =bg ,width =w ,fill ="")
    cv .create_line (cx -r *0.96 ,cy ,cx +r *0.96 ,cy ,fill =bg ,width =w )
    cv .create_line (cx -r *0.82 ,cy -r *0.5 ,cx +r *0.82 ,cy -r *0.5 ,fill =bg ,width =w *0.85 )
    cv .create_line (cx -r *0.82 ,cy +r *0.5 ,cx +r *0.82 ,cy +r *0.5 ,fill =bg ,width =w *0.85 )


def _icon_globe (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"globe",size ,color ,bg =bg ,fallback =_icon_globe_fallback )

def _icon_refresh_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    r =size *0.34 
    w =max (2.0 ,size *0.16 )
    cv .create_arc (cx -r ,cy -r ,cx +r ,cy +r ,start =25 ,extent =145 ,
    style ="arc",outline =color ,width =w )
    cv .create_arc (cx -r ,cy -r ,cx +r ,cy +r ,start =205 ,extent =145 ,
    style ="arc",outline =color ,width =w )
    import math as _m 
    for ang in (25 ,205 ):
        rad =_m .radians (ang )
        tip =(cx +_m .cos (rad )*r ,cy -_m .sin (rad )*r )
        tang =rad +_m .pi /2 
        a =(tip [0 ]+_m .cos (tang -.5 )*r *0.44 ,tip [1 ]-_m .sin (tang -.5 )*r *0.44 )
        b =(tip [0 ]+_m .cos (tang +.5 )*r *0.44 ,tip [1 ]-_m .sin (tang +.5 )*r *0.44 )
        cv .create_polygon (tip [0 ],tip [1 ],a [0 ],a [1 ],b [0 ],b [1 ],fill =color ,outline ="")


def _icon_refresh (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"refresh",size ,color ,bg =bg ,fallback =_icon_refresh_fallback )

def _icon_gear_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    import math as _m 
    bg =bg if bg is not None else BG 
    r =size *0.26 
    tooth_len =size *0.15 
    tooth_w =size *0.13 
    for ang in range (0 ,360 ,45 ):
        rad =_m .radians (ang )
        tx ,ty =cx +_m .cos (rad )*(r +tooth_len *0.55 ),cy +_m .sin (rad )*(r +tooth_len *0.55 )
        perp =rad +_m .pi /2 
        px ,py =_m .cos (perp )*tooth_w /2 ,_m .sin (perp )*tooth_w /2 
        cv .create_polygon (tx -px ,ty -py ,tx +px ,ty +py ,
        cx +_m .cos (rad )*r +px *0.6 ,cy +_m .sin (rad )*r +py *0.6 ,
        cx +_m .cos (rad )*r -px *0.6 ,cy +_m .sin (rad )*r -py *0.6 ,
        fill =color ,outline ="")
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,fill =color ,outline ="")
    hr =r *0.42 
    cv .create_oval (cx -hr ,cy -hr ,cx +hr ,cy +hr ,fill =bg ,outline ="")


def _icon_gear (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"settings",size ,color ,bg =bg ,fallback =_icon_gear_fallback )

def _icon_leaf_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    shade =darken (color ,.22 )
    vein =darken (color ,.38 )
    w =max (1.6 ,size *0.1 )
    stem_top =cy +size *0.24 

    cv .create_line (cx -size *0.02 ,cy +size *0.42 ,cx +size *0.05 ,stem_top ,
    fill =vein ,width =w *0.8 ,capstyle ="round")

    blade =[
    cx +size *0.02 ,stem_top ,
    cx -size *0.32 ,stem_top -size *0.08 ,
    cx -size *0.40 ,stem_top -size *0.34 ,
    cx -size *0.26 ,stem_top -size *0.58 ,
    cx +size *0.02 ,stem_top -size *0.68 ,
    cx +size *0.30 ,stem_top -size *0.56 ,
    cx +size *0.38 ,stem_top -size *0.30 ,
    cx +size *0.24 ,stem_top -size *0.08 ,
    ]
    cv .create_polygon (blade ,fill =color ,outline ="",smooth =True )

    shadow =[
    cx +size *0.02 ,stem_top ,
    cx -size *0.32 ,stem_top -size *0.08 ,
    cx -size *0.40 ,stem_top -size *0.34 ,
    cx -size *0.26 ,stem_top -size *0.58 ,
    cx +size *0.02 ,stem_top -size *0.68 ,
    cx -size *0.06 ,stem_top -size *0.42 ,
    cx -size *0.02 ,stem_top -size *0.16 ,
    ]
    cv .create_polygon (shadow ,fill =shade ,outline ="",smooth =True )

    cv .create_line (cx ,stem_top -size *0.02 ,cx +size *0.06 ,stem_top -size *0.3 ,
    cx +size *0.02 ,stem_top -size *0.6 ,
    fill =vein ,width =max (1.1 ,size *0.045 ),smooth =True ,capstyle ="round")
    cv .create_line (cx +size *0.02 ,stem_top -size *0.22 ,cx -size *0.16 ,stem_top -size *0.34 ,
    fill =vein ,width =max (1.0 ,size *0.035 ),smooth =True ,capstyle ="round")
    cv .create_line (cx +size *0.03 ,stem_top -size *0.42 ,cx +size *0.2 ,stem_top -size *0.48 ,
    fill =vein ,width =max (1.0 ,size *0.035 ),smooth =True ,capstyle ="round")


def _icon_leaf (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"leaf",size ,color ,bg =bg ,fallback =_icon_leaf_fallback )

def _icon_import_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    shaft_w =size *0.14 
    head_w =size *0.34 
    top =cy -size *0.28 
    neck =cy +size *0.02 
    tip =cy +size *0.22 
    cv .create_polygon (
    cx -shaft_w /2 ,top ,cx +shaft_w /2 ,top ,
    cx +shaft_w /2 ,neck ,
    cx +head_w /2 ,neck ,
    cx ,tip ,
    cx -head_w /2 ,neck ,
    cx -shaft_w /2 ,neck ,
    fill =color ,outline ="",smooth =False )
    w =max (1.8 ,size *0.14 )
    cv .create_line (cx -size *0.3 ,cy +size *0.36 ,cx +size *0.3 ,cy +size *0.36 ,
    fill =color ,width =w ,capstyle ="round")


def _icon_import (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"import",size ,color ,bg =bg ,fallback =_icon_import_fallback )

def _icon_check_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    r =size *0.42 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,fill =color ,outline ="")
    w =max (1.6 ,size *0.13 )
    cv .create_line (cx -size *0.20 ,cy +size *0.02 ,cx -size *0.03 ,cy +size *0.18 ,
    cx +size *0.24 ,cy -size *0.18 ,
    fill =bg ,width =w ,joinstyle ="round",capstyle ="round",smooth =False )


def _icon_check (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"check",size ,color ,bg =bg ,fallback =_icon_check_fallback )

def _icon_search_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    r =size *0.25 
    ring_w =max (2.2 ,size *0.15 )
    ccx ,ccy =cx -size *0.08 ,cy -size *0.08 
    cv .create_oval (ccx -r ,ccy -r ,ccx +r ,ccy +r ,fill =color ,outline ="")
    ir =r -ring_w 
    cv .create_oval (ccx -ir ,ccy -ir ,ccx +ir ,ccy +ir ,fill =bg ,outline ="")
    import math as _m 
    ang =_m .radians (45 )
    hx1 =ccx +r *_m .cos (ang )
    hy1 =ccy +r *_m .sin (ang )
    hx2 =cx +size *0.36 *_m .cos (ang )
    hy2 =cy +size *0.36 *_m .sin (ang )
    cv .create_line (hx1 ,hy1 ,hx2 ,hy2 ,fill =color ,
    width =max (2.4 ,size *0.16 ),capstyle ="round")


def _icon_search (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"search",size ,color ,bg =bg ,fallback =_icon_search_fallback )

def _icon_lock_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    bw ,bh =size *0.52 ,size *0.38 
    bx0 ,by0 =cx -bw /2 ,cy -bh /2 +size *0.12 
    bx1 ,by1 =cx +bw /2 ,cy +bh /2 +size *0.12 
    w =max (1.8 ,size *0.13 )
    r =size *0.19 
    cv .create_arc (cx -r ,by0 -r *1.6 ,cx +r ,by0 +r *0.2 ,start =0 ,extent =180 ,
    style ="arc",outline =color ,width =w )
    draw_rrect (cv ,bx0 ,by0 ,bx1 ,by1 ,r =3 ,outline ="",fill =color )
    kr =size *0.06 
    ky =(by0 +by1 )/2 -size *0.03 
    cv .create_oval (cx -kr ,ky -kr ,cx +kr ,ky +kr ,fill =bg ,outline ="")
    cv .create_polygon (cx -kr *0.6 ,ky ,cx +kr *0.6 ,ky ,cx +kr *0.35 ,by1 -size *0.05 ,
    cx -kr *0.35 ,by1 -size *0.05 ,fill =bg ,outline ="")


def _icon_lock (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"lock",size ,color ,bg =bg ,fallback =_icon_lock_fallback )

def _icon_wifi_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bw =size *0.15 
    gap =size *0.08 
    heights =[size *0.22 ,size *0.40 ,size *0.58 ]
    total =3 *bw +2 *gap 
    x =cx -total /2 
    base_y =cy +size *0.3 
    for h in heights :
        draw_rrect (cv ,x ,base_y -h ,x +bw ,base_y ,r =bw *0.4 ,outline ="",fill =color )
        x +=bw +gap 
    dr =size *0.045 
    cv .create_oval (cx -total /2 -dr ,base_y +dr *1.6 -dr ,cx -total /2 +dr ,base_y +dr *1.6 +dr ,
    fill =color ,outline ="")


def _icon_wifi (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"wifi",size ,color ,bg =bg ,fallback =_icon_wifi_fallback )

def _icon_plus_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    r =size *0.28 
    w =max (2.0 ,size *0.15 )
    cv .create_line (cx -r ,cy ,cx +r ,cy ,fill =color ,width =w ,capstyle ="round")
    cv .create_line (cx ,cy -r ,cx ,cy +r ,fill =color ,width =w ,capstyle ="round")


def _icon_plus (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"plus",size ,color ,bg =bg ,fallback =_icon_plus_fallback )

def _icon_link_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    w =max (2.2 ,size *0.16 )
    rx ,ry =size *0.17 ,size *0.115 
    o1 =(cx -size *0.13 ,cy -size *0.13 )
    o2 =(cx +size *0.13 ,cy +size *0.13 )
    cv .create_oval (o1 [0 ]-rx ,o1 [1 ]-ry ,o1 [0 ]+rx ,o1 [1 ]+ry ,outline =color ,width =w )
    cv .create_oval (o2 [0 ]-rx ,o2 [1 ]-ry ,o2 [0 ]+rx ,o2 [1 ]+ry ,outline =color ,width =w )


def _icon_link (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"link",size ,color ,bg =bg ,fallback =_icon_link_fallback )

def _icon_x_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    r =size *0.42 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,fill =color ,outline ="")
    xr =size *0.19 
    w =max (1.6 ,size *0.12 )
    cv .create_line (cx -xr ,cy -xr ,cx +xr ,cy +xr ,fill =bg ,width =w ,capstyle ="round")
    cv .create_line (cx -xr ,cy +xr ,cx +xr ,cy -xr ,fill =bg ,width =w ,capstyle ="round")


def _icon_x (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"xmark",size ,color ,bg =bg ,fallback =_icon_x_fallback )

def _icon_warn_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    pts =[cx ,cy -size *0.36 ,cx -size *0.36 ,cy +size *0.28 ,cx +size *0.36 ,cy +size *0.28 ]
    cv .create_polygon (pts ,fill =color ,outline =color ,joinstyle ="round")
    w =max (1.6 ,size *0.12 )
    cv .create_line (cx ,cy -size *0.04 ,cx ,cy +size *0.1 ,fill =bg ,width =w ,capstyle ="round")
    cv .create_oval (cx -1.6 ,cy +size *0.2 -1.6 ,cx +1.6 ,cy +size *0.2 +1.6 ,outline =bg ,fill =bg )


def _icon_warn (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"warning-triangle",size ,color ,bg =bg ,fallback =_icon_warn_fallback )

def _icon_info_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    r =size *0.42 
    w =max (1.5 ,size *0.12 )
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,fill =color ,outline ="")
    cv .create_oval (cx -1.6 ,cy -r *0.5 -1.6 ,cx +1.6 ,cy -r *0.5 +1.6 ,outline =bg ,fill =bg )
    cv .create_line (cx ,cy -r *0.08 ,cx ,cy +r *0.6 ,fill =bg ,width =w ,capstyle ="round")


def _icon_info (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"info-circle",size ,color ,bg =bg ,fallback =_icon_info_fallback )

def _icon_shield_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.4 ,size *0.09 )
    r =size *0.34 
    pts =[cx ,cy -r ,cx +r *0.9 ,cy -r *0.55 ,cx +r *0.9 ,cy +r *0.15 ,
    cx ,cy +r *1.15 ,cx -r *0.9 ,cy +r *0.15 ,cx -r *0.9 ,cy -r *0.55 ]
    cv .create_polygon (pts ,outline =color ,fill ="",width =w ,joinstyle ="round",smooth =False )


def _icon_shield (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"shield",size ,color ,bg =bg ,fallback =_icon_shield_fallback )

def _icon_building_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.08 )
    bw ,bh =size *0.5 ,size *0.62 
    x0 ,y0 =cx -bw /2 ,cy -bh /2 
    x1 ,y1 =cx +bw /2 ,cy +bh /2 
    cv .create_rectangle (x0 ,y0 ,x1 ,y1 ,outline =color ,width =w )
    for gy in (y0 +bh *0.24 ,y0 +bh *0.52 ,y0 +bh *0.8 ):
        for gx in (x0 +bw *0.27 ,x0 +bw *0.73 ):
            cv .create_oval (gx -1.3 ,gy -1.3 ,gx +1.3 ,gy +1.3 ,outline =color ,fill =color )


def _icon_building (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"city",size ,color ,bg =bg ,fallback =_icon_building_fallback )

def _icon_chat_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.09 )
    bw ,bh =size *0.62 ,size *0.42 
    x0 ,y0 =cx -bw /2 ,cy -bh /2 -size *0.06 
    x1 ,y1 =cx +bw /2 ,cy +bh /2 -size *0.06 
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.14 ,outline =color ,fill ="",width =w )
    cv .create_polygon (cx -size *0.1 ,y1 -1 ,cx -size *0.02 ,y1 +size *0.16 ,cx +size *0.12 ,y1 -1 ,
    outline =color ,fill ="",width =w ,joinstyle ="round")


def _icon_chat (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"chat-bubble",size ,color ,bg =bg ,fallback =_icon_chat_fallback )

def _icon_eye_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.09 )
    rw ,rh =size *0.36 ,size *0.2 
    cv .create_arc (cx -rw ,cy -rh ,cx +rw ,cy +rh ,start =0 ,extent =180 ,style ="arc",outline =color ,width =w )
    cv .create_arc (cx -rw ,cy -rh ,cx +rw ,cy +rh ,start =180 ,extent =180 ,style ="arc",outline =color ,width =w )
    r =size *0.09 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,outline =color ,width =w )


def _icon_eye (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"eye",size ,color ,bg =bg ,fallback =_icon_eye_fallback )

def _icon_dice_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.08 )
    bw =size *0.5 
    x0 ,y0 =cx -bw /2 ,cy -bw /2 
    x1 ,y1 =cx +bw /2 ,cy +bw /2 
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.1 ,outline =color ,fill ="",width =w )
    for dx ,dy in ((-0.2 ,-0.2 ),(0.2 ,0.2 ),(0 ,0 )):
        px ,py =cx +dx *bw ,cy +dy *bw 
        cv .create_oval (px -1.6 ,py -1.6 ,px +1.6 ,py +1.6 ,outline =color ,fill =color )


def _icon_dice (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"dice-five",size ,color ,bg =bg ,fallback =_icon_dice_fallback )

def _icon_robot_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.3 ,size *0.08 )
    bw ,bh =size *0.5 ,size *0.4 
    x0 ,y0 =cx -bw /2 ,cy -bh /2 +size *0.06 
    x1 ,y1 =cx +bw /2 ,cy +bh /2 +size *0.06 
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.1 ,outline =color ,width =w )
    cv .create_line (cx ,y0 ,cx ,y0 -size *0.14 ,fill =color ,width =w ,capstyle ="round")
    cv .create_oval (cx -1.6 ,y0 -size *0.14 -1.6 ,cx +1.6 ,y0 -size *0.14 +1.6 ,outline =color ,fill =color )
    er =size *0.05 
    cv .create_oval (cx -bw *0.22 -er ,cy -er ,cx -bw *0.22 +er ,cy +er ,outline =color ,fill =color )
    cv .create_oval (cx +bw *0.22 -er ,cy -er ,cx +bw *0.22 +er ,cy +er ,outline =color ,fill =color )


def _icon_robot (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"cpu",size ,color ,bg =bg ,fallback =_icon_robot_fallback )

def _icon_onion_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.2 ,size *0.08 )
    for rr in (0.36 ,0.24 ,0.12 ):
        r =size *rr 
        cv .create_oval (cx -r ,cy -r *1.15 ,cx +r ,cy +r *1.15 ,outline =color ,width =w )


def _icon_onion (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"private-wifi",size ,color ,bg =bg ,fallback =_icon_onion_fallback )

def _icon_palette_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    def P (X ,Y ):
        return (cx +(X -12 )/24 *size ,cy +(Y -12 )/24 *size )
    bg =bg if bg is not None else BG 
    w =max (1.6 ,size *0.10 )
    x0 ,y0 =P (3.3 ,3 )
    x1 ,y1 =P (20.6 ,21 )
    cv .create_oval (x0 ,y0 ,x1 ,y1 ,outline =color ,width =w )
    nx ,ny =P (17.5 ,15.5 )
    nr =size *0.10 
    cv .create_oval (nx -nr ,ny -nr ,nx +nr ,ny +nr ,fill =bg ,outline =color ,width =max (1.1 ,w *0.6 ))
    for X ,Y in ((8 ,16 ),(6 ,12 ),(8 ,8 ),(12 ,6 ),(16 ,8 )):
        px ,py =P (X ,Y )
        dr =max (1.3 ,size *0.028 )
        cv .create_oval (px -dr ,py -dr ,px +dr ,py +dr ,fill =color ,outline ="")

def _icon_palette (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"palette",size ,color ,bg =bg ,fallback =_icon_palette_fallback )

def _icon_image_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    def P (X ,Y ):
        return (cx +(X -12 )/24 *size ,cy +(Y -12 )/24 *size )
    w =max (1.5 ,size *0.09 )
    x0 ,y0 =P (3.6 ,3.6 )
    x1 ,y1 =P (20.4 ,21 )
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.04 ,outline =color ,fill ="",width =w )
    sx ,sy =P (16 ,8 )
    sr =max (1.6 ,size *0.055 )
    cv .create_oval (sx -sr ,sy -sr ,sx +sr ,sy +sr ,outline =color ,width =max (1.2 ,w *0.75 ))
    pts =[]
    for X ,Y in ((3 ,16 ),(10 ,13 ),(21 ,18 )):
        pts .extend (P (X ,Y ))
    cv .create_line (*pts ,fill =color ,width =w ,joinstyle ="round",capstyle ="round")

def _icon_image (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"media-image",size ,color ,bg =bg ,fallback =_icon_image_fallback )

def _icon_erase_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    import math as _m 
    w =max (1.6 ,size *0.10 )
    ang =_m .radians (-45 )
    hl ,hw =size *0.30 ,size *0.19 
    corners =[]
    for lx ,ly in ((-hl ,-hw ),(hl ,-hw ),(hl ,hw ),(-hl ,hw )):
        rx =lx *_m .cos (ang )-ly *_m .sin (ang )
        ry =lx *_m .sin (ang )+ly *_m .cos (ang )
        corners .append ((cx +rx ,cy +ry -size *0.04 ))
    cv .create_polygon (*[c for pt in corners for c in pt ],
    outline =color ,width =w ,fill ="",joinstyle ="round")
    mx1 =corners [0 ][0 ]+(corners [1 ][0 ]-corners [0 ][0 ])*0.42 
    my1 =corners [0 ][1 ]+(corners [1 ][1 ]-corners [0 ][1 ])*0.42 
    mx2 =corners [3 ][0 ]+(corners [2 ][0 ]-corners [3 ][0 ])*0.42 
    my2 =corners [3 ][1 ]+(corners [2 ][1 ]-corners [3 ][1 ])*0.42 
    cv .create_line (mx1 ,my1 ,mx2 ,my2 ,fill =color ,width =max (1.2 ,w *0.7 ),capstyle ="round")
    cv .create_line (cx -size *0.30 ,cy +size *0.34 ,cx +size *0.30 ,cy +size *0.34 ,
    fill =color ,width =w ,capstyle ="round")

def _icon_erase (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"erase",size ,color ,bg =bg ,fallback =_icon_erase_fallback )

def _icon_window_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    def P (X ,Y ):
        return (cx +(X -12 )/24 *size ,cy +(Y -12 )/24 *size )
    w =max (1.4 ,size *0.075 )
    x0 ,y0 =P (2 ,3 )
    x1 ,y1 =P (22 ,21 )
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.05 ,outline =color ,fill ="",width =w )
    lx0 ,ly0 =P (2 ,7 )
    lx1 ,ly1 =P (22 ,7 )
    cv .create_line (lx0 ,ly0 ,lx1 ,ly1 ,fill =color ,width =w ,capstyle ="round")
    for X in (5 ,8 ,11 ):
        px ,py =P (X ,5 )
        dr =max (1.1 ,size *0.02 )
        cv .create_oval (px -dr ,py -dr ,px +dr ,py +dr ,fill =color ,outline ="")

def _icon_window (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"app-window",size ,color ,bg =bg ,fallback =_icon_window_fallback )

def _icon_undo_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    import math as _m 
    w =max (1.8 ,size *0.12 )
    r =size *0.28 
    ccx ,ccy =cx +size *0.06 ,cy +size *0.05 
    cv .create_arc (ccx -r ,ccy -r ,ccx +r ,ccy +r ,start =30 ,extent =260 ,
    style ="arc",outline =color ,width =w )
    rad =_m .radians (30 )
    tip =(ccx +_m .cos (rad )*r ,ccy -_m .sin (rad )*r )
    tang =rad +_m .pi /2 
    a =(tip [0 ]+_m .cos (tang -.5 )*r *0.5 ,tip [1 ]-_m .sin (tang -.5 )*r *0.5 )
    b =(tip [0 ]+_m .cos (tang +.5 )*r *0.5 ,tip [1 ]-_m .sin (tang +.5 )*r *0.5 )
    cv .create_polygon (tip [0 ],tip [1 ],a [0 ],a [1 ],b [0 ],b [1 ],fill =color ,outline ="")

def _icon_undo (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"undo",size ,color ,bg =bg ,fallback =_icon_undo_fallback )

def _icon_waves_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    def P (X ,Y ):
        return (cx +(X -12 )/24 *size ,cy +(Y -12 )/24 *size )
    w =max (1.6 ,size *0.09 )
    for base_y in (10 ,17 ):
        pts =[]
        for X ,Y in ((3 ,base_y ),(7.34 ,base_y -3 ),(11.69 ,base_y ),
        (16.66 ,base_y -3 ),(21 ,base_y )):
            pts .extend (P (X ,Y ))
        cv .create_line (*pts ,fill =color ,width =w ,smooth =True ,capstyle ="round")

def _icon_waves (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"sea-waves",size ,color ,bg =bg ,fallback =_icon_waves_fallback )

def _icon_repeat (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"refresh-double",size ,color ,bg =bg ,fallback =_icon_refresh_fallback )

def _icon_download_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    w =max (1.6 ,size *0.10 )
    r =size *0.40 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,outline =color ,width =w )
    shaft_w =size *0.10 
    head_w =size *0.22 
    top =cy -size *0.16 
    neck =cy +size *0.02 
    tip =cy +size *0.15 
    cv .create_polygon (
    cx -shaft_w /2 ,top ,cx +shaft_w /2 ,top ,
    cx +shaft_w /2 ,neck ,cx +head_w /2 ,neck ,
    cx ,tip ,cx -head_w /2 ,neck ,cx -shaft_w /2 ,neck ,
    fill =color ,outline ="")

def _icon_download (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"download-circle",size ,color ,bg =bg ,fallback =_icon_download_fallback )

def _icon_trash_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    bg =bg if bg is not None else BG 
    w =max (1.6 ,size *0.11 )

    lid_y =cy -size *0.26 
    lid_hw =size *0.30 
    cv .create_line (cx -lid_hw ,lid_y ,cx +lid_hw ,lid_y ,
    fill =color ,width =w ,capstyle ="round")

    handle_hw =size *0.13 
    handle_top =lid_y -size *0.14 
    cv .create_line (
    cx -handle_hw ,lid_y ,cx -handle_hw ,handle_top ,
    cx +handle_hw ,handle_top ,cx +handle_hw ,lid_y ,
    fill =color ,width =w ,capstyle ="round",joinstyle ="round",smooth =False )

    top_hw =size *0.245 
    bot_hw =size *0.185 
    body_top =lid_y +size *0.07 
    body_bot =cy +size *0.36 
    cv .create_polygon (
    cx -top_hw ,body_top ,cx +top_hw ,body_top ,
    cx +bot_hw ,body_bot ,cx -bot_hw ,body_bot ,
    outline =color ,width =w ,fill ="",joinstyle ="round")

    sw =max (1.3 ,size *0.075 )
    for dx_top in (-size *0.115 ,0 ,size *0.115 ):
        dx_bot =dx_top *0.72 
        cv .create_line (cx +dx_top ,body_top +size *0.07 ,cx +dx_bot ,body_bot -size *0.06 ,
        fill =color ,width =sw ,capstyle ="round")

def _icon_trash (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"trash",size ,color ,bg =bg ,fallback =_icon_trash_fallback )

def _icon_block_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    import math as _m 
    w =max (1.8 ,size *0.13 )
    r =size *0.38 
    cv .create_oval (cx -r ,cy -r ,cx +r ,cy +r ,outline =color ,width =w )
    ang =_m .radians (45 )
    dx ,dy =_m .cos (ang )*r *0.82 ,_m .sin (ang )*r *0.82 
    cv .create_line (cx -dx ,cy -dy ,cx +dx ,cy +dy ,fill =color ,width =w ,capstyle ="round")

def _icon_block (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"prohibition",size ,color ,bg =bg ,fallback =_icon_block_fallback )

def _icon_phone_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    def P (X ,Y ):
        return (cx +(X -12 )/24 *size ,cy +(Y -12 )/24 *size )
    w =max (1.5 ,size *0.09 )
    x0 ,y0 =P (7 ,4 )
    x1 ,y1 =P (17 ,20 )
    draw_rrect (cv ,x0 ,y0 ,x1 ,y1 ,r =size *0.09 ,outline =color ,fill ="",width =w )
    px ,py =P (12 ,16 )
    dr =max (1.1 ,size *0.025 )
    cv .create_oval (px -dr ,py -dr ,px +dr ,py +dr ,fill =color ,outline ="")

def _icon_phone (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"smartphone-device",size ,color ,bg =bg ,fallback =_icon_phone_fallback )

def _icon_infinity_fallback (cv ,cx ,cy ,size ,color ,bg =None ):
    import math as _m 
    w =max (1.8 ,size *0.13 )
    a =size *0.30 
    steps =48 
    pts =[]
    for i in range (steps +1 ):
        t =(i /steps )*2 *_m .pi 
        denom =1 +_m .sin (t )**2 
        x =a *_m .cos (t )/denom 
        y =a *_m .sin (t )*_m .cos (t )/denom 
        pts .append ((cx +x ,cy +y ))
    flat =[c for p in pts for c in p ]
    cv .create_line (*flat ,fill =color ,width =w ,capstyle ="round",joinstyle ="round")

def _icon_infinity (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"infinite",size ,color ,bg =bg ,fallback =_icon_infinity_fallback )

def _icon_blood (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"blood-drop",size ,color ,bg =bg ,fallback =_icon_warn_fallback )

def _icon_hash (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"hash",size ,color ,bg =bg ,fallback =_icon_chat_fallback )

def _icon_angry (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"angry",size ,color ,bg =bg ,fallback =_icon_eye_fallback )

def _icon_tracking (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"tracking",size ,color ,bg =bg ,fallback =_icon_building_fallback )

def _icon_no_adult (cv ,cx ,cy ,size ,color ,bg =None ):
    _draw_iconoir (cv ,cx ,cy ,"no-adult",size ,color ,bg =bg ,fallback =_icon_lock_fallback )

SIDEBAR_ICON_FUNCS ={
"Ad Blocking":_icon_shield ,
"Evil Companies":_icon_tracking ,
"Social":_icon_hash ,
"Adult & OnlyFans":_icon_no_adult ,
"Gore & Shock":_icon_blood ,
"Conspiracy & Fringe":_icon_angry ,
"Crypto & Gambling":_icon_dice ,
"AI & Chatbots":_icon_robot ,
"Tor & Dark Web":_icon_onion ,
}

SIDEBAR_ICON_COLORS ={
"Ad Blocking":ACCENT ,
"Evil Companies":"#ff8a5c",
"Social":"#5cc8ff",
"Adult & OnlyFans":DANGER ,
"Gore & Shock":WARN ,
"Conspiracy & Fringe":ACCENT2 ,
"Crypto & Gambling":"#ffd166",
"AI & Chatbots":"#3ddc97",
"Tor & Dark Web":"#b48cff",
}

_FONT_CACHE :dict ={}
def _cached_font (font_spec ):
    key =tuple (font_spec )
    f =_FONT_CACHE .get (key )
    if f is None :
        f =tkfont .Font (font =font_spec )
        _FONT_CACHE [key ]=f 
    return f 

_ICON_GLYPHS ={
"🌐":_icon_globe ,"🌍":_icon_globe ,
"🔄":_icon_refresh ,
"⚙️":_icon_gear ,"⚙":_icon_gear ,
"🌱":_icon_leaf ,
"⇪":_icon_import ,
"✅":_icon_check ,
"🔎":_icon_search ,"🔍":_icon_search ,
"🔒":_icon_lock ,
"📶":_icon_wifi ,
"＋":_icon_plus ,"+":_icon_plus ,"➕":_icon_plus ,
"🔗":_icon_link ,
"❌":_icon_x ,
"⚠️":_icon_warn ,"⚠":_icon_warn ,
"ℹ️":_icon_info ,"ℹ":_icon_info ,
"🛡️":_icon_shield ,"🛡":_icon_shield ,
"💬":_icon_chat ,
"🧅":_icon_onion ,
"📥":_icon_download ,
"🗑️":_icon_trash ,"🗑":_icon_trash ,
"🎨":_icon_palette ,
"🖼️":_icon_image ,"🖼":_icon_image ,
"🧹":_icon_erase ,
"🪟":_icon_window ,
"↩️":_icon_undo ,"↩":_icon_undo ,
"🌊":_icon_waves ,
"🔁":_icon_repeat ,
"🚫":_icon_block ,
"📱":_icon_phone ,
"♾️":_icon_infinity ,"♾":_icon_infinity ,
"🟪":_icon_discord ,
"🟨":_icon_swatch ,
"🟩":_icon_pictures ,
"🟦":_icon_image_off ,
}

_ICON_LEAD_RE =re .compile (
r"^(⚙️|⚠️|ℹ️|🛡️|🗑️|🖼️|↩️|♾️|"
r"🌐|🌍|🔄|⚙|🌱|⇪|✅|🔎|🔍|🔒|📶|＋|➕|🔗|❌|⚠|ℹ|"
r"🛡|💬|🧅|📥|🗑|🎨|🖼|🧹|🪟|↩|🌊|🔁|🚫|📱|♾|🟪|🟨|🟩|🟦)\s*")

def _split_icon_text (text :str ):
    if not text :
        return None ,text 
    m =_ICON_LEAD_RE .match (text )
    if not m :
        return None ,text 
    return m .group (1 ),text [m .end ():]

def draw_icon_glyph (cv :tk .Canvas ,cx ,cy ,key :str ,size :float ,color :str ,bg =None ):
    fn =_ICON_GLYPHS .get (key )
    if fn :
        fn (cv ,cx ,cy ,size ,color ,bg =bg )

class FlatBtn (tk .Canvas ):

    _NEUTRAL =None 

    def __init__ (self ,master ,text ="",command =None ,
    base_bg =None ,hover_bg =None ,fg =None ,
    font =None ,radius =10 ,border_col =None ,ghost =False ,
    disabled =False ,**kw ):
        for k in ("relief","bd","activebackground","activeforeground",
        "highlightthickness","highlightbackground"):
            kw .pop (k ,None )
        self ._text =text 
        self ._cmd =command 
        self ._base =base_bg 
        self ._hoverc =hover_bg 
        self ._fg =fg 
        self ._font =font or (FONT_FAMILY ,12 ,"bold")
        self ._r =radius 
        self ._border_col =border_col 
        self ._ghost =ghost 
        self ._active =False 
        self ._t =0.0 
        self ._target =0.0 
        self ._press_t =0.0 
        self ._press_target =0.0 
        self ._pressed =False 
        self ._disabled =disabled 
        self ._job =None 
        self ._press_job =None 
        try :pbg =master .cget ("bg")
        except :pbg =BG 
        self ._pbg =pbg 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,
        cursor ="arrow"if disabled else "hand2",**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self .bind ("<Enter>",lambda e :self ._anim (1.0 ))
        self .bind ("<Leave>",lambda e :(setattr (self ,"_pressed",False ),
        self ._anim (0.0 ),self ._anim_press (0.0 )))
        self .bind ("<ButtonPress-1>",lambda e :self ._on_press ())
        self .bind ("<ButtonRelease-1>",lambda e :self ._on_release ())

    def _on_press (self ):
        if self ._disabled :return 
        self ._pressed =True 
        self ._anim_press (1.0 )

    def _on_release (self ):
        if self ._disabled :return 
        was_pressed =self ._pressed 
        self ._pressed =False 
        self ._anim_press (0.0 )
        if was_pressed and self ._cmd :self ._cmd ()

    def set_disabled (self ,disabled :bool ):
        self ._disabled =disabled 
        self .config (cursor ="arrow"if disabled else "hand2")
        if disabled :
            self ._pressed =False 
            self ._anim (0.0 )
            self ._anim_press (0.0 )
        self ._draw ()

    def set_active (self ,v :bool ):
        self ._active =v 
        self ._draw ()

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :return 
        self .delete ("all")

        is_primary =self ._base ==ACCENT or self ._base ==ACCENT2 
        is_secondary =self ._base in (BORDER ,TOOLBAR ,SIDEBAR ,CARD )or self ._border_col 
        is_tertiary =not is_primary and not is_secondary 

        t =max (self ._t ,1.0 if self ._active else 0.0 )
        dim =0.42 if self ._disabled else 1.0 
        dy =self ._press_t *1.5 

        lift =t *1.5 
        y_off =dy -lift 

        if is_primary :

            bg_idle =self ._base 
            bg_hover =lighten (bg_idle ,0.12 )
            bg_col =lerp_col (bg_idle ,bg_hover ,t )

            if t >0.1 :
                glow_col =lerp_col (self ._pbg ,lighten (bg_idle ,0.2 ),t *0.4 )
                draw_rrect (self ,1 ,1 +y_off +1 ,w -1 ,h -1 +y_off +1 ,self ._r +1 ,fill ="",outline =glow_col ,width =2 )

            draw_rrect (self ,2 ,2 +y_off ,w -2 ,h -2 +y_off ,self ._r ,fill =bg_col ,outline ="",width =0 )

            if t >0.05 :
                hi_col =lighten (bg_col ,0.15 )
                self .create_line (2 +self ._r ,3 +y_off ,w -2 -self ._r ,3 +y_off ,fill =hi_col ,width =1 ,capstyle ="round")

            text_col =TEXT 
        elif is_secondary :

            bg_idle =lighten (self ._pbg ,0.03 )if self ._pbg in (BG ,SIDEBAR ,CARD )else self ._pbg 
            bg_hover =lighten (bg_idle ,0.06 )
            bg_col =lerp_col (bg_idle ,bg_hover ,t )
            brd_col =lerp_col (BORDER ,ACCENT ,t )

            if t >0.1 :
                sh_col =darken (self ._pbg ,0.1 )
                draw_rrect (self ,3 ,3 +y_off +1 ,w -1 ,h -1 +y_off +1 ,self ._r ,fill ="",outline =sh_col ,width =1 )

            draw_rrect (self ,2 ,2 +y_off ,w -2 ,h -2 +y_off ,self ._r ,fill =bg_col ,outline =brd_col ,width =1 )
            text_col =lerp_col (MUTED ,TEXT ,t )
        else :

            text_col =lerp_col (ACCENT ,lighten (ACCENT ,0.15 ),t )
            y_off =dy 

        if self ._fg :text_col =self ._fg 
        if dim <1.0 :text_col =lerp_col (self ._pbg ,text_col ,dim )

        icon_key ,label =_split_icon_text (self ._text )
        icon_sz =max (12 ,min (h -10 ,16 ))
        fnt =tkfont .Font (font =self ._font )
        label_w =fnt .measure (label )if label else 0 
        gap =6 if (icon_key and label )else 0 
        content_w =(icon_sz if icon_key else 0 )+gap +label_w 
        start_x =(w -content_w )/2 
        cy =h /2 +y_off 

        if icon_key :
            draw_icon_glyph (self ,start_x +icon_sz /2 ,cy ,icon_key ,icon_sz ,text_col ,bg =self ._pbg )
        if label :
            self .create_text (start_x +(icon_sz +gap if icon_key else 0 ),cy ,
            text =label ,font =self ._font ,fill =text_col ,anchor ="w")

        if is_tertiary and t >0.1 :
            uy =cy +fnt .metrics ("linespace")/2 +1 
            self .create_line (start_x ,uy ,start_x +content_w ,uy ,fill =text_col ,width =1.5 )

    def _anim (self ,target ):
        if self ._disabled :
            return 
        self ._target =target 
        if self ._job :
            return 
        self ._step_anim ()

    def _step_anim (self ):
        diff =self ._target -self ._t 
        if abs (diff )<0.012 :
            self ._t =self ._target 
            self ._draw ()
            self ._job =None 
            return 
        self ._t +=diff *0.30 
        self ._draw ()
        self ._job =self .after (8 ,self ._step_anim )

    def _anim_press (self ,target ):
        self ._press_target =target 
        if self ._press_job :
            return 
        self ._step_press_anim ()

    def _step_press_anim (self ):
        diff =self ._press_target -self ._press_t 
        if abs (diff )<0.02 :
            self ._press_t =self ._press_target 
            self ._draw ()
            self ._press_job =None 
            return 

        self ._press_t +=diff *0.55 
        self ._draw ()
        self ._press_job =self .after (8 ,self ._step_press_anim )

    def config (self ,**kw ):
        dirty =False 
        for k ,a in (("text","_text"),("fg","_fg"),("font","_font")):
            if k in kw :setattr (self ,a ,kw .pop (k ));dirty =True 
        for d in ("relief","bd","activebackground","activeforeground",
        "highlightthickness","highlightbackground","anchor"):
            kw .pop (d ,None )
        if kw :
            try :super ().config (**kw )
            except :pass 
        if dirty :self ._draw ()
    configure =config 
    def unbind (self ,*a ):pass 

FlatBtn ._NEUTRAL =(None ,CARD ,BORDER ,TOOLBAR ,SIDEBAR )

class IconGlyph (tk .Canvas ):

    def __init__ (self ,master ,glyph ,size =16 ,color =None ,bg =None ,**kw ):
        bgc =bg if bg is not None else (master .cget ("bg")if hasattr (master ,"cget")else BG )
        pad =kw .pop ("pad",4 )
        super ().__init__ (master ,width =size +pad ,height =size +pad ,
        bg =bgc ,highlightthickness =0 ,**kw )
        self ._glyph =glyph 
        self ._size =size 
        self ._color =color or TEXT 
        self .bind ("<Configure>",lambda e :self ._draw ())
        self ._draw ()

    def _draw (self ):
        self .delete ("all")
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :
            w =h =self ._size +4 
        cx ,cy =w /2 ,h /2 
        key ,rest =_split_icon_text (self ._glyph )
        if key and rest =="":
            draw_icon_glyph (self ,cx ,cy ,key ,self ._size ,self ._color ,bg =self .cget ("bg"))
        else :
            self .create_text (cx ,cy ,text =self ._glyph ,
            font =(FONT_FAMILY ,int (self ._size *0.85 )),
            fill =self ._color ,anchor ="center")

class FlowRow (tk .Frame ):

    def __init__ (self ,master ,gap_x =10 ,gap_y =8 ,**kw ):
        bg =kw .pop ("bg",None )or (master .cget ("bg")if hasattr (master ,"cget")else BG )
        super ().__init__ (master ,bg =bg ,**kw )
        self ._gap_x =gap_x 
        self ._gap_y =gap_y 
        self ._items =[]
        self ._last_h =0 
        self .bind ("<Configure>",lambda e :self ._relayout ())

    def add (self ,widget ,width :int ,height :int ):
        self ._items .append ((widget ,width ,height ))
        self ._relayout ()
        return widget 

    def _relayout (self ):
        avail =self .winfo_width ()
        if avail <=1 :
            avail =max ((w for _ ,w ,_ in self ._items ),default =200 )
        x =y =row_h =0 
        for widget ,w ,h in self ._items :
            if x >0 and x +w >avail :
                x =0 
                y +=row_h +self ._gap_y 
                row_h =0 
            widget .place (x =x ,y =y ,width =w ,height =h )
            x +=w +self ._gap_x 
            row_h =max (row_h ,h )
        total_h =y +row_h 
        if total_h !=self ._last_h :
            self ._last_h =total_h 
            self .configure (height =total_h )

class SettingsRow (tk .Canvas ):
    HEIGHT =58 

    def __init__ (self ,master ,icon ,title ,desc ,command ,
    accent =None ,danger =False ,toggle =None ,**kw ):
        for k in ("relief","bd","highlightthickness","highlightbackground"):
            kw .pop (k ,None )
        self ._icon =icon 
        self ._title =title 
        self ._desc =desc 
        self ._cmd =command 
        self ._accent =accent or ACCENT 
        self ._danger =danger 
        self ._hover =False 
        self ._toggle =toggle 
        self ._sw_t =1.0 if toggle else 0.0 
        self ._sw_job =None 
        try :pbg =master .cget ("bg")
        except :pbg =CARD 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,
        height =self .HEIGHT ,cursor ="hand2",**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self .bind ("<Enter>",lambda e :(setattr (self ,"_hover",True ),self ._draw ()))
        self .bind ("<Leave>",lambda e :(setattr (self ,"_hover",False ),self ._draw ()))
        self .bind ("<ButtonRelease-1>",lambda e :self ._cmd ()if self ._cmd else None )

    def set_desc (self ,text ):
        self ._desc =text 
        self ._draw ()

    def set_title (self ,text ):
        self ._title =text 
        self ._draw ()

    def set_toggle (self ,value :bool ):
        if self ._toggle is None :
            return 
        self ._toggle =value 
        target =1.0 if value else 0.0 
        if self ._sw_job :
            self .after_cancel (self ._sw_job )
            self ._sw_job =None 
        self ._step_switch (target )

    def _step_switch (self ,target ):
        diff =target -self ._sw_t 
        if abs (diff )<0.02 :
            self ._sw_t =target 
            self ._draw ()
            self ._sw_job =None 
            return 
        self ._sw_t +=diff *0.35 
        self ._draw ()
        self ._sw_job =self .after (8 ,lambda :self ._step_switch (target ))

    def _draw (self ):
        w =self .winfo_width ()
        h =self .HEIGHT 
        if w <4 :
            return 
        self .delete ("all")
        col =DANGER if self ._danger else self ._accent 
        bg =self .cget ("bg")

        if self ._hover :
            draw_rrect (self ,2 ,2 ,w -2 ,h -2 ,12 ,
            fill =lerp_col (bg ,col ,.18 ),outline ="")
            self .create_rectangle (2 ,8 ,5 ,h -8 ,fill =col ,outline ="")

        cy =h //2 
        cx0 =10 
        icon_key ,_rest =_split_icon_text (self ._icon )
        if icon_key and _rest =="":
            draw_icon_glyph (self ,cx0 +18 ,cy ,icon_key ,18 ,col ,bg =bg )
        else :
            self .create_text (cx0 +18 ,cy ,text =self ._icon ,
            font =(FONT_FAMILY ,17 ),fill =col ,anchor ="center")

        tx =cx0 +36 
        right_w =46 if self ._toggle is not None else 24 
        avail =max (60 ,w -tx -right_w )
        self .create_text (tx ,cy -9 ,text =self ._title ,anchor ="w",
        font =(FONT_FAMILY ,12 ,"bold"),fill =TEXT ,
        width =avail )
        self .create_text (tx ,cy +10 ,text =self ._desc ,anchor ="w",
        font =(FONT_FAMILY ,9 ),fill =lerp_col (MUTED ,TEXT ,.25 ),
        width =avail )

        if self ._toggle is not None :

            sw_w ,sw_h =38 ,20 
            sx1 =w -14 -sw_w 
            sy1 =cy -sw_h //2 
            sx2 ,sy2 =sx1 +sw_w ,sy1 +sw_h 
            track_off =lerp_col (bg ,MUTED ,.35 )
            track_on =col 
            track_col =lerp_col (track_off ,track_on ,self ._sw_t )
            draw_rrect (self ,sx1 ,sy1 ,sx2 ,sy2 ,sw_h //2 ,
            fill =track_col ,outline ="")
            r =sw_h //2 -2 
            kx =sx1 +sw_h //2 +self ._sw_t *(sw_w -sw_h )
            ky =cy 
            self .create_oval (kx -r ,ky -r ,kx +r ,ky +r ,fill ="#ffffff",outline ="")
        else :

            arrow_col =col if self ._hover else MUTED 
            self .create_text (w -12 ,cy ,text ="›",anchor ="e",
            font =(FONT_FAMILY ,18 ,"bold"),fill =arrow_col )

class SidebarBtn (tk .Canvas ):

    _DRAG_THRESHOLD =6 

    def __init__ (self ,master ,text ="",command =None ,
    font =None ,height =46 ,count =0 ,topic =None ,
    reorder_start =None ,reorder_motion =None ,reorder_end =None ,
    icon_picker =None ,icon =None ,icon_color =None ,icon_fn =None ,**kw ):

        self ._text =text 
        self ._icon =icon 
        self ._icon_fn =icon_fn 
        self ._icon_color =icon_color 
        self ._cmd =command 
        self ._font =font or (FONT_FAMILY ,12 )
        self ._count =count 
        self ._active =False 
        self ._t =0.0 
        self ._target =0.0 
        self ._job =None 
        self .topic =topic 
        self ._reorder_start =reorder_start 
        self ._reorder_motion =reorder_motion 
        self ._reorder_end =reorder_end 
        self ._icon_picker =icon_picker 
        self ._press_y =None 
        self ._dragging =False 
        self ._dragging_visual =False 
        try :pbg =master .cget ("bg")
        except :pbg =SIDEBAR 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,
        height =height ,cursor ="hand2",**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self .bind ("<Enter>",lambda e :(not self ._active )and self ._anim (1.0 ))
        self .bind ("<Leave>",lambda e :(not self ._active )and self ._anim (0.0 ))
        self .bind ("<ButtonPress-1>",self ._on_press )
        self .bind ("<B1-Motion>",self ._on_motion )
        self .bind ("<ButtonRelease-1>",self ._on_release )
        self .bind ("<Button-3>",lambda e :
        self ._icon_picker (self .topic )if self ._icon_picker else None )

    def set_active (self ,v :bool ):
        self ._active =v 
        self ._t =1.0 if v else self ._t 
        self ._draw ()

    def set_count (self ,n :int ):
        self ._count =n 
        self ._draw ()

    def set_dragging (self ,v :bool ):
        self ._dragging_visual =v 
        self ._draw ()

    def _on_press (self ,e ):
        self ._press_y =e .y_root 
        self ._dragging =False 
        if self ._reorder_start :
            self ._reorder_start (self )

    def _on_motion (self ,e ):
        if self ._press_y is None :
            return 
        if not self ._dragging and abs (e .y_root -self ._press_y )>self ._DRAG_THRESHOLD :
            self ._dragging =True 
            self .set_dragging (True )
            try :self .config (cursor ="fleur")
            except Exception :pass 
        if self ._dragging and self ._reorder_motion :
            self ._reorder_motion (self ,e )

    def _on_release (self ,e ):
        was_dragging =self ._dragging 
        self ._press_y =None 
        self ._dragging =False 
        self .set_dragging (False )
        try :self .config (cursor ="hand2")
        except Exception :pass 
        if was_dragging :
            if self ._reorder_end :
                self ._reorder_end (self ,e )
        elif self ._cmd :
            self ._cmd ()

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :return 
        self .delete ("all")
        t =self ._t 

        if self ._active :
            bg_col =ACCENT_DIM 
            bar_col =ACCENT 
            bar_h =h -18 
            text_col =TEXT 
            badge_col =ACCENT 
        else :
            bg_col =lerp_col (SIDEBAR ,lighten (BORDER ,.04 ),t )
            bar_col =lerp_col (SIDEBAR ,ACCENT2 ,t )
            bar_h =int (t *(h -18 ))
            text_col =lerp_col (MUTED ,TEXT ,t )
            badge_col =lerp_col (darken (MUTED ,.2 ),ACCENT2 ,t )

        if self ._active or t >.05 :
            draw_rrect (self ,8 ,3 ,w -8 ,h -3 ,16 ,
            fill =bg_col ,
            outline =lerp_col (SIDEBAR ,ACCENT_DIM ,max (t ,.3 ))if not self ._active else "",
            width =1 )

        if self ._active or t >.08 :
            draw_rrect (self ,0 ,(h -bar_h )//2 ,3 ,(h -bar_h )//2 +bar_h ,2 ,
            fill =bar_col ,outline ="",width =0 )

        if self ._dragging_visual :
            draw_rrect (self ,6 ,1 ,w -6 ,h -1 ,16 ,fill ="",outline =ACCENT ,width =2 )

        if self ._icon_fn or self ._icon :
            icon_col_x =24 
            label_x =icon_col_x +20 
            icon_color =self ._icon_color or text_col 
            if self ._icon_fn :
                self ._icon_fn (self ,icon_col_x ,h //2 ,19 ,icon_color )
            else :
                _ik ,_ir =_split_icon_text (self ._icon )
                if _ik and _ir =="":
                    draw_icon_glyph (self ,icon_col_x ,h //2 ,_ik ,19 ,icon_color ,bg =self .cget ("bg"))
                else :
                    self .create_text (icon_col_x ,h //2 ,text =self ._icon ,
                    font =(FONT_FAMILY ,15 ),
                    fill =icon_color ,anchor ="center")
        else :
            label_x =28 

        if self ._count >0 :
            badge_label =str (self ._count )
            bw =20 +8 *len (badge_label )
            bx =w -16 -bw 
            by =h //2 -10 
            badge_left =bx -8 
        else :
            badge_left =w -14 

        max_label_w =max (10 ,badge_left -label_x )
        fnt =_cached_font (self ._font )
        disp_text =self ._text 
        if fnt .measure (disp_text )>max_label_w :
            while disp_text and fnt .measure (disp_text +"…")>max_label_w :
                disp_text =disp_text [:-1 ]
            disp_text =disp_text +"…"if disp_text else "…"

        self .create_text (label_x ,h //2 ,text =disp_text ,
        font =self ._font ,fill =text_col ,anchor ="w")

        if self ._count >0 :
            draw_rrect (self ,bx ,by ,bx +bw ,by +20 ,10 ,
            fill =BADGE_BG ,
            outline =lerp_col (BORDER ,ACCENT_DIM ,max (t ,.25 )),
            width =1 )
            self .create_text (bx +bw //2 ,by +10 ,text =badge_label ,
            font =(FONT_FAMILY ,10 ,"bold"),
            fill =badge_col ,anchor ="center")

    def _anim (self ,target ):
        self ._target =target 
        if self ._job :
            return 
        self ._step_anim ()

    def _step_anim (self ):
        diff =self ._target -self ._t 
        if abs (diff )<0.012 :
            self ._t =self ._target 
            self ._draw ()
            self ._job =None 
            return 
        self ._t +=diff *0.30 
        self ._draw ()
        self ._job =self .after (8 ,self ._step_anim )

    def config (self ,**kw ):
        for d in ("bg","fg","font","activebackground","activeforeground"):
            kw .pop (d ,None )
        if kw :
            try :super ().config (**kw )
            except :pass 
    configure =config 
    def unbind (self ,*a ):pass 

class ShieldBar (tk .Canvas ):
    STEPS =2 ;DELAY =14 

    FRAME_MS =8 
    PULSE_SPEED =3.9 
    WAVE_PERIOD =1.35 
    WAVE_DURATION =1.6 
    WAVE_MAX_PAD =34 

    def __init__ (self ,master ,command =None ,**kw ):
        for k in ("relief","bd"):kw .pop (k ,None )
        self ._cmd =command 
        self ._active =False 
        self ._t =0.0 
        self ._t_target =0.0 
        self ._pt =0.0 
        self ._gt =0.0 
        self ._prev_gt =0.0 
        self ._sway_t =0.0 
        self ._pressed =False 
        self ._job_h =None 
        self ._job_p =None 
        self ._last_t =None 
        self ._wave_accum =0.0 
        self ._waves =[]
        self ._rain_accum =0.0 

        self ._drops =[]
        try :pbg =master .cget ("bg")
        except :pbg =BG 
        self ._pbg =pbg 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,cursor ="hand2",**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self .bind ("<Enter>",lambda e :self ._anim (1.0 ))
        self .bind ("<Leave>",lambda e :(setattr (self ,"_pressed",False ),self ._anim (0.0 )))
        self .bind ("<ButtonPress-1>",lambda e :(setattr (self ,"_pressed",True ),self ._draw ()))
        self .bind ("<ButtonRelease-1>",lambda e :(setattr (self ,"_pressed",False ),self ._draw (),
        self ._cmd ()if self ._cmd else None ))

    def set_active (self ,v :bool ):
        self ._active =v 
        if self ._job_p is None :
            self ._last_t =time .perf_counter ()
            self ._tick ()
        if v :
            self ._waves =[0.0 ]
        self ._draw ()

    def _tick (self ):
        now =time .perf_counter ()
        dt =now -self ._last_t if self ._last_t is not None else 1.0 /120 
        dt =min (dt ,0.05 )
        self ._last_t =now 

        self ._pt +=dt *self .PULSE_SPEED 

        self ._sway_t +=dt *1.2 

        target_gt =1.0 if self ._active else 0.0 
        if abs (self ._gt -target_gt )>0.001 :

            speed =1.1 if self ._gt <target_gt else 1.4 
            step =dt *speed 
            if self ._gt <target_gt :self ._gt =min (target_gt ,self ._gt +step )
            else :self ._gt =max (target_gt ,self ._gt -step )

        self ._prev_gt =self ._gt 

        if self ._active :
            self ._rain_accum +=dt 
            spawn_interval =0.045 
            while self ._rain_accum >=spawn_interval :
                self ._rain_accum -=spawn_interval 
                import random 
                _ ,h =self .winfo_width (),self .winfo_height ()
                r =min (h *0.44 ,20 )
                self ._drops .append ([
                32 +random .uniform (-r *0.85 ,r *0.85 ),
                (h /2 )-r *0.10 ,
                random .uniform (60 ,100 ),
                0.0 ,random .uniform (0.22 ,0.36 )
                ])
        else :
            self ._rain_accum =0.0 

        rain_gravity =160.0 
        self ._drops =[
        [dx ,dy +vy *dt ,vy +rain_gravity *dt ,age +dt ,max_life ]
        for dx ,dy ,vy ,age ,max_life in self ._drops 
        if age +dt <max_life 
        ]

        if self ._active :
            self ._wave_accum +=dt 
            while self ._wave_accum >=self .WAVE_PERIOD :
                self ._wave_accum -=self .WAVE_PERIOD 
                self ._waves .append (0.0 )

        self ._waves =[t +dt for t in self ._waves if t +dt <self .WAVE_DURATION ]

        self ._draw ()
        self ._job_p =self .after (self .FRAME_MS ,self ._tick )

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :return 
        self .delete ("all")

        pa =(math .sin (self ._pt )+1 )/2 

        if self ._active :
            body =lerp_col (darken (ACCENT ,.35 ),ACCENT ,pa *.3 )
            border =lerp_col (ACCENT ,ACCENT2 ,pa )
            txt ="  Shield active  ·  tap to disable"
            txt_c ="#0b0e14"
            icon ="🛡"
        else :
            body =lerp_col (darken (ENTRY ,.05 ),lighten (ENTRY ,.12 ),self ._t )
            border =lerp_col (BORDER ,ACCENT_DIM ,self ._t )
            txt ="  Activate shield"
            txt_c =lerp_col (MUTED ,TEXT ,self ._t )
            icon =""

        if self ._pressed :body =darken (body ,.15 )

        if self ._active :
            glow_amt =0.25 +pa *0.35 
            for i ,pad in enumerate ((7 ,4 ,2 )):
                ring_t =glow_amt *(1 -i *0.28 )
                if ring_t <=0.02 :
                    continue 
                draw_rrect (self ,-pad ,-pad ,w +pad ,h +pad ,24 +pad ,
                fill ="",outline =lerp_col (self ._pbg ,ACCENT ,ring_t ),
                width =1 )

            for t in self ._waves :
                prog =t /self .WAVE_DURATION 
                ease =1 -(1 -prog )**2 
                pad =ease *self .WAVE_MAX_PAD 
                fade =max (0.0 ,1 -prog )**1.4 
                if fade <=0.02 :
                    continue 
                draw_rrect (self ,-pad ,-pad ,w +pad ,h +pad ,24 +pad ,
                fill ="",outline =lerp_col (self ._pbg ,ACCENT2 ,fade *0.65 ),
                width =2 )

        draw_rrect (self ,0 ,0 ,w ,h ,24 ,fill =body ,outline =border ,width =1 )

        cy =h //2 
        dy =1 if self ._pressed else 0 

        r_full =min (h *0.44 ,20 )
        ix =32 

        bob =math .sin (self ._sway_t )*r_full *0.06 *self ._gt 

        if self ._gt >0.05 :
            hr =(r_full *1.25 +pa *r_full *0.30 )*self ._gt 
            if hr >1 :
                glow_c =lerp_col (body ,ACCENT2 if self ._active else "#4a5568",.7 -pa *.2 )
                self .create_oval (ix -hr ,cy -hr +dy ,ix +hr ,cy +hr +dy ,
                fill ="",outline =glow_c ,width =1 )

        self ._draw_cloud (ix ,cy +dy ,r_full ,self ._gt ,bob )

        for dx ,dpy ,vy ,age ,max_life in self ._drops :
            fade =1.0 -age /max_life 
            if fade <0.05 :
                continue 
            length =min (8 ,3 +vy *0.035 )
            col =lerp_col (self ._pbg ,"#8fd3ff"if self ._active else "#5b6478",
            0.5 +0.4 *fade )
            oy =dy 
            self .create_line (dx ,dpy +oy ,dx ,dpy +length +oy ,
            fill =col ,width =1.6 ,capstyle ="round")

        label_x =ix +r_full *1.05 +10 
        self .create_text (label_x ,cy +dy ,text =txt ,
        font =(FONT_FAMILY ,15 ,"bold"),
        fill =txt_c ,anchor ="w")

        if icon :
            draw_icon_glyph (self ,w -26 ,cy +dy ,icon ,18 ,txt_c ,bg =body )

    def _draw_cloud (self ,cx ,cy ,r ,gt ,bob ):

        cy +=bob 

        base_c =lerp_col ("#5b6478","#eef4ff",gt )
        shadow_c =lerp_col ("#464e60","#c9defc",gt )
        hi_c =lerp_col (base_c ,"#ffffff",0.55 *gt )

        puffs =[

        (-r *0.62 ,r *0.20 ,r *0.52 ,r *0.40 ,shadow_c ),
        (r *0.58 ,r *0.22 ,r *0.55 ,r *0.38 ,shadow_c ),
        (0.0 ,r *0.06 ,r *0.85 ,r *0.48 ,base_c ),
        (-r *0.26 ,-r *0.26 ,r *0.48 ,r *0.40 ,base_c ),
        (r *0.22 ,-r *0.36 ,r *0.40 ,r *0.34 ,hi_c ),
        ]
        for dx ,dyf ,rx ,ry ,col in puffs :
            self .create_oval (cx +dx -rx ,cy +dyf -ry ,
            cx +dx +rx ,cy +dyf +ry ,
            fill =col ,outline ="")

    def _anim (self ,target ):
        self ._t_target =target 
        if self ._job_h :
            return 
        self ._step_anim ()

    def _step_anim (self ):
        if not hasattr (self ,"_t_target"):
            self ._t_target =0.0 
        diff =self ._t_target -self ._t 
        if abs (diff )<0.012 :
            self ._t =self ._t_target 
            self ._draw ()
            self ._job_h =None 
            return 
        self ._t +=diff *0.30 
        self ._draw ()
        self ._job_h =self .after (8 ,self ._step_anim )

    def config (self ,**kw ):
        for d in ("relief","bd","activebackground","activeforeground"):
            kw .pop (d ,None )
        if kw :
            try :super ().config (**kw )
            except :pass 
    configure =config 
    def unbind (self ,*a ):pass 

class LifetimeBtn (tk .Canvas ):
    STEPS =2 ;DELAY =14 
    PULSE =8 
    PULSE_STEP =0.4 *(8 /95 )

    def __init__ (self ,master ,command =None ,**kw ):
        for k in ("relief","bd"):kw .pop (k ,None )
        self ._cmd =command 
        self ._on =False 
        self ._t =0.0 
        self ._t_target =0.0 
        self ._pt =0.0 
        self ._pressed =False 
        self ._job_h =None 
        self ._job_p =None 
        try :pbg =master .cget ("bg")
        except :pbg =BG 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,cursor ="hand2",**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self .bind ("<Enter>",lambda e :self ._anim (1.0 ))
        self .bind ("<Leave>",lambda e :(setattr (self ,"_pressed",False ),self ._anim (0.0 )))
        self .bind ("<ButtonPress-1>",lambda e :(setattr (self ,"_pressed",True ),self ._draw ()))
        self .bind ("<ButtonRelease-1>",lambda e :(setattr (self ,"_pressed",False ),self ._draw (),
        self ._cmd ()if self ._cmd else None ))

    def set_on (self ,v :bool ):
        self ._on =v 
        if v :self ._pulse_start ()
        else :self ._pulse_stop ()
        self ._draw ()

    def _pulse_start (self ):
        if self ._job_p :return 
        self ._tick ()

    def _pulse_stop (self ):
        if self ._job_p :
            try :self .after_cancel (self ._job_p )
            except :pass 
            self ._job_p =None 
        self ._pt =0.0 

    def _tick (self ):
        self ._pt +=self .PULSE_STEP 
        self ._draw ()
        self ._job_p =self .after (self .PULSE ,self ._tick )

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :return 
        self .delete ("all")
        r =10 
        pa =(math .sin (self ._pt )+1 )/2 
        t =self ._t 
        dy =self ._pressed *1.5 
        lift =t *1.5 
        y_off =dy -lift 

        if self ._on :

            bg_idle =darken (WARN ,0.1 )
            bg_hover =WARN 
            bg_col =lerp_col (bg_idle ,bg_hover ,pa *0.5 +t *0.5 )

            glow_col =lerp_col (self .master .cget ("bg")if hasattr (self .master ,"cget")else BG ,lighten (WARN ,0.2 ),(pa *0.3 +t *0.3 ))
            draw_rrect (self ,1 ,1 +y_off +1 ,w -1 ,h -1 +y_off +1 ,r +1 ,fill ="",outline =glow_col ,width =2 )

            draw_rrect (self ,2 ,2 +y_off ,w -2 ,h -2 +y_off ,r ,fill =bg_col ,outline ="",width =0 )

            hi_col =lighten (bg_col ,0.15 )
            self .create_line (2 +r ,3 +y_off ,w -2 -r ,3 +y_off ,fill =hi_col ,width =1 ,capstyle ="round")

            fg ="#0b0e14"
            txt ="♾  Disable lifetime mode"
        else :

            bg_idle =lighten (self .master .cget ("bg"),0.03 )if hasattr (self .master ,"cget")else BG 
            bg_hover =lighten (bg_idle ,0.05 )
            bg_col =lerp_col (bg_idle ,bg_hover ,t )
            brd_col =lerp_col (BORDER ,WARN ,t )

            if t >0.1 :
                sh_col =darken (bg_idle ,0.1 )
                draw_rrect (self ,3 ,3 +y_off +1 ,w -1 ,h -1 +y_off +1 ,r ,fill ="",outline =sh_col ,width =1 )

            draw_rrect (self ,2 ,2 +y_off ,w -2 ,h -2 +y_off ,r ,fill =bg_col ,outline =brd_col ,width =1 )
            fg =lerp_col (MUTED ,TEXT ,t )
            txt ="♾  Enable lifetime mode"

        self .create_text (w //2 ,h //2 +y_off ,text =txt ,
        font =(FONT_FAMILY ,12 ,"bold"),fill =fg ,anchor ="center")

    def _anim (self ,target ):
        self ._t_target =target 
        if self ._job_h :
            return 
        self ._step_anim ()

    def _step_anim (self ):
        if not hasattr (self ,"_t_target"):
            self ._t_target =0.0 
        diff =self ._t_target -self ._t 
        if abs (diff )<0.012 :
            self ._t =self ._t_target 
            self ._draw ()
            self ._job_h =None 
            return 
        self ._t +=diff *0.30 
        self ._draw ()
        self ._job_h =self .after (8 ,self ._step_anim )

    def config (self ,**kw ):
        for d in ("relief","bd","activebackground","activeforeground"):
            kw .pop (d ,None )
        if kw :
            try :super ().config (**kw )
            except :pass 
    configure =config 
    def unbind (self ,*a ):pass 

class BlockedTicker (tk .Canvas ):
    POLL =300 
    STEPS =8 
    DELAY =8 

    def __init__ (self ,master ,label ="blocked this session",**kw ):
        for k in ("relief","bd","highlightthickness","highlightbackground"):
            kw .pop (k ,None )
        self ._label =label 
        self ._shown =0 
        self ._display =0.0 
        self ._active =False 
        self ._poll_job =None 
        self ._anim_job =None 
        try :pbg =master .cget ("bg")
        except :pbg =BG 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,height =22 ,**kw )
        self .bind ("<Configure>",lambda e :self ._draw ())
        self ._draw ()

    def set_active (self ,active :bool ):
        self ._active =active 
        if active :
            if not self ._poll_job :
                self ._poll ()
        else :
            if self ._poll_job :
                try :self .after_cancel (self ._poll_job )
                except :pass 
                self ._poll_job =None 
            self ._shown =0 
            self ._display =0.0 
            self ._draw ()

    def _poll (self ):
        try :
            n =get_blocked_count ()
        except Exception :
            n =self ._shown 
        if n !=self ._shown :
            self ._shown =n 
            self ._animate_to (n )
        else :
            self ._draw ()
        self ._poll_job =self .after (self .POLL ,self ._poll )

    def _animate_to (self ,target ):
        if self ._anim_job :
            try :self .after_cancel (self ._anim_job )
            except :pass 
            self ._anim_job =None 
        self ._step_toward (target )

    def _step_toward (self ,target ):
        diff =target -self ._display 
        if abs (diff )<0.6 :
            self ._display =float (target )
            self ._draw ()
            self ._anim_job =None 
            return 
        self ._display +=diff *0.35 
        self ._draw ()
        self ._anim_job =self .after (self .DELAY ,lambda :self ._step_toward (target ))

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :
            return 
        self .delete ("all")
        n =int (round (self ._display ))
        dot_col =ACCENT if (self ._active and n >0 )else MUTED 
        self .create_oval (2 ,h //2 -3 ,8 ,h //2 +3 ,fill =dot_col ,outline ="")
        txt =f"{n :,}  {self ._label }"
        self .create_text (16 ,h //2 ,text =txt ,anchor ="w",
        font =(FONT_FAMILY ,12 ,"bold"),fill =TEXT if self ._active else MUTED )

class ShieldAura (tk .Canvas ):
    N_PARTICLES =14 
    FRAME_MS =8 
    TWINKLE_SPEED =1.1 

    def __init__ (self ,master ,**kw ):
        for k in ("relief","bd","highlightthickness","highlightbackground"):
            kw .pop (k ,None )
        try :pbg =master .cget ("bg")
        except :pbg =BG 
        super ().__init__ (master ,bg =pbg ,highlightthickness =0 ,**kw )
        self ._pbg =pbg 
        self ._active =False 
        self ._job =None 
        self ._last_t =None 
        self ._particles =[]
        self .bind ("<Configure>",lambda e :self ._reseed ())

    def _reseed (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :
            return 
        if not self ._particles :
            import random 
            for _ in range (self .N_PARTICLES ):
                self ._particles .append ([
                random .uniform (0 ,w ),random .uniform (0 ,h ),
                random .uniform (1.4 ,3.2 ),random .uniform (3.3 ,11.1 ),
                random .uniform (0 ,math .tau if hasattr (math ,"tau")else 6.283 ),
                ])
        self ._draw ()

    def set_active (self ,active :bool ):
        self ._active =active 
        if active :
            self ._reseed ()
            if not self ._job :
                self ._last_t =time .perf_counter ()
                self ._tick ()
        else :
            if self ._job :
                try :self .after_cancel (self ._job )
                except :pass 
                self ._job =None 
            self .delete ("all")

    def _tick (self ):
        now =time .perf_counter ()
        dt =now -self ._last_t if self ._last_t is not None else 1.0 /120 
        dt =min (dt ,0.05 )
        self ._last_t =now 

        w ,h =self .winfo_width (),self .winfo_height ()
        if w >4 and h >4 :
            for p in self ._particles :
                p [0 ]-=p [3 ]*dt 
                p [4 ]+=self .TWINKLE_SPEED *dt 
                if p [0 ]<-4 :
                    p [0 ]=w +4 
            self ._draw ()
        self ._job =self .after (self .FRAME_MS ,self ._tick )

    def _draw (self ):
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 or h <4 :
            return 
        self .delete ("all")
        if not self ._active :
            return 
        for x ,y ,r ,_spd ,phase in self ._particles :
            twinkle =(math .sin (phase )+1 )/2 
            col =lerp_col (self ._pbg ,ACCENT ,0.15 +twinkle *0.35 )
            rr =r *(0.7 +twinkle *0.6 )
            self .create_oval (x -rr ,y -rr ,x +rr ,y +rr ,fill =col ,outline ="")

    def config (self ,**kw ):
        for d in ("relief","bd","activebackground","activeforeground"):
            kw .pop (d ,None )
        if kw :
            try :super ().config (**kw )
            except :pass 
    configure =config 

class CloseX (tk .Canvas ):
    def __init__ (self ,master ,command =None ,size =24 ,bg =None ,
    fg =None ,hover_fg =None ,font =None ,**kw ):

        self ._cmd =command 
        if bg is not None :
            pbg =bg 
        else :
            try :pbg =master .cget ("bg")
            except :pbg =BG 
        super ().__init__ (master ,bg =pbg ,width =size ,height =size ,
        highlightthickness =0 ,cursor ="hand2",**kw )
        self ._t =0.0 
        self .bind ("<Enter>",lambda e :self ._anim (1.0 ))
        self .bind ("<Leave>",lambda e :self ._anim (0.0 ))
        self .bind ("<Button-1>",lambda e :self ._cmd ()if self ._cmd else None )
        self ._draw ()

    def _anim (self ,target ):
        self ._t =target 
        self ._draw ()

    def _draw (self ):
        self .delete ("all")
        w ,h =self .winfo_width (),self .winfo_height ()
        if w <4 :w ,h =24 ,24 
        t =self ._t 
        lift =t *1.5 

        bg_col =lerp_col ("#fff1f2","#ffe4e6",t )

        if t >0.1 :
            self .create_oval (1 ,1 -lift +1 ,w -1 ,h -1 -lift +1 ,fill ="",outline ="#fecaca",width =2 )

        self .create_oval (2 ,2 -lift ,w -2 ,h -2 -lift ,fill =bg_col ,outline ="#fecaca",width =1 )

        x_col ="#dc2626"
        pad =w //3.5 
        self .create_line (pad ,pad -lift ,w -pad ,h -pad -lift ,fill =x_col ,width =2 ,capstyle ="round")
        self .create_line (w -pad ,pad -lift ,pad ,h -pad -lift ,fill =x_col ,width =2 ,capstyle ="round")

class Toast (tk .Toplevel ):

    _stack :list =[]
    _BOTTOM_MARGIN =60 
    _GAP =10 
    _SLIDE_IN_PX =46 

    _KIND_STYLE ={
    "success":(ACCENT ,_icon_check ),
    "error":(DANGER ,_icon_x ),
    "warn":(WARN ,_icon_warn ),
    "info":(ACCENT2 ,_icon_info ),
    }

    def __init__ (self ,master ,title :str ,msg :str ,ok :bool =True ,
    count_to :int =None ,kind :str =None ,duration_ms :int =3800 ):
        super ().__init__ (master )
        self .overrideredirect (True )
        self .attributes ("-topmost",True )
        self .attributes ("-alpha",0.0 )
        self .configure (bg =darken (CARD ,.05 ))
        kind =kind or ("success"if ok else "error")
        accent ,icon_fn =self ._KIND_STYLE .get (kind ,self ._KIND_STYLE ["success"])
        tk .Frame (self ,bg =accent ,width =4 ).pack (side ="left",fill ="y")
        body =tk .Frame (self ,bg =darken (CARD ,.05 ),padx =14 ,pady =11 )
        body .pack (side ="left",fill ="both",expand =True )
        row =tk .Frame (body ,bg =darken (CARD ,.05 ))
        row .pack (fill ="x")
        icon_cv =tk .Canvas (row ,width =15 ,height =15 ,bg =darken (CARD ,.05 ),
        highlightthickness =0 )
        icon_cv .pack (side ="left",padx =(0 ,6 ))
        icon_fn (icon_cv ,7.5 ,7.5 ,14 ,accent ,bg =darken (CARD ,.05 ))
        tk .Label (row ,text =title ,font =(FONT_FAMILY ,12 ,"bold"),
        fg =TEXT ,bg =darken (CARD ,.05 )).pack (side ="left")
        self ._msg_template =msg 
        self ._count_to =count_to 

        init_text =msg .format (count =f"{count_to :,}")if count_to is not None else msg 
        self .msg_lbl =tk .Label (body ,text =init_text ,font =(FONT_FAMILY ,10 ),fg =MUTED ,
        bg =darken (CARD ,.05 ),wraplength =270 ,
        justify ="left")
        self .msg_lbl .pack (anchor ="w",pady =(3 ,0 ))
        self .update_idletasks ()
        sw =self .winfo_screenwidth ()

        self ._toast_w =330 
        self ._h =self .winfo_reqheight ()
        self ._x =sw -self ._toast_w -20 
        self ._y =self ._BOTTOM_MARGIN 
        self ._closing =False 

        Toast ._stack .append (self )
        self ._reflow_stack ()

        if count_to is not None :
            self .msg_lbl .config (text =msg .format (count =0 ))
            self .after (120 ,lambda :self ._count_up (count_to ,time .perf_counter ()))
        self .after (duration_ms ,self ._start_fade_out )

    @classmethod 
    def _reflow_stack (cls ):
        if not cls ._stack :
            return 
        sh =cls ._stack [0 ].winfo_screenheight ()
        y =sh -cls ._BOTTOM_MARGIN 
        for t in reversed (cls ._stack ):
            y -=t ._h 
            is_newest =(t is cls ._stack [-1 ])
            t ._y =y 
            try :
                if is_newest and not t ._closing :

                    t .geometry (f"{t ._toast_w }x{t ._h }+{t ._x +cls ._SLIDE_IN_PX }+{y }")
                    t ._slide_x (t ._x +cls ._SLIDE_IN_PX ,t ._x )
                    t ._fade (0.0 ,1.0 )
                else :
                    t ._slide_y_to (y )
            except Exception :
                pass 
            y -=cls ._GAP 

    def _slide_x (self ,cur_x :float ,target_x :float ):
        step =(target_x -cur_x )*0.35 
        nxt =cur_x +step 
        if abs (target_x -nxt )<0.75 :
            nxt =target_x 
        try :
            self .geometry (f"{self ._toast_w }x{self ._h }+{int (nxt )}+{self ._y }")
        except Exception :
            return 
        if nxt !=target_x :
            self .after (8 ,lambda :self ._slide_x (nxt ,target_x ))

    def _slide_y_to (self ,target_y :float ):
        try :
            cur_geo =self .geometry ()
            cur_x ,cur_y =int (cur_geo .split ("+")[1 ]),int (cur_geo .split ("+")[2 ])
        except Exception :
            return 
        step =(target_y -cur_y )*0.30 
        nxt =cur_y +step 
        if abs (target_y -nxt )<0.75 :
            nxt =target_y 
        try :
            self .geometry (f"{self ._toast_w }x{self ._h }+{cur_x }+{int (nxt )}")
        except Exception :
            return 
        if nxt !=target_y :
            try :
                if self .winfo_exists ():
                    self .after (8 ,lambda :self ._slide_y_to (target_y ))
            except Exception :
                pass 

    def _count_up (self ,target :int ,t0 :float ,duration :float =0.6 ):
        elapsed =time .perf_counter ()-t0 
        prog =min (1.0 ,elapsed /duration )
        ease =1 -(1 -prog )**3 
        cur =int (round (target *ease ))
        try :
            self .msg_lbl .config (text =self ._msg_template .format (count =f"{cur :,}"))
        except Exception :
            return 
        if prog <1.0 :
            try :
                if self .winfo_exists ():
                    self .after (8 ,lambda :self ._count_up (target ,t0 ,duration ))
            except Exception :
                pass 

    def _start_fade_out (self ):
        if self ._closing :
            return 
        self ._closing =True 
        self ._fade (1.0 ,0.0 )

    def _fade (self ,cur :float ,target :float ):
        step =.5 if target >cur else -.4 
        nxt =cur +step 
        if (step >0 and nxt >=target )or (step <0 and nxt <=target ):
            try :
                self .attributes ("-alpha",target )
            except Exception :
                pass 
            if target ==0 :
                self ._on_closed ()
            return 
        try :
            self .attributes ("-alpha",nxt )
        except Exception :
            return 
        try :
            if self .winfo_exists ():
                self .after (8 ,lambda :self ._fade (nxt ,target ))
        except Exception :
            pass 

    def _on_closed (self ):
        if self in Toast ._stack :
            Toast ._stack .remove (self )
        try :
            self .destroy ()
        except Exception :
            pass 
        self ._reflow_stack ()

class _SpotlightRing :

    THICK =3 
    PAD =6 

    def __init__ (self ,widget ):
        self .widget =widget 
        toplevel =widget .winfo_toplevel ()
        self .bars =[tk .Toplevel (toplevel )for _ in range (4 )]
        for b in self .bars :
            b .overrideredirect (True )
            try :
                b .attributes ("-topmost",True )
            except Exception :
                pass 
            b .configure (bg =ACCENT )
        self ._alpha =0.9 
        self ._dir =-1 
        self ._job =None 
        self .reposition ()
        self ._pulse ()

    def reposition (self ):
        try :
            x =self .widget .winfo_rootx ()-self .PAD 
            y =self .widget .winfo_rooty ()-self .PAD 
            w =max (1 ,self .widget .winfo_width ()+self .PAD *2 )
            h =max (1 ,self .widget .winfo_height ()+self .PAD *2 )
        except Exception :
            return 
        top ,bottom ,left ,right =self .bars 
        try :
            top .geometry (f"{w }x{self .THICK }+{x }+{y }")
            bottom .geometry (f"{w }x{self .THICK }+{x }+{y +h -self .THICK }")
            left .geometry (f"{self .THICK }x{h }+{x }+{y }")
            right .geometry (f"{self .THICK }x{h }+{x +w -self .THICK }+{y }")
        except Exception :
            pass 

    def _pulse (self ):
        if not self .bars or not self .bars [0 ].winfo_exists ():
            return 
        self ._alpha +=0.03 *self ._dir 
        if self ._alpha <=0.45 :
            self ._alpha ,self ._dir =0.45 ,1 
        elif self ._alpha >=0.95 :
            self ._alpha ,self ._dir =0.95 ,-1 
        for b in self .bars :
            try :
                b .attributes ("-alpha",self ._alpha )
            except Exception :
                pass 
        try :
            self ._job =self .bars [0 ].after (40 ,self ._pulse )
        except Exception :
            pass 

    def destroy (self ):
        for b in self .bars :
            try :
                if b .winfo_exists ():
                    b .destroy ()
            except Exception :
                pass 
        self .bars =[]

class OnboardingBubble (tk .Toplevel ):

    WIDTH =300 

    def __init__ (self ,app ,target ,title ,desc ,step ,total ,
    on_next ,on_back ,on_skip ):
        super ().__init__ (app )
        self .overrideredirect (True )
        try :
            self .attributes ("-topmost",True )
            self .attributes ("-alpha",0.0 )
        except Exception :
            pass 
        self .configure (bg =darken (CARD ,.05 ))

        tk .Frame (self ,bg =ACCENT ,height =3 ).pack (fill ="x")
        body =tk .Frame (self ,bg =darken (CARD ,.05 ),padx =16 ,pady =13 )
        body .pack (fill ="both",expand =True )

        top_row =tk .Frame (body ,bg =darken (CARD ,.05 ))
        top_row .pack (fill ="x")
        tk .Label (top_row ,text =f"STEP {step } OF {total }",
        font =(FONT_FAMILY ,9 ,"bold"),fg =ACCENT2 ,
        bg =darken (CARD ,.05 )).pack (side ="left")
        CloseX (top_row ,bg =darken (CARD ,.05 ),command =on_skip ).pack (side ="right")

        tk .Label (body ,text =title ,font =(FONT_FAMILY ,13 ,"bold"),
        fg =TEXT ,bg =darken (CARD ,.05 ),anchor ="w",
        wraplength =self .WIDTH -32 ,justify ="left"
        ).pack (anchor ="w",pady =(6 ,3 ))
        tk .Label (body ,text =desc ,font =(FONT_FAMILY ,10 ),fg =MUTED ,
        bg =darken (CARD ,.05 ),anchor ="w",
        wraplength =self .WIDTH -32 ,justify ="left"
        ).pack (anchor ="w")

        btn_row =tk .Frame (body ,bg =darken (CARD ,.05 ))
        btn_row .pack (fill ="x",pady =(12 ,0 ))
        if on_back :
            FlatBtn (btn_row ,text ="Back",base_bg =darken (CARD ,.05 ),
            hover_bg =lighten (CARD ,.06 ),fg =MUTED ,ghost =True ,
            border_col =BORDER ,radius =13 ,font =(FONT_FAMILY ,10 ,"bold"),
            command =on_back ,height =28 ,width =64 
            ).pack (side ="left")
        FlatBtn (btn_row ,text ="Skip tour",base_bg =darken (CARD ,.05 ),
        hover_bg =lighten (CARD ,.06 ),fg =MUTED ,ghost =True ,
        border_col =BORDER ,radius =13 ,font =(FONT_FAMILY ,10 ,"bold"),
        command =on_skip ,height =28 ,width =84 
        ).pack (side ="left",padx =(6 ,0 ))
        FlatBtn (btn_row ,text =("Finish"if step ==total else "Next  →"),
        base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
        radius =13 ,font =(FONT_FAMILY ,10 ,"bold"),
        command =on_next ,height =28 ,width =84 
        ).pack (side ="right")

        self .update_idletasks ()
        self ._place_near (target )
        self ._fade (0.0 ,1.0 )

    def _place_near (self ,target ):
        h =self .winfo_reqheight ()
        w =self .WIDTH 
        sw ,sh =self .winfo_screenwidth (),self .winfo_screenheight ()
        try :
            tx ,ty =target .winfo_rootx (),target .winfo_rooty ()
            _ ,th =target .winfo_width (),target .winfo_height ()
        except Exception :
            tx ,ty ,_ ,th =sw //2 ,sh //2 ,0 ,0 

        x =min (max (tx ,10 ),max (10 ,sw -w -10 ))
        y =ty +th +14 
        if y +h >sh -10 :
            y =ty -h -14 
        if y <10 :
            y =10 
        try :
            self .geometry (f"{w }x{h }+{x }+{y }")
        except Exception :
            pass 

    def _fade (self ,cur ,target ):
        step =.5 if target >cur else -.4 
        nxt =cur +step 
        if (step >0 and nxt >=target )or (step <0 and nxt <=target ):
            try :
                self .attributes ("-alpha",target )
            except Exception :
                pass 
            return 
        try :
            self .attributes ("-alpha",nxt )
        except Exception :
            return 
        try :
            if self .winfo_exists ():
                self .after (8 ,lambda :self ._fade (nxt ,target ))
        except Exception :
            pass 

class OnboardingTour :

    def __init__ (self ,app ,steps :list [tuple ]):
        self .app =app 
        self .steps =steps 
        self .i =0 
        self .ring =None 
        self .bubble =None 

    def start (self ):
        if not self .steps :
            _mark_onboarding_done ()
            return 
        self .i =0 
        self ._show_step ()

    def _current_widget (self ):
        while self .i <len (self .steps ):
            getter ,_title ,_desc =self .steps [self .i ]
            try :
                w =getter ()
                if w is not None and w .winfo_exists ()and w .winfo_ismapped ():
                    return w 
            except Exception :
                pass 
            self .i +=1 
        return None 

    def _show_step (self ):
        self ._cleanup ()
        w =self ._current_widget ()
        if w is None :
            self .finish ()
            return 
        _getter ,title ,desc =self .steps [self .i ]
        try :
            self .ring =_SpotlightRing (w )
            self .bubble =OnboardingBubble (
            self .app ,w ,title ,desc ,
            step =self .i +1 ,total =len (self .steps ),
            on_next =self ._next ,
            on_back =self ._back if self .i >0 else None ,
            on_skip =self .finish ,
            )
        except Exception :
            self .finish ()

    def _next (self ):
        self .i +=1 
        self ._show_step ()

    def _back (self ):
        self .i -=1 
        self ._show_step ()

    def _cleanup (self ):
        if self .ring :
            self .ring .destroy ()
            self .ring =None 
        if self .bubble :
            try :
                self .bubble .destroy ()
            except Exception :
                pass 
            self .bubble =None 

    def finish (self ):
        self ._cleanup ()
        _mark_onboarding_done ()

class Revolt (tk .Tk ):

    ICONS ={
    "Ad Blocking":"🛡",
    "Evil Companies":"🏢",
    "Social":"💬",
    "Adult & OnlyFans":"🔒",
    "Gore & Shock":"⚠",
    "Conspiracy & Fringe":"🕵",
    "Crypto & Gambling":"🎲",
    "AI & Chatbots":"🤖",
    "Tor & Dark Web":"🧅",
    }

    def _sync_dpi_scaling (self ):
        # Tk defaults to 96 DPI, but with Windows DPI virtualization off now
        # (see _enable_windows_dpi_awareness) we need to tell it the real value
        # or fonts render too small/blurry
        try :
            self .update_idletasks ()
            real_dpi =self .winfo_fpixels ("1i")
            if real_dpi >1 :
                self .tk .call ("tk","scaling",real_dpi /72.0 )
        except Exception :
            pass 

    def __init__ (self ):
        super ().__init__ ()
        self ._sync_dpi_scaling ()
        self .title ("Revolt — Internet Shield")
        self .minsize (860 ,540 )
        self .configure (bg =BG )
        self ._set_app_icon ()

        self ._pick_font ()
        self ._setup_scrollbar_styles ()

        w ,h =1160 ,760 
        self .update_idletasks ()
        sw ,sh =self .winfo_screenwidth (),self .winfo_screenheight ()
        x ,y =max (0 ,(sw -w )//2 ),max (0 ,(sh -h )//2 -20 )
        self .geometry (f"{w }x{h }+{x }+{y }")

        self .topics ,self ._lifetime ,self .theme_data =load_config ()
        self .custom_feeds :list [dict ]=load_custom_feeds ()
        self .custom_dns :str |None =load_custom_dns ()
        set_custom_dns_ip (self .custom_dns )
        if self .custom_dns :
            apply_direct_custom_dns_async ()
        self .allowlist :set [str ]=load_allowlist ()
        self .lock_data :dict =load_lock ()
        self ._pending_disable_id =None 
        self ._pending_disable_deadline =None 
        self .selected =next (iter (self .topics ),None )
        self ._apply_theme_data ()
        self .shield_on =detect_shield ()
        self ._dom_list :list [str ]=[]

        for t in self .ICONS :
            self .topics .setdefault (t ,set ())
        for feed in self .custom_feeds :
            self .topics .setdefault (feed ["category"],set ())

        self .custom_icons :dict [str ,str ]=dict (self .theme_data .get ("icons",{}))
        all_topics =[t for t in self .topics if not t .startswith ("_")]
        saved_order =self .theme_data .get ("order")
        if saved_order :
            order =[t for t in saved_order if t in all_topics ]
            order +=[t for t in all_topics if t not in order ]
        else :
            order =list (self .ICONS .keys ())
            order +=sorted (t for t in all_topics if t not in order )
        self .topic_order :list [str ]=order 

        self ._sb_btns :dict [str ,SidebarBtn ]={}
        self ._tray_icon =None 
        self ._build ()
        self ._refresh_shield_ui ()
        if self .shield_on :
            self .shield_btn ._gt =1.0 
            self .shield_btn .set_active (True )
            self ._start_vpn_guard ()

        self .after (400 ,lambda :prompt_desktop_shortcut_once (parent =self ))

        self ._tour =None 
        self .after (1100 ,self ._maybe_start_onboarding )

        self .protocol ("WM_DELETE_WINDOW",self ._on_window_close )

        self .bind ("<Unmap>",self ._on_unmap )

        if self ._lifetime and not self .shield_on and is_admin ():
            self .after (400 ,self ._silent_apply )
        elif self ._lifetime :
            self .after (600 ,self ._sync_lifetime_hosts )

    def _onboarding_steps (self ):
        return [
        (lambda :getattr (self ,"_topic_frame",None ),
        "Pick what to block",
        "These are your categories — ads, adult content, social "
        "media, and more. Click one to see and edit its domain list, "
        "or add your own."),
        (lambda :getattr (self ,"shield_btn",None ),
        "Flip the Shield on",
        "This is the master switch. While it's on, every lookup "
        "gets checked against whatever categories you've enabled."),
        (lambda :getattr (self ,"blocked_ticker",None ),
        "Watch it work",
        "This counts every blocked lookup live. Click it any time "
        "to open a feed of exactly which domains are being blocked, "
        "as it happens."),
        (lambda :getattr (self ,"vpn_btn",None ),
        "Bring your own VPN",
        "Connect a WireGuard or OpenVPN tunnel using your own "
        "provider's config file. Revolt drives it, but never bundles "
        "or picks a server for you."),
        (lambda :getattr (self ,"hotspot_btn",None ),
        "Share the Shield",
        "Turn this PC into a filtered Wi-Fi hotspot — any phone or "
        "device that joins gets the same DNS filtering automatically."),
        (lambda :getattr (self ,"lifetime_btn",None ),
        "Lifetime mode",
        "For when willpower alone isn't enough — locks the Shield "
        "on so it can't be casually switched off."),
        ]

    def _maybe_start_onboarding (self ):
        if os .path .exists (_ONBOARDING_MARKER ):
            return 
        try :
            self ._tour =OnboardingTour (self ,self ._onboarding_steps ())
            self ._tour .start ()
        except Exception :
            _mark_onboarding_done ()

    def _set_app_icon (self ):
        try :
            if os .name =="nt"and os .path .exists (ICON_PATH ):
                self .iconbitmap (ICON_PATH )
        except Exception :
            pass 
        try :
            if os .path .exists (ICON_PNG_PATH ):
                self ._app_icon_img =tk .PhotoImage (file =ICON_PNG_PATH )
                self .iconphoto (True ,self ._app_icon_img )
        except Exception :
            pass 

    def _make_tray_image (self ,active :bool =True ):
        size =64 
        base_col =ACCENT if active else "#6b7280"
        img =Image .new ("RGBA",(size ,size ),(0 ,0 ,0 ,0 ))
        d =ImageDraw .Draw (img )

        pasted_logo =False 
        if os .path .exists (ICON_PATH ):
            try :
                logo =Image .open (ICON_PATH ).convert ("RGBA").resize ((size ,size ))
                if not active :

                    alpha =logo .getchannel ("A")
                    grey =logo .convert ("L").convert ("RGBA")
                    grey .putalpha (alpha )
                    logo =grey 
                img .paste (logo ,(0 ,0 ),logo )
                pasted_logo =True 
            except Exception :
                pasted_logo =False 

        if not pasted_logo :
            d .rounded_rectangle ([4 ,4 ,size -4 ,size -4 ],radius =16 ,fill =base_col )
            d .text ((size /2 ,size /2 ),"R",fill ="white",anchor ="mm")

        dot_col ="#22c55e"if active else "#ef4444"
        dr =size *0.34 
        cx ,cy =size -dr /2 -2 ,size -dr /2 -2 
        d .ellipse ([cx -dr /2 ,cy -dr /2 ,cx +dr /2 ,cy +dr /2 ],
        fill =dot_col ,outline ="#00000055",width =2 )
        return img 

    def _minimize_to_tray (self ):
        if not _TRAY_AVAILABLE :
            self .iconify ()
            return 

        self .withdraw ()

        if self ._tray_icon is not None :
            return 

        def _restore (icon =None ,item =None ):
            if icon is not None :
                icon .stop ()
            self ._tray_icon =None 
            self .after (0 ,lambda :(self .deiconify (),self .lift (),self .focus_force ()))

        def _quit (icon ,item ):
            icon .stop ()
            self ._tray_icon =None 
            self .after (0 ,self ._quit_app )

        def _status_text (item ):
            return "Shield: ON  (click to disable)"if self .shield_on else "Shield: OFF  (click to enable)"

        def _status_checked (item ):
            return self .shield_on 

        def _toggle_from_tray (icon ,item ):

            self .after (0 ,self ._toggle_shield_from_tray )

        menu =pystray .Menu (
        pystray .MenuItem (_status_text ,_toggle_from_tray ,checked =_status_checked ),
        pystray .Menu .SEPARATOR ,
        pystray .MenuItem ("Open Revolt",_restore ,default =True ),
        pystray .MenuItem ("Quit",_quit ),
        )
        icon =pystray .Icon ("Revolt",self ._make_tray_image (self .shield_on ),
        self ._tray_title (),menu )
        self ._tray_icon =icon 
        threading .Thread (target =icon .run ,daemon =True ).start ()

    def _tray_title (self )->str :
        return f"Revolt — Shield {'ON'if self .shield_on else 'OFF'}"

    def _toggle_shield_from_tray (self ):
        self ._toggle_shield ()
        self ._update_tray_visual ()

    def _update_tray_visual (self ):
        if self ._tray_icon is None :
            return 
        try :
            self ._tray_icon .icon =self ._make_tray_image (self .shield_on )
            self ._tray_icon .title =self ._tray_title ()
        except Exception :
            pass 

    def _native_notify (self ,title :str ,message :str ):
        # try winotify first
        if _WINOTIFY_AVAILABLE :
            try :
                _notif =_WiNotification (
                    app_id ="Revolt",
                    title =title ,
                    msg =message ,
                    duration ="short",
                )
                try :
                    _notif .set_audio (_wn_audio .Default ,loop =False )
                except Exception :
                    pass 
                _notif .show ()
                return 
            except Exception :
                pass 

        # fall back to plyer
        if _PLYER_AVAILABLE :
            try :
                _plyer_notification .notify (
                    title =title ,
                    message =message ,
                    app_name ="Revolt",
                    timeout =6 ,
                )
                return 
            except Exception :
                pass 

        # last resort - pystray tray bubble, only works if the tray icon is up
        if _TRAY_AVAILABLE and self ._tray_icon is not None :
            try :
                self ._tray_icon .notify (message ,title )
            except Exception :
                pass 

    def _fire (self ,title :str ,message :str ,ok :bool =True ,
    count_to :int =None ,native :str =None ,duration_ms :int =3800 ):
        # system notification always fires
        notify_msg =native if native is not None else message 
        threading .Thread (
            target =self ._native_notify ,
            args =(title ,notify_msg ),
            daemon =True ,
        ).start ()

        # plus an in-app toast if the window is actually visible
        try :
            if self .winfo_exists () and self .state () not in ("iconic","withdrawn"):
                Toast (self ,title ,message ,ok =ok ,count_to =count_to ,
                duration_ms =duration_ms )
        except Exception :
            pass 

    def _on_window_close (self ):
        self ._quit_app ()

    def _on_unmap (self ,event ):

        if event .widget is self and self .state ()=="iconic":
            self .after (10 ,self ._minimize_to_tray )

    def _quit_app (self ):
        try :
            if self .shield_on :
                remove_blocking ()
                self .shield_on =False 
                self ._stop_vpn_guard ()
        except Exception :
            pass 
        if self ._tray_icon is not None :
            try :self ._tray_icon .stop ()
            except Exception :pass 
            self ._tray_icon =None 
        self .destroy ()

    def _on_resize (self ,event ):
        if event .widget ==self :
            self ._update_bg_label ()

    def _apply_theme_data (self ):
        global BG ,SIDEBAR ,CARD ,TOOLBAR ,ACCENT ,ACCENT2 ,ACCENT_DIM ,ENTRY ,BORDER ,ROW_ALT ,BADGE_BG ,SEL_BG ,SCROLL_BG1 ,SCROLL_BG2 
        ACCENT =self .theme_data .get ("accent","#5b7fff")
        ACCENT2 =lerp_col (ACCENT ,"#ffffff",0.25 )
        ACCENT_DIM =darken (ACCENT ,0.6 )

        BG =darken (ACCENT ,0.90 )
        SIDEBAR =darken (ACCENT ,0.905 )
        CARD =darken (ACCENT ,0.85 )
        TOOLBAR =darken (ACCENT ,0.815 )
        ENTRY =TOOLBAR 
        BORDER =darken (ACCENT ,0.72 )
        ROW_ALT =darken (ACCENT ,0.875 )
        BADGE_BG =darken (ACCENT ,0.78 )
        SEL_BG =darken (ACCENT ,0.6 )
        SCROLL_BG1 =ACCENT 
        SCROLL_BG2 =lighten (darken (ACCENT ,0.3 ),.15 )

        self .configure (bg =BG )
        self ._apply_titlebar_color ()

        bg_path =self .theme_data .get ("bg_img")
        if bg_path and os .path .exists (bg_path ):
            self ._set_background_image (bg_path )
        else :
            self ._bg_img_raw =None 

    def _apply_titlebar_color (self ):
        try :
            self .after_idle (lambda :apply_titlebar_theme (
            self ,self .theme_data .get ("titlebar_color")))
        except Exception :
            pass 

    def _set_background_image (self ,path ):
        try :
            self ._bg_img_raw =tk .PhotoImage (file =path )
            self ._update_bg_label ()
        except Exception as e :
            self ._bg_img_raw =None 
            messagebox .showerror (
            "Background Image",
            "Couldn't load that picture.\n\n"
            "Without the PIL library, only PNG and GIF images are "
            f"supported. Please pick a .png or .gif file.\n\n({e })")

    def _update_bg_label (self ):
        if not getattr (self ,"_bg_img_raw",None ):
            return 
        try :
            w ,h =self .winfo_width (),self .winfo_height ()
            if w <10 or h <10 :
                w ,h =1160 ,760 
            src =self ._bg_img_raw 
            sw ,sh =src .width (),src .height ()
            if sw <=0 or sh <=0 :
                return 
            img =src 

            zx ,zy =max (1 ,round (w /sw )),max (1 ,round (h /sh ))
            if zx >1 or zy >1 :
                img =img .zoom (zx ,zy )
                sw ,sh =img .width (),img .height ()
            sx ,sy =max (1 ,round (sw /w )),max (1 ,round (sh /h ))
            if sx >1 or sy >1 :
                img =img .subsample (sx ,sy )
            self ._bg_photo =img 
            if not hasattr (self ,"_bg_label")or not self ._bg_label .winfo_exists ():
                self ._bg_label =tk .Label (self ,image =self ._bg_photo ,bd =0 )
                self ._bg_label .place (x =0 ,y =0 ,relwidth =1 ,relheight =1 )
                self ._bg_label .lower ()
            else :
                self ._bg_label .config (image =self ._bg_photo )
        except Exception :
            pass 

    def _settings_group (self ,parent ,title ):
        section =tk .Frame (parent ,bg =BG )
        section .pack (fill ="x")
        tk .Label (section ,text =title .upper (),font =(FONT_FAMILY ,9 ,"bold"),
        fg =ACCENT ,bg =BG ,anchor ="w"
        ).pack (fill ="x",padx =4 ,pady =(2 ,6 ))
        card =tk .Frame (section ,bg =CARD ,highlightthickness =1 ,
        highlightbackground =lerp_col (BORDER ,ACCENT ,.35 ),
        highlightcolor =lerp_col (BORDER ,ACCENT ,.55 ))
        card .pack (fill ="x",pady =(0 ,18 ))
        return section ,card 

    def _settings_row (self ,card ,icon ,title ,desc ,command ,
    accent =None ,danger =False ,toggle =None ):
        if card .winfo_children ():
            tk .Frame (card ,bg =BORDER ,height =1 ).pack (fill ="x",padx =14 )
        row =SettingsRow (card ,icon ,title ,desc ,command ,
        accent =accent ,danger =danger ,toggle =toggle )
        row .pack (fill ="x",padx =6 ,pady =2 )
        return row 

    def _open_settings (self ):
        DISCORD_BLURPLE ="#5865F2"

        win =tk .Toplevel (self )
        win .title ("Settings")
        win .geometry ("760x600")
        win .minsize (640 ,460 )
        win .configure (bg =BG )

        win .transient (self )
        win .resizable (True ,True )

        header =tk .Frame (win ,bg =BG )
        header .pack (fill ="x")

        htxt =tk .Frame (header ,bg =BG )
        htxt .pack (side ="left",padx =(24 ,12 ),pady =(20 ,14 ))
        tk .Label (htxt ,text ="⚙  Settings",font =(FONT_FAMILY ,21 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (htxt ,text ="Appearance, network tools & more",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w").pack (anchor ="w")

        strip =tk .Canvas (win ,height =3 ,bg =BG ,highlightthickness =0 )
        strip .pack (fill ="x")
        def _draw_strip (e =None ):
            strip .delete ("all")
            w =strip .winfo_width ()
            steps =48 
            for i in range (steps ):
                t =i /(steps -1 )
                col =lerp_col (ACCENT ,ACCENT2 ,t )
                x0 ,x1 =int (w *i /steps ),int (w *(i +1 )/steps )
                strip .create_rectangle (x0 ,0 ,x1 ,3 ,fill =col ,outline =col )
        strip .bind ("<Configure>",_draw_strip )

        body =tk .Frame (win ,bg =BG )
        body .pack (fill ="both",expand =True )

        rail =tk .Frame (body ,bg =SIDEBAR ,width =180 )
        rail .pack (side ="left",fill ="y")
        rail .pack_propagate (False )
        tk .Frame (rail ,bg =SIDEBAR ,height =14 ).pack ()

        content_wrap =tk .Frame (body ,bg =BG )
        content_wrap .pack (side ="left",fill ="both",expand =True )

        search_bar =tk .Frame (content_wrap ,bg =BG )
        search_bar .pack (fill ="x",padx =22 ,pady =(16 ,6 ))
        search_wrap =tk .Frame (search_bar ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        search_wrap .pack (fill ="x")
        IconGlyph (search_wrap ,"🔍",size =14 ,color =MUTED ,bg =ENTRY 
        ).pack (side ="left",padx =(10 ,2 ))
        search_var =tk .StringVar ()
        search_entry =tk .Entry (search_wrap ,textvariable =search_var ,
        font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        search_entry .pack (side ="left",fill ="x",expand =True ,ipady =8 ,padx =(0 ,10 ))

        canvas_wrap =tk .Frame (content_wrap ,bg =BG )
        canvas_wrap .pack (fill ="both",expand =True )
        canvas =tk .Canvas (canvas_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (canvas_wrap ,orient ="vertical",
        style ="Settings.Vertical.TScrollbar",
        command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )

        content =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =content ,anchor ="nw")
        content .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        def build_appearance (parent ,want ):
            def pick_color ():
                c =colorchooser .askcolor (initialcolor =ACCENT ,title ="Pick Accent Color")[1 ]
                if c :
                    self .theme_data ["accent"]=c 
                    self ._save_and_refresh ()

            def upload_bg ():
                path =filedialog .askopenfilename (
                filetypes =[("Image files","*.png *.gif *.pgm *.ppm")])
                if path :
                    self .theme_data ["bg_img"]=path 
                    self ._save_and_refresh ()

            def clear_bg ():
                self .theme_data ["bg_img"]=None 
                self ._save_and_refresh ()

            def pick_titlebar_color ():
                current =self .theme_data .get ("titlebar_color")or "#1a1a1a"
                c =colorchooser .askcolor (initialcolor =current ,
                title ="Pick Title Bar Color")[1 ]
                if c :
                    self .theme_data ["titlebar_color"]=c 
                    self ._save_config_and_sync ()
                    self ._apply_titlebar_color ()

            def reset_titlebar_color ():
                self .theme_data ["titlebar_color"]=None 
                self ._save_config_and_sync ()
                self ._apply_titlebar_color ()

            rows =[
            ("🟨","Accent Color",
            "The highlight color used across buttons and toggles.",
            pick_color ,{"accent":ACCENT2 }),
            ("🟩","Background Picture",
            "Show a custom picture behind the app window.",
            upload_bg ,{"accent":ACCENT2 }),
            ("🟦","Clear Background",
            "Remove the custom background picture, if any.",
            clear_bg ,{"danger":True }),
            ]
            if os .name =="nt":
                rows +=[
                ("🪟","Title Bar Color",
                "Color of the app's window title bar. Dark by default — "
                "pick any color you like (Windows 11 required for "
                "custom colors; older Windows stays dark).",
                pick_titlebar_color ,{"accent":ACCENT2 }),
                ("🔄","Reset Title Bar Color",
                "Go back to the default dark title bar.",
                reset_titlebar_color ,{"danger":True }),
                ]
            matches =[r for r in rows if want (r [1 ],r [2 ])]
            if not matches :
                return 
            _ ,card =self ._settings_group (parent ,"Appearance")
            for icon ,title ,desc ,cmd ,extra in matches :
                self ._settings_row (card ,icon ,title ,desc ,cmd ,**extra )

        def build_network (parent ,want ):
            row_holder ={}

            def do_flush_dns ():
                row =row_holder .get ("dns")
                if row is not None :
                    row .set_desc ("Flushing DNS cache…")
                def worker ():
                    flush_dns ()
                    def done ():
                        if row is not None and row .winfo_exists ():
                            row .set_desc ("Clear locally cached DNS lookups.")
                        Toast (self ,"DNS Cache Flushed",
                        "The local DNS cache has been cleared.",ok =True )
                    self .after (0 ,done )
                threading .Thread (target =worker ,daemon =True ).start ()

            def do_flush_ip ():
                row =row_holder .get ("ip")
                if row is not None :
                    row .set_desc ("Releasing and renewing…")
                def worker ():
                    flush_ip ()
                    def done ():
                        if row is not None and row .winfo_exists ():
                            row .set_desc ("Release your IP and request a new one.")
                        Toast (self ,"IP Renewed",
                        "The DHCP lease was released and a new IP was requested.",ok =True )
                    self .after (0 ,done )
                threading .Thread (target =worker ,daemon =True ).start ()

            rows =[
            ("dns","🌊","Flush DNS Cache",
            "Clear locally cached DNS lookups.",do_flush_dns ),
            ("ip","🔁","Flush / Renew IP",
            "Release your IP and request a new one.",do_flush_ip ),
            ]
            matches =[r for r in rows if want (r [2 ],r [3 ])]
            if not matches :
                return 
            _ ,card =self ._settings_group (parent ,"Network Tools")
            for key ,icon ,title ,desc ,cmd in matches :
                row_holder [key ]=self ._settings_row (card ,icon ,title ,desc ,cmd ,accent =ACCENT )

        def build_protection (parent ,want ):
            def toggle_tor_block ():
                current =self .topics .get ("_block_all_tor",False )
                new_val =not current 
                self .topics ["_block_all_tor"]=new_val 
                self ._save_config_and_sync ()
                if tor_row .get ("row")is not None :
                    tor_row ["row"].set_toggle (new_val )
                if self .shield_on :
                    apply_blocking (self .topics )
                self ._update_stat ()
                self ._refresh_listbox ()
                for t ,btn in self ._sb_btns .items ():
                    btn .set_count (self ._total_domain_count (t ))

            tor_row ={"row":None }
            tor_active =self .topics .get ("_block_all_tor",False )
            tor_title ,tor_desc ="Block all Tor traffic","Instantly block all .onion sites and Tor gateways."
            if want (tor_title ,tor_desc ):
                _ ,tor_card =self ._settings_group (parent ,"Tor & Dark Web")
                tor_row ["row"]=self ._settings_row (tor_card ,"🧅",tor_title ,tor_desc ,
                toggle_tor_block ,accent =ACCENT ,toggle =tor_active )

            feeds_title ,feeds_desc ="Manage Custom Feeds",self ._feed_summary_text ()
            if want (feeds_title ,feeds_desc ):
                _ ,feeds_card =self ._settings_group (parent ,"Custom Blocklist Feeds")
                self ._feeds_row =self ._settings_row (feeds_card ,"🔗",feeds_title ,feeds_desc ,
                self ._open_custom_feeds_manager ,accent =ACCENT2 )

            lock_title ,lock_desc ="Disable Password Lock",self ._lock_summary_text ()
            if want (lock_title ,lock_desc ):
                _ ,lock_card =self ._settings_group (parent ,"Password Lock")
                self ._lock_row =self ._settings_row (lock_card ,"🔒",lock_title ,lock_desc ,
                self ._open_lock_settings ,accent =WARN )

        def build_community (parent ,want ):
            def open_discord ():
                webbrowser .open ("https://discord.gg/Y9gqrujAJg")

            title ,desc ="Join our Discord Server","Updates, support, and chat with other users."
            if not want (title ,desc ):
                return 
            _ ,card =self ._settings_group (parent ,"Community")
            self ._settings_row (card ,"🟪",title ,desc ,open_discord ,accent =DISCORD_BLURPLE )

        TABS =[
        ("appearance","🎨","Appearance",build_appearance ),
        ("network","🌐","Network",build_network ),
        ("protection","🛡️","Protection",build_protection ),
        ("community","💬","Community",build_community ),
        ]
        TAB_BUILDERS ={tid :fn for tid ,_ ,_ ,fn in TABS }
        state ={"tab":"appearance"}

        def _wheel (event ):
            if getattr (event ,"num",None )==4 :
                canvas .yview_scroll (-1 ,"units")
            elif getattr (event ,"num",None )==5 :
                canvas .yview_scroll (1 ,"units")
            else :
                canvas .yview_scroll (int (-event .delta /120 ),"units")
            return "break"

        def _bind_wheel (widget ):
            widget .bind ("<MouseWheel>",_wheel ,add ="+")
            widget .bind ("<Button-4>",_wheel ,add ="+")
            widget .bind ("<Button-5>",_wheel ,add ="+")
            for child in widget .winfo_children ():
                _bind_wheel (child )

        def render ():
            for w in content .winfo_children ():
                w .destroy ()
            tk .Frame (content ,bg =BG ,height =6 ).pack ()

            q =search_var .get ().strip ().lower ()
            def want (title ,desc ):
                return (not q )or (q in title .lower ())or (q in desc .lower ())

            TAB_BUILDERS [state ["tab"]](content ,want )

            if q and len (content .winfo_children ())<=1 :
                tk .Label (content ,text =f'No results for “{search_var .get ().strip ()}”',
                font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG ).pack (pady =40 )

            for t ,btn in rail_btns .items ():
                btn .set_active (t ==state ["tab"])
            _bind_wheel (canvas_wrap )

        def select_tab (tab_id ):
            state ["tab"]=tab_id 
            render ()

        search_var .trace_add ("write",lambda *a :render ())

        rail_btns ={}
        for tid ,icon ,label ,_ in TABS :
            btn =SidebarBtn (rail ,text =label ,font =(FONT_FAMILY ,12 ),
            command =lambda t =tid :select_tab (t ),height =44 ,
            icon =icon )
            btn .pack (fill ="x",pady =2 ,padx =10 )
            rail_btns [tid ]=btn 

        render ()

    def _save_and_refresh (self ):
        self ._save_config_and_sync ()
        self ._rebuild_ui ()

    def _rebuild_ui (self ):
        for w in self .winfo_children ():
            if isinstance (w ,tk .Toplevel ):
                continue 
            w .destroy ()
        if hasattr (self ,"_bg_label"):
            del self ._bg_label 
        self ._sb_btns ={}
        self ._apply_theme_data ()
        self ._setup_scrollbar_styles ()
        self ._build ()
        self ._refresh_shield_ui ()

    def _pick_font (self ):
        global FONT_FAMILY ,MONO_FAMILY 
        try :
            fams =set (tkfont .families (self ))
        except Exception :
            fams =set ()
        # check Hubot Sans first since it's bundled with the app
        for cand in ("Hubot Sans","Segoe UI","SF Pro Text","Helvetica Neue",
        "Ubuntu","Cantarell","Noto Sans","Arial"):
            if cand in fams :
                FONT_FAMILY =cand 
                break 
        for cand in ("Consolas","SF Mono","Cascadia Mono",
        "Ubuntu Mono","DejaVu Sans Mono","Courier New"):
            if cand in fams :
                MONO_FAMILY =cand 
                break 

    def _setup_scrollbar_styles (self ):
        style =ttk .Style (self )
        try :
            style .theme_use ("clam")
        except Exception :
            pass 

        def _scrollbar_style (name ,trough ,thumb ,active ):
            style .configure (name ,
            gripcount =0 ,background =thumb ,troughcolor =trough ,
            bordercolor =trough ,lightcolor =thumb ,darkcolor =thumb ,
            arrowsize =12 ,arrowcolor =trough ,relief ="flat",width =8 )
            style .map (name ,background =[("active",active ),("pressed",active )])

            style .layout (name ,[
            ("Vertical.Scrollbar.trough",{"sticky":"ns","children":[
            ("Vertical.Scrollbar.thumb",{"expand":"1","sticky":"nswe"})
            ]})
            ])

        _scrollbar_style ("Topics.Vertical.TScrollbar",SIDEBAR ,SCROLL_BG1 ,ACCENT )

        _scrollbar_style ("Domains.Vertical.TScrollbar",CARD ,SCROLL_BG2 ,ACCENT2 )

        _scrollbar_style ("Settings.Vertical.TScrollbar",BG ,SCROLL_BG2 ,ACCENT )

    def _on_mousewheel (self ,event ):
        widget =self .winfo_containing (event .x_root ,event .y_root )
        target =None 
        w =widget 
        while w is not None :
            if w is getattr (self ,"_sb_canvas",None )or w is getattr (self ,"_topic_frame",None ):
                target =self ._sb_canvas 
                break 
            if w is getattr (self ,"listbox",None ):
                target =self .listbox 
                break 
            w =w .master if hasattr (w ,"master")else None 
        if target is None :
            return 
        if getattr (event ,"num",None )==4 :
            target .yview_scroll (-1 ,"units")
        elif getattr (event ,"num",None )==5 :
            target .yview_scroll (1 ,"units")
        else :
            target .yview_scroll (int (-event .delta /120 ),"units")
        return "break"

    def _silent_apply (self ):
        try :
            apply_blocking (self .topics )
            self .shield_on =True 
            self ._start_vpn_guard ()
            self ._refresh_shield_ui ()
            self ._sync_lifetime_hosts ()
            n =self ._total_all_domains ()
            self ._fire ("Shield Activated 🛡",
            f"Lifetime mode — {{count}} domains blocked.\n\n“{SHIELD_QUOTE }”",
            ok =True ,count_to =n ,
            native =f"Lifetime mode — {n :,} domains are now blocked.")
        except Exception :
            pass 

    def _build (self ):

        self .sidebar =tk .Frame (self ,bg =SIDEBAR ,width =264 ,
        highlightthickness =1 ,highlightbackground =BORDER ,
        highlightcolor =BORDER )

        gap =46 if self .theme_data .get ("bg_img")else 0 
        self .sidebar .pack (side ="left",fill ="y",padx =(gap ,gap //2 ),pady =gap )
        self .sidebar .pack_propagate (False )

        brand =tk .Frame (self .sidebar ,bg =SIDEBAR ,pady =24 ,padx =20 )
        brand .pack (fill ="x")
        chip =tk .Canvas (brand ,width =36 ,height =36 ,bg =SIDEBAR ,
        highlightthickness =0 )
        chip .pack (side ="left",padx =(0 ,10 ))

        try :
            self ._brand_chip_img =tk .PhotoImage (file =CHIP_ICON_PATH )
        except Exception :
            self ._brand_chip_img =None 
        def _draw_brand_chip ():
            if self ._brand_chip_img is not None :
                chip .create_image (18 ,18 ,image =self ._brand_chip_img ,anchor ="center")
            else :
                draw_rrect (chip ,0 ,0 ,36 ,36 ,14 ,fill =ACCENT_DIM ,
                outline =lerp_col (BORDER ,ACCENT ,.5 ),width =1 )
                chip .create_text (18 ,18 ,text ="⚡",font =(FONT_FAMILY ,17 ),fill =ACCENT ,anchor ="center")
        chip .after (10 ,_draw_brand_chip )
        brand_txt =tk .Frame (brand ,bg =SIDEBAR )
        brand_txt .pack (side ="left")
        tk .Label (brand_txt ,text ="Revolt",
        font =(FONT_FAMILY ,18 ,"bold"),
        fg =TEXT ,bg =SIDEBAR ,anchor ="w").pack (anchor ="w")
        tk .Label (brand_txt ,text ="Internet Shield",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =SIDEBAR ,anchor ="w").pack (anchor ="w")

        tk .Label (self .sidebar ,text ="CATEGORIES",
        font =(FONT_FAMILY ,10 ,"bold"),fg =MUTED ,
        bg =SIDEBAR ,anchor ="w").pack (fill ="x",padx =22 ,pady =(4 ,4 ))

        wrap =tk .Frame (self .sidebar ,bg =SIDEBAR )
        wrap .pack (fill ="both",expand =True )

        self ._sb_canvas =tk .Canvas (wrap ,bg =SIDEBAR ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (wrap ,orient ="vertical",
        style ="Topics.Vertical.TScrollbar",
        command =self ._sb_canvas .yview )
        self ._sb_canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        self ._sb_canvas .pack (side ="left",fill ="both",expand =True )

        self ._topic_frame =tk .Frame (self ._sb_canvas ,bg =SIDEBAR )
        self ._win_id =self ._sb_canvas .create_window (
        (0 ,0 ),window =self ._topic_frame ,anchor ="nw")
        self ._topic_frame .bind ("<Configure>",lambda e :
        self ._sb_canvas .configure (
        scrollregion =self ._sb_canvas .bbox ("all")))
        self ._sb_canvas .bind ("<Configure>",lambda e :
        self ._sb_canvas .itemconfig (self ._win_id ,width =e .width ))

        self .bind_all ("<MouseWheel>",self ._on_mousewheel )
        self .bind_all ("<Button-4>",self ._on_mousewheel )
        self .bind_all ("<Button-5>",self ._on_mousewheel )
        self .bind ("<Configure>",self ._on_resize )

        self ._build_sidebar_buttons ()

        self ._stat_lbl =tk .Label (self .sidebar ,text ="",
        font =(FONT_FAMILY ,12 ,"bold"),fg =TEXT ,bg =SIDEBAR )
        self ._stat_lbl .pack (pady =(6 ,4 ))
        self ._update_stat ()

        bot_ctrl =tk .Frame (self .sidebar ,bg =SIDEBAR )
        bot_ctrl .pack (side ="bottom",fill ="x",padx =18 ,pady =18 )

        FlatBtn (bot_ctrl ,text ="➕  New category",
        base_bg =SIDEBAR ,hover_bg =lighten (ACCENT_DIM ,.06 ),
        fg =ACCENT ,font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._add_topic ,border_col =ACCENT ,ghost =True ,
        radius =20 ,height =46 
        ).pack (fill ="x",pady =(0 ,10 ))

        FlatBtn (bot_ctrl ,text ="⚙️  Settings",
        base_bg =SIDEBAR ,hover_bg =lighten (ACCENT_DIM ,.06 ),
        fg =TEXT ,font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._open_settings ,border_col =lighten (BORDER ,.35 ),
        ghost =True ,radius =20 ,height =46 
        ).pack (fill ="x")

        FlatBtn (bot_ctrl ,text ="🌱  Donate",
        base_bg =SIDEBAR ,hover_bg =lighten (ACCENT_DIM ,.06 ),
        fg ="#3ddc97",font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._open_donate_dialog ,border_col ="#3ddc97",
        ghost =True ,radius =20 ,height =46 
        ).pack (fill ="x",pady =(10 ,0 ))

        main =self 

        hdr =tk .Frame (main ,bg =BG ,padx =32 ,pady =24 )
        hdr .pack (fill ="x",side ="top",padx =(gap //2 ,gap ),pady =(gap ,0 ))

        self .hdr_icon =tk .Canvas (hdr ,width =36 ,height =48 ,
        bg =BG ,highlightthickness =0 )
        self .hdr_icon .pack (side ="left",padx =(0 ,12 ))
        self .hdr_icon .pack_propagate (False )

        def _set_hdr_icon (topic =None ):
            self .hdr_icon .delete ("all")
            has_custom =bool (topic )and topic in self .custom_icons and self .custom_icons .get (topic )!=self .ICONS .get (topic )
            fn =None if has_custom else SIDEBAR_ICON_FUNCS .get (topic )if topic else None 
            if fn :
                fn (self .hdr_icon ,18 ,24 ,26 ,SIDEBAR_ICON_COLORS .get (topic ,ACCENT ))
            else :
                glyph =self ._icon_for (topic )if topic else "◆"
                self .hdr_icon .create_text (18 ,24 ,text =glyph ,
                font =(FONT_FAMILY ,25 ),fill =ACCENT )
        self ._set_hdr_icon =_set_hdr_icon 
        _set_hdr_icon (self .selected if self .selected else None )

        hdr_titles =tk .Frame (hdr ,bg =BG )
        hdr_titles .pack (side ="left",fill ="y")
        self .title_lbl =tk .Label (hdr_titles ,
        text =self .selected or "—",
        font =(FONT_FAMILY ,24 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w")
        self .title_lbl .pack (anchor ="w")
        self .count_lbl =tk .Label (hdr_titles ,text ="",
        font =(FONT_FAMILY ,12 ),fg =MUTED ,
        bg =BG ,anchor ="w")
        self .count_lbl .pack (anchor ="w",pady =(2 ,0 ))

        FlatBtn (hdr ,text ="🗑️  Delete category",
        base_bg =BG ,hover_bg =darken (DANGER ,.6 ),
        fg =DANGER ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._delete_topic ,border_col =DANGER ,ghost =True ,
        radius =17 ,height =34 ,width =170 
        ).pack (side ="right",anchor ="e")

        card =tk .Frame (main ,bg =CARD ,
        highlightthickness =1 ,highlightbackground =BORDER )
        card .pack (fill ="both",expand =True ,
        padx =(32 +gap //2 ,32 +gap ),pady =(0 ,12 ))

        tk .Frame (card ,bg =BORDER_HI ,height =1 ).pack (fill ="x")

        bar =tk .Frame (card ,bg =TOOLBAR ,pady =12 ,padx =20 )
        bar .pack (fill ="x")
        tk .Label (bar ,text ="Blocked domains",
        font =(FONT_FAMILY ,13 ,"bold"),fg =TEXT ,bg =TOOLBAR ,
        anchor ="w").pack (side ="left")
        tk .Label (bar ,text ="  ·  built-in domains are silenced automatically",
        font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =TOOLBAR ,
        anchor ="w").pack (side ="left")

        tk .Frame (card ,bg =BORDER_LO ,height =1 ).pack (fill ="x")

        lf =tk .Frame (card ,bg =CARD ,padx =18 ,pady =12 )
        lf .pack (fill ="both",expand =True )
        vsb2 =ttk .Scrollbar (lf ,orient ="vertical",
        style ="Domains.Vertical.TScrollbar")
        vsb2 .pack (side ="right",fill ="y")
        self .listbox =tk .Listbox (lf ,
        font =(MONO_FAMILY ,13 ),
        bd =0 ,highlightthickness =0 ,
        bg =CARD ,fg =TEXT ,
        selectbackground =SEL_BG ,
        selectforeground =SEL_FG ,
        activestyle ="none",
        yscrollcommand =vsb2 .set )
        self .listbox .pack (side ="left",fill ="both",expand =True )
        vsb2 .config (command =self .listbox .yview )

        tk .Frame (card ,bg =BORDER ,height =1 ).pack (fill ="x")

        inp =tk .Frame (card ,bg =TOOLBAR ,padx =18 ,pady =14 )
        inp .pack (fill ="x")

        entry_wrap =tk .Frame (inp ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        entry_wrap .pack (side ="left",fill ="x",expand =True ,padx =(0 ,10 ))
        self .entry =tk .Entry (entry_wrap ,
        font =(FONT_FAMILY ,13 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        self .entry .pack (fill ="x",expand =True ,ipady =9 ,padx =10 )
        self .entry .bind ("<Return>",lambda _ :self ._add_domain ())
        self .entry .insert (0 ,"")
        self ._entry_placeholder ("example.com")

        FlatBtn (inp ,text ="➕  Add",
        base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),
        fg =BG ,font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._add_domain ,
        radius =21 ,height =42 ,width =98 
        ).pack (side ="left")
        FlatBtn (inp ,text ="🗑️  Remove",
        base_bg =TOOLBAR ,hover_bg =darken (DANGER ,.6 ),
        fg =DANGER ,font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._remove_domain ,border_col =DANGER ,ghost =True ,
        radius =21 ,height =42 ,width =118 
        ).pack (side ="left",padx =(8 ,0 ))
        FlatBtn (inp ,text ="⇪  Import .txt",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,13 ,"bold"),
        command =self ._import_domains_from_file ,ghost =True ,
        radius =21 ,height =42 ,width =146 
        ).pack (side ="left",padx =(8 ,0 ))

        foot =tk .Frame (main ,bg =BG ,padx =32 ,pady =18 )
        foot .pack (fill ="x",side ="bottom",
        padx =(gap //2 ,gap ),pady =(0 ,gap ))

        top_foot =tk .Frame (foot ,bg =BG )
        top_foot .pack (fill ="x",pady =(0 ,10 ))

        self .status_lbl =tk .Label (top_foot ,text ="",
        font =(FONT_FAMILY ,12 ,"bold"),fg =MUTED ,bg =BG )
        self .status_lbl .pack (side ="left")

        self .remote_status_lbl =tk .Label (top_foot ,text ="",
        font =(FONT_FAMILY ,12 ),fg =MUTED ,bg =BG )
        self .remote_status_lbl .pack (side ="left",padx =(10 ,0 ))
        self ._refresh_remote_status_label ()

        self .blocked_ticker =BlockedTicker (top_foot ,width =190 )
        self .blocked_ticker .pack (side ="left",padx =(14 ,0 ))

        self .blocked_ticker .configure (cursor ="hand2")
        self .blocked_ticker .bind ("<Button-1>",lambda e :self ._open_live_feed_dialog ())

        self .lifetime_btn =LifetimeBtn (top_foot ,
        command =self ._toggle_lifetime ,
        height =32 ,width =210 )
        self .lifetime_btn .pack (side ="right")
        self .lifetime_btn .set_on (self ._lifetime )

        action_row =FlowRow (foot ,bg =BG ,gap_x =10 ,gap_y =8 )
        action_row .pack (fill ="x",pady =(0 ,10 ))

        BTN_H =34 
        self .update_lists_btn =FlatBtn (action_row ,text ="🔄  Update Blocklists",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._update_remote_blocklists ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .update_lists_btn ,width =184 ,height =BTN_H )

        self .test_internet_btn =FlatBtn (action_row ,text ="🌐  Test Your Internet",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._test_internet ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .test_internet_btn ,width =198 ,height =BTN_H )

        self .dns_btn =FlatBtn (action_row ,text ="⚙️  Custom DNS: Default",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._open_custom_dns_dialog ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .dns_btn ,width =206 ,height =BTN_H )
        self ._refresh_dns_btn_label ()

        self .allowlist_btn =FlatBtn (action_row ,text ="✅  Allowlist",
        base_bg =TOOLBAR ,hover_bg =darken ("#3ddc97",.55 ),
        fg ="#3ddc97",font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._open_allowlist_dialog ,ghost =True ,
        border_col ="#3ddc97",radius =15 )
        action_row .add (self .allowlist_btn ,width =180 ,height =BTN_H )
        self ._refresh_allowlist_btn_label ()

        self .check_site_btn =FlatBtn (action_row ,text ="🔎  Check a Site",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._open_check_site_dialog ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .check_site_btn ,width =182 ,height =BTN_H )

        self .vpn_btn =FlatBtn (action_row ,text ="🔒  Connect VPN",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._open_vpn_dialog ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .vpn_btn ,width =174 ,height =BTN_H )
        self ._refresh_vpn_btn_label ()

        self .hotspot_btn =FlatBtn (action_row ,text ="📶  Hotspot",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),
        fg =TEXT ,font =(FONT_FAMILY ,12 ,"bold"),
        command =self ._open_hotspot_dialog ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =15 )
        action_row .add (self .hotspot_btn ,width =152 ,height =BTN_H )
        self ._refresh_hotspot_btn_label ()

        shield_slot =tk .Frame (foot ,bg =BG )
        shield_slot .pack (fill ="x")
        self .shield_aura =ShieldAura (shield_slot ,height =60 )
        self .shield_aura .place (x =0 ,y =-6 ,relwidth =1.0 ,height =60 )
        self .shield_btn =ShieldBar (shield_slot ,command =self ._toggle_shield ,height =48 )
        self .shield_btn .pack (fill ="x")

        cred =tk .Frame (foot ,bg =BG )
        cred .pack (anchor ="e",pady =(10 ,0 ))
        tk .Label (cred ,text ="crafted by u29z",
        font =(FONT_FAMILY ,15 ,"bold"),
        fg =MUTED ,bg =BG ).pack (side ="left")
        try :
            self ._credit_icon_img =tk .PhotoImage (file =CREDIT_ICON_PATH )
            tk .Label (cred ,image =self ._credit_icon_img ,bg =BG 
            ).pack (side ="left",padx =(4 ,0 ))
        except Exception :
            tk .Label (cred ,text =" ✦",
            font =(FONT_FAMILY ,16 ),fg =ACCENT2 ,bg =BG ).pack (side ="left")

        self ._version_lbl =tk .Label (self ,text ="v1.05",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG )
        self ._version_lbl .place (relx =1.0 ,rely =1.0 ,x =-6 ,y =-4 ,anchor ="se")
        self ._version_lbl .lift ()

        self ._refresh_listbox ()

    def _total_domain_count (self ,topic :str )->int :
        if topic =="Tor & Dark Web"and self .topics .get ("_block_all_tor"):
            return 1 

        remote =load_remote_cache ().get ("categories",{}).get (topic ,[])
        combined =(set (TOPICS_DATABASE .get (topic ,[]))
        |set (self .topics .get (topic ,set ()))
        |set (remote ))
        return len (combined )

    def _total_all_domains (self )->int :
        return sum (self ._total_domain_count (t )for t in self .topics 
        if not t .startswith ("_"))

    def _update_stat (self ):
        self ._stat_lbl .config (text =f"{self ._total_all_domains ():,} domains in database")

    def _icon_for (self ,topic :str )->str :
        return self .custom_icons .get (topic )or self .ICONS .get (topic ,"◆")

    def _build_sidebar_buttons (self ):
        for w in self ._topic_frame .winfo_children ():
            w .destroy ()
        self ._sb_btns .clear ()

        for t in self .ICONS :
            self .topics .setdefault (t ,set ())

        all_topics =[t for t in self .topics if not t .startswith ("_")]
        self .topic_order =[t for t in self .topic_order if t in all_topics ]+[t for t in all_topics if t not in self .topic_order ]

        for topic in self .topic_order :
            icon =self ._icon_for (topic )

            has_custom =topic in getattr (self ,"custom_icons",{})and self .custom_icons .get (topic )!=self .ICONS .get (topic )
            icon_fn =None if has_custom else SIDEBAR_ICON_FUNCS .get (topic )
            icon_color =None if has_custom else SIDEBAR_ICON_COLORS .get (topic )
            label =topic 
            count =self ._total_domain_count (topic )
            btn =SidebarBtn (self ._topic_frame ,
            text =label ,font =(FONT_FAMILY ,13 ,"bold"),
            command =lambda t =topic :self ._select_topic (t ),
            height =48 ,count =count ,topic =topic ,
            reorder_start =self ._reorder_start ,
            reorder_motion =self ._reorder_motion ,
            reorder_end =self ._reorder_end ,
            icon_picker =self ._open_icon_picker ,
            icon =icon ,icon_fn =icon_fn ,icon_color =icon_color )
            btn .pack (fill ="x",pady =2 ,padx =10 )
            self ._sb_btns [topic ]=btn 

        self ._update_sidebar_active ()

    def _relayout_sidebar_buttons (self ,order ):
        for t in order :
            btn =self ._sb_btns .get (t )
            if btn :
                btn .pack_forget ()
                btn .pack (fill ="x",pady =2 ,padx =10 )

    def _reorder_start (self ,btn ):
        self ._drag_topic =btn .topic 
        self ._drag_order =list (self .topic_order )

    def _reorder_motion (self ,btn ,event ):
        if not getattr (self ,"_drag_topic",None ):
            return 
        order =self ._drag_order 
        if self ._drag_topic not in order :
            return 
        idx_cur =order .index (self ._drag_topic )
        y =event .y_root -self ._topic_frame .winfo_rooty ()
        row_h =max (1 ,btn .winfo_height ()+4 )
        new_idx =max (0 ,min (len (order )-1 ,y //row_h ))
        if new_idx !=idx_cur :
            order .pop (idx_cur )
            order .insert (new_idx ,self ._drag_topic )
            self ._relayout_sidebar_buttons (order )

    def _reorder_end (self ,btn ,event ):
        if getattr (self ,"_drag_topic",None ):
            self .topic_order =list (self ._drag_order )
            self .theme_data ["order"]=self .topic_order 
            self ._save_config_and_sync ()
        self ._drag_topic =None 
        self ._drag_order =None 

        self .after (10 ,self ._build_sidebar_buttons )

    _ICON_CHOICES =[
    "🛡️","🏢","💬","🔞","⚠️","🕵️","🎰","🤖","🧅",
    "🎮","📺","📰","🛒","💸","🍔","🎵","📷","🏀",
    "✈️","💊","🔥","🗞️","📱","💻","🧠","🔗","🔹",
    ]

    def _open_icon_picker (self ,topic :str ):
        if not topic :
            return 
        win =tk .Toplevel (self )
        win .title (f"Icon — {topic }")
        win .configure (bg =BG )
        win .resizable (False ,False )
        win .transient (self )
        win .grab_set ()

        tk .Label (win ,text =f"Choose an icon for “{topic }”",
        font =(FONT_FAMILY ,14 ,"bold"),fg =TEXT ,bg =BG ,
        anchor ="w").pack (anchor ="w",padx =20 ,pady =(18 ,4 ))
        tk .Label (win ,text ="Right-click any category to reopen this.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,
        anchor ="w").pack (anchor ="w",padx =20 ,pady =(0 ,10 ))

        grid =tk .Frame (win ,bg =BG )
        grid .pack (padx =20 ,pady =(0 ,8 ))

        def choose (icon :str ):
            self .custom_icons [topic ]=icon 
            self .theme_data ["icons"]=self .custom_icons 
            self ._save_config_and_sync ()
            if topic in self ._sb_btns :
                self ._build_sidebar_buttons ()
            if self .selected ==topic :
                self ._set_hdr_icon (topic )
            win .destroy ()

        cols =9 
        for i ,icon in enumerate (self ._ICON_CHOICES ):
            r ,c =divmod (i ,cols )
            cell =tk .Canvas (grid ,width =36 ,height =36 ,bg =BG ,
            highlightthickness =0 ,cursor ="hand2")
            cell .grid (row =r ,column =c ,padx =3 ,pady =3 )
            is_current =(self .custom_icons .get (topic )or 
            self .ICONS .get (topic ,"◆"))==icon 
            draw_rrect (cell ,1 ,1 ,35 ,35 ,10 ,
            fill =ACCENT_DIM if is_current else CARD ,
            outline =ACCENT if is_current else BORDER ,width =1 )
            cell .create_text (18 ,18 ,text =icon ,font =(FONT_FAMILY ,16 ),anchor ="center")
            cell .bind ("<Button-1>",lambda e ,ic =icon :choose (ic ))

        custom_row =tk .Frame (win ,bg =BG )
        custom_row .pack (fill ="x",padx =20 ,pady =(6 ,18 ))
        tk .Label (custom_row ,text ="Or type any emoji/character:",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ).pack (anchor ="w")
        entry_wrap =tk .Frame (custom_row ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        entry_wrap .pack (fill ="x",pady =(6 ,0 ),side ="left",expand =True )
        custom_entry =tk .Entry (entry_wrap ,font =(FONT_FAMILY ,13 ),bd =0 ,
        relief ="flat",bg =ENTRY ,fg =TEXT ,
        insertbackground =ACCENT ,width =6 )
        custom_entry .pack (fill ="x",ipady =6 ,padx =8 )
        custom_entry .bind ("<Return>",lambda e :
        choose (custom_entry .get ().strip ()or "◆"))
        FlatBtn (custom_row ,text ="Use",
        base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),
        fg =BG ,font =(FONT_FAMILY ,10 ,"bold"),
        command =lambda :choose (custom_entry .get ().strip ()or "◆"),
        radius =16 ,height =32 ,width =64 
        ).pack (side ="left",padx =(8 ,0 ),pady =(6 ,0 ))

        win .update_idletasks ()
        w ,h =win .winfo_width (),win .winfo_height ()
        sw ,sh =win .winfo_screenwidth (),win .winfo_screenheight ()
        win .geometry (f"+{(sw -w )//2 }+{(sh -h )//2 -40 }")

    def _update_sidebar_active (self ):
        for t ,btn in self ._sb_btns .items ():
            btn .set_active (t ==self .selected )

    def _select_topic (self ,topic :str ):
        self .selected =topic 
        self .title_lbl .config (text =topic )
        self ._set_hdr_icon (topic )
        self ._update_sidebar_active ()
        self ._refresh_listbox ()

    def _refresh_listbox (self ):
        self .listbox .delete (0 ,tk .END )
        self ._dom_list =[]
        if not self .selected :
            self .count_lbl .config (text ="")
            return 

        if self .selected =="Tor & Dark Web"and self .topics .get ("_block_all_tor"):
            self .listbox .insert (tk .END ,"  [ ALL TOR SITES BLOCKED ]")
            self .listbox .itemconfig (tk .END ,fg =ACCENT )
            self .count_lbl .config (text ="Global Tor block is active")
            return 

        user =sorted (self .topics .get (self .selected ,set ()))
        builtin_n =len (TOPICS_DATABASE .get (self .selected ,[]))
        custom_n =len (user )

        for i ,d in enumerate (user ):
            self .listbox .insert (tk .END ,f"   {mask_domain (d )}")
            if i %2 ==1 :
                self .listbox .itemconfig (i ,bg =ROW_ALT )
            self ._dom_list .append (d )

        if custom_n ==0 :
            sub =f"{builtin_n } built-in domains silently blocked"
        else :
            sub =f"{custom_n } custom  ·  {builtin_n } built-in silently blocked"
        self .count_lbl .config (text =sub )

    def _entry_placeholder (self ,hint :str ):
        self .entry .insert (0 ,hint )
        self .entry .config (fg =MUTED )
        state ={"placeholder":True }

        def on_focus_in (_e ):
            if state ["placeholder"]:
                self .entry .delete (0 ,tk .END )
                self .entry .config (fg =TEXT )
                state ["placeholder"]=False 

        def on_focus_out (_e ):
            if not self .entry .get ().strip ():
                self .entry .insert (0 ,hint )
                self .entry .config (fg =MUTED )
                state ["placeholder"]=True 

        self .entry .bind ("<FocusIn>",on_focus_in )
        self .entry .bind ("<FocusOut>",on_focus_out )
        self ._entry_placeholder_state =state 

    def _add_domain (self ):
        if getattr (self ,"_entry_placeholder_state",{}).get ("placeholder"):
            return 
        raw =self .entry .get ().strip ()
        if not raw :return 
        d =clean_domain (raw )
        if not d :
            messagebox .showwarning ("Invalid","Enter a valid domain.")
            return 
        bucket =self .topics .setdefault (self .selected ,set ())
        if d not in bucket :
            bucket .add (d )
            self ._save_config_and_sync ()
        self .entry .delete (0 ,tk .END )
        self ._refresh_listbox ()
        if self .selected in self ._sb_btns :
            self ._sb_btns [self .selected ].set_count (
            self ._total_domain_count (self .selected ))
        self ._update_stat ()
        if self .shield_on :
            try :apply_blocking (self .topics )
            except Exception :pass 

    def _remove_domain (self ):
        sel =self .listbox .curselection ()
        if not sel :return 
        idx =sel [0 ]
        if idx >=len (self ._dom_list ):return 
        real =self ._dom_list [idx ]
        self .topics .get (self .selected ,set ()).discard (real )
        self ._save_config_and_sync ()
        self ._refresh_listbox ()
        if self .selected in self ._sb_btns :
            self ._sb_btns [self .selected ].set_count (
            self ._total_domain_count (self .selected ))
        self ._update_stat ()
        if self .shield_on :
            try :apply_blocking (self .topics )
            except Exception :pass 

    def _import_domains_from_file (self ):
        path =filedialog .askopenfilename (
        title ="Import blocklist from .txt",
        filetypes =[("Text files","*.txt"),("All files","*.*")])
        if not path :
            return 
        try :
            with open (path ,"r",encoding ="utf-8",errors ="ignore")as f :
                lines =f .readlines ()
        except Exception as e :
            messagebox .showerror ("Import Failed",f"Could not read file:\n{e }")
            return 

        bucket =self .topics .setdefault (self .selected ,set ())
        added ,skipped =0 ,0 
        for line in lines :
            raw =line .strip ()
            if not raw or raw .startswith ("#")or raw .startswith ("!"):
                continue 

            token =raw .split ()[-1 ]if raw .split ()else raw 
            d =clean_domain (token )
            if not d or "."not in d :
                skipped +=1 
                continue 
            if d not in bucket :
                bucket .add (d )
                added +=1 
            else :
                skipped +=1 

        if added :
            self ._save_config_and_sync ()
        self ._refresh_listbox ()
        if self .selected in self ._sb_btns :
            self ._sb_btns [self .selected ].set_count (
            self ._total_domain_count (self .selected ))
        self ._update_stat ()

        Toast (self ,"Import Complete ⇪",
        f"{added } domain(s) added"
        +(f", {skipped } skipped (invalid or already present)."
        if skipped else "."),
        ok =True )

        if self .shield_on :
            try :
                apply_blocking (self .topics )
            except Exception :
                pass 

    def _add_topic (self ):
        name =simpledialog .askstring ("New Category","Category name:",parent =self )
        if not name or not name .strip ():return 
        name =name .strip ()
        if name in self .topics :
            messagebox .showinfo ("Exists",f'"{name }" already exists.')
            return 
        self .topics [name ]=set ()
        self .topic_order .append (name )
        self .theme_data ["order"]=self .topic_order 
        self .selected =name 
        self ._save_config_and_sync ()
        self ._build_sidebar_buttons ()
        self .title_lbl .config (text =name )
        self ._set_hdr_icon (None )
        self ._refresh_listbox ()
        self ._update_stat ()

    def _delete_topic (self ):
        if not self .selected :return 
        if self .selected in self .ICONS :
            messagebox .showwarning ("Built-in",
            f'"{self .selected }" is a built-in category and cannot be deleted.')
            return 
        if messagebox .askyesno ("Confirm Delete",
        f'Delete "{self .selected }"?',parent =self ):
            del self .topics [self .selected ]
            if self .selected in self .topic_order :
                self .topic_order .remove (self .selected )
            self .custom_icons .pop (self .selected ,None )
            self .theme_data ["order"]=self .topic_order 
            self .theme_data ["icons"]=self .custom_icons 
            self .selected =next (iter (self .topics ),None )
            self ._save_config_and_sync ()
            self ._build_sidebar_buttons ()
            self .title_lbl .config (text =self .selected or "—")
            self ._set_hdr_icon (self .selected )
            self ._refresh_listbox ()
            self ._update_stat ()

    def _refresh_remote_status_label (self ):
        cache =load_remote_cache ()
        ts =cache .get ("last_updated")
        n =sum (len (v )for v in cache .get ("categories",{}).values ())
        if ts :
            self .remote_status_lbl .config (
            text =f"Remote lists: {n } domains · last updated {relative_time (ts )}")
        else :
            self .remote_status_lbl .config (
            text ="Remote lists: not fetched yet")

    def _update_remote_blocklists (self ):
        self .update_lists_btn .config (state ="disabled")if hasattr (self .update_lists_btn ,"config")else None 
        self .remote_status_lbl .config (text ="Fetching latest lists…")
        combined_sources =build_combined_sources (self .custom_feeds )

        def on_done (added ,errors ):
            def apply ():
                try :
                    if not self .winfo_exists ():return 
                    self ._refresh_remote_status_label ()
                    if errors and not added :

                        msg =("No new domains — the feeds couldn't be reached "
                        "(check your internet connection).")
                        self ._fire ("Couldn't Update Blocklists",msg ,ok =False ,
                        native =msg )
                    else :
                        msg =(f"{added } new domains pulled in from public feeds."
                        if added else "Already up to date — no new domains found.")
                        self ._fire ("Blocklists Updated ⟳",msg ,ok =True ,native =msg )
                        if self .shield_on :
                            try :
                                apply_blocking (self .topics )
                            except Exception :
                                pass 
                        if self ._lifetime :
                            self ._sync_lifetime_hosts ()
                    for cat in self ._sb_btns :
                        self ._sb_btns [cat ].set_count (self ._total_domain_count (cat ))
                    self ._update_stat ()
                except Exception :
                    pass 
                finally :
                    try :
                        if self .winfo_exists ()and hasattr (self ,"update_lists_btn"):
                            self .update_lists_btn .config (state ="normal")
                    except Exception :
                        pass 
            self .after (0 ,apply )

        update_remote_blocklists_async (on_done ,sources =combined_sources )

    def _feed_summary_text (self )->str :
        n =len (self .custom_feeds )
        if n ==0 :
            return "Subscribe to your own hosts-format blocklist URLs."
        enabled =sum (1 for f in self .custom_feeds if f .get ("enabled",True ))
        return f"{enabled } of {n } feed(s) active"

    def _open_custom_feeds_manager (self ):
        win =tk .Toplevel (self )
        win .title ("Custom Blocklist Feeds")
        win .geometry ("480x540")
        win .minsize (420 ,360 )
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()

        header =tk .Frame (win ,bg =BG )
        header .pack (fill ="x",padx =24 ,pady =(20 ,8 ))
        tk .Label (header ,text ="Custom Blocklist Feeds",
        font =(FONT_FAMILY ,17 ,"bold"),fg =TEXT ,bg =BG ,
        anchor ="w").pack (anchor ="w")
        tk .Label (header ,
        text ="Subscribe to any hosts-format blocklist URL — it "
        "merges into the category you pick, right alongside "
        "the built-in feeds, on every \"Update Blocklists\".",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =430 ,justify ="left").pack (anchor ="w",pady =(4 ,0 ))

        tk .Frame (win ,bg =BORDER ,height =1 ).pack (fill ="x",pady =(10 ,0 ))

        list_wrap =tk .Frame (win ,bg =BG )
        list_wrap .pack (fill ="both",expand =True ,padx =14 ,pady =10 )

        canvas =tk .Canvas (list_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (list_wrap ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )

        rows_frame =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =rows_frame ,anchor ="nw")
        rows_frame .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        STATUS_COLORS ={
        "ok":"#3ddc97","failed":DANGER ,"stale":WARN ,"unknown":MUTED ,
        }

        def _wheel (event ):
            if getattr (event ,"num",None )==4 :
                canvas .yview_scroll (-1 ,"units")
            elif getattr (event ,"num",None )==5 :
                canvas .yview_scroll (1 ,"units")
            else :
                canvas .yview_scroll (int (-event .delta /120 ),"units")
            return "break"

        def _bind_wheel (widget ):
            widget .bind ("<MouseWheel>",_wheel ,add ="+")
            widget .bind ("<Button-4>",_wheel ,add ="+")
            widget .bind ("<Button-5>",_wheel ,add ="+")
            for child in widget .winfo_children ():
                _bind_wheel (child )

        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"):
            canvas .bind (seq ,_wheel )

        def rebuild_rows ():
            for w in rows_frame .winfo_children ():
                w .destroy ()
            if not self .custom_feeds :
                tk .Label (rows_frame ,text ="No custom feeds yet — add one below.",
                font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG ).pack (pady =(20 ,8 ))
            else :
                _draw_feed_cards ()
            _draw_suggested_section ()
            _bind_wheel (rows_frame )

        def _draw_feed_cards ():
            feed_status =load_remote_cache ().get ("feed_status",{})
            for i ,feed in enumerate (self .custom_feeds ):
                card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                highlightbackground =BORDER )
                card .pack (fill ="x",pady =(0 ,8 ),padx =2 )

                top =tk .Frame (card ,bg =CARD )
                top .pack (fill ="x",padx =12 ,pady =(10 ,2 ))

                var =tk .BooleanVar (value =feed .get ("enabled",True ))

                def on_toggle (idx =i ,var =var ):
                    self .custom_feeds [idx ]["enabled"]=var .get ()
                    save_custom_feeds (self .custom_feeds )
                    self ._feeds_row .set_desc (self ._feed_summary_text ())

                tk .Checkbutton (top ,variable =var ,command =on_toggle ,
                bg =CARD ,activebackground =CARD ,
                highlightthickness =0 ,bd =0 ,
                selectcolor =darken (CARD ,.15 )
                ).pack (side ="left")

                tk .Label (top ,text =feed .get ("label")or feed ["url"],
                font =(FONT_FAMILY ,12 ,"bold"),fg =TEXT ,bg =CARD ,
                anchor ="w").pack (side ="left",padx =(4 ,0 ),
                fill ="x",expand =True )

                def remove (idx =i ):
                    target =self .custom_feeds [idx ]
                    if messagebox .askyesno ("Remove Feed",
                    f'Remove "{target .get ("label")or target ["url"]}"?',
                    parent =win ):
                        del self .custom_feeds [idx ]
                        save_custom_feeds (self .custom_feeds )
                        self ._feeds_row .set_desc (self ._feed_summary_text ())
                        rebuild_rows ()

                CloseX (top ,bg =CARD ,fg =DANGER ,hover_fg =lighten (DANGER ,.2 ),
                command =remove ).pack (side ="right")

                meta =tk .Frame (card ,bg =CARD )
                meta .pack (fill ="x",padx =12 ,pady =(0 ,10 ))
                tk .Label (meta ,text =f"Category: {feed ['category']}",
                font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =CARD ,
                anchor ="w").pack (anchor ="w")
                url_disp =feed ["url"]if len (feed ["url"])<=62 else feed ["url"][:59 ]+"…"
                tk .Label (meta ,text =url_disp ,
                font =(MONO_FAMILY ,9 ),fg =darken (MUTED ,.1 ),
                bg =CARD ,anchor ="w").pack (anchor ="w")

                health =feed_health (feed ["url"],feed_status )
                col =STATUS_COLORS .get (health ["state"],MUTED )
                glyph ={"ok":"✅","failed":"❌","stale":"⏳",
                "unknown":"⚪"}.get (health ["state"],"⚪")

                status_row =tk .Frame (meta ,bg =CARD )
                status_row .pack (anchor ="w",fill ="x",pady =(6 ,0 ))
                dot =tk .Canvas (status_row ,width =10 ,height =10 ,bg =CARD ,
                highlightthickness =0 )
                dot .pack (side ="left",pady =1 )
                dot .create_oval (1 ,1 ,9 ,9 ,fill =col ,outline ="")
                tk .Label (status_row ,text =f"{glyph }  {health ['label']}",
                font =(FONT_FAMILY ,9 ,"bold"),fg =col ,bg =CARD ,
                anchor ="w").pack (side ="left",padx =(6 ,0 ))

                tk .Label (meta ,text =health ["detail"],
                font =(FONT_FAMILY ,8 ),fg =darken (MUTED ,.1 ),bg =CARD ,
                anchor ="w",wraplength =380 ,justify ="left"
                ).pack (anchor ="w",pady =(1 ,0 ))

        def _add_suggested_feed (sf ):
            cat =sf ["category"]
            self .topics .setdefault (cat ,set ())
            self ._save_config_and_sync ()
            self .custom_feeds .append ({
            "label":sf ["label"],"url":sf ["url"],
            "category":cat ,"enabled":True ,
            })
            save_custom_feeds (self .custom_feeds )
            self ._build_sidebar_buttons ()
            self ._feeds_row .set_desc (self ._feed_summary_text ())
            rebuild_rows ()
            Toast (self ,"Feed Added 🔗",
            f'"{sf ["label"]}" subscribed under "{cat }". Updating…',
            ok =True )
            self ._update_remote_blocklists ()

        def _draw_suggested_section ():
            added_urls ={f ["url"]for f in self .custom_feeds }
            available =[sf for sf in SUGGESTED_FEEDS if sf ["url"]not in added_urls ]
            if not available :
                return 

            tk .Frame (rows_frame ,bg =BORDER ,height =1 ).pack (fill ="x",pady =(6 ,12 ))
            head =tk .Frame (rows_frame ,bg =BG )
            head .pack (fill ="x",pady =(0 ,6 ))
            tk .Label (head ,text ="✨  Suggested Feeds",
            font =(FONT_FAMILY ,13 ,"bold"),fg =TEXT ,bg =BG ,
            anchor ="w").pack (anchor ="w")
            tk .Label (head ,
            text ="Not added by default — tap Add to subscribe, "
            "remove anytime from the list above.",
            font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,
            anchor ="w",wraplength =420 ,justify ="left"
            ).pack (anchor ="w",pady =(2 ,0 ))

            for sf in available :
                card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                highlightbackground =BORDER )
                card .pack (fill ="x",pady =(0 ,8 ),padx =2 )

                top =tk .Frame (card ,bg =CARD )
                top .pack (fill ="x",padx =12 ,pady =(10 ,2 ))

                tk .Label (top ,text =sf ["label"],
                font =(FONT_FAMILY ,12 ,"bold"),fg =TEXT ,bg =CARD ,
                anchor ="w").pack (side ="left",fill ="x",expand =True )

                FlatBtn (top ,text ="＋ Add",base_bg =ACCENT2 ,
                hover_bg =lighten (ACCENT2 ,.1 ),fg =BG ,
                font =(FONT_FAMILY ,9 ,"bold"),
                command =lambda sf =sf :_add_suggested_feed (sf ),
                radius =14 ,height =26 ,width =70 
                ).pack (side ="right")

                meta =tk .Frame (card ,bg =CARD )
                meta .pack (fill ="x",padx =12 ,pady =(0 ,10 ))
                tk .Label (meta ,text =f"Category: {sf ['category']}",
                font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =CARD ,
                anchor ="w").pack (anchor ="w")
                tk .Label (meta ,text =sf ["desc"],
                font =(FONT_FAMILY ,8 ),fg =darken (MUTED ,.1 ),bg =CARD ,
                anchor ="w",wraplength =380 ,justify ="left"
                ).pack (anchor ="w",pady =(2 ,0 ))

        rebuild_rows ()

        tk .Frame (win ,bg =BORDER ,height =1 ).pack (fill ="x")
        footer =tk .Frame (win ,bg =BG )
        footer .pack (fill ="x",pady =14 )
        FlatBtn (footer ,text ="＋  Add Feed",
        base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
        font =(FONT_FAMILY ,12 ,"bold"),
        command =lambda :self ._open_add_feed_dialog (win ,rebuild_rows ),
        radius =20 ,height =40 ,width =130 
        ).pack (side ="left",padx =(24 ,8 ))
        FlatBtn (footer ,text ="🔄  Refresh Status",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,
        font =(FONT_FAMILY ,12 ,"bold"),command =rebuild_rows ,
        ghost =True ,radius =20 ,height =40 ,width =140 
        ).pack (side ="left",padx =(0 ,8 ))
        FlatBtn (footer ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =20 ,height =40 ,width =100 
        ).pack (side ="left")

    def _open_add_feed_dialog (self ,parent_win ,on_saved ):
        win =tk .Toplevel (parent_win )
        win .title ("Add Custom Feed")
        win .geometry ("420x400")
        win .configure (bg =BG )
        win .transient (parent_win )
        win .grab_set ()

        body =tk .Frame (win ,bg =BG ,padx =24 ,pady =20 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Add Custom Feed",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Any hosts-format URL (lines like \"0.0.0.0 domain.com\" "
        "or \"127.0.0.1 domain.com\").",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =370 ,justify ="left").pack (anchor ="w",pady =(2 ,14 ))

        def labeled_entry (label_text ):
            tk .Label (body ,text =label_text ,font =(FONT_FAMILY ,10 ,"bold"),
            fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(6 ,3 ))
            wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
            highlightbackground =BORDER ,highlightcolor =ACCENT )
            wrap .pack (fill ="x")
            e =tk .Entry (wrap ,font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
            bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
            e .pack (fill ="x",ipady =8 ,padx =8 )
            return e 

        label_entry =labeled_entry ("Label (optional)")
        url_entry =labeled_entry ("Blocklist URL")

        tk .Label (body ,text ="Category",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(6 ,3 ))
        cat_var =tk .StringVar (value =self .selected or "")
        cat_box =ttk .Combobox (body ,textvariable =cat_var ,
        values =sorted (self .topics .keys ()))
        cat_box .pack (fill ="x",ipady =4 )
        tk .Label (body ,
        text ="Pick an existing category, or type a new one to create it.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,
        anchor ="w").pack (anchor ="w",pady =(4 ,0 ))

        def do_save ():
            url =url_entry .get ().strip ()
            cat =cat_var .get ().strip ()
            label =label_entry .get ().strip ()
            if not url or not (url .startswith ("http://")or url .startswith ("https://")):
                messagebox .showwarning ("Invalid URL",
                "Enter a valid http(s):// URL.",parent =win )
                return 
            if not cat :
                messagebox .showwarning ("Missing Category",
                "Enter or pick a category.",parent =win )
                return 
            if any (f ["url"]==url and f ["category"]==cat 
            for f in self .custom_feeds ):
                messagebox .showinfo ("Already Added",
                "This feed is already subscribed for that category.",
                parent =win )
                return 

            self .topics .setdefault (cat ,set ())
            self ._save_config_and_sync ()
            self .custom_feeds .append ({
            "label":label ,"url":url ,"category":cat ,"enabled":True 
            })
            save_custom_feeds (self .custom_feeds )
            self ._build_sidebar_buttons ()
            if hasattr (self ,"_feeds_row"):
                self ._feeds_row .set_desc (self ._feed_summary_text ())
            win .destroy ()
            on_saved ()
            Toast (self ,"Feed Added 🔗",
            f'"{label or url }" subscribed under "{cat }". Updating…',
            ok =True )
            self ._update_remote_blocklists ()

        footer =tk .Frame (body ,bg =BG )
        footer .pack (fill ="x",pady =(18 ,0 ))
        FlatBtn (footer ,text ="Save",base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),
        fg =BG ,font =(FONT_FAMILY ,12 ,"bold"),command =do_save ,
        radius =18 ,height =38 ,width =100 ).pack (side ="left")
        FlatBtn (footer ,text ="Cancel",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =18 ,height =38 ,width =100 
        ).pack (side ="left",padx =(8 ,0 ))

    def _allowlist_summary_text (self )->str :
        n =len (self .allowlist )
        if n ==0 :
            return "Sites that should never be blocked, no matter what."
        return f"{n } site(s) always allowed"

    def _add_to_allowlist (self ,raw :str ,win =None )->bool :
        d =clean_domain (raw )
        if not d :
            messagebox .showwarning ("Invalid","Enter a valid domain.",parent =win or self )
            return False 
        if d in self .allowlist :
            messagebox .showinfo ("Already Added",
            f'"{d }" is already on the allowlist.',parent =win or self )
            return False 

        self .allowlist .add (d )
        save_allowlist (self .allowlist )
        self ._refresh_allowlist_btn_label ()
        if self .shield_on :
            try :
                apply_blocking (self .topics ,self .allowlist )
            except Exception :
                pass 
        if self ._lifetime :
            self ._sync_lifetime_hosts ()

        def worker ():
            ok ,msg =open_ports_for_domain (d )
            def done ():
                Toast (self ,"Site Allowed ✅"if ok else "Couldn't Verify ⚠",
                msg ,ok =ok )
            self .after (0 ,done )
        threading .Thread (target =worker ,daemon =True ).start ()
        return True 

    def _remove_from_allowlist (self ,domain :str ):
        self .allowlist .discard (domain )
        save_allowlist (self .allowlist )
        self ._refresh_allowlist_btn_label ()
        if self .shield_on :
            try :
                apply_blocking (self .topics ,self .allowlist )
            except Exception :
                pass 
        if self ._lifetime :
            self ._sync_lifetime_hosts ()
        threading .Thread (target =close_ports_for_domain ,args =(domain ,),
        daemon =True ).start ()

    def _refresh_allowlist_btn_label (self ):
        n =len (self .allowlist )
        text =f"✅  Allowlist ({n })"if n else "✅  Allowlist"
        if hasattr (self ,"allowlist_btn")and self .allowlist_btn .winfo_exists ():
            self .allowlist_btn .config (text =text )

    def _open_allowlist_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Always-Allowed Sites")
        win .geometry ("460x520")
        win .minsize (400 ,340 )
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()

        header =tk .Frame (win ,bg =BG )
        header .pack (fill ="x",padx =24 ,pady =(20 ,8 ))
        tk .Label (header ,text ="Always-Allowed Sites",
        font =(FONT_FAMILY ,17 ,"bold"),fg =TEXT ,bg =BG ,
        anchor ="w").pack (anchor ="w")
        tk .Label (header ,
        text ="Sites here are never blocked — even if they show up "
        "on a blocklist category or a subscribed feed. Adding "
        "one double-checks that it actually resolves and is "
        "reachable, and (on Windows) opens an outbound "
        "firewall allowance for it.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =410 ,justify ="left").pack (anchor ="w",pady =(4 ,0 ))

        tk .Frame (win ,bg =BORDER ,height =1 ).pack (fill ="x",pady =(10 ,0 ))

        list_wrap =tk .Frame (win ,bg =BG )
        list_wrap .pack (fill ="both",expand =True ,padx =14 ,pady =10 )

        canvas =tk .Canvas (list_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (list_wrap ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )

        rows_frame =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =rows_frame ,anchor ="nw")
        rows_frame .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        def _wheel (event ):
            if getattr (event ,"num",None )==4 :
                canvas .yview_scroll (-1 ,"units")
            elif getattr (event ,"num",None )==5 :
                canvas .yview_scroll (1 ,"units")
            else :
                canvas .yview_scroll (int (-event .delta /120 ),"units")
            return "break"

        def _bind_wheel (widget ):
            widget .bind ("<MouseWheel>",_wheel ,add ="+")
            widget .bind ("<Button-4>",_wheel ,add ="+")
            widget .bind ("<Button-5>",_wheel ,add ="+")
            for child in widget .winfo_children ():
                _bind_wheel (child )

        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"):
            canvas .bind (seq ,_wheel )

        def rebuild_rows ():
            for w in rows_frame .winfo_children ():
                w .destroy ()
            if not self .allowlist :
                tk .Label (rows_frame ,text ="No always-allowed sites yet — add one below.",
                font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG ).pack (pady =(20 ,8 ))
            else :
                for d in sorted (self .allowlist ):
                    card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                    highlightbackground =BORDER )
                    card .pack (fill ="x",pady =(0 ,8 ),padx =2 )
                    row =tk .Frame (card ,bg =CARD )
                    row .pack (fill ="x",padx =12 ,pady =10 )
                    row_txt =tk .Frame (row ,bg =CARD )
                    row_txt .pack (side ="left",fill ="x",expand =True )
                    IconGlyph (row_txt ,"✅",size =14 ,color ="#3ddc97",bg =CARD 
                    ).pack (side ="left",padx =(0 ,6 ))
                    tk .Label (row_txt ,text =d ,font =(FONT_FAMILY ,12 ,"bold"),
                    fg =TEXT ,bg =CARD ,anchor ="w"
                    ).pack (side ="left",fill ="x",expand =True )

                    def remove (domain =d ):
                        if messagebox .askyesno ("Remove From Allowlist",
                        f'Remove "{domain }" from the allowlist? It will '
                        "go back to being blocked if it matches any "
                        "category or feed you have on.",parent =win ):
                            self ._remove_from_allowlist (domain )
                            rebuild_rows ()

                    CloseX (row ,bg =CARD ,fg =DANGER ,hover_fg =lighten (DANGER ,.2 ),
                    command =remove ).pack (side ="right")
            _bind_wheel (rows_frame )

        rebuild_rows ()

        tk .Frame (win ,bg =BORDER ,height =1 ).pack (fill ="x")
        add_bar =tk .Frame (win ,bg =BG )
        add_bar .pack (fill ="x",padx =24 ,pady =(12 ,6 ))
        wrap =tk .Frame (add_bar ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        wrap .pack (fill ="x")
        entry =tk .Entry (wrap ,font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        entry .pack (fill ="x",ipady =8 ,padx =8 )
        entry .focus_set ()

        def do_add (_e =None ):
            raw =entry .get ().strip ()
            if not raw :
                return 
            if self ._add_to_allowlist (raw ,win =win ):
                entry .delete (0 ,tk .END )
                rebuild_rows ()

        entry .bind ("<Return>",do_add )

        footer =tk .Frame (win ,bg =BG )
        footer .pack (fill ="x",pady =14 ,padx =24 )
        FlatBtn (footer ,text ="＋  Add Site",base_bg =ACCENT ,
        hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
        font =(FONT_FAMILY ,12 ,"bold"),command =do_add ,
        radius =20 ,height =40 ,width =120 ).pack (side ="left")
        FlatBtn (footer ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =20 ,height =40 ,width =100 
        ).pack (side ="left",padx =(8 ,0 ))

    def _open_donate_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Donate")
        win .geometry ("460x520")
        win .minsize (420 ,460 )
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =26 ,pady =22 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="🌱  Donate",font =(FONT_FAMILY ,18 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")

        tk .Label (body ,
        text ="i just want to make earth a better place",
        font =(FONT_FAMILY ,12 ,"italic"),fg ="#3ddc97",bg =BG ,
        anchor ="w",wraplength =400 ,justify ="left"
        ).pack (anchor ="w",pady =(6 ,12 ))

        tk .Label (body ,
        text ="All donations go to support environmental conservation "
        "campaigns, fighting Capitalist corporations, and "
        "supporting low-income communities.",
        font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =400 ,justify ="left").pack (anchor ="w",pady =(0 ,4 ))

        tk .Label (body ,
        text ="Note: crypto is used because known donation "
        "websites are blocked where I live (Iraq).",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =400 ,justify ="left").pack (anchor ="w",pady =(0 ,16 ))

        tk .Frame (body ,bg =BORDER ,height =1 ).pack (fill ="x",pady =(0 ,14 ))

        def copy_row (parent ,network :str ,address :str ):
            row =tk .Frame (parent ,bg =BG )
            row .pack (fill ="x",pady =(0 ,12 ))

            tk .Label (row ,text =network ,font =(FONT_FAMILY ,10 ,"bold"),
            fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,4 ))

            wrap =tk .Frame (row ,bg =ENTRY ,highlightthickness =1 ,
            highlightbackground =BORDER ,highlightcolor =ACCENT ,
            cursor ="hand2")
            wrap .pack (fill ="x")

            addr_lbl =tk .Label (wrap ,text =address ,font =(FONT_FAMILY ,10 ),
            fg =MUTED ,bg =ENTRY ,anchor ="w",cursor ="hand2")
            addr_lbl .pack (side ="left",fill ="x",expand =True ,
            ipady =8 ,padx =(8 ,4 ))

            copy_lbl =tk .Label (wrap ,text ="⧉ Copy",font =(FONT_FAMILY ,9 ,"bold"),
            fg =ACCENT ,bg =ENTRY ,cursor ="hand2")
            copy_lbl .pack (side ="right",padx =(0 ,10 ))

            def do_copy (event =None ):
                self .clipboard_clear ()
                self .clipboard_append (address )
                self .update ()
                copy_lbl .config (text ="✓ Copied",fg ="#3ddc97")
                win .after (1400 ,lambda :copy_lbl .winfo_exists ()and 
                copy_lbl .config (text ="⧉ Copy",fg =ACCENT ))

            for w in (wrap ,addr_lbl ,copy_lbl ):
                w .bind ("<Button-1>",do_copy )

        copy_row (body ,"Base","0x9457b1C0e463D1F34865725e9341B93cBA436d7d")
        copy_row (body ,"Polygon","0x9457b1C0e463D1F34865725e9341B93cBA436d7d")
        copy_row (body ,"Solana","6Vjwapknrm8bw1JAnfYarBvgi2HBoNe5p6kR4dEJ7WFG")

        tk .Label (body ,
        text ="You can check where your money goes in our Discord "
        "server, which you can find in the Settings tab.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =400 ,justify ="left").pack (anchor ="w",pady =(4 ,10 ))

    def _lock_summary_text (self )->str :
        if not self .lock_data .get ("enabled"):
            return "Off — anyone can disable the Shield instantly."
        cd =self .lock_data .get ("cooldown_min",0 )
        if cd :
            return f"On — password required, {cd } min cooldown before disabling."
        return "On — password required to disable the Shield."

    def _open_lock_settings (self ):
        win =tk .Toplevel (self )
        win .title ("Disable Password Lock")
        win .geometry ("380x360")
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =24 ,pady =20 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="🔒  Disable Password Lock",
        font =(FONT_FAMILY ,16 ,"bold"),fg =TEXT ,bg =BG ,
        anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Require a password (and, optionally, a cooldown "
        "timer) before the Shield can be switched off — so "
        "an impulsive moment can't undo it in one click.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =330 ,justify ="left").pack (anchor ="w",pady =(4 ,14 ))

        already_on =self .lock_data .get ("enabled",False )

        def labeled_entry (label_text ,show =None ):
            tk .Label (body ,text =label_text ,font =(FONT_FAMILY ,10 ,"bold"),
            fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(6 ,3 ))
            wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
            highlightbackground =BORDER ,highlightcolor =ACCENT )
            wrap .pack (fill ="x")
            e =tk .Entry (wrap ,font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
            bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT ,
            show =show or "")
            e .pack (fill ="x",ipady =8 ,padx =8 )
            return e 

        pw_entry =labeled_entry (
        "New password"if not already_on else "New password (leave blank to keep current)",
        show ="•")

        tk .Label (body ,text ="Cooldown before disabling (minutes, 0 = none)",
        font =(FONT_FAMILY ,10 ,"bold"),fg =TEXT ,bg =BG ,
        anchor ="w").pack (anchor ="w",pady =(10 ,3 ))
        cd_var =tk .StringVar (value =str (self .lock_data .get ("cooldown_min",0 )))
        cd_wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        cd_wrap .pack (fill ="x")
        cd_entry =tk .Entry (cd_wrap ,textvariable =cd_var ,font =(FONT_FAMILY ,12 ),
        bd =0 ,relief ="flat",bg =ENTRY ,fg =TEXT ,
        insertbackground =ACCENT )
        cd_entry .pack (fill ="x",ipady =8 ,padx =8 )

        def do_save ():
            cd_raw =cd_var .get ().strip ()
            try :
                cd =max (0 ,int (cd_raw or "0"))
            except ValueError :
                messagebox .showwarning ("Invalid Cooldown",
                "Cooldown must be a whole number of minutes.",parent =win )
                return 
            pw =pw_entry .get ()
            if not already_on or pw :
                if not pw :
                    messagebox .showwarning ("Password Required",
                    "Enter a password to enable the lock.",parent =win )
                    return 
                salt =secrets .token_hex (16 )
                self .lock_data ["salt"]=salt 
                self .lock_data ["hash"]=hash_password (pw ,salt )
            self .lock_data ["enabled"]=True 
            self .lock_data ["cooldown_min"]=cd 
            save_lock (self .lock_data )
            self ._lock_row .set_desc (self ._lock_summary_text ())
            win .destroy ()
            Toast (self ,"Lock Enabled 🔒",
            "The Shield now requires a password to disable.",ok =True )

        def do_disable_lock ():
            self .lock_data =dict (_LOCK_DEFAULT )
            save_lock (self .lock_data )
            self ._lock_row .set_desc (self ._lock_summary_text ())
            win .destroy ()
            Toast (self ,"Lock Disabled","The Shield can be disabled freely again.",ok =False )

        footer =tk .Frame (body ,bg =BG )
        footer .pack (fill ="x",pady =(18 ,0 ))
        FlatBtn (footer ,text ="Save",base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),
        fg =BG ,font =(FONT_FAMILY ,12 ,"bold"),command =do_save ,
        radius =18 ,height =38 ,width =90 ).pack (side ="left")
        if already_on :
            FlatBtn (footer ,text ="Turn Off Lock",base_bg =BORDER ,fg =DANGER ,
            command =do_disable_lock ,radius =18 ,height =38 ,width =120 
            ).pack (side ="left",padx =(8 ,0 ))
        FlatBtn (footer ,text ="Cancel",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =18 ,height =38 ,width =90 
        ).pack (side ="left",padx =(8 ,0 ))

    def _authorize_disable (self )->bool :
        lock =self .lock_data 
        if not lock .get ("enabled"):
            return True 

        if self ._pending_disable_id is not None :
            pw =simpledialog .askstring ("Shield Locked",
            "A cooldown is already counting down.\n"
            "Enter password to disable immediately:",
            show ="*",parent =self )
            if pw is None :
                return False 
            ok ,migrated =verify_password (pw ,lock .get ("salt",""),lock .get ("hash",""))
            if not ok :
                messagebox .showerror ("Incorrect Password","That password is incorrect.")
                return False 
            if migrated :
                lock ["hash"]=migrated 
                save_lock (lock )
            try :
                self .after_cancel (self ._pending_disable_id )
            except Exception :
                pass 
            self ._pending_disable_id =None 
            self ._pending_disable_deadline =None 
            return True 

        pw =simpledialog .askstring ("Shield Locked",
        "Enter password to disable the Shield:",show ="*",parent =self )
        if pw is None :
            return False 
        ok ,migrated =verify_password (pw ,lock .get ("salt",""),lock .get ("hash",""))
        if not ok :
            messagebox .showerror ("Incorrect Password","That password is incorrect.")
            return False 
        if migrated :
            lock ["hash"]=migrated 
            save_lock (lock )

        cd =lock .get ("cooldown_min",0 )
        if cd and cd >0 :
            self ._pending_disable_deadline =time .time ()+cd *60 

            def _fire_disable ():
                self ._pending_disable_id =None 
                self ._pending_disable_deadline =None 
                try :
                    remove_blocking ()
                    self .shield_on =False 
                    self ._stop_vpn_guard ()
                    self ._refresh_shield_ui ()
                    self ._fire ("Shield Disabled",
                    "Cooldown complete — all blocked domains released.",
                    ok =False ,
                    native ="Cooldown complete — the Shield has been disabled.")
                except Exception :
                    pass 

            self ._pending_disable_id =self .after (int (cd *60 *1000 ),_fire_disable )
            Toast (self ,"Cooldown Started ⏳",
            f"Password accepted. The Shield will disable in {cd } "
            "minute(s). Tap the Shield bar again to confirm and "
            "disable it immediately instead.",ok =False )
            return False 

        return True 

    def _require_admin (self )->bool :
        if is_admin ():return True 
        if os .name =="nt":
            if messagebox .askyesno ("Administrator Required",
            "Revolt needs Administrator rights to run its local DNS "
            "shield and change your network's DNS settings.\n\n"
            "Restart as Administrator now?"):
                elevate_windows ()
                self .destroy ()
        else :
            messagebox .showerror ("Root Required",
            "Run:  sudo python3 revolt.py")
        return False 

    def _toggle_shield (self ):
        if not self ._require_admin ():return 
        try :
            if self .shield_on :
                if not self ._authorize_disable ():return 
                remove_blocking ()
                self .shield_on =False 
                self ._stop_vpn_guard ()
                self ._fire ("Shield Disabled",
                "All blocked domains released.",ok =False ,
                native ="All blocked domains have been released.")
            else :
                apply_blocking (self .topics )
                self .shield_on =True 
                self ._start_vpn_guard ()
                n =self ._total_all_domains ()
                self ._fire ("Shield Activated 🛡",
                f"{{count}} domains are now blocked.\n\n“{SHIELD_QUOTE }”",
                ok =True ,count_to =n ,
                native =f"{n :,} domains are now blocked.")
            self ._refresh_shield_ui ()
        except PermissionError as e :
            messagebox .showerror ("Permission Denied",str (e ))
        except Exception as e :
            messagebox .showerror ("Error",str (e ))

    _VPN_GUARD_INTERVAL_MS =4000 

    def _start_vpn_guard (self ):
        self ._vpn_guard_active =True 
        self ._vpn_guard_tick ()

    def _stop_vpn_guard (self ):
        self ._vpn_guard_active =False 

    def _vpn_guard_tick (self ):
        if not getattr (self ,"_vpn_guard_active",False ):
            return 

        def worker ():
            ifaces =any_vpn_interface_active ()
            if ifaces :
                killed =[name for name in ifaces if force_down_interface (name )]

                def done ():
                    if killed :
                        self ._fire ("VPN Blocked 🛡",
                        f"A VPN connection ({', '.join (killed )}) was "
                        f"detected while the Shield is active and has "
                        f"been disconnected. Disable the Shield with "
                        f"your password to use a VPN.",
                        ok =False ,
                        native ="A VPN connection was detected and "
                        "disconnected while the Shield is active.")
                    self .after (self ._VPN_GUARD_INTERVAL_MS ,self ._vpn_guard_tick )
                self .after (0 ,done )
            else :
                self .after (self ._VPN_GUARD_INTERVAL_MS ,self ._vpn_guard_tick )

        threading .Thread (target =worker ,daemon =True ).start ()

    def _refresh_shield_ui (self ):
        self .shield_btn .set_active (self .shield_on )
        if hasattr (self ,"shield_aura"):
            self .shield_aura .set_active (self .shield_on )
        if hasattr (self ,"blocked_ticker"):
            self .blocked_ticker .set_active (self .shield_on )
        if self .shield_on :
            self .status_lbl .config (
            text ="🟢  Shield active — all categories blocking",fg =ACCENT )
        else :
            self .status_lbl .config (
            text ="⚪  Shield inactive",fg =MUTED )
        self ._update_tray_visual ()

    def _save_config_and_sync (self ):
        save_config (self .topics ,self ._lifetime ,self .theme_data )
        if self ._lifetime :
            self ._sync_lifetime_hosts ()

    def _sync_lifetime_hosts (self )->bool :
        if not self ._lifetime :
            return True 
        try :
            blocked =_combined_blocklist (self .topics )
            allow =getattr (self ,"allowlist",None )
            if allow is None :
                allow =load_allowlist ()
            domains =blocked -allow 
            ok ,msg =write_lifetime_hosts (domains )
            if not ok :
                log .warning (f"Lifetime hosts sync failed: {msg }")
            return ok 
        except Exception as e :
            log .warning (f"Lifetime hosts sync error: {e }")
            return False 

    def _disable_lifetime_hosts (self )->bool :
        try :
            ok ,msg =clear_lifetime_hosts ()
            if not ok :
                log .warning (f"Could not clear lifetime hosts block: {msg }")
            return ok 
        except Exception as e :
            log .warning (f"Error clearing lifetime hosts: {e }")
            return False 

    def _toggle_lifetime (self ):
        if not self ._lifetime :
            if not self ._require_admin ():return 
            self ._lifetime =True 
            self ._save_config_and_sync ()
            hosts_ok =_has_hosts_write_access ()
            try :set_startup_enabled (True )
            except Exception :pass 
            if not self .shield_on :
                try :
                    apply_blocking (self .topics )
                    self .shield_on =True 
                    self ._start_vpn_guard ()
                    self ._refresh_shield_ui ()
                    n =self ._total_all_domains ()
                    hosts_note =("" if hosts_ok else 
                    "\n\n⚠ The system hosts file couldn't be updated — "
                    "run Revolt as Administrator for full lifetime protection.")
                    self ._fire ("Shield Activated 🛡",
                    f"Lifetime mode — {{count}} domains blocked.\n\n“{SHIELD_QUOTE }”"+hosts_note ,
                    ok =True ,count_to =n ,
                    native =f"Lifetime mode — {n :,} domains are now blocked.")
                except Exception as e :
                    messagebox .showerror ("Error",str (e ))
            else :
                msg =("Shield auto-activates on every login, and the block "
                "list is now written directly into the system hosts file."
                if hosts_ok else 
                "Shield auto-activates on every login. The system hosts "
                "file couldn't be updated — run Revolt as Administrator "
                "for full lifetime protection.")
                Toast (self ,"Lifetime Active ♾",msg ,ok =hosts_ok )
        else :
            self ._lifetime =False 
            save_config (self .topics ,self ._lifetime ,self .theme_data )
            hosts_ok =self ._disable_lifetime_hosts ()
            try :set_startup_enabled (False )
            except Exception :pass 
            msg =("Shield will no longer auto-activate on startup, and the "
            "hosts file entries have been removed."if hosts_ok else 
            "Shield will no longer auto-activate on startup. The hosts "
            "file entries could not be removed automatically — you may "
            "need to run Revolt as Administrator to clear them.")
            Toast (self ,"Lifetime Disabled",msg ,ok =False )
        self .lifetime_btn .set_on (self ._lifetime )

    _CONNECTIVITY_HOSTS =(
    ("1.1.1.1",443 ),
    ("8.8.8.8",443 ),
    ("www.cloudflare.com",443 ),
    )

    _TEST_USER_AGENT =("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 Revolt/1.0")

    _DOWNLOAD_STREAMS =6 
    _UPLOAD_STREAMS =4 
    _TARGET_SECONDS =6.0 
    _MIN_BYTES_PER_STREAM =1_500_000 
    _MAX_BYTES_PER_STREAM =40_000_000 
    _LATENCY_SAMPLES =12 

    def _http_get (self ,url :str ,timeout :float ,max_bytes :int =None )->bytes :
        req =urllib .request .Request (url ,headers ={"User-Agent":self ._TEST_USER_AGENT })
        with urllib .request .urlopen (req ,timeout =timeout )as resp :
            return resp .read (max_bytes )if max_bytes else resp .read ()

    def _run_with_timeout (self ,fn ,timeout :float ):
        box ={}
        def target ():
            try :
                box ["value"]=fn ()
            except Exception as e :
                box ["error"]=e 
        t =threading .Thread (target =target ,daemon =True )
        t .start ()
        t .join (timeout )
        if t .is_alive ():
            raise TimeoutError (f"timed out after {timeout :.0f}s")
        if "error"in box :
            raise box ["error"]
        return box .get ("value")

    def _parallel_transfer (self ,make_task ,count :int ,timeout :float ):
        results =[None ]*count 
        finish_times =[None ]*count 
        errors =[None ]*count 

        def run (i ):
            try :
                results [i ]=make_task ()
                finish_times [i ]=time .time ()
            except Exception as e :
                errors [i ]=e 

        threads =[threading .Thread (target =run ,args =(i ,),daemon =True )
        for i in range (count )]
        t_start =time .time ()
        for t in threads :
            t .start ()
        deadline =t_start +timeout 
        for t in threads :
            t .join (max (0.05 ,deadline -time .time ()))

        done =[i for i in range (count )if finish_times [i ]is not None ]
        if not done :
            raise next ((e for e in errors if e is not None ),
            TimeoutError ("no stream completed in time"))
        total_bytes =sum (results [i ]for i in done )
        elapsed =max (max (finish_times [i ]for i in done )-t_start ,0.001 )
        return total_bytes ,elapsed 

    def _measure_latency (self ,host :str ,port :int )->tuple :
        samples =[]
        for _ in range (self ._LATENCY_SAMPLES ):
            t0 =time .time ()
            with socket .create_connection ((host ,port ),timeout =4 ):
                pass 
            samples .append ((time .time ()-t0 )*1000 )
        warm =samples [2 :]if len (samples )>2 else samples 
        sorted_warm =sorted (warm )
        median =sorted_warm [len (sorted_warm )//2 ]
        if len (warm )>1 :
            diffs =[abs (warm [i ]-warm [i -1 ])for i in range (1 ,len (warm ))]
            jitter =sum (diffs )/len (diffs )
        else :
            jitter =0.0 
        return median ,jitter 

    def _select_best_server (self ,timeout_each :float =3.0 ):
        best ={}
        def probe (h ,p ):
            try :
                t0 =time .time ()
                with socket .create_connection ((h ,p ),timeout =timeout_each ):
                    pass 
                best [(h ,p )]=(time .time ()-t0 )*1000 
            except Exception :
                pass 
        threads =[threading .Thread (target =probe ,args =hp ,daemon =True )
        for hp in self ._CONNECTIVITY_HOSTS ]
        for t in threads :
            t .start ()
        for t in threads :
            t .join (timeout_each +0.5 )
        if not best :
            return None 
        return min (best ,key =best .get )

    def _measure_download_mbps (self )->float :

        try :
            t0 =time .time ()
            warm_bytes =len (self ._run_with_timeout (
            lambda :self ._http_get (
            "https://speed.cloudflare.com/__down?bytes=750000",
            timeout =6 ,max_bytes =750_000 ),8 ))
            rough_mbps =(warm_bytes *8 /1_000_000 )/max (time .time ()-t0 ,0.05 )
        except Exception :
            rough_mbps =20.0 

        bytes_per_stream =int (min (max (
        (rough_mbps *1_000_000 /8 *self ._TARGET_SECONDS )/self ._DOWNLOAD_STREAMS ,
        self ._MIN_BYTES_PER_STREAM ),self ._MAX_BYTES_PER_STREAM ))

        def one_stream ():
            return len (self ._http_get (
            f"https://speed.cloudflare.com/__down?bytes={bytes_per_stream }",
            timeout =20 ,max_bytes =bytes_per_stream ))

        total_bytes ,elapsed =self ._parallel_transfer (
        one_stream ,self ._DOWNLOAD_STREAMS ,timeout =25 )
        return (total_bytes *8 /1_000_000 )/elapsed 

    def _measure_upload_mbps (self )->float :
        try :
            payload =secrets .token_bytes (500_000 )
            t0 =time .time ()
            req =urllib .request .Request (
            "https://speed.cloudflare.com/__up",data =payload ,method ="POST",
            headers ={"User-Agent":self ._TEST_USER_AGENT ,
            "Content-Type":"application/octet-stream"})
            self ._run_with_timeout (
            lambda :urllib .request .urlopen (req ,timeout =6 ).read (),8 )
            rough_mbps =(len (payload )*8 /1_000_000 )/max (time .time ()-t0 ,0.05 )
        except Exception :
            rough_mbps =10.0 

        bytes_per_stream =int (min (max (
        (rough_mbps *1_000_000 /8 *self ._TARGET_SECONDS )/self ._UPLOAD_STREAMS ,
        self ._MIN_BYTES_PER_STREAM ),self ._MAX_BYTES_PER_STREAM ))

        def one_stream ():
            payload =secrets .token_bytes (bytes_per_stream )
            req =urllib .request .Request (
            "https://speed.cloudflare.com/__up",data =payload ,method ="POST",
            headers ={"User-Agent":self ._TEST_USER_AGENT ,
            "Content-Type":"application/octet-stream"})
            with urllib .request .urlopen (req ,timeout =20 )as resp :
                resp .read ()
            return bytes_per_stream 

        total_bytes ,elapsed =self ._parallel_transfer (
        one_stream ,self ._UPLOAD_STREAMS ,timeout =25 )
        return (total_bytes *8 /1_000_000 )/elapsed 

    def _test_internet (self ):
        if getattr (self ,"_testing_internet",False ):
            return 
        self ._testing_internet =True 
        self .test_internet_btn .config (text ="🌐  Testing…")

        def worker ():
            ok ,latency_ms ,jitter_ms ,down_mbps ,up_mbps ,detail =False ,None ,None ,None ,None ,""
            try :

                try :
                    best =self ._run_with_timeout (self ._select_best_server ,6 )
                except Exception :
                    best =None 
                ordered_hosts =(
                [best ]+[h for h in self ._CONNECTIVITY_HOSTS if h !=best ]
                if best else list (self ._CONNECTIVITY_HOSTS ))

                for host ,port in ordered_hosts :
                    try :
                        latency_ms ,jitter_ms =self ._run_with_timeout (
                        lambda h =host ,p =port :self ._measure_latency (h ,p ),8 )
                        latency_ms =int (round (latency_ms ))
                        jitter_ms =round (jitter_ms ,1 )
                        ok =True 
                        break 
                    except Exception as e :
                        detail =f"{host }: {e }"

                if ok :
                    self .after (0 ,lambda :self .test_internet_btn .config (
                    text ="🌐  Measuring download…"))
                    try :
                        down_mbps =self ._run_with_timeout (self ._measure_download_mbps ,30 )
                    except Exception :
                        pass 

                    self .after (0 ,lambda :self .test_internet_btn .config (
                    text ="🌐  Measuring upload…"))
                    try :
                        up_mbps =self ._run_with_timeout (self ._measure_upload_mbps ,30 )
                    except Exception :
                        pass 
            except Exception as e :

                ok =False 
                detail =detail or str (e )
            finally :
                self .after (0 ,lambda :self ._report_internet_test (
                ok ,latency_ms ,jitter_ms ,down_mbps ,up_mbps ,detail ))

        threading .Thread (target =worker ,daemon =True ).start ()

    def _report_internet_test (self ,ok :bool ,latency_ms ,jitter_ms ,
    down_mbps ,up_mbps ,detail :str ):
        self ._testing_internet =False 
        self .test_internet_btn .config (text ="🌐  Test Your Internet")
        if ok :
            parts =[]
            if down_mbps is not None :
                parts .append (f"{down_mbps :.1f} Mbps ↓")
            if up_mbps is not None :
                parts .append (f"{up_mbps :.1f} Mbps ↑")
            speed_txt =", "+" / ".join (parts )if parts else ""
            jitter_txt =f", {jitter_ms :.1f} ms jitter"if jitter_ms is not None else ""
            note =""
            if down_mbps is None and up_mbps is None :
                note =(" (speed sample failed — connection is up, but the "
                "speed-test server didn't respond in time)")
            shield_note =(" Shield stays active — blocked sites are still blocked."
            if self .shield_on else "")
            self ._fire ("Internet Connected ✓",
            f"You're online ({latency_ms } ms{jitter_txt }{speed_txt })."
            f"{note }{shield_note }",
            ok =True ,
            native =f"Internet check passed ({latency_ms } ms{speed_txt }).",
            duration_ms =10000 )
        else :
            detail_txt =f"\n\nDetails: {detail }"if detail else ""
            self ._fire ("No Internet ✗",
            "Couldn't reach the internet. Check your Wi-Fi, "
            f"ethernet, or router connection.{detail_txt }",
            ok =False ,
            native ="Internet check failed — no connection detected.",
            duration_ms =10000 )

    def _refresh_dns_btn_label (self ):
        label =self .custom_dns if self .custom_dns else "Default"
        self .dns_btn .config (text =f"⚙  Custom DNS: {label }")

    def _open_custom_dns_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Custom DNS")
        win .geometry ("420x340")
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =24 ,pady =20 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Custom DNS",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="This actually changes your computer's network DNS — "
        "your ISP's, your router's, or a public one like 9.9.9.9 "
        "or 8.8.8.8 — the same as setting it in Windows/macOS "
        "network settings.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =370 ,justify ="left").pack (anchor ="w",pady =(4 ,6 ))
        tk .Label (body ,
        text ="🛡  This never weakens the Shield: while it's active, "
        "your adapter's PRIMARY resolver stays locked to Revolt's "
        "own filter no matter what you set here — your custom "
        "server can only ever sit as a secondary, so blocked sites "
        "still get sinkholed either way.",
        font =(FONT_FAMILY ,9 ,"bold"),fg =ACCENT ,bg =BG ,anchor ="w",
        wraplength =370 ,justify ="left").pack (anchor ="w",pady =(0 ,14 ))

        tk .Label (body ,text ="DNS Server IP",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,3 ))
        wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        wrap .pack (fill ="x")
        entry =tk .Entry (wrap ,font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        entry .pack (fill ="x",ipady =8 ,padx =8 )
        if self .custom_dns :
            entry .insert (0 ,self .custom_dns )

        tk .Label (body ,
        text ="Leave blank and click \"Use Default\" to go back to "
        "the built-in resolver (1.1.1.1).",
        font =(FONT_FAMILY ,8 ),fg =darken (MUTED ,.1 ),bg =BG ,
        anchor ="w",wraplength =370 ,justify ="left"
        ).pack (anchor ="w",pady =(4 ,0 ))

        def do_save (clear =False ):
            ip =""if clear else entry .get ().strip ()
            if ip and not is_valid_ipv4 (ip ):
                messagebox .showwarning ("Invalid IP",
                "Enter a valid IPv4 address (e.g. 9.9.9.9), or use "
                "\"Use Default\" instead.",parent =win )
                return 
            self .custom_dns =ip or None 
            save_custom_dns (self .custom_dns )
            set_custom_dns_ip (self .custom_dns )
            apply_direct_custom_dns_async ()
            self ._refresh_dns_btn_label ()
            win .destroy ()
            label =self .custom_dns or "the default resolver (1.1.1.1)"
            shield_note =(" (applied as a backup resolver — the Shield "
            "keeps itself as the primary DNS so blocked sites stay "
            "blocked)"if detect_shield ()else "")
            self ._fire ("Custom DNS Saved",
            f"Now using {label } for everyday lookups{shield_note }. "
            "Blocked sites are still blocked.",ok =True ,
            native =f"Custom DNS set to {label }.")

        footer =tk .Frame (body ,bg =BG )
        footer .pack (fill ="x",pady =(18 ,0 ))
        FlatBtn (footer ,text ="Save",base_bg =ACCENT ,hover_bg =lighten (ACCENT ,.1 ),
        fg =BG ,font =(FONT_FAMILY ,12 ,"bold"),command =do_save ,
        radius =18 ,height =38 ,width =90 ).pack (side ="left")
        FlatBtn (footer ,text ="Use Default",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),
        font =(FONT_FAMILY ,12 ,"bold"),
        command =lambda :do_save (clear =True ),
        radius =18 ,height =38 ,width =118 ).pack (side ="left",padx =(8 ,0 ))
        FlatBtn (footer ,text ="Cancel",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =18 ,height =38 ,width =90 
        ).pack (side ="left",padx =(8 ,0 ))

    def _open_live_feed_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Live Blocked Feed")
        win .geometry ("460x620")
        win .minsize (380 ,420 )
        win .resizable (True ,True )
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()

        body =tk .Frame (win ,bg =BG ,padx =22 ,pady =18 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Live Blocked Feed",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Every domain the Shield sinkholes, as it happens — "
        "newest at the top. Each entry's category fills in a "
        "moment after it appears.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =410 ,justify ="left").pack (anchor ="w",pady =(4 ,10 ))

        status_row =tk .Frame (body ,bg =BG )
        status_row .pack (fill ="x",pady =(0 ,8 ))
        status_dot =tk .Canvas (status_row ,width =9 ,height =9 ,bg =BG ,
        highlightthickness =0 )
        status_dot .pack (side ="left")
        status_lbl =tk .Label (status_row ,text ="",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w")
        status_lbl .pack (side ="left",padx =(6 ,0 ))

        list_wrap =tk .Frame (body ,bg =BG )
        list_wrap .pack (fill ="both",expand =True )
        canvas =tk .Canvas (list_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (list_wrap ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )
        rows_frame =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =rows_frame ,anchor ="nw")
        rows_frame .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        def _wheel (event ):
            if getattr (event ,"num",None )==4 :
                canvas .yview_scroll (-1 ,"units")
            elif getattr (event ,"num",None )==5 :
                canvas .yview_scroll (1 ,"units")
            else :
                canvas .yview_scroll (int (-event .delta /120 ),"units")
            return "break"
        canvas .bind ("<MouseWheel>",_wheel )
        canvas .bind ("<Button-4>",_wheel )
        canvas .bind ("<Button-5>",_wheel )

        state ={"open":True ,"cat_cache":{},"pending":set ()}

        def resolve_category (domain ):
            if domain in state ["cat_cache"]or domain in state ["pending"]:
                return 
            state ["pending"].add (domain )
            def worker ():
                try :
                    info =check_site_status (domain ,self .topics ,self .allowlist )
                    cat =info .get ("source")if info .get ("valid")else None 
                except Exception :
                    cat =None 
                def done ():
                    state ["pending"].discard (domain )
                    state ["cat_cache"][domain ]=cat or "Uncategorized"
                    if state ["open"]:
                        render ()
                try :
                    self .after (0 ,done )
                except Exception :
                    pass 
            threading .Thread (target =worker ,daemon =True ).start ()

        def render ():
            entries =get_recent_blocked (80 )
            for w in rows_frame .winfo_children ():
                w .destroy ()
            if not entries :
                tk .Label (rows_frame ,text ="Nothing blocked yet this session.",
                font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG 
                ).pack (pady =(10 ,6 ))
                return 
            for e in entries :
                domain =e ["domain"]or "(unknown)"
                cat =state ["cat_cache"].get (domain )
                if cat is None :
                    resolve_category (domain )
                card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                highlightbackground =BORDER )
                card .pack (fill ="x",pady =(0 ,6 ),padx =2 )
                inner =tk .Frame (card ,bg =CARD ,padx =10 ,pady =7 )
                inner .pack (fill ="x")
                top =tk .Frame (inner ,bg =CARD )
                top .pack (fill ="x")
                tk .Label (top ,text =f"⛔  {domain }",font =(FONT_FAMILY ,10 ,"bold"),
                fg =TEXT ,bg =CARD ,anchor ="w").pack (side ="left")
                tk .Label (top ,text =_fmt_ago (e ["ts"]),font =(FONT_FAMILY ,9 ),
                fg =MUTED ,bg =CARD ,anchor ="e").pack (side ="right")
                tk .Label (inner ,text =(cat if cat else "resolving category…"),
                font =(FONT_FAMILY ,9 ),
                fg =(MUTED if cat else ACCENT2 ),
                bg =CARD ,anchor ="w").pack (anchor ="w",pady =(1 ,0 ))

        def poll ():
            if not state ["open"]:
                return 
            on =detect_shield ()
            status_dot .delete ("all")
            status_dot .create_oval (1 ,1 ,8 ,8 ,fill =(ACCENT if on else MUTED ),
            outline ="")
            status_lbl .config (
            text =(f"Shield is on — {get_blocked_count ():,} blocked this session"
            if on else "Shield is off — feed will resume once it's on"),
            fg =(TEXT if on else MUTED ))
            render ()
            win .after (1000 ,poll )
        poll ()

        def close ():
            state ["open"]=False 
            win .destroy ()
        win .protocol ("WM_DELETE_WINDOW",close )

        FlatBtn (body ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =close ,radius =14 ,height =32 ,width =90 
        ).pack (anchor ="e",pady =(12 ,0 ))

    def _open_check_site_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Check a Site")
        win .geometry ("440x460")
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =24 ,pady =20 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Check a Site",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Type a domain to instantly see whether the Shield "
        "would block it right now — and which category or "
        "feed catches it — or ping it to check whether it's "
        "simply down.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =390 ,justify ="left").pack (anchor ="w",pady =(4 ,14 ))

        tk .Label (body ,text ="Domain",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,3 ))
        wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        wrap .pack (fill ="x")
        entry =tk .Entry (wrap ,font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        entry .pack (fill ="x",ipady =8 ,padx =8 )
        entry .insert (0 ,"example.com")
        entry .focus_set ()
        entry .select_range (0 ,"end")

        result_card =tk .Frame (body ,bg =TOOLBAR ,highlightthickness =1 ,
        highlightbackground =BORDER )
        result_card .pack (fill ="x",pady =(16 ,0 ))
        result_inner =tk .Frame (result_card ,bg =TOOLBAR ,padx =14 ,pady =12 )
        result_inner .pack (fill ="x")

        status_lbl =tk .Label (result_inner ,text ="Enter a domain above and "
        "run a check.",font =(FONT_FAMILY ,13 ,"bold"),
        fg =MUTED ,bg =TOOLBAR ,anchor ="w",
        justify ="left",wraplength =370 )
        status_lbl .pack (anchor ="w",fill ="x")
        detail_lbl =tk .Label (result_inner ,text ="",font =(FONT_FAMILY ,10 ),
        fg =MUTED ,bg =TOOLBAR ,anchor ="w",
        justify ="left",wraplength =370 )
        detail_lbl .pack (anchor ="w",fill ="x",pady =(4 ,0 ))

        GREEN ="#3ddc97"

        def set_result (text ,color ,detail =""):
            status_lbl .config (text =text ,fg =color )
            detail_lbl .config (text =detail )

        def do_check ():
            raw =entry .get ().strip ()
            if not raw :
                set_result ("Enter a domain first.",WARN )
                return 
            res =check_site_status (raw ,self .topics ,self .allowlist )
            if not res .get ("valid"):
                set_result ("⚠  That doesn't look like a valid domain.",WARN )
                return 
            d =res ["domain"]
            if res .get ("allowlisted"):
                set_result (f"✅  {d } is always allowed",GREEN ,
                "It's on your allowlist — never blocked, even "
                "if it also appears on a blocklist.")
            elif res .get ("blocked"):
                origin =res .get ("origin")or ""
                cat =res .get ("source")or "Unknown"
                extra =f"  ·  {origin }"if origin else ""
                set_result (f"🚫  {d } is blocked",DANGER ,
                f"Caught by category: {cat }{extra }")
            else :
                set_result (f"✅  {d } is not blocked",GREEN ,
                "It doesn't match anything on your active "
                "blocklists or subscribed feeds right now.")

        def do_ping ():
            raw =entry .get ().strip ()
            if not raw :
                set_result ("Enter a domain first.",WARN )
                return 
            d =clean_domain (raw )
            if not d :
                set_result ("⚠  That doesn't look like a valid domain.",WARN )
                return 
            ping_btn .config (text ="📶  Pinging…")

            def worker ():
                res =ping_site (d )

                def report ():
                    ping_btn .config (text ="📶  Ping Site")
                    if not res .get ("resolved"):
                        set_result (f"⚠  Couldn't resolve {d }",WARN ,
                        "No DNS record found — double-check the "
                        "spelling, or the site may not exist.")
                    elif res .get ("up"):
                        ms =res .get ("latency_ms")
                        ip =res ["ips"][0 ]if res .get ("ips")else "?"
                        note =""
                        if self .shield_on :
                            note =("  Shield is on — a blocked site would "
                            "instead resolve to your own machine "
                            "and fail this ping, not pass it.")
                        set_result (f"🟢  {d } is up ({ms } ms)",GREEN ,
                        f"Responded from {ip }.{note }")
                    else :
                        set_result (f"🔴  {d } looks down",DANGER ,
                        "Resolved fine, but didn't respond on "
                        "port 443 or 80 — it may be down, "
                        "blocked, or just slow to answer.")
                self .after (0 ,report )

            threading .Thread (target =worker ,daemon =True ).start ()

        entry .bind ("<Return>",lambda e :do_check ())

        btn_row =tk .Frame (body ,bg =BG )
        btn_row .pack (fill ="x",pady =(20 ,0 ))
        FlatBtn (btn_row ,text ="🔎  Check Block Status",base_bg =ACCENT ,
        hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
        font =(FONT_FAMILY ,12 ,"bold"),command =do_check ,
        radius =18 ,height =38 ,width =190 ).pack (side ="left")
        ping_btn =FlatBtn (btn_row ,text ="📶  Ping Site",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),
        font =(FONT_FAMILY ,12 ,"bold"),command =do_ping ,
        radius =18 ,height =38 ,width =140 )
        ping_btn .pack (side ="left",padx =(8 ,0 ))

        FlatBtn (body ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =18 ,height =34 ,width =90 
        ).pack (anchor ="e",pady =(16 ,0 ))

    def _refresh_vpn_btn_label (self ):
        active =vpn_is_active ()
        if active :
            self .vpn_btn .config (text ="🔒  VPN Connected",fg ="#3ddc97")
        else :
            self .vpn_btn .config (text ="🔒  Connect VPN",fg =TEXT )

    def _open_vpn_dialog (self ):
        cfg =load_vpn_config ()

        win =tk .Toplevel (self )
        win .title ("Connect VPN")
        win .geometry ("460x540")
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =24 ,pady =20 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Connect VPN",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,14 ))

        tk .Label (body ,text ="VPN Type",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,3 ))
        kind_row =tk .Frame (body ,bg =BG )
        kind_row .pack (anchor ="w")
        kind_state ={"kind":cfg .get ("kind")or "wireguard"}

        relay_note_lbl =tk .Label (body ,
        text ="VPN Gate (the free relay list below) only carries "
        "OpenVPN — there's no equivalent trusted, no-signup "
        "source for WireGuard relays. Use \"Get a Free VPN\" "
        "for a WireGuard config instead.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =405 ,justify ="left")

        def refresh_kind_buttons ():
            wg_on =kind_state ["kind"]=="wireguard"
            wg_btn .config (text =("● "if wg_on else "○ ")+"WireGuard",
            fg =ACCENT if wg_on else MUTED )
            ovpn_btn .config (text =("● "if not wg_on else "○ ")+"OpenVPN",
            fg =ACCENT if not wg_on else MUTED )
            if wg_on :
                relay_note_lbl .pack (anchor ="w",pady =(6 ,0 ),before =config_hdr_lbl )
            else :
                relay_note_lbl .pack_forget ()

        def pick_kind (k ):
            kind_state ["kind"]=k 
            refresh_kind_buttons ()

        wg_btn =FlatBtn (kind_row ,text ="",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =MUTED ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =14 ,
        font =(FONT_FAMILY ,10 ,"bold"),
        command =lambda :pick_kind ("wireguard"),
        height =32 ,width =130 )
        wg_btn .pack (side ="left")
        ovpn_btn =FlatBtn (kind_row ,text ="",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =MUTED ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =14 ,
        font =(FONT_FAMILY ,10 ,"bold"),
        command =lambda :pick_kind ("openvpn"),
        height =32 ,width =130 )
        ovpn_btn .pack (side ="left",padx =(8 ,0 ))

        config_hdr_lbl =tk .Label (body ,text ="Config File",
        font =(FONT_FAMILY ,10 ,"bold"),fg =TEXT ,bg =BG ,anchor ="w")
        config_hdr_lbl .pack (anchor ="w",pady =(16 ,3 ))
        file_row =tk .Frame (body ,bg =BG )
        file_row .pack (fill ="x")
        path_state ={"path":cfg .get ("config_path")or ""}
        path_lbl =tk .Label (file_row ,
        text =os .path .basename (path_state ["path"])if path_state ["path"]
        else "No file selected",
        font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG ,anchor ="w")
        path_lbl .pack (side ="left",fill ="x",expand =True )

        def choose_file ():
            kind =kind_state ["kind"]
            ft =[("WireGuard config","*.conf")]if kind =="wireguard"else [("OpenVPN config","*.ovpn")]
            p =filedialog .askopenfilename (title ="Select VPN Config",
            filetypes =ft +[("All files","*.*")])
            if p :
                path_state ["path"]=p 
                path_lbl .config (text =os .path .basename (p ),fg =TEXT )
                save_vpn_config ({"config_path":p ,"kind":kind })

        FlatBtn (file_row ,text ="Browse…",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =14 ,
        font =(FONT_FAMILY ,10 ,"bold"),command =choose_file ,
        height =32 ,width =100 ).pack (side ="right",padx =(10 ,0 ))

        def on_relay_selected (path ,kind ):
            kind_state ["kind"]=kind 
            path_state ["path"]=path 
            path_lbl .config (text =os .path .basename (path ),fg =TEXT )
            refresh_kind_buttons ()
            save_vpn_config ({"config_path":path ,"kind":kind })

        quick_row =tk .Frame (body ,bg =BG )
        quick_row .pack (fill ="x",pady =(10 ,0 ))
        FlatBtn (quick_row ,text ="🌍  Browse Free OpenVPN Relays",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =14 ,
        font =(FONT_FAMILY ,10 ,"bold"),
        command =lambda :self ._open_vpngate_browser (win ,on_relay_selected ),
        height =32 ,width =220 ).pack (side ="left")
        FlatBtn (quick_row ,text ="🔗  Get a Free VPN",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =14 ,
        font =(FONT_FAMILY ,10 ,"bold"),
        command =self ._open_get_vpn_dialog ,
        height =32 ,width =170 ).pack (side ="left",padx =(8 ,0 ))

        status_frame =tk .Frame (body ,bg =TOOLBAR ,highlightthickness =1 ,
        highlightbackground =BORDER )
        status_frame .pack (fill ="x",pady =(20 ,0 ))
        status_inner =tk .Frame (status_frame ,bg =TOOLBAR ,padx =14 ,pady =12 )
        status_inner .pack (fill ="x")
        status_lbl =tk .Label (status_inner ,text ="",font =(FONT_FAMILY ,13 ,"bold"),
        fg =MUTED ,bg =TOOLBAR ,anchor ="w",justify ="left",
        wraplength =380 )
        status_lbl .pack (anchor ="w",fill ="x")
        detail_lbl =tk .Label (status_inner ,text ="",font =(FONT_FAMILY ,10 ),
        fg =MUTED ,bg =TOOLBAR ,anchor ="w",justify ="left",
        wraplength =380 )
        detail_lbl .pack (anchor ="w",fill ="x",pady =(4 ,0 ))

        def refresh_status ():
            if vpn_is_active ():
                status_lbl .config (text ="🟢  Connected",fg ="#3ddc97")
                detail_lbl .config (text ="Traffic is routed through your VPN. "
                "Most VPNs push their own DNS, which "
                "bypasses the Shield's sinkhole — "
                "that's why connecting while the "
                "Shield is on requires the same "
                "password/cooldown as disabling it.")
                connect_btn .config (text ="Disconnect")
            else :
                status_lbl .config (text ="⚪  Disconnected",fg =MUTED )
                detail_lbl .config (text ="Pick a config file above, then connect.")
                connect_btn .config (text ="🔒  Connect")
            self ._refresh_vpn_btn_label ()

        def do_toggle ():
            if not path_state ["path"]or not os .path .exists (path_state ["path"]):
                messagebox .showwarning ("No Config Selected",
                "Choose a WireGuard (.conf) or OpenVPN (.ovpn) config "
                "file first.",parent =win )
                return 
            kind =kind_state ["kind"]
            path =path_state ["path"]
            going_up =not vpn_is_active ()

            if going_up and self .shield_on :
                if not self ._authorize_disable ():
                    return 
                try :
                    remove_blocking ()
                except Exception :
                    pass 
                self .shield_on =False 
                self ._stop_vpn_guard ()
                self ._refresh_shield_ui ()
                self ._fire ("Shield Disabled",
                "Disabled to connect the VPN.",ok =False ,
                native ="The Shield was disabled so the VPN "
                "could connect.")
            connect_btn .config (text ="Connecting…"if going_up else "Disconnecting…")

            def worker ():
                if going_up :
                    ok ,msg =connect_vpn (path ,kind )
                else :
                    ok ,msg =disconnect_vpn (path ,kind )

                def done ():
                    if win .winfo_exists ():
                        refresh_status ()
                        detail_lbl .config (text =msg )
                    self ._fire ("VPN Connected"if (going_up and ok )else 
                    "VPN Disconnected"if (not going_up and ok )else 
                    "VPN Error",msg ,ok =ok )
                self .after (0 ,done )

            threading .Thread (target =worker ,daemon =True ).start ()

        btn_row =tk .Frame (body ,bg =BG )
        btn_row .pack (fill ="x",pady =(20 ,0 ))
        connect_btn =FlatBtn (btn_row ,text ="🔒  Connect",base_bg =ACCENT ,
        hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
        font =(FONT_FAMILY ,12 ,"bold"),command =do_toggle ,
        radius =18 ,height =38 ,width =160 )
        connect_btn .pack (side ="left")
        FlatBtn (btn_row ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =18 ,height =38 ,width =90 
        ).pack (side ="left",padx =(8 ,0 ))

        refresh_kind_buttons ()
        refresh_status ()

    def _open_vpngate_browser (self ,parent_win ,on_selected ):
        win =tk .Toplevel (parent_win )
        win .title ("Free Community Relays — VPN Gate")
        win .geometry ("520x500")
        win .configure (bg =BG )
        win .transient (parent_win )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =20 ,pady =18 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Free Community Relays",font =(FONT_FAMILY ,15 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Pulled live from VPN Gate (vpngate.net) — a public "
        "relay directory run by the University of Tsukuba "
        "since 2011, not an anonymous list. That said, "
        "individual relays are volunteer-run and NOT audited "
        "for logging — fine for basic unblocking, not a "
        "substitute for a real privacy VPN. Sorted by "
        "reliability score.",
        font =(FONT_FAMILY ,9 ),fg =WARN ,bg =BG ,anchor ="w",
        wraplength =470 ,justify ="left").pack (anchor ="w",pady =(4 ,12 ))

        search_wrap =tk .Frame (body ,bg =ENTRY ,highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        search_wrap .pack (fill ="x",pady =(0 ,10 ))
        IconGlyph (search_wrap ,"🔍",size =14 ,color =MUTED ,bg =ENTRY 
        ).pack (side ="left",padx =(10 ,2 ))
        search_var =tk .StringVar ()
        search_entry =tk .Entry (search_wrap ,textvariable =search_var ,
        font =(FONT_FAMILY ,12 ),bd =0 ,relief ="flat",
        bg =ENTRY ,fg =TEXT ,insertbackground =ACCENT )
        search_entry .pack (side ="left",fill ="x",expand =True ,ipady =8 ,padx =(0 ,10 ))
        search_entry .focus_set ()

        list_wrap =tk .Frame (body ,bg =BG )
        list_wrap .pack (fill ="both",expand =True )
        canvas =tk .Canvas (list_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (list_wrap ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )
        rows_frame =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =rows_frame ,anchor ="nw")
        rows_frame .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        def _wheel (event ):
            canvas .yview_scroll (int (-event .delta /60 )if event .delta else 0 ,"units")
        canvas .bind ("<Enter>",lambda e :canvas .bind_all ("<MouseWheel>",_wheel ))
        canvas .bind ("<Leave>",lambda e :canvas .unbind_all ("<MouseWheel>"))

        status_lbl =tk .Label (body ,text ="Loading relays…",font =(FONT_FAMILY ,10 ),
        fg =MUTED ,bg =BG )
        status_lbl .pack (anchor ="w",pady =(8 ,0 ))

        def use_relay (relay ):
            status_lbl .config (text =f"Preparing {relay ['ip']}…")
            def worker ():
                path =save_vpngate_config (relay )
                def done ():
                    if not path :
                        if win .winfo_exists ():
                            status_lbl .config (text ="Couldn't decode that "
                            "relay's config — try another one.")
                        return 
                    on_selected (path ,"openvpn")
                    if win .winfo_exists ():
                        win .destroy ()
                self .after (0 ,done )
            threading .Thread (target =worker ,daemon =True ).start ()

        def render (relays ):
            if not win .winfo_exists ():
                return 
            for w in rows_frame .winfo_children ():
                w .destroy ()
            if not relays :
                status_lbl .config (text ="Couldn't reach VPN Gate — check "
                "your internet connection and try again.")
                return 
            query =search_var .get ().strip ().lower ()
            if query :
                shown =[r for r in relays if 
                query in r ["country_long"].lower ()
                or query in r ["country_short"].lower ()
                or query in r ["ip"].lower ()
                or query in r ["host"].lower ()]
            else :
                shown =relays 
            if not shown :
                status_lbl .config (text =f"No relays match \"{query }\" "
                f"— {len (relays )} total available.")
                return 
            count_txt =(f"{len (shown )} of {len (relays )} relays match."
            if query else f"{len (relays )} relays available.")
            status_lbl .config (text =count_txt )
            for r in shown [:140 ]:
                row =tk .Frame (rows_frame ,bg =TOOLBAR ,highlightthickness =1 ,
                highlightbackground =BORDER )
                row .pack (fill ="x",pady =3 )
                inner =tk .Frame (row ,bg =TOOLBAR ,padx =10 ,pady =8 )
                inner .pack (fill ="x")
                text_col =tk .Frame (inner ,bg =TOOLBAR )
                text_col .pack (side ="left",fill ="x",expand =True )
                ping_txt =f"{r ['ping_ms']} ms"if r ['ping_ms']is not None else "? ms"
                speed_txt =f"{r ['speed_mbps']} Mbps"if r ['speed_mbps']is not None else "? Mbps"
                tk .Label (text_col ,text =f"{r ['country_long']}  ·  {r ['ip']}",
                font =(FONT_FAMILY ,12 ,"bold"),fg =TEXT ,bg =TOOLBAR ,
                anchor ="w").pack (anchor ="w")
                tk .Label (text_col ,text =f"ping {ping_txt }   ·   {speed_txt }"
                f"   ·   score {r ['score']:,}",
                font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =TOOLBAR ,
                anchor ="w").pack (anchor ="w")
                FlatBtn (inner ,text ="Use",base_bg =ACCENT ,
                hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
                font =(FONT_FAMILY ,10 ,"bold"),
                command =lambda relay =r :use_relay (relay ),
                radius =12 ,height =30 ,width =66 ).pack (side ="right")

        _relay_cache ={"all":[]}

        def worker ():
            relays =fetch_vpngate_relays ()
            _relay_cache ["all"]=relays 
            self .after (0 ,lambda :render (relays ))
        threading .Thread (target =worker ,daemon =True ).start ()

        search_var .trace_add ("write",
        lambda *a :render (_relay_cache ["all"]))

        FlatBtn (body ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =14 ,height =32 ,width =90 
        ).pack (anchor ="e",pady =(10 ,0 ))

    def _open_get_vpn_dialog (self ):
        win =tk .Toplevel (self )
        win .title ("Get a Free VPN")
        win .geometry ("440x460")
        win .configure (bg =BG )
        win .transient (self )
        win .grab_set ()
        win .resizable (False ,False )

        body =tk .Frame (win ,bg =BG ,padx =22 ,pady =18 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Get a Free VPN",font =(FONT_FAMILY ,15 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(0 ,14 ))

        providers =[
        ("ProtonVPN Free","WireGuard + OpenVPN configs — free tier",
        "No data cap · 1 device · the one free provider here whose "
        "WireGuard export isn't paywalled.",
        "https://protonvpn.com/free-vpn"),
        ("Windscribe Free","OpenVPN/IKEv2 configs — WireGuard is Premium-only",
        "10GB/month · pick OpenVPN in Revolt's VPN Type selector "
        "for this one.",
        "https://windscribe.com/features"),
        ]
        for name ,proto_note ,desc ,url in providers :
            card =tk .Frame (body ,bg =TOOLBAR ,highlightthickness =1 ,
            highlightbackground =BORDER )
            card .pack (fill ="x",pady =5 )
            inner =tk .Frame (card ,bg =TOOLBAR ,padx =12 ,pady =10 )
            inner .pack (fill ="x")
            text_col =tk .Frame (inner ,bg =TOOLBAR )
            text_col .pack (side ="left",fill ="x",expand =True )
            tk .Label (text_col ,text =name ,font =(FONT_FAMILY ,12 ,"bold"),
            fg =TEXT ,bg =TOOLBAR ,anchor ="w").pack (anchor ="w")
            tk .Label (text_col ,text =proto_note ,font =(FONT_FAMILY ,9 ,"bold"),
            fg =ACCENT ,bg =TOOLBAR ,anchor ="w",wraplength =230 ,
            justify ="left").pack (anchor ="w",pady =(2 ,0 ))
            tk .Label (text_col ,text =desc ,font =(FONT_FAMILY ,9 ),fg =MUTED ,
            bg =TOOLBAR ,anchor ="w",wraplength =230 ,
            justify ="left").pack (anchor ="w",pady =(2 ,0 ))
            FlatBtn (inner ,text ="Open",base_bg =ACCENT ,
            hover_bg =lighten (ACCENT ,.1 ),fg =BG ,
            font =(FONT_FAMILY ,10 ,"bold"),
            command =lambda u =url :webbrowser .open (u ),
            radius =12 ,height =30 ,width =70 ).pack (side ="right")

        FlatBtn (body ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =win .destroy ,radius =14 ,height =32 ,width =90 
        ).pack (anchor ="e",pady =(14 ,0 ))

    def _refresh_hotspot_btn_label (self ):
        try :
            st =hotspot_status ()
        except Exception :
            st ={"running":False }
        if st .get ("running"):
            self .hotspot_btn .config (text ="📶  Hotspot On",fg ="#3ddc97")
        else :
            self .hotspot_btn .config (text ="📶  Hotspot",fg =TEXT )

    def _offer_ics_retry (self ,parent ,reason ):
        if not messagebox .askyesno (
        "Turn On Internet Sharing?",
        "Your hotspot Wi-Fi is broadcasting and devices can join it, "
        f"but internet sharing didn't turn on automatically ({reason }).\n\n"
        "Want Revolt to turn it on for you now?",
        parent =parent ):
            return 

        def worker ():
            ok ,msg =_enable_ics_to_hosted_network ()
            if not ok :

                time .sleep (2.5 )
                ok ,msg =_enable_ics_to_hosted_network ()

            def done ():
                if ok :
                    messagebox .showinfo (
                    "Hotspot",
                    "Internet sharing is on — connected devices should "
                    "have internet now.",parent =parent )
                else :
                    if messagebox .askyesno (
                    "Still Not On",
                    f"Internet sharing still couldn't turn on ({msg }). "
                    "Try again?",parent =parent ):
                        self ._offer_ics_retry (parent ,msg )
            self .after (0 ,done )
        threading .Thread (target =worker ,daemon =True ).start ()

    def _open_hotspot_dialog (self ):
        if os .name !="nt":
            messagebox .showinfo ("Hotspot",
            "Hotspot creation is only supported on Windows right now.")
            return 

        cfg =load_hotspot_config ()
        win =tk .Toplevel (self )
        win .title ("Hotspot")
        win .geometry ("480x720")
        win .minsize (440 ,480 )
        win .resizable (True ,True )
        win .configure (bg =BG )

        win .transient (self )

        body =tk .Frame (win ,bg =BG ,padx =22 ,pady =18 )
        body .pack (fill ="both",expand =True )

        tk .Label (body ,text ="Hotspot",font =(FONT_FAMILY ,16 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w")
        tk .Label (body ,
        text ="Turn this PC into a Wi-Fi hotspot. Phones or other "
        "devices that join it share this PC's internet "
        "connection — and get the Shield's DNS filtering "
        "automatically, the same way this PC does.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =430 ,justify ="left").pack (anchor ="w",pady =(4 ,12 ))

        if not hotspot_supported ():
            tk .Label (body ,
            text ="⚠ Neither hotspot method Revolt can drive (the "
            "modern Mobile Hotspot API or the older hosted-"
            "network API) reports support on this PC. Start "
            "below may still work, but if it doesn't, try "
            "Windows Settings → Network & internet → Mobile "
            "hotspot directly.",
            font =(FONT_FAMILY ,9 ,"bold"),fg ="#e8a33d",bg =BG ,
            anchor ="w",wraplength =430 ,justify ="left"
            ).pack (anchor ="w",pady =(0 ,10 ))

        tk .Label (body ,text ="Network Name (SSID)",font =(FONT_FAMILY ,10 ,"bold"),
        fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(4 ,3 ))
        ssid_var =tk .StringVar (value =cfg .get ("ssid")or "Revolt-Hotspot")
        ssid_entry =tk .Entry (body ,textvariable =ssid_var ,font =(FONT_FAMILY ,12 ),
        bg =TOOLBAR ,fg =TEXT ,insertbackground =TEXT ,
        relief ="flat",highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        ssid_entry .pack (fill ="x",ipady =6 )

        pass_hdr_row =tk .Frame (body ,bg =BG )
        pass_hdr_row .pack (fill ="x",pady =(10 ,3 ))
        tk .Label (pass_hdr_row ,text ="Password (min. 8 characters)",
        font =(FONT_FAMILY ,10 ,"bold"),fg =TEXT ,bg =BG ,anchor ="w"
        ).pack (side ="left")
        pass_var =tk .StringVar (value =cfg .get ("password")or "")
        pass_entry =tk .Entry (body ,textvariable =pass_var ,font =(FONT_FAMILY ,12 ),
        show ="•",bg =TOOLBAR ,fg =TEXT ,insertbackground =TEXT ,
        relief ="flat",highlightthickness =1 ,
        highlightbackground =BORDER ,highlightcolor =ACCENT )
        pass_entry .pack (fill ="x",ipady =6 )

        def toggle_show ():
            pass_entry .config (show =""if pass_entry .cget ("show")else "•")
        FlatBtn (pass_hdr_row ,text ="Show/Hide",base_bg =TOOLBAR ,
        hover_bg =lighten (TOOLBAR ,.08 ),fg =MUTED ,ghost =True ,
        border_col =lighten (BORDER ,.35 ),radius =10 ,
        font =(FONT_FAMILY ,9 ,"bold"),command =toggle_show ,
        height =22 ,width =88 ).pack (side ="right")

        wifi_adapters =list_wifi_adapters ()
        saved_selection =set (cfg .get ("broadcast_adapters")or [])
        adapter_vars :dict [str ,tk .BooleanVar ]={}

        if len (wifi_adapters )>1 :
            tk .Label (body ,text ="Broadcast On",font =(FONT_FAMILY ,10 ,"bold"),
            fg =TEXT ,bg =BG ,anchor ="w").pack (anchor ="w",pady =(12 ,3 ))
            tk .Label (body ,
            text ="This PC has more than one Wi-Fi adapter. Pick which "
            "one(s) should broadcast the hotspot — Windows has "
            "no built-in way to choose, so Revolt does it by "
            "briefly turning the others off while the hotspot "
            "is on, then back on when it stops.",
            font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
            wraplength =430 ,justify ="left").pack (anchor ="w",pady =(0 ,6 ))
            adapters_frame =tk .Frame (body ,bg =BG )
            adapters_frame .pack (fill ="x")
            for a in wifi_adapters :

                checked =a ["name"]in saved_selection if saved_selection else True 
                var =tk .BooleanVar (value =checked )
                adapter_vars [a ["name"]]=var 
                label =a ["name"]
                if a ["description"]and a ["description"]!=a ["name"]:
                    label +=f"  ({a ['description']})"
                if not a ["enabled"]:
                    label +="  — currently off"
                tk .Checkbutton (adapters_frame ,text =label ,variable =var ,
                font =(FONT_FAMILY ,10 ),fg =TEXT ,bg =BG ,
                activebackground =BG ,activeforeground =TEXT ,
                selectcolor =TOOLBAR ,anchor ="w"
                ).pack (anchor ="w",pady =1 )

        def selected_broadcast_adapters ()->list [str ]:
            if not adapter_vars :
                return []
            picked =[name for name ,var in adapter_vars .items ()if var .get ()]

            return []if len (picked )==len (adapter_vars )else picked 

        status_lbl =tk .Label (body ,text ="",font =(FONT_FAMILY ,10 ,"bold"),
        fg =MUTED ,bg =BG ,anchor ="w")
        status_lbl .pack (anchor ="w",pady =(12 ,0 ))

        toggle_btn_holder ={}

        def refresh_status_line (live_count =None ):
            st =hotspot_status ()
            if st .get ("running"):
                n =live_count if live_count is not None else st .get ("clients",0 )
                status_lbl .config (
                text =f"●  Broadcasting \"{st .get ('ssid')or ssid_var .get ()}\" "
                f"— {n } device(s) connected",
                fg ="#3ddc97")
            else :
                status_lbl .config (text ="○  Hotspot is off",fg =MUTED )
            if "btn"in toggle_btn_holder :
                if st .get ("running"):
                    toggle_btn_holder ["btn"].config (text ="Stop Hotspot",fg =DANGER )
                else :
                    toggle_btn_holder ["btn"].config (text ="Start Hotspot",fg =TEXT )

        def do_toggle ():
            st =hotspot_status ()
            toggle_btn_holder ["btn"].config (state ="disabled")

            def worker ():
                if st .get ("running"):
                    ok ,msg =stop_hotspot ()
                else :
                    ok ,msg =start_hotspot (ssid_var .get ().strip (),pass_var .get (),
                    selected_broadcast_adapters ())

                def done ():
                    toggle_btn_holder ["btn"].config (state ="normal")
                    refresh_status_line ()
                    self ._refresh_hotspot_btn_label ()
                    if ok and msg .startswith ("ICS_PENDING:"):
                        self ._offer_ics_retry (win ,msg .split ("ICS_PENDING:",1 )[1 ])
                    else :
                        (messagebox .showinfo if ok else messagebox .showerror )(
                        "Hotspot",msg ,parent =win )
                self .after (0 ,done )
            threading .Thread (target =worker ,daemon =True ).start ()

        toggle_btn_holder ["btn"]=FlatBtn (body ,text ="Start Hotspot",
        base_bg =TOOLBAR ,hover_bg =lighten (TOOLBAR ,.08 ),fg =TEXT ,
        border_col =lighten (BORDER ,.35 ),radius =16 ,
        font =(FONT_FAMILY ,12 ,"bold"),command =do_toggle ,
        height =36 ,width =160 )
        toggle_btn_holder ["btn"].pack (anchor ="w",pady =(8 ,4 ))
        refresh_status_line ()

        tk .Frame (body ,bg =BORDER ,height =1 ).pack (fill ="x",pady =(12 ,10 ))

        head_row =tk .Frame (body ,bg =BG )
        head_row .pack (fill ="x")
        tk .Label (head_row ,text ="Connected Devices & Traffic",
        font =(FONT_FAMILY ,13 ,"bold"),fg =TEXT ,bg =BG ,anchor ="w"
        ).pack (side ="left")
        bw_lbl =tk .Label (head_row ,text ="",font =(FONT_FAMILY ,9 ),
        fg =MUTED ,bg =BG ,anchor ="e")
        bw_lbl .pack (side ="right")

        tk .Label (body ,
        text ="Windows only exposes combined hotspot bandwidth, not "
        "a per-device split (that needs a packet driver) — "
        "the number above is total traffic across every "
        "connected device.",
        font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =BG ,anchor ="w",
        wraplength =430 ,justify ="left").pack (anchor ="w",pady =(2 ,8 ))

        list_wrap =tk .Frame (body ,bg =BG )
        list_wrap .pack (fill ="both",expand =True )
        canvas =tk .Canvas (list_wrap ,bg =BG ,highlightthickness =0 ,bd =0 )
        vsb =ttk .Scrollbar (list_wrap ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )
        rows_frame =tk .Frame (canvas ,bg =BG )
        win_id =canvas .create_window ((0 ,0 ),window =rows_frame ,anchor ="nw")
        rows_frame .bind ("<Configure>",lambda e :
        canvas .configure (scrollregion =canvas .bbox ("all")))
        canvas .bind ("<Configure>",lambda e :
        canvas .itemconfig (win_id ,width =e .width ))

        def _wheel (event ):
            if getattr (event ,"num",None )==4 :
                canvas .yview_scroll (-1 ,"units")
            elif getattr (event ,"num",None )==5 :
                canvas .yview_scroll (1 ,"units")
            else :
                canvas .yview_scroll (int (-event .delta /120 ),"units")
            return "break"
        canvas .bind ("<MouseWheel>",_wheel )
        canvas .bind ("<Button-4>",_wheel )
        canvas .bind ("<Button-5>",_wheel )

        def _fmt_since (ts ):
            secs =max (0 ,time .time ()-ts )
            if secs <60 :
                return "just joined"
            mins =int (secs //60 )
            if mins <60 :
                return f"connected {mins }m"
            hrs ,mins =divmod (mins ,60 )
            return f"connected {hrs }h {mins }m"

        def do_block (ip ,mac ,hostname ):
            if not messagebox .askyesno ("Block Device",
            f'Block "{hostname }" ({ip }) from this hotspot? It will '
            "lose network access immediately.",parent =win ):
                return 
            def worker ():
                ok ,msg =block_hotspot_device (ip ,mac )
                def done ():
                    if ok :
                        Toast (self ,"Device Blocked 🚫",
                        f'"{hostname }" was removed from the hotspot.',ok =True )
                    else :
                        messagebox .showerror ("Couldn't Block Device",msg ,parent =win )
                    poll (force =True )
                self .after (0 ,done )
            threading .Thread (target =worker ,daemon =True ).start ()

        def do_unblock (mac ):
            def worker ():
                ok ,msg =unblock_hotspot_device (mac )
                def done ():
                    if not ok :
                        messagebox .showerror ("Couldn't Unblock Device",msg ,parent =win )
                    poll (force =True )
                self .after (0 ,done )
            threading .Thread (target =worker ,daemon =True ).start ()

        def render_devices (devices ,blocked ):
            for w in rows_frame .winfo_children ():
                w .destroy ()
            if not devices and not blocked :
                tk .Label (rows_frame ,text ="No devices connected yet.",
                font =(FONT_FAMILY ,10 ),fg =MUTED ,bg =BG 
                ).pack (pady =(10 ,6 ))
                return 
            for d in devices :
                card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                highlightbackground =BORDER )
                card .pack (fill ="x",pady =(0 ,6 ),padx =2 )
                inner =tk .Frame (card ,bg =CARD ,padx =10 ,pady =8 )
                inner .pack (fill ="x")
                top_row =tk .Frame (inner ,bg =CARD )
                top_row .pack (fill ="x")
                name =d ["hostname"]
                if d .get ("vendor"):
                    name +=f"  ·  {d ['vendor']}"
                IconGlyph (top_row ,"📱",size =13 ,color =TEXT ,bg =CARD 
                ).pack (side ="left",padx =(0 ,5 ))
                tk .Label (top_row ,text =name ,
                font =(FONT_FAMILY ,10 ,"bold"),fg =TEXT ,bg =CARD ,
                anchor ="w").pack (side ="left")
                FlatBtn (top_row ,text ="Block",base_bg =CARD ,
                hover_bg =lighten (CARD ,.08 ),fg =DANGER ,ghost =True ,
                border_col =DANGER ,radius =10 ,font =(FONT_FAMILY ,9 ,"bold"),
                height =22 ,width =58 ,
                command =lambda ip =d ["ip"],mac =d ["mac"],hn =d ["hostname"]:
                do_block (ip ,mac ,hn )
                ).pack (side ="right")
                tk .Label (inner ,text =f"{d ['ip']}   ·   {d ['mac']}   ·   "
                f"{_fmt_since (d ['since'])}",
                font =(FONT_FAMILY ,9 ),fg =MUTED ,bg =CARD ,
                anchor ="w").pack (anchor ="w",pady =(1 ,0 ))
            if blocked :
                tk .Label (rows_frame ,text ="Blocked",
                font =(FONT_FAMILY ,10 ,"bold"),fg =MUTED ,bg =BG ,anchor ="w"
                ).pack (anchor ="w",pady =(8 ,4 ))
                for b in blocked :
                    card =tk .Frame (rows_frame ,bg =CARD ,highlightthickness =1 ,
                    highlightbackground =BORDER )
                    card .pack (fill ="x",pady =(0 ,6 ),padx =2 )
                    inner =tk .Frame (card ,bg =CARD ,padx =10 ,pady =8 )
                    inner .pack (fill ="x")
                    row_l =tk .Frame (inner ,bg =CARD )
                    row_l .pack (side ="left")
                    IconGlyph (row_l ,"🚫",size =12 ,color =MUTED ,bg =CARD 
                    ).pack (side ="left",padx =(0 ,5 ))
                    tk .Label (row_l ,text =b ['mac'],
                    font =(FONT_FAMILY ,10 ,"bold"),fg =MUTED ,bg =CARD ,
                    anchor ="w").pack (side ="left")
                    FlatBtn (inner ,text ="Unblock",base_bg =CARD ,
                    hover_bg =lighten (CARD ,.08 ),fg =TEXT ,ghost =True ,
                    border_col =lighten (BORDER ,.35 ),radius =10 ,
                    font =(FONT_FAMILY ,9 ,"bold"),height =22 ,width =66 ,
                    command =lambda mac =b ["mac"]:do_unblock (mac )
                    ).pack (side ="right")

        state ={"open":True ,"prev_bw":None ,"prev_t":None ,
        "known_macs":set (),"first_poll":True ,"pending_id":None }

        def poll (force =False ):
            if not state ["open"]:
                return 
            if force and state ["pending_id"]is not None :
                try :self .after_cancel (state ["pending_id"])
                except Exception :pass 
                state ["pending_id"]=None 

            def worker ():
                st =hotspot_status ()
                devices =list_hotspot_devices ()if st .get ("running")else []
                blocked =list_blocked_hotspot_devices ()
                bw =get_hotspot_bandwidth ()if st .get ("running")else None 

                def done ():
                    if not state ["open"]:
                        return 
                    refresh_status_line (live_count =len (devices ))
                    render_devices (devices ,blocked )

                    now_macs ={d ["mac"]for d in devices }
                    if not state ["first_poll"]:
                        joined =now_macs -state ["known_macs"]
                        left =state ["known_macs"]-now_macs 
                        by_mac ={d ["mac"]:d for d in devices }
                        for mac in joined :
                            hn =by_mac .get (mac ,{}).get ("hostname","A device")
                            Toast (self ,"Device Connected 📶",
                            f'"{hn }" joined the hotspot.',ok =True )
                        for _mac in left :
                            Toast (self ,"Device Disconnected",
                            "A device left the hotspot.",ok =False )
                    state ["known_macs"]=now_macs 
                    state ["first_poll"]=False 

                    now =time .time ()
                    if bw and state ["prev_bw"]and state ["prev_t"]:
                        dt =max (now -state ["prev_t"],0.01 )
                        up =max (0 ,(bw ["sent"]-state ["prev_bw"]["sent"])/1024 /dt )
                        down =max (0 ,(bw ["received"]-state ["prev_bw"]["received"])/1024 /dt )
                        bw_lbl .config (text =f"↑ {up :.0f} KB/s   ↓ {down :.0f} KB/s")
                    elif not st .get ("running"):
                        bw_lbl .config (text ="")
                    state ["prev_bw"],state ["prev_t"]=bw ,now 
                    state ["pending_id"]=self .after (2000 ,poll )
                self .after (0 ,done )
            threading .Thread (target =worker ,daemon =True ).start ()
        poll ()

        def close ():
            state ["open"]=False 
            win .destroy ()
        win .protocol ("WM_DELETE_WINDOW",close )

        FlatBtn (body ,text ="Close",base_bg =BORDER ,fg =TEXT ,
        command =close ,radius =14 ,height =32 ,width =90 
        ).pack (anchor ="e",pady =(12 ,0 ))

if __name__ =="__main__":
    try :

        if os .name =="nt":
            try :
                ctypes .windll .shell32 .SetCurrentProcessExplicitAppUserModelID (
                "Revolt.InternetShield.App")
            except Exception :
                pass 

        if not ensure_admin ():
            sys .exit (0 )

        try :
            recover_dns_from_previous_session ()
        except Exception :
            pass 

        app =Revolt ()
        app .mainloop ()
    except SystemExit :
        raise 
    except Exception :

        import traceback 
        traceback .print_exc ()
        input ("\nRevolt crashed — see the error above. Press Enter to close...")
