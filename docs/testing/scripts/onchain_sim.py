"""Simulate contract calls from given addresses via eth_call on Sepolia and decode custom errors.

Usage: python onchain_sim.py [extra_sys_path] < checks.py   (checks call sim(label, from, to, signature, *args))
Requires: pycryptodome; run from anywhere inside the repo.
"""
import sys, json, subprocess, re, glob, os
if len(sys.argv) > 1: sys.path.insert(0, sys.argv[1])
from Crypto.Hash import keccak
def k(s): h=keccak.new(digest_bits=256); h.update(s.encode()); return h.hexdigest()
REPO=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
errs={}
for f in glob.glob(REPO+"/contracts/contracts/**/*.sol", recursive=True):
    for m in re.finditer(r"error\s+(\w+)\(([^)]*)\)", open(f,encoding="utf-8").read()):
        t=",".join((lambda ty: ty if re.match(r"(u?int\d*|address|bytes\d*|bool|string)$", ty) else "uint8")(p.strip().split()[0]) for p in m.group(2).split(",") if p.strip())
        errs[k(f"{m.group(1)}({t})")[:8]]=m.group(1)
for s in ["ERC1155InsufficientBalance(address,uint256,uint256,uint256)","ERC20InsufficientBalance(address,uint256,uint256)","ERC20InsufficientAllowance(address,uint256,uint256)","EnforcedPause()","AccessControlUnauthorizedAccount(address,bytes32)"]:
    errs[k(s)[:8]]=s.split("(")[0]
def enc(a):
    if isinstance(a,int): return hex(a)[2:].rjust(64,"0")
    return a[2:].lower().rjust(64,"0")
RESULTS=[]
def encode_args(args):
    head=[]; tail=""; base=32*len(args)
    for a in args:
        if isinstance(a,tuple) and a[0]=="str":
            b=a[1].encode(); off=base+len(tail)//2
            head.append(hex(off)[2:].rjust(64,"0"))
            tail+=hex(len(b))[2:].rjust(64,"0")+(b.hex()+"00"*((32-len(b)%32)%32) if b else "")
        else: head.append(enc(a))
    return "".join(head)+tail
def sim(label, frm, to, sig, *args):
    data="0x"+k(sig)[:8]+encode_args(args)
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"from":frm,"to":to,"data":data},"latest"]})
    r=json.loads(subprocess.run(["curl","-s","-m","20","-X","POST","-H","Content-Type: application/json","--data",body,"https://ethereum-sepolia-rpc.publicnode.com"],capture_output=True,text=True).stdout)
    if "error" in r:
        d=r["error"].get("data","") or ""; name=errs.get(d[2:10], d[:10] or r["error"].get("message"))
        print(f"{label}: REVERT {name}"); RESULTS.append((label,"REVERT "+str(name)))
    else: print(f"{label}: SUCCESS (would not revert)"); RESULTS.append((label,"SUCCESS"))
A=dict(S1="0xC5192Be82Ef411Ca3ec3B8Ea03EA260C770795F2",S2="0xE128d23F32B6f576054f0F9D7ec0B6Ef2EAa282e",CE="0x3d06C8284962154159c2F7eC6F8789A75dd7A892",F1="0xE21E58104Aa80450bA60C6A535129E7d9F8b9916",F2="0x9c781511c1b3843837da8be745e0CCCeCd04661E",AU="0x2aAEe8c8A554c988872179d6391A29f6f18d37ce",X="0x0B1A4a58beAAF4C990C058158716D9867f053D55",ADM2="0x877c15eB8449DF65323a2e49902d889052a9Df42")
RM="0x82f86a2B31C424b4833b5BAb82464eB7f69B6a2E"; IR="0x39605C1D4FCE3D85DC14f7f283899b984dd1eD7a"; RT="0x3c9EcDdf7e788F7B8e04D4177d04B3c291E0368f"; FP="0x2bb0A6e688C331248fe8575121F799B5286985c6"; MU="0xE3C713Db876c97600141Ba34C7Cb68898CF1E04F"
exec(sys.stdin.read())
