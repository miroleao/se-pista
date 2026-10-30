#!/usr/bin/env python3
# Adiciona a 89a Expozebu Nelore 2024 (Uberaba/MG) ao index.html (SE Agro Pista)
# Fonte: ExpoZebu_2024_Resultado_Nelore.pdf (ABCZ) -> pdftotext -layout -> z.txt
import re,json,unicodedata,datetime,sys
H='/home/claude/se-pista/index.html'
TXT='/tmp/claude-0/-home-claude/6bb9e83c-7722-5fa5-85ab-583cb2b9a57a/scratchpad/ez24/z.txt'
NOME='89ª Expozebu Nelore 2024'
h=open(H,encoding='utf-8').read()
m=re.search(r'(<script type="application/json" id="data">)(.*?)(</script>)',h,re.S)
D=json.loads(m.group(2))
S,E,A,R,C=D['S'],D['E'],D['A'],D['R'],D['C']
if any(e['nome']==NOME for e in E): sys.exit('ja existe')
def norm(s): return re.sub(r'[^A-Z0-9]','',unicodedata.normalize('NFKD',s.upper()).encode('ascii','ignore').decode())
SM={}
for i,s in enumerate(S): SM.setdefault(norm(s),i)
newS=[]
def sidx(s):
    s=re.sub(r'\s+',' ',s).strip(" _.'|")
    if not s: return -1
    k=norm(s)
    if k in SM: return SM[k]
    S.append(s); SM[k]=len(S)-1; newS.append(s); return SM[k]
L=open(TXT,encoding='utf-8').read().split('\n')
FEM={'BEZERRA JOVEM','BEZERRA','NOVILHA MENOR','NOVILHA MAIOR','VACA JOVEM','VACA','VACA ADULTA'}
def catn(s): return s.strip().upper().replace('JUNIOR','JÚNIOR')
ORD={'primeiro':1,'segundo':2,'terceiro':3,'quarto':4,'quinto':5,'sexto':6,'sétimo':7,'setimo':7,'oitavo':8,'nono':9,'décimo':10,'decimo':10,'vigésimo':20}
def ordpos(t):
    p=t.lower().split(); n=0
    for w in p:
        if w in ORD: n+=ORD[w]
        elif w=='primeiro': n+=1
    return n
HDR=re.compile(r'^\s*E\s+(\d+)\s+(.+?)\s+RG:\s+(.+?)\s+Nasc:\s+(\d\d/\d\d/\d{4})\s+Pai:\s+(.+?)\s{2,}(\S.*?)\s*$')
def card(i):
    mm=HDR.match(L[i])
    if not mm: return None,i
    c=dict(id=int(mm.group(1)),nome=re.sub(r'\s+',' ',mm.group(2)).strip(),rg=re.sub(r'\s+','',mm.group(3)),nasc=mm.group(4),pai=mm.group(5).strip(),pairg=re.sub(r'\s+','',mm.group(6)))
    j=i+1; blk=[]
    while j<len(L) and not L[j].strip().startswith('Fazenda:') and j<i+9:
        blk.append(L[j]); j+=1
    fz=L[j] if j<len(L) else ''
    t='\n'.join(blk)
    mi=re.search(r'Idade:\s*(\d+)\s*Meses\s*(\d+)\s*Dias',t); mp=re.search(r'Peso:\s*(\d+)\s*Kg',t)
    c['idade']=int(mi.group(2)) if mi else None
    c['peso']=float(mp.group(1)) if mp else None
    ma=re.search(r'\(\s*(.+?)\s{2,}(\S[^()]*?)\s*\)',blk[0]) if blk else None
    c['avop']=ma.group(1).strip() if ma else ''
    mf=re.search(r'Cria:\s*([SN]?)\s+Pr:\s*([SN]?)',t)
    c['cria']=mf.group(1) if mf else ''; c['pr']=mf.group(2) if mf else ''
    cr=[x for x in blk if 'Criador:' in x]
    mc=re.search(r'Criador:\s*(.+?)\s{2,}M[ãa]e:\s*(.+?)\s{2,}(\S.*?)\s*$',cr[0]) if cr else None
    if not mc and cr: mc=re.search(r'Criador:\s*(.+?)\s+M[ãa]e:\s*(.+?)\s{2,}(\S.*?)\s*$',cr[0])
    if mc: c['criador']=mc.group(1).strip(); c['mae']=mc.group(2).strip(); c['maerg']=re.sub(r'\s+','',mc.group(3))
    else: c['criador']=c['mae']=c['maerg']=''
    ex=[x for x in blk if 'Expositor:' in x]
    me=re.search(r'Expositor:\s*(.+?)(?:\s{2,}\(\s*(.+?)\s{2,}(\S[^()]*?)\s*\))?\s*$',ex[0]) if ex else None
    c['exp']=me.group(1).strip() if me else ''; c['avom']=(me.group(2) or '').strip() if me else ''
    mz=re.search(r'Fazenda:\s*(.+?)\s{2,}(.+?)\s{2,}([A-Z]{2})\s*$',fz)
    c['faz']=mz.group(1).strip() if mz else ''; c['uf']=mz.group(3) if mz else ''
    return c,j
