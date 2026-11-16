import re,os,sys,json,difflib,urllib.parse
S=sys.argv[1]; romdir=sys.argv[2]
def idx(f): return [urllib.parse.unquote(h)[:-4] for h in re.findall(r'href="([^"]+\.png)"',open(f,encoding='utf8').read())]
box=idx(S+'/box.html'); snap=set(idx(S+'/snap.html'))
ALIAS={'Pokemon - Fire Red':'Pokemon - FireRed Version','Wario Ware Inc.':'WarioWare, Inc. - Mega Microgame$!',
 'Zelda - the Minish Cap':'Legend of Zelda, The - The Minish Cap','Monkey Ball Jr.':'Super Monkey Ball Jr.',
 'Donkey Kong - King of Swing':'DK - King of Swing','Ray-Man 3 - Hoodlum Havoc':'Rayman 3','Puzzle Fighter 2 Turbo':'Super Puzzle Fighter II',
 'Crazy Taxi':'Crazy Taxi - Catch a Ride','Dr. Mario _ Puzzle League':'2 Games in One! - Dr. Mario + Puzzle League',
 'Mario Advanced - Mario Bros. 2 + Mario Classic':'Super Mario Advance','Mario Advanced 2 - Mario World':'Super Mario Advance 2 - Super Mario World',
 'Mario Advanced 4 - Mario Bros. 3':'Super Mario Advance 4 - Super Mario Bros. 3','Final Fantasy 4 Advance':'Final Fantasy IV Advance',
 'Final Fantasy 5 Advance':'Final Fantasy V Advance','Final Fantasy 6 Advance':'Final Fantasy VI Advance','R-Type III':'R-Type III - The Third Lightning',
 'Bomberman Max 2 - Blue':'Bomberman Max 2 - Blue Advance','Bomberman Max 2 - Red':'Bomberman Max 2 - Red Advance',
 'Buffy - The Vampire Slayer':'Buffy the Vampire Slayer - Wrath of the Darkhul King','Krazy Racers':'Konami Krazy Racers',
 "LEGO Island 2":"LEGO Island 2 - The Brickster's Revenge","Shonen Jump's - One Piece":'One Piece',
 'Teen Titans 2 - The Brotherhood\'s Revenge':'Teen Titans 2','Phalanx - The Enforce Fighter A-144':'Phalanx',
 "Disney's Magical Quest":'Magical Quest Starring Mickey _ Minnie',"Disney's Magical Quest 2":'Magical Quest 2 Starring Mickey _ Minnie',
 'Spider-Man - The Movie':'Spider-Man','Spirit - Stallion of The Cimarron':'Spirit - Stallion of the Cimarron - Search for Homeland'}
ALIAS.update({'F-Zero 2 - GP Legend':'F-Zero - GP Legend','Final Fantasy 1 + 2 - Dawn of Souls':'Final Fantasy I _ II - Dawn of Souls',
'Ninja Five-0':'Ninja Five-O','Spyro 3 - Attack of the Rhynocs':'Spyro - Attack of the Rhynocs','Pocket Professor Kwik Notes Vol. 1':'Pocket Professor - Kwik Notes - Volume One',
'2-in-1 - Cartoon Network - Block Party & Cartoon Network - Speedway':'2 Games in 1 - Cartoon Network Block Party + Cartoon Network Speedway',
"2-in-1 - Tony Hawk's Underground & Kelly Slater's Pro Surfer":"2 in 1 Game Pack - Tony Hawk's Underground + Kelly Slater's Pro Surfer",
'FIFA World Cup 2006':'FIFA World Cup - Germany 2006','MX 2K2 Ricky Carmichael':'MX 2002 featuring Ricky Carmichael',
"Archer Maclean's Super Dropzone":'Super Dropzone - Intergalactic Rescue Mission','Snood 2 - Snoods on Vacation':'Snood 2 - On Vacation',
'Rugrats - All Grown Up! - Express Yourself':'All Grown Up! - Express Yourself','Sudoku Fever':'Sudoku Fever',
"2-in-1 - Dragon Ball Z Gamepack - Buu's Fury & GT - Transformation":"2 Games in 1 - Dragon Ball Z - Buu's Fury + Dragon Ball GT - Transformation",
'2-in-1 - Paperboy & Rampage':'2 Games in 1 - Paperboy + Rampage','2-in-1 - Spy Hunter & Super Sprint':'2 Games in 1 - Spy Hunter + Super Sprint',
'Gauntlet & Rampart':'2 Games in 1 - Gauntlet + Rampart','Marble Madness & Klax':'2 Games in 1 - Marble Madness + Klax',
'2-in-1 - Uno & Skin Bo':'2 Games in 1 - Uno + Skip-Bo'})
ROMAN={'2':'ii','3':'iii','4':'iv','5':'v','6':'vi'}
def base(s): return re.sub(r'\s*(\(.*?\)|\[.*?\])','',s).strip()
def norm(s,roman=False):
    s=base(s).lower().replace('&','and').replace(' _ ',' and ').replace('+','and')
    s=re.sub(r"^(the |disney's |disney_s |dr\. seuss' )|, the\b",'',s)
    if roman: s=re.sub(r'\b([2-6])\b',lambda m:ROMAN[m.group(1)],s)
    s=re.sub(r'\b(and|the|of)\b','',s)
    return re.sub(r'[^a-z0-9]','',s)
def digits(s): return re.findall(r'\d+|\b[ivx]+\b',s)
def score(n):
    r=0
    for t,w in (('USA',4),('Brazil',3),('Europe',2),('World',2)):
        if t in n: r+=w
    if 'Virtual Console' in n: r-=1
    if re.search(r'Beta|Proto|Demo|Sample|Kiosk|Hack|Unl|Pirate',n): r-=10
    return r
by={}
for b in box:
    for k in {norm(b),norm(b,True)}: by.setdefault(k,[]).append(b)
keys=list(by)
res={}; miss=[]
for f in sorted(os.listdir(romdir)):
    if not f.lower().endswith('.gba'): continue
    t=base(f[:-4]); how='exact'; k=None
    if t in ALIAS: t=ALIAS[t]; how='alias'
    for cand in (norm(t),norm(t,True)):
        if cand in by: k=cand; break
    if not k:
        n=norm(t,True); pre=[x for x in keys if len(n)>=8 and (x.startswith(n) or n.startswith(x)) and len(x)>=8]
        c=difflib.get_close_matches(n,keys,1,0.88)
        if c and digits(re.sub(r'[^0-9]','',n))==digits(re.sub(r'[^0-9]','',c[0])): k=c[0]; how='fuzzy'
        elif pre: k=min(pre,key=lambda x:abs(len(x)-len(n))); how='prefix'
    if not k or how in('fuzzy','prefix') and re.sub(r'\D','',norm(t))!=re.sub(r'\D','',k): 
        if not k or how!='alias': miss.append(f); continue
    best=max(set(by[k]),key=score)
    res[f]={'box':best,'snap':best if best in snap else None,'how':how,'name':base(f[:-4]).replace('_',"'")}
json.dump(res,open(S+'/map.json','w'),indent=1)
print('matched',len(res),'missing',len(miss))
for f,v in res.items():
    if v['how'] in('fuzzy','prefix','alias'): print('  ',v['how'][:3],f,'=>',v['box'])
print('--- no boxart:'); [print('  ',m) for m in miss]
