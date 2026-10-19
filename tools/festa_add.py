#!/usr/bin/env python3
# Adiciona a 64a Festa do Boi 2026 (Parnamirim/RN) ao index.html (SE Agro Pista)
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
FIX={') PAGROPECUARIA LTDA':'J P AGROPECUÁRIA LTDA','CHEVERRIAQ FIV DA 42':'CHEVERRIA9 FIV DA 42','PAGROPECUARIA LTDA':'J P AGROPECUÁRIA LTDA'}
NAMEFIX={'JGLM1100':'DONA KIKI MONTANA JG','JGLM1000':'RARIDADE I FIV MONTANA JG','RSBP7488':'OSAKA DA RS','AFJI146':'CRSTAL FIV ARESE','JALC386':'LUA DA COLINAS JALC'}
def sidx(s):
    s=s.strip(" _.'|")
    if not s: return -1
    s=FIX.get(s,s)
    k=norm(s)
    if k in SM: return SM[k]
    S.append(s); SM[k]=len(S)-1; newS.append(s); return SM[k]
cards=json.load(open('/home/claude/se-pista/tools/festa_cards.json'))
DB=datetime.date(2026,10,15)
if any(e['nome']=='Parnamirim 2026' for e in E): sys.exit('ja existe')
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
    rg=x['rgd'];nasc=datetime.datetime.strptime(x['nasc'],'%d/%m/%Y').date().isoformat()
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
rk=[(1,'HDR AGRONEGÓCIOS LTDA','HDRAGRONEGOCIOS LTDA','CE',904),(2,'JOSE GILMAR DE CARVALHO LOPES','JAGUARANA','RN',702),(3,'LUIZ JATOBA FILHO .','FAZ. IMBIRIBEIRA','AL',564),(4,'J P AGROPECUÁRIA LTDA','J P AGROPECUARIA','RN',419),(5,'VICENTE VIDAL SAMPAIO','FAZENDA HDR AGRONEGOCIOS','CE',380),(6,'ANDRE DE QUEIROZ LEITE JALES','FAZ. STER BOM','RN',198),(7,'JOSE DA SILVA NOGUEIRA FILHO','ENG. BUENOS AIRES','AL',116),(8,'JOSENILDO ALCANTARA DE SOUZA','FAZ. COLINAS','PB',112),(9,'MODESTO CUNHA DE AZEVEDO','RANCHO AZEVEDO','RN',48),(10,'LUIZ OTAVIO VIEIRA DE MOURA CASTRO JATOBA','FAZENDA IMBIRIBEIRA','AL',40),(11,'MAGDA JACOME PATRIOTA',"OLHO 'AGUA",'RN',24)]
rkc=[(1,'JOSE GILMAR DE CARVALHO LOPES',660),(2,'LUIZ JATOBA FILHO',508),(3,'ESPOLIO JOÃO DINARTE PATRIOTA',374),(4,'JANDER MASCARENHAS MARQUES',208),(5,'J P AGROPECUÁRIA LTDA',194.25),(6,'DORIVAL GIBERTONI',186),(7,'JOSENILDO ALCANTARA DE SOUZA',164),(8,'MAGDA JACOME PATRIOTA',148.75),(9,'CESAR TOME GARETTI',131),(10,'JOSE DA SILVA NOGUEIRA FILHO',116),(11,'LUIZ APARECIDO DE ANDRADE OUT - COND.',108),(12,'CONDOMINIO RURAL OURO FINO',106),(13,'DAVI CAVALCANTI NOGUEIRA',100),(14,'CÁSSIO MARTINHO TOTTENE',73),(15,'SAUL FERREIRA DE MOURA FILHO',60),(16,'ANTONIO PIOVESAN',48),(17,'ANTONIO LUIS AUGUSTO RODRIGUES',40),(18,'NELORE MONTANA AGRONEGÓCIOS LTDA -EPP',37),(19,'JOSÉ ANTÔNIO FURTADO',32),(20,'JULIO GALVÃO PASSOS SALES',28),(20,'ANDRÉ LUIZ VOLPE E ANDERSON EDUARDO VOLPE',28),(20,'ROBERTO BAVARESCO',28),(23,'JOANA DA MOTA CORREA',20),(23,'HENRIQUE E JULIANO PRODUÇÕES E EVENTOS LTDA.',20),(25,'ANTÔNIO FABIO SANTOS DANTAS',16),(25,'MODESTO CUNHA DE AZEVEDO',16)]
ev={'nome':'Parnamirim 2026','cidade':'Parnamirim','uf':'RN','ini':'2026-10-09','fim':'2026-10-18','db':'2026-10-15','n':96,'nf':70,'nm':26,'exp':11,'ind':1.0,'jur':['EDUARDA GABRIELE DE AZEVEDO S. GUIMARÃES'],'arq':'RESULTADO_FINAL_NELORE_FESTA_DO_BOI_2026.pdf','aus':2,'nivel':'R','src':'acnb',
 'rk':[[p,sidx(e),sidx(f),uf,float(pt)] for p,e,f,uf,pt in rk],'rkc':[[p,sidx(c),float(pt)] for p,c,pt in rkc],
 'oficial':'64ª Exposição de Animais e Máquinas Agrícolas - Festa do Boi 2026'}
E.append(ev)
new=json.dumps(D,ensure_ascii=False,separators=(',',':'))
h2=h[:m.start(2)]+new+h[m.end(2):]
if '--dry' not in sys.argv: open(H,'w',encoding='utf-8').write(h2)
print('R+',nR,'C+',nC,'A novos',len(report['novos']),'A exist',len(report['exist']),'S novos',len(newS))
print('CONFLITOS',json.dumps(report['conf'],ensure_ascii=False))
print('S novos',newS)
json.dump(report,open('/tmp/festa_report.json','w'),ensure_ascii=False)
