# SKILL-osint — Open-Source Intelligence

## Domain & IP Recon
```bash
whois target.com
dig target.com ANY
dig target.com MX
dig target.com TXT              # SPF, DKIM, verification codes sometimes hidden here
nslookup -type=any target.com
host -a target.com

# Subdomains
subfinder -d target.com
amass enum -d target.com
# Online: crt.sh, dnsdumpster.com, securitytrails.com
curl "https://crt.sh/?q=%.target.com&output=json" | python3 -m json.tool | grep name_value
```

## Web Archiving
```bash
# Wayback Machine snapshots
curl "http://archive.org/wayback/available?url=target.com"
# Browse: https://web.archive.org/web/*/target.com/*

# Cached pages
# Google: cache:target.com
# Bing: slightly different cache
```

## Google Dorking
```
site:target.com filetype:pdf
site:target.com inurl:admin
site:target.com intext:"internal use only"
"@target.com" filetype:xls
"target.com" "password" site:pastebin.com
intitle:"index of" site:target.com
```

## Email & Username Recon
```bash
# Email format discovery
# hunter.io, clearbit.com (web)
theHarvester -d target.com -b google,bing,linkedin

# Username search across platforms
sherlock username         # search 300+ sites
maigret username          # deeper profile aggregation

# Email breach check
# haveibeenpwned.com API
curl "https://haveibeenpwned.com/api/v3/breachedaccount/email@target.com" \
  -H "hibp-api-key: KEY"
```

## Social Media & People Search
```
LinkedIn: site:linkedin.com "target company" "engineer"
Twitter/X: from:user OR to:user keyword
GitHub: site:github.com "target.com" password
Pastebin: site:pastebin.com "target.com"
```

## Image OSINT
```bash
exiftool image.jpg            # GPS coords, camera, timestamp, author
# Reverse image search: Google Images, TinEye, Yandex Images
# GPS: copy lat/long from exiftool into Google Maps
```

## GitHub Recon
```bash
# Search for secrets in repos
# truffleHog, gitleaks, or manual search:
# site:github.com "target.com" "api_key"
# site:github.com "target.com" "password"

# View deleted commits (via reflog if you have the repo)
git log --all --full-history
git show <deleted-commit-hash>

# GitHub dorks
# filename:.env "target.com"
# filename:config.py "target.com" password
```

## Metadata Extraction
```bash
exiftool -r ./documents/         # batch all files
metagoofil -d target.com -t pdf,docx -o ./meta_output/
```

## Common CTF OSINT Patterns
- **Flag in image metadata**: `exiftool image.jpg | grep -i flag`
- **Flag in Wayback Machine source**: view archived page source
- **Flag in git history**: `git log -p | grep -i flag`
- **Flag in DNS TXT record**: `dig target.ctf TXT`
- **Username → profile → bio contains flag**: check all social platforms
- **Document author/company reveals next step**: check metadata of provided PDF/DOCX
