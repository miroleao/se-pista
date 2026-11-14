#!/usr/bin/env python3
"""Converte o catálogo de uma exposição (CSV normalizado) em documentos do banco do Tattersal.

uso (na raiz do repositório):
    python3 tools/catalogo.py catalogo.csv --nome "Expoapi 2026" --cidade "Araçatuba" --uf SP \
        --ini 2026-12-08 --fim 2026-12-13 --db 2026-12-08 [--novo]

CSV (UTF-8, separador ; ou ,), uma linha por animal, cabeçalho com estes nomes:
    ct, seq, sub, sx, cat, m1, m2, animal, rg, pai, mae, avo, expositor, peso, nasc
  ct = nº do catálogo · seq = sequência · sub = subdivisão (A, B…) · sx = F/M (ou Fêmea/Macho)
  cat = categoria (ex.: Bezerra Maior) · m1/m2 = faixa de meses · avo = avô materno
  peso em kg (aceita vírgula) · nasc = DD/MM/AAAA ou AAAA-MM-DD
Faz: valida, grava tools/catalogo_atual.json (usado pelo lancar.py --tatt) e os documentos
tools/out/cat-<gen>-NN.json (tipo "cat", até 100 animais cada) e imprime WRITES=[...] para o
Claude gravar na coleção aovivo do Tattersal. A aba "Ao vivo" lê esses documentos sozinha.
--novo zera o acompanhamento anterior (tools/live_tatt.json e tools/estado_tatt.json).
"""
import csv, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'out'); os.makedirs(OUT, exist_ok=True)
a = sys.argv[1:]
def opt(n, d=''):
    if n in a:
        i = a.index(n); v = a[i + 1]; del a[i:i + 2]; return v
    return d
novo = '--novo' in a; a = [x for x in a if x != '--novo']
meta = {k: opt('--' + k) for k in ('nome', 'cidade', 'uf', 'ini', 'fim', 'db')}
assert a and meta['nome'], 'uso: catalogo.py catalogo.csv --nome "..." [--cidade --uf --ini --fim --db] [--novo]'
txt = open(a[0], encoding='utf-8-sig').read()
dl = ';' if txt.split('\n', 1)[0].count(';') >= txt.split('\n', 1)[0].count(',') else ','
rd = list(csv.DictReader(txt.splitlines(), delimiter=dl))
rd = [{(k or '').strip().lower(): (v or '').strip() for k, v in r.items()} for r in rd]
ALIAS = {'animal': ('animal', 'nome'), 'expositor': ('expositor',), 'rg': ('rg', 'registro')}
def g(r, k):
    for n in ALIAS.get(k, (k,)):
        if r.get(n): return r[n]
    return ''
def iso(d):
    d = d.strip()
    m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', d)
    if m: return f'{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}'
    return d if re.fullmatch(r'\d{4}-\d\d-\d\d', d) else ''
def num(v):
    v = v.replace('.', '').replace(',', '.') if ',' in v else v
    try: return float(v) if v else None
    except ValueError: return None
rows, avisos, seen = [], [], set()
for i, r in enumerate(rd, 2):
    ct = int(re.sub(r'\D', '', g(r, 'ct')) or 0)
    if not ct: avisos.append(f'linha {i}: sem número de catálogo'); continue
    if ct in seen: avisos.append(f'linha {i}: catálogo {ct} repetido'); continue
    seen.add(ct)
    sx = 'F' if g(r, 'sx').upper().startswith('F') else 'M' if g(r, 'sx').upper().startswith('M') else ''
    if not sx: avisos.append(f'catálogo {ct}: sexo não reconhecido')
    nasc = iso(g(r, 'nasc'))
    if g(r, 'nasc') and not nasc: avisos.append(f'catálogo {ct}: nascimento ilegível "{g(r, "nasc")}"')
    p = num(g(r, 'peso'))
    m1 = int(g(r, 'm1')) if g(r, 'm1').isdigit() else None; m2 = int(g(r, 'm2')) if g(r, 'm2').isdigit() else None
    if not g(r, 'seq') or not g(r, 'sub'): avisos.append(f'catálogo {ct}: falta sequência ou subdivisão')
    rows.append([ct, int(g(r, 'seq') or 0), g(r, 'sub').upper() or 'A', sx, g(r, 'cat').upper(), m1, m2, g(r, 'animal'), g(r, 'rg'),
                 g(r, 'pai'), g(r, 'mae'), g(r, 'avo'), g(r, 'expositor'), int(p) if p and p == int(p) else p, nasc])
    if not nasc: avisos.append(f'catálogo {ct}: sem nascimento (idade ficará em branco)')
    if p is None: avisos.append(f'catálogo {ct}: sem peso')
rows.sort(key=lambda x: x[0])
subs = {}
for r in rows: subs.setdefault((r[1], r[2]), set()).add((r[3], r[4]))
for k, v in subs.items():
    if len(v) > 1: avisos.append(f'sub {k[0]}-{k[1]}: mistura sexo/categoria {sorted(v)}')
gen = time.strftime('%Y%m%d%H%M%S')
meta = {k: v for k, v in meta.items() if v}
writes = []
for n, i in enumerate(range(0, len(rows), 100), 1):
    d = {'tipo': 'cat', 'gen': gen, 'parte': n, 'de': (len(rows) + 99) // 100, 'rows': rows[i:i + 100]}
    if n == 1: d['ev'] = meta
    did = f'cat-{gen}-{n:02d}'; f = os.path.join(OUT, did + '.json'); json.dump(d, open(f, 'w'), ensure_ascii=False)
    writes.append({'op': 'set', 'collection': 'aovivo', 'doc_id': did, 'file_path': f})
json.dump({'gen': gen, 'meta': meta, 'rows': rows}, open(os.path.join(ROOT, 'tools', 'catalogo_atual.json'), 'w'), ensure_ascii=False)
if novo:
    json.dump({'subs': {}, 'camp': {}, 'upd': ''}, open(os.path.join(ROOT, 'tools', 'live_tatt.json'), 'w'))
    json.dump({'v': {}}, open(os.path.join(ROOT, 'tools', 'estado_tatt.json'), 'w'))
print(f'{len(rows)} animais · {len(subs)} subdivisões · {len(writes)} documento(s) · geração {gen}')
print('AVISOS:\n- ' + '\n- '.join(avisos[:40]) + (f'\n- … e mais {len(avisos) - 40}' if len(avisos) > 40 else '') if avisos else 'Sem divergências.')
print('WRITES=' + json.dumps(writes, ensure_ascii=False))
