#!/usr/bin/env python3
"""Lança PDFs de resultado da 55ª Expoinel Nacional 2026 de uma vez só.

uso (na raiz do repositório):
    python3 tools/lancar.py "DD/MM HH:MM" arquivo1.pdf [arquivo2.pdf ...] [--sv N] [--no-git]

Aceita PDFs de sub (Sequência/Sub-divisão) e de campeonato (Campeã / Reservada / 3º Prêmio).
Faz: git pull -> lê e confere cada PDF com o catálogo e a grade dos jurados -> embute no
nacional.html (LIVE) -> grava os documentos do banco em tools/out/ -> commit + push.
No fim imprime um resumo curto e o JSON de `writes` pronto para o ArtifactData batch
do SE Agro Pista (coleção aovivo). --sv N força a versão atual do doc `status`.
"""
import json, re, subprocess, sys, unicodedata, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'out'); os.makedirs(OUT, exist_ok=True)
EST = os.path.join(ROOT, 'tools', 'estado.json')
NAC = os.path.join(ROOT, 'nacional.html')

args = sys.argv[1:]
nogit = '--no-git' in args; args = [a for a in args if a != '--no-git']
sv = None
if '--sv' in args:
    i = args.index('--sv'); sv = int(args[i + 1]); del args[i:i + 2]
T, pdfs = args[0], args[1:]
assert re.fullmatch(r'\d\d/\d\d \d\d:\d\d', T), 'hora no formato "DD/MM HH:MM"'

def sh(*c): return subprocess.run(c, cwd=ROOT, capture_output=True, text=True)
if not nogit: sh('git', 'pull', '-q', '--rebase')

s = open(NAC, encoding='utf8').read()
m = re.search(r'(<script type="application/json" id="data">)(.*?)(</script>)', s, re.S)
D = json.loads(m.group(2)); L = D['LIVE']; A, S, K = D['A'], D['S'], D['K']
nk = lambda x: re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFD', x).encode('ascii', 'ignore').decode().upper())
BYCT = {r[9]: r for r in K}
tc = lambda x: ' '.join(w.capitalize() for w in str(x).split())

def parse(pdf):
    t = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    Ls = t.split('\n'); rows = []
    for l in Ls:
        mm = re.match(r'\s*(\d+)\s+(\d+)\s{2,}(.+?)\s{2,}(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s{2,}\S', l)
        if mm:
            p, c, nm, n, j1, j2, j3 = mm.groups(); rows.append([int(p), int(c), nm.strip(), int(n), int(j1), int(j2), int(j3)])
    i = next(k for k, l in enumerate(Ls) if 'NOTAS DO(S) JURADO(S)' in l)
    g = []
    for l in Ls[i + 2:i + 8]:
        nums = re.findall(r'\b\d+\b', l)
        if nums: g.append([int(x) for x in nums])
    return t, Ls, rows, g[:3]

avisos, writes, resumo = [], [], []

def check(rows, g, pool, label):
    """confere nomes, grade dos jurados e sequência de colocações"""
    for p, c, nm, n, j1, j2, j3 in rows:
        assert c in pool, f'{label}: catálogo {c} não pertence a esta disputa'
        if nk(A[BYCT[c][0]][1]) != nk(nm): avisos.append(f'{label}: nome diferente no {c} — catálogo "{A[BYCT[c][0]][1]}" × PDF "{nm}"')
        for k, j in enumerate((j1, j2, j3)):
            if g[k][j - 1] != c: avisos.append(f'{label}: voto do jurado {k+1} no {c} ({j}º) não bate com a grade')
    assert [x[0] for x in rows] == list(range(1, len(rows) + 1)), f'{label}: colocações fora de sequência'
    for a, b in zip(rows, rows[1:]):
        if a[3] == b[3]: avisos.append(f'{label}: empate {a[3]} pts — {a[1]} {tc(a[2])} ({a[0]}º) e {b[1]} {tc(b[2])} ({b[0]}º), desempate da organizadora')

def top3(rows):
    return '; '.join(f'{p}º {c} {tc(nm)} ({n}) — {tc(S[BYCT[c][7]])}' for p, c, nm, n, *_ in rows[:3])

