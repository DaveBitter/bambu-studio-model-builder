#!/usr/bin/env python3
"""Parametric model -> Bambu Studio .3mf
usage: python3 build.py OUT.3mf [FALLBACK_SETTINGS.3mf]
OUT.3mf   file in the models folder, rewritten on every run
FALLBACK  any .3mf saved from Bambu Studio; used only when OUT does not exist yet
"""
import json, os, shutil, sys, time, zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import numpy as np, trimesh
from manifold3d import Manifold, CrossSection, JoinType

# ---- parameters (mm): edit and re-run ----
NAME = 'model'
W, D, H = 60, 60, 100      # outer width, depth, height
R = 24                     # corner radius: ~1 = square, W/2 = circle
FIL = 3                    # top-edge fillet
WALL, FLOOR = 3, 4

def rrect(w, d, r):
    # clamp the core: r = w/2 (a circle) would otherwise give an empty shape
    return CrossSection.square([max(w - 2*r, 0.01), max(d - 2*r, 0.01)], center=True).offset(r, JoinType.Round, 2.0, 96)

def extrude(cs, h):
    return Manifold.extrude(cs, h)

def build_body():
    # REPLACE with the real design. Example: open cup with a softened top edge.
    body = extrude(rrect(W, D, R), H - FIL)
    n = 8
    for i in range(n):
        a = (i + 0.5) / n * np.pi / 2
        inset = FIL * (1 - np.cos(a))   # cos, not sin: sin flares the edge into a lip
        body += extrude(rrect(W - 2*inset, D - 2*inset, max(R - inset, 1)), FIL / n).translate([0, 0, H - FIL + FIL * i / n])
    body -= extrude(rrect(W - 2*WALL, D - 2*WALL, max(R - WALL, 1)), H).translate([0, 0, FLOOR])
    return body

def read_settings(path):
    if not path or not os.path.exists(path) or not zipfile.is_zipfile(path):
        return None
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if 'Metadata/project_settings.config' not in names:
            return None
        proj = z.read('Metadata/project_settings.config')
        mcfg = z.read('Metadata/model_settings.config') if 'Metadata/model_settings.config' in names else None
    return proj, mcfg

def main():
    out = os.path.abspath(sys.argv[1])
    fallback = sys.argv[2] if len(sys.argv) > 2 else None
    got, used = None, None
    for cand in (out, fallback):          # existing output first: keeps what the user saved in Studio
        got = read_settings(cand)
        if got:
            used = cand
            break
    if not got:
        sys.exit('No settings source. Save any project from Bambu Studio (right printer, filament, process) and pass it as the 2nd argument.')
    proj, mcfg = got
    print('settings from:', 'existing output file' if used == out else used)

    # bed size and centre come from the user's printer profile, not from a hard-coded A1
    cfg = json.loads(proj)
    pts = [tuple(float(v) for v in p.split('x')) for p in cfg.get('printable_area', ['0x0', '256x0', '256x256', '0x256'])]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    max_h = float(cfg.get('printable_height', 1e9))   # Studio stores numbers as strings, so always cast

    # per-object overrides (brim, supports, ...) from the first object of the existing file. UNTESTED.
    extra = ''
    if mcfg:
        try:
            obj = ET.fromstring(mcfg).find('object')
            for md in obj.findall('metadata'):
                k = md.get('key')
                if k and k not in ('name', 'extruder') and md.get('face_count') is None:
                    extra += '<metadata key="%s" value="%s"/>' % (escape(k), escape(md.get('value') or '', {'"': '&quot;'}))
        except Exception as e:
            print('per-object overrides not carried:', e)
    if extra:
        print('per-object overrides carried:', extra.count('<metadata'))

    mesh = build_body().to_mesh()
    m = trimesh.Trimesh(vertices=mesh.vert_properties[:, :3], faces=mesh.tri_verts)
    b = m.bounds
    m.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])   # centre on XY, sit on z=0
    print('watertight', m.is_watertight, 'extents', m.extents.round(1), 'volume cm3', round(m.volume / 1000, 1))
    if m.extents[0] > x1 - x0 or m.extents[1] > y1 - y0 or m.extents[2] > max_h:
        print('WARNING: model does not fit the build volume')

    verts = ''.join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in m.vertices)
    tris = ''.join(f'<triangle v1="{a}" v2="{b_}" v3="{c}"/>' for a, b_, c in m.faces)
    name = escape(NAME, {'"': '&quot;'})
    model = (f'<?xml version="1.0" encoding="UTF-8"?>'
             f'<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
             f'<metadata name="Application">BambuStudio-02.08.02.61</metadata><metadata name="BambuStudio:3mfVersion">1</metadata>'
             f'<resources><object id="1" type="model"><mesh><vertices>{verts}</vertices><triangles>{tris}</triangles></mesh></object></resources>'
             f'<build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 {cx} {cy} 0" printable="1"/></build></model>')
    settings = (f'<?xml version="1.0" encoding="UTF-8"?><config><object id="1"><metadata key="name" value="{name}"/><metadata key="extruder" value="1"/>{extra}'
                f'<part id="1" subtype="normal_part"><metadata key="name" value="{name}"/><metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/></part></object>'
                f'<plate><metadata key="plater_id" value="1"/><metadata key="plater_name" value=""/><metadata key="locked" value="false"/>'
                f'<model_instance><metadata key="object_id" value="1"/><metadata key="instance_id" value="0"/></model_instance></plate></config>')
    ctypes = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
              '<Default Extension="config" ContentType="text/xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')

    if os.path.exists(out):                # back up the previous version before overwriting it
        bdir = os.path.join(os.path.expanduser('~'), 'work', 'backups')
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(out, os.path.join(bdir, time.strftime('%Y%m%d-%H%M%S-') + os.path.basename(out)))

    tmp = out + '.tmp'                     # write to a temp name, then rename: no half-written file for Studio or a cloud-sync client
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ctypes)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', model)
        z.writestr('Metadata/model_settings.config', settings)
        z.writestr('Metadata/project_settings.config', proj)
    os.replace(tmp, out)
    print('wrote', out)

if __name__ == '__main__':
    main()
