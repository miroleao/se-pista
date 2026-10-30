#!/usr/bin/env python3
# Adiciona a 76a Expoagro 2026 (Maceio/AL) ao index.html (SE Agro Pista)
import re,json,unicodedata,datetime,sys
H='/home/claude/se-pista/index.html'
h=open(H,encoding='utf-8').read()
m=re.search(r'(<script type="application/json" id="data">)(.*?)(</script>)',h,re.S)
D=json.loads(m.group(2))
S,E,A,R,C=D['S'],D['E'],D['A'],D['R'],D['C']
def norm(s): return re.sub(r'[^A-Z0-9]','',unicodedata.normalize('NFKD',s.upper()).encode('ascii','ignore').decode())
SM={}
for i,s in enumerate(S): SM.setdefault(norm(s),i)
newS=[]
FIX={') PAGROPECUARIA LTDA':'J P AGROPECUÁRIA LTDA','CHEVERRIAQ FIV DA 42':'CHEVERRIA9 FIV DA 42','PAGROPECUARIA LTDA':'J P AGROPECUÁRIA LTDA','RIMAA7313':'RIMA A7313'}
NAMEFIX={'AFJI146':'CRSTAL FIV ARESE','GAM487':'DAILA FIV N. GAM','ANP7090':'LIBERIA DA ANP','JALC389':'GIFT DA COLINAS JALC','RSBP8523':'OZANA DA RS','CLBE31':'DAMASCO DA N. VIDA'}
def sidx(s):
    s=s.strip(" _.'|")
    if not s: return -1
    s=FIX.get(s,s)
    k=norm(s)
    if k in SM: return SM[k]
    S.append(s); SM[k]=len(S)-1; newS.append(s); return SM[k]
cards=json.load(open('/home/claude/se-pista/tools/maceio_cards.json'))
DB=datetime.date(2026,10,26)
if any(e['nome']=='Maceió 2026' for e in E): sys.exit('ja existe')
# fixes manuais (OCR)
EXPFIX={'HDR AGRONEGOCIOS LTDA':'HDR AGRONEGÓCIOS LTDA','J PAGROPECUARIA LTDA':'J P AGROPECUÁRIA LTDA'}
def expo(s):
    s=s.strip(" _.'|").replace('LUIZ JATOBA FILHO','LUIZ JATOBA FILHO .') if False else s.strip(" _'|")
    return s
def clean(s):
    return re.sub(r'\s+',' ',s).strip()
cl={x['ct']:x for x in cards if ':' in x['sec']}
EI=len(E)
# animais
aidx={a[0]:i for i,a in enumerate(A)}
report={'novos':[],'exist':[],'conf':[]}
def anc(line,tag):
    mm=re.match(r'^\S+:\s*(.*?)\s+-\s+(\S+)\s+(.*?)\s*(?:Criador|Expositor):',line)
    if not mm: return ('','','')
    avo=mm.group(3).strip(); avo=re.sub(r'\s*-\s*[A-Z]*\d+[A-Z0-9_]*$','',avo) if avo!='-' else ''
    avo=avo.strip(' -_')
    avo=re.sub(r'[^A-Z0-9)]+$','',avo)
    avo=re.sub(r'\s*-\s*[A-Z]*\d+[A-Z0-9_]*$','',avo).strip(' -_')
    return (mm.group(1).strip(),mm.group(2).strip(),avo)
amap={}
for ct,x in sorted(cl.items()):
    rg=x['rgd'].replace('LJUFI','LJFI');nasc=datetime.datetime.strptime(x['nasc'],'%d/%m/%Y').date().isoformat()
    pai,pairg,avop=anc(x['paiL'],'p'); mae,maerg,avom=anc(x['maeL'] if x['maeL'] else '', 'm')
    nome=NAMEFIX.get(rg,clean(x['nome']))
    if rg in aidx:
        i=aidx[rg]; a=A[i]
        if norm(a[1])!=norm(nome) or a[3]!=nasc: report['conf'].append((rg,a[1],nome,a[3],nasc))
        report['exist'].append((rg,a[1]))
    else:
        row=[rg,nome,x['sx'],nasc,sidx(pai),pairg,sidx(mae),maerg,sidx(avop),sidx(avom),sidx(x['criador']),-1,'']
        A.append(row); i=len(A)-1; aidx[rg]=i; report['novos'].append((rg,nome))
    amap[ct]=i
def catn(s):
    s=s.split(':')[0].strip().upper()
    return s.replace('JUNIOR','JÚNIOR').replace('SENIOR','SÊNIOR')
