# WebTester-Kali

Simple **authorized** website load tester for Kali Linux. Python stdlib only — no pip install needed.

## Kali par chalana (3 commands)

```bash
git clone https://github.com/MrYaseen0/webtester-kali.git
cd webtester-kali
chmod +x run.sh
./run.sh
```

Phir browser mein kholo: **http://127.0.0.1:8080**

## GUI mein

1. **Website URL** dalo (apni website — `https://...`)
2. **Concurrent users** (1–500), **Target req/sec** (1–2000), **Duration** (5–600 sec)
3. **Ownership checkbox** tick karo — ye lazmi hai
4. **START TEST** dabao — live stats (requests, success %, avg/p95 latency, status codes)
5. Test khatam hone par **CSV report** download kar lo

## Safety rules (code mein hard-coded, bypass nahi ho sakte)

- Ownership confirm kiye baghair test start nahi hota
- Har request mein identifiable User-Agent jata hai (contact ke saath)
- **Koi "unlimited" mode nahi** — max 500 users / 2000 req-sec / 10 min
- Koi proxy, koi header spoofing, koi block-evasion nahi
- 429 / 503 (rate-limit / block) result mein report hote hain, evade nahi hote

Sirf apni websites par ya jahan test ki ijazat ho, wahan istemal karo.
