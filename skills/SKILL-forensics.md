# SKILL-forensics — Digital Forensics

## First Look at Any File
```bash
file suspicious_file
xxd suspicious_file | head -20    # check magic bytes
strings suspicious_file | head -40
exiftool suspicious_file          # metadata
binwalk suspicious_file           # embedded files / entropy
```

## Magic Bytes Cheat Sheet
| Header (hex) | Format |
|---|---|
| `FF D8 FF` | JPEG |
| `89 50 4E 47` | PNG |
| `47 49 46 38` | GIF |
| `50 4B 03 04` | ZIP |
| `52 61 72 21` | RAR |
| `25 50 44 46` | PDF |
| `7F 45 4C 46` | ELF |
| `4D 5A` | PE (Windows EXE) |

## File Carving
```bash
binwalk -e archive.bin              # extract embedded files
foremost -i disk.img -o out/        # carve by magic bytes
photorec disk.img                   # interactive carving

# Manual ZIP extraction from broken archive
zip -FF broken.zip --out fixed.zip
unzip -p archive.zip secret.txt
```

## Steganography
```bash
# LSB (images)
zsteg image.png          # PNG LSB channels
steghide extract -sf image.jpg -p ""   # no password
steghide extract -sf image.jpg -p password

# Audio LSB
sonic-visualizer audio.wav         # look for spectrogram message
audacity audio.wav                 # view spectrogram (Analyze → Plot Spectrum)

# Text / whitespace stego
cat -A file.txt | grep -P '\s+$'   # trailing whitespace
# Snow: stegsnow -C -p "" file.txt

# PDF hidden layers
pdfimages document.pdf images/
pdftotext document.pdf
```

## PCAP / Network Forensics
```bash
tcpdump -r capture.pcap -A         # read and print ASCII
wireshark capture.pcap             # GUI

# Tshark one-liners
tshark -r capture.pcap -Y "http" -T fields -e http.request.uri
tshark -r capture.pcap -Y "dns" -T fields -e dns.qry.name
tshark -r capture.pcap -Y "tcp.port==4444" -T fields -e data.data

# Extract HTTP objects
tshark -r capture.pcap --export-objects http,./http_objects/

# Follow TCP stream (Wireshark): right-click packet → Follow → TCP Stream
```

## Memory Forensics (Volatility)
```bash
vol -f memory.dmp windows.info     # identify OS
vol -f memory.dmp windows.pslist   # running processes
vol -f memory.dmp windows.cmdline  # command lines
vol -f memory.dmp windows.filescan # files in memory
vol -f memory.dmp windows.dumpfiles --pid 1234
vol -f memory.dmp windows.netscan  # network connections
vol -f memory.dmp windows.hashdump # password hashes
```

## Disk Image
```bash
fdisk -l disk.img                  # partition table
mount -o loop,offset=$((512*2048)) disk.img /mnt/img
# or
mmls disk.img                      # sleuthkit partition listing
fls -r disk.img                    # file listing (deleted files included)
icat disk.img <inode>              # extract file by inode
```

## ZIP / Archive Passwords
```bash
zip2john protected.zip > hash.txt
john hash.txt --wordlist=rockyou.txt

# Known-plaintext attack (if you know one file in the zip)
bkcrack -C encrypted.zip -c plainfile.txt -p known_plaintext.txt
```

## Common CTF Forensics Patterns
- **Flag in EXIF**: `exiftool image.jpg | grep -i flag`
- **Flag in unused space**: `strings disk.img | grep -i flag`
- **Flag in deleted file**: recover with `extundelete` or `testdisk`
- **Flag encoded in audio spectrogram**: open in Audacity, switch to spectrogram view
- **Flag in PDF metadata**: `pdfinfo file.pdf`
- **Flag hidden by identical colors**: open in GIMP, color histogram off by 1
