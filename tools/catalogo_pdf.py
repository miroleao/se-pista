#!/usr/bin/env python3
"""Lê o PDF do catálogo ACNB (sistema Gold Agroeventos) e gera o CSV para tools/catalogo.py.

uso (na raiz do repositório):
    python3 tools/catalogo_pdf.py catalogo.pdf [--saida catalogo.csv] [--dpi 200] [--jobs 2]

Os PDFs desse sistema vêm com fontes sem texto (Type 3), então o texto sai por OCR (tesseract) com
posição das palavras: cada cartão de animal é achado pelo número grande do catálogo (CTLG) à direita
e os campos são lidos por zona (nome, expositor, RG/sexo/nascimento, peso, pai, mãe, avô materno).
A sequência/subdivisão/categoria vêm do rodapé de cada subdivisão ("CATEGORIA: DE MAIS DE a MESES ATÉ b
MESES   N / A"). Só 1 chamada de OCR por página (~2 s).
Imprime um resumo da conferência: contagem por subdivisão (confere com "N Animal(is)" do PDF),
números de catálogo repetidos ou faltando e campos vazios. Progênie de mãe/pai não entra no CSV
(os mesmos animais já aparecem nas subdivisões normais).
"""
import csv, json, os, re, statistics, subprocess, sys, tempfile, unicodedata
from concurrent.futures import ThreadPoolExecutor

def nrm(s): return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode()

def ocr_page(png):
    r = subprocess.run(['tesseract', png, 'stdout', '--psm', '11', '-l', 'eng', 'tsv'], capture_output=True, text=True)
    ws = []
    for ln in r.stdout.split('\n')[1:]:
        f = ln.split('\t')
        if len(f) < 12 or f[0] != '5' or not f[11].strip(): continue
        ws.append({'x': int(f[6]), 'y': int(f[7]), 'w': int(f[8]), 'h': int(f[9]), 't': f[11].strip()})
    return ws

def lines_of(ws):
    """agrupa palavras em linhas (mesmo y) e ordena por x"""
    out = []
    for w in sorted(ws, key=lambda w: w['y']):
        for ln in out:
            if abs(w['y'] + w['h'] / 2 - ln['cy']) <= max(6, w['h'] * 0.7):
                ln['w'].append(w); ln['cy'] = sum(x['y'] + x['h'] / 2 for x in ln['w']) / len(ln['w']); break
        else: out.append({'cy': w['y'] + w['h'] / 2, 'w': [w]})
    for ln in out:
        ln['w'].sort(key=lambda w: w['x']); ln['txt'] = ' '.join(w['t'] for w in ln['w']); ln['x0'] = ln['w'][0]['x']
    return sorted(out, key=lambda l: l['cy'])

def ct_boxes(png):
    """acha as caixas pretas do número do catálogo (coluna da direita): só a posição vertical de cada cartão"""
    import numpy as np
    from PIL import Image, ImageOps
    im = Image.open(png).convert('L'); W, H = im.size
    a = np.asarray(im); x0, x1 = int(0.84 * W), int(0.985 * W)
    D = a[:, x0:x1] < 90
    dark = D.mean(axis=1) > 0.25
    boxes, i = [], 0
    while i < H:
        if dark[i]:
            j = i
            while j < H and dark[j]: j += 1
            if j - i >= 0.02 * H:
                cols = np.where(D[i:j].mean(axis=0) > 0.5)[0]
                if len(cols) and 0.06 * W <= len(cols) <= 0.14 * W: boxes.append((i, j))
            i = j
        else: i += 1
    return [{'y': t, 't': '0'} for (t, b) in boxes]

def nome_rg(s):
    s = re.sub(r'\s+', ' ', s).strip(' -')
    m = re.match(r'^(.*?)\s+-\s+([A-Z0-9]*\d[A-Z0-9]*)$', s)
    return (m[1].strip(), m[2]) if m else (s, '')

CATL = re.compile(r'^[FM]\w*\s*-\s*(.+?)\s*:?\s*(?:DE MAIS DE|DE)\s*(\d+)\s*MESES\s*ATE\s*(\d+)\s*MESES', re.I)
CATP = re.compile(r'^[FM]\w*\s*-\s*(Prog\w*(?:\s+\w+){0,3})\s*$', re.I)
FOOT = re.compile(r'^[FM]\w*\s*-\s*(.+?)\s*:?\s*(?:DE MAIS DE|DE)\s*(\d+)\s*MESES\s*ATE\s*(\d+)\s*MESES\s*(\d+)\s*/\s*([A-Z])\s*$', re.I)
FOOTP = re.compile(r'^[FM]\w*\s*-\s*(Prog\w*(?:\s+\w+)*?)\s+(\d+)\s*/\s*([A-Z])\s*$', re.I)
HEAD_N = re.compile(r'(\d+)\s*Animal', re.I)

