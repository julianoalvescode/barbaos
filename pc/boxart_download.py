import json,os,sys,urllib.request,urllib.parse,concurrent.futures as cf
S,romdir=sys.argv[1],sys.argv[2]; m=json.load(open(S+'/map.json'))
base='https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy%20Advance/'
os.makedirs(romdir+'/images',exist_ok=True)
def get(kind,name,dest):
    if os.path.exists(dest) and os.path.getsize(dest)>0: return True
    u=base+kind+'/'+urllib.parse.quote(name.replace('&','_').replace('*','_').replace('/','_').replace(':','_').replace('?','_'))+'.png'
    for _ in range(3):
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'rom-thumb-fetch'}),timeout=30).read()
            open(dest,'wb').write(r); return True
        except Exception as e: err=e
    print('ERR',kind,name,err); return False
jobs=[]
for f,v in m.items():
    stem=os.path.splitext(f)[0]
    jobs.append(('Named_Boxarts',v['box'],f'{romdir}/images/{stem}-image.png'))
    if v['snap']: jobs.append(('Named_Snaps',v['snap'],f'{romdir}/images/{stem}-thumb.png'))
with cf.ThreadPoolExecutor(8) as ex: ok=sum(ex.map(lambda j:get(*j),jobs))
print('downloaded',ok,'of',len(jobs))