# classes -> R
groups={}
for ct,x in sorted(cl.items()): groups.setdefault((x['sx'],x['sec']),[]).append(x)
nR=0
for (sx,sec),L in groups.items():
    mm=re.search(r'DE\s+(?:MAIS DE\s+)?(\d+)\s+MESES\s+ATE\s+(\d+)',sec)
    mi,mf=int(mm.group(1)),int(mm.group(2))
    cat=sidx(catn(sec))
    L=sorted(L,key=lambda y:y['p']*1000+(y['ct'] if False else 0))  # ordem do documento
    L=[y for y in groups[(sx,sec)]]
    for k,y in enumerate(L,1):
        nasc=datetime.datetime.strptime(y['nasc'],'%d/%m/%Y').date()
        R.append([EI,amap[y['ct']],cat,mi,mf,'',k,len(L),y['peso'],(DB-nasc).days,sidx(y['expositor']),y['flag']]); nR+=1
# campeonatos
ch=[x for x in cards if ':' not in x['sec'] and not x['sec'].startswith('Prog')]
nC=0
for x in ch:
    t=x['sec']
    lvl=3 if t.startswith('3') else 2 if t.startswith('RESERV') else 1
    base=re.sub(r'^(3° PREMIO |RESERVAD[AO] |)','',t)
    base=re.sub(r'^(CAMPE[AÃ]O?|CAMPEA) ','',base)
    if base.startswith('GRANDE'): cat='GRANDE'
    else: cat=catn(base)
    y=cl[x['ct']]
    C.append([EI,amap[x['ct']],sidx(cat),lvl,y['peso'],sidx(y['expositor']),x['sx']]); nC+=1
# ranking
rk=[(1,'ANTONIO FABIO SANTOS DANTAS','NOSSA SENHORA DE FATIMA','SE',772),(2,'HDR AGRONEGÓCIOS LTDA','FAZENDA HARAS DONA ROSA','CE',740),(3,'LUIZ JATOBA FILHO .','FAZ. IMBIRIBEIRA','AL',516),(4,'JOSENILDO ALCANTARA DE SOUZA','FAZ. COLINAS','PB',285),(5,'JOSE DA SILVA NOGUEIRA FILHO','ENG. BUENOS AIRES','AL',139),(6,'DAVI CAVALCANTI NOGUEIRA','FAZENDA ENGENHO BUENOS','AL',125),(7,'VICENTE VIDAL SAMPAIO','FAZENDA HARAS DONA ROSA','CE',40)]
rkc=[(1,'LUIZ JATOBA FILHO',464),(2,'JOSENILDO ALCANTARA DE SOUZA',293),(3,'JANDER MASCARENHAS MARQUES',198),(4,'JOSE GILMAR DE CARVALHO LOPES',180),(5,'LUIZ APARECIDO DE ANDRADE OUT - COND.',156),(6,'CÁSSIO MARTINHO TOTTENE',148),(7,'JOSÉ DA SILVA NOGUEIRA FILHO',139),(8,'LUCIO FLAVIO DA SILVEIRA QUEIROZ',132),(9,'ANTÔNIO FABIO SANTOS DANTAS',126),(10,'DAVI CAVALCANTI NOGUEIRA',125),(11,'CESAR TOME GARETTI',115),(12,'JORGE LUIZ SOUSA SANTOS',110),(13,'FAZENDA DO SABIA',100),(14,'ANTONIO LUIS AUGUSTO RODRIGUES',60),(14,'JORGE LUIZ SOUSA SANTOS',60),(14,'JOSÉ ANTÔNIO FURTADO',60),(17,'MAGDA JACOME PATRIOTA',40),(17,'ROBERTO BAVARESCO',40),(19,'ANDRÉ LUIZ VOLPE E ANDERSON EDUARDO VOLPE',35),(20,'CLAUDIO LEONARDO BARBOZA',24),(20,'RAPHAEL ZOLLER',24),(22,'AGROPECUARIA NELORE PARANÃ LTDA',20),(23,'JULIO GALVÃO PASSOS SALES',16)]
ev={'nome':'Maceió 2026','cidade':'Maceió','uf':'AL','ini':'2026-10-23','fim':'2026-11-01','db':'2026-10-26','n':62,'nf':44,'nm':18,'exp':7,'ind':1.0,'jur':['RAFAEL RESENDE DE OLIVEIRA'],'arq':'RESULTADO_FINAL_NELORE_MACEIO__2026.pdf','aus':0,'nivel':'R','src':'acnb',
 'rk':[[p,sidx(e),sidx(f),uf,float(pt)] for p,e,f,uf,pt in rk],'rkc':[[p,sidx(c),float(pt)] for p,c,pt in rkc],
 'oficial':'76ª Expoagro 2026 - O Encontro da Pecuária Nordestina'}
E.append(ev)
new=json.dumps(D,ensure_ascii=False,separators=(',',':'))
h2=h[:m.start(2)]+new+h[m.end(2):]
if '--dry' not in sys.argv: open(H,'w',encoding='utf-8').write(h2)
print('R+',nR,'C+',nC,'A novos',len(report['novos']),'A exist',len(report['exist']),'S novos',len(newS))
print('CONFLITOS',json.dumps(report['conf'],ensure_ascii=False))
print('S novos',newS)
json.dump(report,open('/tmp/maceio_report.json','w'),ensure_ascii=False)