def parse_table(ws, W):
    """linhas da 'Relação de animais por expositor': CTLG, idade, sexo, animal, RG -> lista de {ct, animal, rg}"""
    out = []
    for ln in lines_of(ws):
        t = ln['w']
        if len(t) < 4: continue
        if re.fullmatch(r'\d{1,3}M', t[0]['t']) and t[0]['x'] < 0.14 * W: t = [{'t': '', 'x': 0}] + t  # linha sem o número lido
        if not re.fullmatch(r'\d{0,4}', t[0]['t']) or t[0]['x'] > 0.09 * W: continue
        if not re.fullmatch(r'\d{1,3}M', t[1]['t']): continue
        nome = ' '.join(w['t'] for w in t[2:] if 0.165 * W <= w['x'] < 0.385 * W)
        rg = ''.join(w['t'] for w in t[2:] if 0.385 * W <= w['x'] < 0.46 * W)
        if nome and rg: out.append({'ct': int(t[0]['t']) if t[0]['t'] else None, 'animal': nome, 'rg': rg, 'sx': ''})
    return out

def parse_page(ws, W, bigs):
    """devolve eventos da página em ordem vertical: ('card', y, dict) | ('foot', y, dict) | ('head', y, dict)"""
    ev = []
    bigs = sorted(bigs, key=lambda w: w['y'])
    pitch = int(statistics.median([b['y'] - a['y'] for a, b in zip(bigs, bigs[1:]) if 150 < b['y'] - a['y'] < 400] or [245 * W / 1653]))
    X1, X2 = 0.39 * W, 0.735 * W
    for k, b in enumerate(bigs):
        top = b['y'] - 0.04 * pitch
        end = bigs[k + 1]['y'] - 0.04 * pitch if k + 1 < len(bigs) else top + pitch
        cw = [w for w in ws if top <= w['y'] < end]
        left = lines_of([w for w in cw if w['x'] < X1])
        mid = [w for w in cw if X1 <= w['x'] < X2]
        c = {'ct': None, 'animal': '', 'rg': '', 'sx': '', 'nasc': '', 'expositor': '', 'peso': '', 'pai': '', 'mae': '', 'avo': ''}
        if left: c['animal'] = re.sub(r'^[^A-Za-z0-9]+', '', left[0]['txt']).strip()
        for i, ln in enumerate(left):
            if re.match(r'^\W*Expositor', ln['txt'], re.I) and i + 1 < len(left):
                c['expositor'] = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9.)]+$', '', left[i + 1]['txt'].strip()); break
        hdr = [w for w in mid if w['y'] < top + 0.28 * pitch]
        toks = [w['t'] for w in sorted(hdr, key=lambda w: w['x'])]
        di = next((i for i, t in enumerate(toks) if re.fullmatch(r'\d{2}/\d{2}/\d{4}', t)), None)
        if di is not None:
            d, m_, y = toks[di].split('/'); c['nasc'] = f'{d}/{m_}/{y}'
            pre = nrm(''.join(toks[:di]))
            m_sx = re.search(r'(Femeas?|Machos?)$', pre, re.I)
            if m_sx: c['sx'] = 'F' if m_sx[1][0].upper() == 'F' else 'M'; pre = pre[:m_sx.start()]
            c['rg'] = pre.strip(' -|')
        for w in cw:
            if 0.715 * W <= w['x'] < 0.79 * W and re.fullmatch(r'\d{3,4}([.,]\d)?', w['t']) and w['y'] < top + 0.5 * pitch and w['h'] < 30: c['peso'] = w['t']
        ped = lines_of([w for w in mid if w['y'] >= top + 0.25 * pitch])
        pai_i = next((i for i, l in enumerate(ped) if re.match(r'^\W*Pai\W', l['txt'], re.I)), None)
        mae_i = next((i for i, l in enumerate(ped) if re.match(r'^\W*M[aãáâ]e\W', l['txt'], re.I)), None)
        strip = lambda s: re.sub(r'^\W*(Pai|M[aãáâ]e)\W*', '', s, flags=re.I)
        if pai_i is not None: c['pai'] = nome_rg(strip(ped[pai_i]['txt']))[0]
        if mae_i is not None:
            c['mae'] = nome_rg(strip(ped[mae_i]['txt']))[0]
            if mae_i >= 1 and mae_i - 1 != pai_i: c['avo'] = nome_rg(ped[mae_i - 1]['txt'])[0]
        ev.append(('card', top, c))
    cats = []
    for ln in lines_of(ws):
        t = nrm(ln['txt']).strip()
        m = CATL.match(t)
        if m:
            d = {'cat': m[1].strip().upper(), 'm1': int(m[2]), 'm2': int(m[3]), 'sx': 'F' if t[:1].upper() == 'F' else 'M'}
            cats.append((ln['cy'], d))
            if not re.search(r'\d+\s*/\s*\w\s*$', t): ev.append(('cat', ln['cy'], d))  # linha de categoria sem rodapé (pode ficar na página anterior ao "Seq.")
            continue
        m = CATP.match(t)
        if m: cats.append((ln['cy'], {'cat': m[1].strip().upper(), 'm1': None, 'm2': None, 'sx': 'F' if t[:1].upper() == 'F' else 'M', 'prog': True})); continue
        if re.match(r'^\W*Progeni\w*(?:\(s\))?\s+(?:Jovens\s+)?de\s+(?:Mae|Pai)', t, re.I):
            ev.append(('sub', ln['cy'], {'cat': 'PROGENIE', 'm1': None, 'm2': None, 'sx': '', 'seq': 0, 'sub': '', 'n': None, 'prog': True})); continue
        m = re.search(r'Seq\.?\s*(\d+)\s+Sub-?Divis\w*:?\s*([A-Z])\b(?:.*?(\d+)\s*Animal)?', t)
        if m:
            c = next((d for cy, d in reversed(cats) if 15 < ln['cy'] - cy < 90), None)
            ev.append(('sub', ln['cy'], {**(c or {'cat': '?', 'm1': None, 'm2': None, 'sx': ''}), 'seq': int(m[1]), 'sub': m[2].upper(), 'n': int(m[3]) if m[3] else None}))
    return sorted(ev, key=lambda e: e[1])