camps_touched = set()
for pdf in pdfs:
    t, Ls, rows, g = parse(pdf)
    mc = re.search(r'Campeonato:\s*(.+)', t)
    if mc and 'Categoria' not in mc.group(0) and 'Sequência' not in t:
        txt = mc.group(1).strip(); up = nk(txt)
        kind = 2 if 'RESERV' in up else 3 if ('PREMIO' in up or 'TERCEIR' in up) else 1
        sx = 'M' if re.search(r'Sexo:\s*Macho', t) else 'F'
        cat = 'GRANDE' if 'GRANDE' in up else re.sub(r'^(Grande\s+)?(Campeã|Campeão|Campea|Campeao|Reservada|Reservado|3º Prêmio|3º Premio|Terceira|Terceiro)\s+', '', txt, flags=re.I).strip().upper()
        if cat != 'GRANDE': cat = next((x for x in set(S[r[1]] for r in K) if nk(x) == nk(cat)), cat)
        if cat != 'GRANDE': assert cat in set(S[r[1]] for r in K), f'categoria não reconhecida: {cat!r}'
        pool = {r[9] for r in K if A[r[0]][2] == sx and (cat == 'GRANDE' or S[r[1]] == cat)}
        label = f'{"Fêmeas" if sx=="F" else "Machos"} · {["","Campeã(o)","Reservada(o)","3º Prêmio"][kind]} {cat}'
        check(rows, g, pool, label)
        key = f'{sx}|{cat}'; o = L['camp'].setdefault(key, {'l': [], 'cl': [], 't': T})
        l = [x for x in o.get('l', []) if x[0] != kind] + [[kind, rows[0][1]]]; o['l'] = sorted(l)
        tail = [x for x in o.get('cl', []) if x[0] >= 4]
        if kind == 3: tail = [[i + 4, r[1]] for i, r in enumerate(rows[1:])]
        o['cl'] = o['l'] + tail; o['t'] = T
        camps_touched.add(key)
        resumo.append(f'{label}: {rows[0][1]} {tc(rows[0][2])} ({rows[0][3]}) — {tc(S[BYCT[rows[0][1]][7]])}' + (f' | 2º no PDF: {rows[1][1]} {tc(rows[1][2])}' if len(rows) > 1 else ''))
    else:
        seq = int(next(x for x in Ls[next(i for i, l in enumerate(Ls) if 'Sequência' in l) + 1:][:4] if x.strip()).split()[0])
        sub = next(x for x in Ls[next(i for i, l in enumerate(Ls) if 'Sub-divisão' in l) + 1:][:4] if x.strip()).split()[0]
        catx = re.search(r'Campeonato / Categoria:\s*(.+)', t).group(1).strip()
        pool = {r[9] for r in K if r[10] == seq and r[4] == sub}
        label = f'{seq}-{sub}'
        check(rows, g, pool, label)
        aus = sorted(pool - {r[1] for r in rows})
        L['subs'][label] = {'r': [[c, p, n, j1, j2, j3] for p, c, nm, n, j1, j2, j3 in rows], 'aus': aus, 't': T}
        d = {'tipo': 'sub', 'seq': seq, 'sub': sub, 'cat': catx, 't': T, 'aus': aus,
             'r': [{'c': c, 'p': p, 'n': n, 'j1': j1, 'j2': j2, 'j3': j3} for p, c, nm, n, j1, j2, j3 in rows]}
        f = os.path.join(OUT, f's-{seq}-{sub}.json'); json.dump(d, open(f, 'w'), ensure_ascii=False)
        writes.append({'op': 'set', 'collection': 'aovivo', 'doc_id': f's-{seq}-{sub}', 'file_path': f})
        ausn = ', '.join(f'{c} {tc(A[BYCT[c][0]][1])}' for c in aus) or 'nenhuma'
        resumo.append(f'Sub {label} · {tc(catx.split(":")[0])} {catx.split("DE MAIS DE")[-1].strip().lower() if "DE MAIS DE" in catx else ""} · {len(rows)} julgados · ausências: {ausn}\n   {top3(rows)}')

for key in sorted(camps_touched):
    sx, cat = key.split('|'); o = L['camp'][key]
    d = {'tipo': 'camp', 'sx': sx, 'cat': cat, 'l': o['l'], 'cl': o['cl'], 't': o['t']}
    did = 'c-' + sx + '-' + unicodedata.normalize('NFD', cat).encode('ascii', 'ignore').decode().replace(' ', '-')
    f = os.path.join(OUT, did + '.json'); json.dump(d, open(f, 'w'), ensure_ascii=False)
    writes.append({'op': 'set', 'collection': 'aovivo', 'doc_id': did, 'file_path': f})
    if len(o['l']) < 3: avisos.append(f'{key}: campeonato incompleto ({len(o["l"])} de 3 PDFs) — falta {", ".join(n for k,n in [(1,"Campeã(o)"),(2,"Reservada(o)"),(3,"3º Prêmio")] if k not in [x[0] for x in o["l"]])}')

L['upd'] = T
s = s[:m.start(2)] + json.dumps(D, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + s[m.end(2):]
open(NAC, 'w', encoding='utf8').write(s)

# versões dos docs do banco (cada gravação soma 1). Se o batch recusar por versão, ele informa a
# versão atual: rode de novo com --sv N (status) ou corrija tools/estado.json e refaça o batch.
est = json.load(open(EST)) if os.path.exists(EST) else {'v': {}}
V = est.setdefault('v', {})
if sv is not None: V['status'] = sv
writes.append({'op': 'update', 'collection': 'aovivo', 'doc_id': 'status', 'data': {'upd': T}})
for w in writes:
    if w['doc_id'] in V: w['if_version'] = V[w['doc_id']]
    V[w['doc_id']] = V.get(w['doc_id'], 0) + 1
json.dump(est, open(EST, 'w'), ensure_ascii=False, indent=0, sort_keys=True)

tot = len({r[10] * 100 + ord(r[4]) for r in K})
print('\n'.join(resumo))
print(f'Total: {len(L["subs"])}/{tot} subs · {len(L["camp"])} campeonatos · upd {T}')
print('AVISOS:\n- ' + '\n- '.join(avisos) if avisos else 'Sem divergências.')
if not nogit:
    msg = 'Resultados: ' + ', '.join(x.split(' ·')[0].split(':')[0] for x in resumo) + f' ({T})'
    sh('git', 'add', 'nacional.html', 'tools/estado.json')
    r = sh('git', '-c', 'user.name=miroleao', '-c', 'user.email=mirobleao@gmail.com', 'commit', '-q', '-m',
           msg + '\n\nCo-Authored-By: Claude <noreply@anthropic.com>')
    p = sh('git', 'push', '-q', 'origin', 'main')
    if p.returncode: p = (sh('git', 'pull', '-q', '--rebase'), sh('git', 'push', '-q', 'origin', 'main'))[1]
    print('GitHub:', 'ok' if p.returncode == 0 else 'ERRO ' + p.stderr.strip())
print('WRITES=' + json.dumps(writes, ensure_ascii=False))