# ---- 1) categorias
start=next(i for i,l in enumerate(L) if l.strip()=='CAMPEONATO BEZERRA JOVEM' and i>1400)
end=next(i for i in range(start,len(L)) if 'Prêmio Progênie' in L[i])
champ=cat=None; mi=mf=0; sub=''; pos=0; cat_cards=[]
i=start
while i<end:
    l=L[i].strip()
    mm=re.match(r'CAMPEONATO (.+)$',l)
    if mm: champ=catn(mm.group(1)); sub=''
    mm=re.match(r'(\d+)\s*ª Categoria - de (?:mais de )?(\d+) até (\d+) meses',l)
    if mm: cat=int(mm.group(1)); mi,mf=int(mm.group(2)),int(mm.group(3)); sub=''
    mm=re.match(r'Sub-Categoria \((\w)\)',l)
    if mm: sub=mm.group(1)
    mm=re.match(r'^([\wéêíóáç ]+?) Prêmio\s*$',l)
    if mm: pos=ordpos(mm.group(1))
    c,j=card(i)
    if c:
        c.update(champ=champ,cat=cat,mi=mi,mf=mf,sub=sub,pos=pos,sx='F' if champ in FEM else 'M'); cat_cards.append(c); i=j
    i+=1
# ---- 2) campeonatos
cs=next(i for i,l in enumerate(L) if l.strip()=='Grande Campeã' and i>1000)
ce=next(i for i in range(cs,len(L)) if 'Conjunto Campeão Progênie' in L[i])
champ_cards=[]; title=None; i=cs
while i<ce:
    l=L[i].strip()
    if re.match(r'^(Grande|Reservad|Terceir|Campe)',l) and 'RG:' not in l and not l.startswith('Criador'): title=l
    c,j=card(i)
    if c: c['title']=title; champ_cards.append(c); i=j
    i+=1
# ---- 3) rankings
def rank_lines(a,b):
    out=[]
    for l in L[a:b]:
        mm=re.match(r'^\s*(\d+)\s*º\s+(.+?)\s{2,}(.+?)\s+([A-Z]{2})\s+(\d+)\s*$',l)
        if mm: out.append((int(mm.group(1)),mm.group(2).strip(),mm.group(3).strip(),mm.group(4),int(mm.group(5)))); continue
        mm=re.match(r'^\s*(\d+)\s*º\s+(.+?)\s+([A-Z]{2})\s+(\d+)\s*$',l)
        if mm:
            nm=mm.group(2).strip()
            for sfx,fz in (('CONDOMINIO AGUA LIMPA','AGUA LIMPA'),('E S FENIX','FENIX')):
                if nm.endswith(sfx): nm=nm[:-len(fz)].strip(); out.append((int(mm.group(1)),nm,fz,mm.group(3),int(mm.group(4)))); break
            else: out.append(('??',l))
    return out
ie=next(i for i,l in enumerate(L) if 'PONTOS POR CRIADOR' in l)
ir=next(i for i,l in enumerate(L) if 'REPRODUTORES DA RA' in l)
rk=rank_lines(0,ie); rkc=rank_lines(ie,ir)
def fixr(x):
    p,nm,fz,uf,pt=x
    if nm.startswith('CESAR AUGUSTO BRUNETO'): nm,fz='CESAR AUGUSTO BRUNETO E OUTRO CONDOMINIO','AGUA LIMPA'
    if nm.startswith('MOACYR ANTONIO LAGES'): nm,fz='MOACYR ANTONIO LAGES KOWARICK DE SOUZA E SILVA','FENIX'
    return (p,nm,fz,uf,pt)
rk=[fixr(x) for x in rk]; rkc=[fixr(x) for x in rkc]
# ---- 4) inserir
EI=len(E)
dias=set()
for c in cat_cards:
    d=datetime.datetime.strptime(c['nasc'],'%d/%m/%Y').date()
    if c['idade'] is not None: dias.add(d+datetime.timedelta(days=c['idade']))
from collections import Counter
dbc=Counter(dias)
DB=dbc.most_common(1)[0][0]
aidx={a[0]:i for i,a in enumerate(A)}
rep={'novos':[],'exist':[],'conf':[]}
amap={}
def addanimal(c):
    rg=c['rg']; nasc=datetime.datetime.strptime(c['nasc'],'%d/%m/%Y').date().isoformat()
    if rg in aidx:
        a=A[aidx[rg]]
        if norm(a[1])!=norm(c['nome']) or a[3]!=nasc: rep['conf'].append((rg,a[1],c['nome'],a[3],nasc))
        if rg not in amap: rep['exist'].append((rg,a[1]))
        amap[rg]=aidx[rg]; return aidx[rg]
    row=[rg,c['nome'],c['sx'] if 'sx' in c else '?',nasc,sidx(c['pai']),c['pairg'],sidx(c['mae']),c['maerg'],sidx(c['avop']),sidx(c['avom']),sidx(c['criador']),-1,'']
    A.append(row); aidx[rg]=len(A)-1; amap[rg]=aidx[rg]; rep['novos'].append((rg,c['nome'])); return aidx[rg]