def main():
    a = sys.argv[1:]
    def opt(n, d):
        if n in a:
            i = a.index(n); v = a[i + 1]; del a[i:i + 2]; return v
        return d
    out = opt('--saida', 'catalogo.csv'); dpi = int(opt('--dpi', '200')); jobs = int(opt('--jobs', '2'))
    pdf = a[0]
    tmp = tempfile.mkdtemp(prefix='cat_')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', pdf, os.path.join(tmp, 'p')], check=True, stderr=subprocess.DEVNULL)
    pages = sorted(f for f in os.listdir(tmp) if f.endswith('.png'))
    from PIL import Image
    W = Image.open(os.path.join(tmp, pages[0])).size[0]
    with ThreadPoolExecutor(jobs) as ex:
        res = list(ex.map(lambda f: ocr_page(os.path.join(tmp, f)), pages))
        boxes = list(ex.map(lambda f: ct_boxes(os.path.join(tmp, f)), pages))
    seq_events, meta_txt, tabela, pg = [], [], [], 1
    for ws, bx in zip(res, boxes):
        meta_txt.append('\n'.join(l['txt'] for l in lines_of(ws)))
        seq_events += [(k, y, d, pg) for k, y, d in parse_page(ws, W, bx)]; pg += 1
        tabela += parse_table(ws, W)
    rows, heads, avisos, prog, cur, last_cat = [], {}, [], 0, None, None
    for kind, y, d, pgn in seq_events:
        if kind == 'cat': last_cat = d; continue
        if kind == 'sub':
            if d['cat'] == '?' and last_cat and not d.get('prog'): d = {**d, **{k: last_cat[k] for k in ('cat', 'm1', 'm2', 'sx')}}
            cur = d
            if not d.get('prog'): heads[(d['seq'], d['sub'])] = d.get('n')
        elif kind == 'card':
            if cur is None: continue  # capa/resumo: nada de animais antes da primeira subdivisão
            if cur.get('prog'): prog += 1; continue
            rows.append({**d, 'pg': pgn, 'seq': cur['seq'], 'sub': cur['sub'], 'cat': cur['cat'], 'm1': cur['m1'], 'm2': cur['m2'], 'sx': d['sx'] or cur['sx']})
    # número do catálogo: o CTLG segue a ordem dos cartões (1..N, subdivisão a subdivisão); a tabela por expositor
    # só serve para limpar o nome (o OCR às vezes cola um "I" da barra vertical) e para conferir o número
    import difflib
    key = lambda x: re.sub(r'[^A-Z0-9]', '', nrm(x).upper())
    for i, r in enumerate(rows):
        r['ct'] = i + 1
        r['rg'] = re.sub(r'(Femeas?|Machos?)$', '', nrm(r['rg']), flags=re.I).strip(' -|')
        t = next((t for t in tabela if key(t['rg']) and key(t['rg']) == key(r['rg'])), None)
        if t is None:
            cand = sorted(((difflib.SequenceMatcher(None, key(t['animal']), key(r['animal'])).ratio(), j) for j, t in enumerate(tabela)), reverse=True)
            if cand and cand[0][0] >= 0.85: t = tabela[cand[0][1]]
        if t is None: avisos.append(f'ct {r["ct"]} "{r["animal"]}" {r["rg"]}: não achado na tabela por expositor (nome pode ter ruído de OCR)'); continue
        if t['animal'] and t['animal'] != r['animal']: r['animal'] = t['animal']
        if t['ct'] is not None and t['ct'] != r['ct']: avisos.append(f'ct {r["ct"]} "{r["animal"]}": a tabela por expositor traz {t["ct"]} (leitura de número no OCR; vale a ordem do catálogo)')
    for r in rows:
        for k in ('animal', 'pai', 'mae', 'avo', 'expositor'):
            r[k] = re.sub(r'\bD[!|](?=\s|$)', 'DI', r[k]).strip(' .|\\[]')
    # expositor: ajusta ruído de OCR ("EEDVALDO", "IJOAO") ao nome mais frequente parecido
    from collections import Counter
    freq = Counter(r['expositor'] for r in rows)
    for r in rows:
        if freq[r['expositor']] <= 2:
            alvo = max(((difflib.SequenceMatcher(None, r['expositor'], e).ratio(), e) for e in freq if freq[e] > 2), default=(0, ''))
            if alvo[0] >= 0.9: r['expositor'] = alvo[1]
    # conferências
    cts = [r['ct'] for r in rows]
    dup = sorted({c for c in cts if cts.count(c) > 1})
    if dup: avisos.append(f'números de catálogo repetidos: {dup}')
    if cts:
        falta = sorted(set(range(1, max(cts) + 1)) - set(cts))
        if falta: avisos.append(f'números de catálogo faltando (1..{max(cts)}): {falta}')
    cnt = {}
    for r in rows: cnt[(r['seq'], r['sub'])] = cnt.get((r['seq'], r['sub']), 0) + 1
    for k, n in sorted(cnt.items()):
        if heads.get(k) not in (None, n): avisos.append(f'sub {k[0]}-{k[1]}: {n} cartões lidos × {heads[k]} animais no cabeçalho do PDF')
    for k in heads:
        if k not in cnt: avisos.append(f'sub {k[0]}-{k[1]}: cabeçalho diz {heads[k]} animais e nenhum cartão foi associado')
    for campo, nome in (('animal', 'sem nome'), ('rg', 'sem RG'), ('nasc', 'sem nascimento'), ('pai', 'sem pai'), ('mae', 'sem mãe'), ('expositor', 'sem expositor'), ('sx', 'sem sexo')):
        v = [r['ct'] for r in rows if not r[campo]]
        if v: avisos.append(f'{len(v)} {nome}: ct {v[:15]}')
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';'); w.writerow('ct seq sub sx cat m1 m2 animal rg pai mae avo expositor peso nasc'.split())
        for r in sorted(rows, key=lambda r: r['ct']):
            w.writerow([r['ct'], r['seq'], r['sub'], r['sx'], r['cat'], r['m1'] if r['m1'] is not None else '', r['m2'] if r['m2'] is not None else '', r['animal'], r['rg'], r['pai'], r['mae'], r['avo'], r['expositor'], r['peso'], r['nasc']])
    # metadados do evento (capa): período e data-base
    txt = '\n'.join(meta_txt[:3])
    mes = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
           'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12}
    def dt(d, m, y): return f'{y}-{mes[nrm(m).lower()]:02d}-{int(d):02d}'
    per = re.search(r'Per\w*:\s*(\d+)\s+de\s+(\w+)\s+at\w*\s+(\d+)\s+de\s+(\w+)\s+de\s+(\d{4})', nrm(txt))
    dbm = re.search(r'Data\s*Base\D{0,10}(\d+)\s+de\s+(\w+)\s+de\s+(\d{4})', nrm(txt))
    meta = {}
    try:
        if per: meta['ini'] = dt(per[1], per[2], per[5]); meta['fim'] = dt(per[3], per[4], per[5])
        if dbm: meta['db'] = dt(dbm[1], dbm[2], dbm[3])
    except KeyError: pass
    cid = re.search(r'\n([A-Z][A-Z ]+)\s*/\s*([A-Z]{2})\n', nrm(txt))
    if cid: meta['cidade'] = cid[1].strip().title(); meta['uf'] = cid[2]
    ttl = re.search(r'\n(\d+\W?\s*[A-Z][^\n]{8,80})\n', nrm(txt))
    if ttl: meta['titulo_ocr'] = ttl[1]
    json.dump(meta, open(os.path.splitext(out)[0] + '_meta.json', 'w', encoding='utf-8'), ensure_ascii=False)
    subs = len(cnt)
    print(f'{len(rows)} animais · {subs} subdivisões · {len(pages)} páginas · progênie ignorada: {prog} cartões')
    print('META:', json.dumps(meta, ensure_ascii=False))
    print('AVISOS:\n- ' + '\n- '.join(avisos) if avisos else 'Sem divergências.')
    print('CSV:', out)

main()
