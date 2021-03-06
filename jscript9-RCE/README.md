# Jscript9 Remote Code Execution Exploit
Full proof-of-concept exploit for a JIT Type Confusion vulnerability in Microsoft JavaScript engine (Jscript9.dll).

Writeup: [JavaScript Engines Exploitation: a Jscript9 Case Study (Full Exploit)](https://zerodayengineering.com/research/javascript-engines-exploitation-jscript9.html)

### Features
* compliant with systematical exploit engineering practices  
* shows one classical technique of JavaScript engines exploitation  
* no heap spray, precise control of program state and placement of shellcodes  
* state-of-the-art (c.2017) process continuation to avoid crash  
* multi-stage shellcode design  
* drop-in functional shellcode template (CoE and helper shellcode stages are hidden away)  
* fully dynamic ASLR bypass  
* tested 100% stable on one full year of target software updates in 2017 before it was patched  
* includes special versions of code with debugging helpers and comments  
* x32 only

### Contacts 
Author: Alisa Esage ([@alisaesage](https://twitter.com/alisaesage))  
My project: [Zero Day Engineering Training & Intelligence](https://zerodayengineering.com)  
Email: [contact@zerodayengineering.com](mailto:contact@zerodayengineering.com)