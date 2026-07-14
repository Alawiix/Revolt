
# Revolt
A free OpenSource  DNS shield, VPN guard, hotspot blocking App designed to make humanity Better
    
a content-blocking / parental controls app for windows. blocks stuff at the DNS level, hosts file, VPN, and even hotspot traffic, so it actually sticks instead of being a browser extension someone closes in two seconds.
made by NCZ.
what it does
DNS shield - sinkholes blocked domains so they don't resolve at all
hosts file blocking - old school but still works, backs it up so nothing gets nuked
lifetime block - permanent blocks that survive uninstall/reinstall attempts
VPN guard - bring your own WireGuard/OpenVPN config (Revolt doesn't bundle sketchy "free" VPN lists, you connect your own trusted provider)
hotspot blocking - covers devices connected through your PC's mobile hotspot too, not just the PC itself
blocking topics - pick categories instead of managing a giant domain list yourself:
🛡 Ad Blocking
🏢 Evil Companies
💬 Social
🔒 Adult & OnlyFans
⚠ Gore & Shock
🕵 Conspiracy & Fringe
🎲 Crypto & Gambling
🤖 AI & Chatbots
🧅 Tor & Dark Web

![GitHub All Releases](https://img.shields.io/github/downloads/alawiix/Revolt/total)
<img width="1159" height="755" alt="image" src="https://github.com/user-attachments/assets/847edb2d-6640-4036-9e92-a997da4ddd3c" />

allowlist - because category blocking is never perfect, you can always whitelist stuff
custom feeds - point it at your own remote blocklist if the built-in categories aren't enough
native notifications - real Windows Action Center toasts, not some janky in-app popup that disappears if you alt-tab
password protected - so it can't just get turned off in 5 seconds
it's a windows desktop app, built with tkinter (mid PyQt6 migration right now so some of this will look different soon).
running it from source
```
pip install -r requirements.txt
python revolt_app_tkniter.py
```
you'll want to run it as admin for the DNS/hosts file stuff to actually work, it'll prompt you with a UAC dialog when it needs elevation.
building the exe
```
pyinstaller --onefile --manifest revolt.exe.manifest --version-file version.txt --icon=revolt_icon.ico revolt_app_tkniter.py
```
the manifest handles DPI awareness + UAC behavior, the version file is what shows up in the exe's Properties tab in explorer.
why not just use a free public VPN list / auto-picked servers
didn't want to bundle some list of unverified "free" servers that could see everything a blocked site would've seen. you grab a config from a provider you actually trust (ProtonVPN and Windscribe both have solid free tiers) and Revolt just connects it for you.
license
free forever, can't be sold, and it's not for spying on people without their consent - see LICENSE.
discord
updates, support, bug reports: https://discord.gg/Y9gqrujAJg
 
