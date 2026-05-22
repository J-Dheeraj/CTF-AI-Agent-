# SKILL-recon — Reconnaissance & Enumeration

## Port Scanning
```bash
# Fast full-port scan
nmap -p- --min-rate 5000 -T4 target -oN ports.txt

# Service + script scan on open ports
nmap -p 22,80,443 -sV -sC target -oN services.txt

# UDP scan (top 100)
nmap -sU --top-ports 100 target

# Masscan (very fast)
masscan -p1-65535 target --rate=10000
```

## Web Enumeration
```bash
# Directory brute force
gobuster dir -u http://target -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
ffuf -u http://target/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt

# Virtual host / subdomain brute force
ffuf -u http://target -H "Host: FUZZ.target.com" -w subdomains.txt -fc 302

# Parameter fuzzing
ffuf -u "http://target/page?FUZZ=value" -w params.txt -mc 200

# Recursive scan
gobuster dir -u http://target -w wordlist.txt -r
```

## Service-Specific Enumeration

### FTP (21)
```bash
ftp target              # try anonymous login: user=anonymous, pass=(empty)
nmap -p 21 --script ftp-anon,ftp-brute target
```

### SSH (22)
```bash
ssh-audit target        # check key exchange / cipher weaknesses
# Username enumeration (older OpenSSH)
ssh -v target -l user 2>&1 | grep "Invalid user"
```

### SMB (445)
```bash
smbclient -L //target -N          # list shares, no password
smbclient //target/share -N
smbmap -H target
enum4linux -a target
crackmapexec smb target --shares
```

### HTTP/HTTPS (80/443)
```bash
whatweb http://target             # tech fingerprinting
nikto -h http://target
curl -I http://target             # headers — framework, server version
```

### MySQL (3306)
```bash
mysql -h target -u root -p
nmap -p 3306 --script mysql-info,mysql-brute target
```

### Redis (6379)
```bash
redis-cli -h target ping
redis-cli -h target info
redis-cli -h target keys '*'
```

### SNMP (161 UDP)
```bash
snmpwalk -c public -v1 target
onesixtyone -c community_strings.txt target
```

## Common Finding → Next Step
| Found | Next action |
|---|---|
| FTP anonymous login | List all files, download everything |
| SMB null session | smbmap to list shares, mount and browse |
| robots.txt | Read it, visit every Disallowed path |
| `.git` directory exposed | `git-dumper http://target/.git ./repo` |
| Backup file (`*.bak`, `*.old`, `~`) | Download and read source |
| Admin panel | Default creds, SQLi, brute force |
| API endpoint | Test auth, enumerate `/api/v1/users`, etc. |
| WebSocket | ws-harness or Burp Suite WebSocket tab |

## Wordlists (SecLists paths)
```
/usr/share/seclists/Discovery/Web-Content/common.txt
/usr/share/seclists/Discovery/Web-Content/big.txt
/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt
/usr/share/seclists/Passwords/Leaked-Databases/rockyou.txt
/usr/share/wordlists/dirb/common.txt
```