groups={}
for c in cat_cards: groups.setdefault((c['champ'],c['cat'],c['sub']),[]).append(c)
nR=0; byrg={}
for c in cat_cards:
    ai=addanimal(c); byrg[c['rg']]=c
    g=groups[(c['champ'],c['cat'],c['sub'])]
    flag=('Pre+' if c['pr']=='S' else '')+('Par' if c['cria']=='S' else '')
    nasc=datetime.datetime.strptime(c['nasc'],'%d/%m/%Y').date()
    R.append([EI,ai,sidx(c['champ']),c['mi'],c['mf'],c['sub'],c['pos'],len(g),c['peso'],(DB-nasc).days,sidx(c['exp']),flag]); nR+=1
nC=0; miss=[]
for c in champ_cards:
    t=c['title'] or ''; tl=t.lower()
    lvl=2 if tl.startswith('reservad') else 3 if tl.startswith('terceir') else 1
    if 'grande' in tl: cat='GRANDE'
    else:
        cat=catn(re.sub(r'^(terceir[oa] melhor\s+)?(reservad[oa]\s+)?campe[ãa]o?\s+','',tl))
    if c['rg'] not in byrg: miss.append((c['rg'],c['nome'],t)); continue
    b=byrg[c['rg']]
    C.append([EI,amap[c['rg']],sidx(cat),lvl,b['peso'],sidx(b['exp']),b['sx']]); nC+=1
exps=set(norm(c['exp']) for c in cat_cards)
nf=sum(1 for c in cat_cards if c['sx']=='F'); nm_=len(cat_cards)-nf
ev={'nome':NOME,'cidade':'Uberaba','uf':'MG','ini':'2024-04-27','fim':'2024-05-05','db':DB.isoformat(),'n':len(cat_cards),'nf':nf,'nm':nm_,'exp':len(rk),'ind':None,
 'jur':['RAFAEL MAZAO GHIZZONI','FERNANDO JOSE GARCIA DE CARVALHO'],'arq':'ExpoZebu_2024_Resultado_Nelore.pdf','aus':0,'nivel':'N','src':'abcz','oficial':NOME,'serie':'Expozebu',
 'rk':[[p,sidx(e),sidx(f),uf,float(pt)] for p,e,f,uf,pt in rk],'rkc':[[p,sidx(cn),float(pt)] for p,cn,fz,uf,pt in rkc]}
E.append(ev)
new=json.dumps(D,ensure_ascii=False,separators=(',',':'))
if '--dry' not in sys.argv: open(H,'w',encoding='utf-8').write(h[:m.start(2)]+new+h[m.end(2):])
print('DB',DB,dict(dbc.most_common(4)))
print('cards cat',len(cat_cards),'F',nf,'M',nm_,'R+',nR,'C+',nC,'champ cards',len(champ_cards),'miss',miss)
print('rk',len(rk),'rkc',len(rkc),[x for x in rk+rkc if x[0]=='??'])
print('A novos',len(rep['novos']),'exist',len(rep['exist']),'S novos',len(newS),'exp',len(exps))
print('CONFLITOS',json.dumps(rep['conf'],ensure_ascii=False))
print('groups',len(groups),Counter(len(v) for v in groups.values()).most_common(5))
print('S novos',newS)
# sanidade
bad=[(c['rg'],c['nome']) for c in cat_cards if not (c['criador'] and c['mae'] and c['maerg'] and c['exp'] and c['peso'] and c['pos'])]
print('incompletos',bad)
json.dump({'rep':rep,'cats':sorted(set((k[0],k[1]) for k in groups))},open('/tmp/claude-0/-home-claude/6bb9e83c-7722-5fa5-85ab-583cb2b9a57a/scratchpad/ez24/rep.json','w'),ensure_ascii=False)
if '--dbg' in sys.argv:
    for x in rk+rkc:
        if 'BRUNETO' in x[1] or 'KOWARICK' in x[1]: print(x)
    for c in cat_cards:
        if 'BRUNETO' in c['exp'] or 'KOWARICK' in c['exp'] or 'BRUNETO' in c['criador']: print(c['exp'],'|',c['criador'],'|',c['faz']); 
    print(len(rk),len(set(x[0] for x in rk)),len(rkc))
    e=[x for x in E if x['nome']=='88ª Expozebu 2023'][0]; print(len(e['rk']),e['exp'],len(e['rkc']))
