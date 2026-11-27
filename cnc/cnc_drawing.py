"""M5Dial Bracket CNC 版 本体の加工指示図（タップ穴）を PDF で出す。

JLCCNC など「ねじは 2D 図面で指示」の加工サービス向け。STEP（m5dial_cnc_body.step）
と同じ名前の m5dial_cnc_body.pdf を作る。図面の文字は英語（海外の加工先向け）。

形状は m5dial_cnc.py が出した m5dial_cnc_body.stl の断面から描き、寸法の数値は
m5dial_cnc.py の定数を読んで使う（両者がずれないように）。

    python cnc_drawing.py        # 先に python m5dial_cnc.py を実行しておく
"""
import ast
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Arc
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent


def read_consts(names):
    """m5dial_cnc.py の「NAME = 数値」の定数を読む（build123d を import しないため）"""
    tree = ast.parse((HERE / 'm5dial_cnc.py').read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in names and isinstance(node.value, ast.Constant):
                out[t.id] = float(node.value.value)
    missing = set(names) - set(out)
    assert not missing, f'm5dial_cnc.py に定数がない: {missing}'
    return out


C = read_consts(['X_OUT', 'Y_OUT', 'SCREW_XY', 'TAP_DRILL', 'TAP_DEPTH', 'DRILL_DEPTH',
                 'LID_T', 'REBATE_WALL', 'HOLE_D'])
X, Y, S = C['X_OUT'], C['Y_OUT'], C['SCREW_XY']
LID_T = C['LID_T']
M_D = 3.0                                            # M3 の呼び径
HOLES = [(x, y) for x in (S, X - S) for y in (S, Y - S)]

LW, THIN = 0.8, 0.35


def section_lines(mesh, origin, normal, to2d):
    """断面の線分を 2D に写して返す"""
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    assert sec is not None, f'断面が空: {origin}'
    segs = []
    for ent in sec.entities:
        pts = sec.vertices[ent.points]
        segs.append(np.array([to2d(p) for p in pts]))
    return segs


def dim(ax, p0, p1, off, text, horiz=True, fs=7):
    """寸法線（p0-p1 を off だけずらした位置に、矢印と数値）"""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = np.array([0, off]) if horiz else np.array([off, 0])
    a, b = p0 + d, p1 + d
    ax.annotate('', a, b, arrowprops=dict(arrowstyle='<|-|>', lw=THIN, color='k',
                                          shrinkA=0, shrinkB=0, mutation_scale=6))
    sgn = np.sign(off)
    ext = d / abs(off)                               # 寸法線の先へ 1mm 延ばす
    for p, q in ((p0, a), (p1, b)):                  # 寸法補助線
        ax.plot(*zip(p, q + ext), lw=THIN, color='k')
    mid = (a + b) / 2
    if horiz:
        ax.text(mid[0], mid[1] + 0.8 * sgn, text, ha='center',
                va='bottom' if sgn > 0 else 'top', fontsize=fs)
    else:
        ax.text(mid[0] + 0.8 * sgn, mid[1], text, ha='left' if sgn > 0 else 'right',
                va='center', rotation=90, fontsize=fs)


def main():
    body = trimesh.load(HERE / 'm5dial_cnc_body.stl')
    assert body.is_watertight

    fig = plt.figure(figsize=(11.69, 8.27))         # A4 横
    fig.text(0.04, 0.95, 'M5Dial Bracket CNC  -  BODY  (m5dial_cnc_body.step)',
             fontsize=13, weight='bold')
    fig.text(0.04, 0.925, 'Drawing for tapped holes. Geometry: follow the STEP file. '
             'Threads / notes: follow this drawing.', fontsize=8.5)

    # ---------------- 底面図（下から見る。左右が反転するので x を -x で描く）
    ax = fig.add_axes([0.03, 0.12, 0.55, 0.78])
    ax.set_aspect('equal')
    ax.axis('off')
    to_bottom = lambda p: (X - p[0], p[1])           # 下から見た図（右が x=0 側）
    for z, lw in ((LID_T / 2, LW), (LID_T + 0.5, THIN)):
        for s in section_lines(body, (0, 0, z), (0, 0, 1), to_bottom):
            ax.plot(s[:, 0], s[:, 1], color='k' if lw == LW else '0.45', lw=lw)
    for x, y in HOLES:                               # ねじ: 下穴（実線）＋ 谷径 3/4 円（細線）
        cx, cy = X - x, y
        ax.add_patch(Circle((cx, cy), C['TAP_DRILL'] / 2, fill=False, lw=LW))
        ax.add_patch(Arc((cx, cy), M_D, M_D, theta1=0, theta2=270, lw=THIN))
        ax.plot([cx - 2.6, cx + 2.6], [cy, cy], lw=THIN, color='k', ls=(0, (6, 2, 1, 2)))
        ax.plot([cx, cx], [cy - 2.6, cy + 2.6], lw=THIN, color='k', ls=(0, (6, 2, 1, 2)))

    # 断面 A-A の切断線（x = SCREW_XY）
    ax.plot([X - S] * 2, [-2.5, Y + 2.5], lw=THIN, color='k', ls=(0, (8, 2, 1, 2)))
    for yy in (-2.5, Y + 2.5):
        ax.text(X - S + 1.0, yy, 'A', fontsize=8, weight='bold', ha='left',
                va='top' if yy < 0 else 'bottom')

    # 寸法（外形・ねじ位置）
    dim(ax, (0, 0), (X, 0), -7, f'{X:g}')
    dim(ax, (X - S, 0), (S, 0), -3.5, f'{X - 2 * S:g}', fs=6.5)
    dim(ax, (X, 0), (X - S, 0), -3.5, f'{S:g}', fs=6.5)
    dim(ax, (X, 0), (X, Y), 7, f'{Y:g}', horiz=False)
    dim(ax, (X, S), (X, Y - S), 3.5, f'{Y - 2 * S:g}', horiz=False, fs=6.5)
    dim(ax, (X, 0), (X, S), 3.5, f'{S:g}', horiz=False, fs=6.5)

    # 穴の指示
    hx, hy = X - S, Y - S
    ax.annotate(f'4x M3x0.5-6H  depth {C["TAP_DEPTH"]:g} (full thread)\n'
                f'Tap drill {C["TAP_DRILL"]:g}  depth {C["DRILL_DEPTH"]:g}\n'
                f'(depths from the recess floor, {LID_T:g} mm above bottom face)',
                xy=(hx - 1.1, hy + 1.1), xytext=(hx - 30, Y + 12), fontsize=8, weight='bold',
                arrowprops=dict(arrowstyle='-|>', lw=THIN, color='k', mutation_scale=7))
    ax.text(X / 2, Y + 0.9, 'BACK (cable exit)', ha='center', va='bottom', fontsize=7,
            color='0.3')
    ax.text(X / 2, -14, 'VIEW FROM BOTTOM', ha='center', fontsize=9, weight='bold')
    ax.set_xlim(-12, X + 14)
    ax.set_ylim(-17, Y + 22)

    # ---------------- 断面 A-A（タップ穴の中心、x = SCREW_XY の YZ 面）
    ax2 = fig.add_axes([0.60, 0.45, 0.37, 0.45])
    ax2.set_aspect('equal')
    ax2.axis('off')
    for s in section_lines(body, (S, 0, 0), (1, 0, 0), lambda p: (p[1], p[2])):
        ax2.plot(s[:, 0], s[:, 1], color='k', lw=LW)
    z0, zt, zd = LID_T, LID_T + C['TAP_DEPTH'], LID_T + C['DRILL_DEPTH']
    for sx in (-1, 1):                               # ねじの外径線（細線）
        ax2.plot([S + sx * M_D / 2] * 2, [z0, zt], lw=THIN, color='k')
    ax2.plot([S - M_D / 2, S + M_D / 2], [zt, zt], lw=THIN, color='k')
    ax2.plot([S, S], [z0 - 2, zd + 2], lw=THIN, color='k', ls=(0, (6, 2, 1, 2)))
    dim(ax2, (S + 2.5, z0), (S + 2.5, zt), 2.0, f'{C["TAP_DEPTH"]:g}', horiz=False, fs=6.5)
    dim(ax2, (S + 2.5, z0), (S + 2.5, zd), 5.0, f'{C["DRILL_DEPTH"]:g}', horiz=False, fs=6.5)
    dim(ax2, (-0.0, 0), (-0.0, z0), -2.5, f'{LID_T:g}', horiz=False, fs=6.5)
    ax2.annotate('recess floor (bottom lid seats here)', xy=(S + 4, z0), xytext=(S + 6, z0 - 3.5),
                 fontsize=6.5, color='0.3',
                 arrowprops=dict(arrowstyle='-', lw=THIN, color='0.3'))
    ax2.text(S - 6, -4.5, 'SECTION A-A  (through hole centre, enlarged)',
             fontsize=8, weight='bold')
    ax2.set_xlim(-6, 28)
    ax2.set_ylim(-5, 18)

    # ---------------- 注記
    notes = [
        'NOTES',
        '1. Material: Aluminium 6061-T6.',
        '2. General tolerance: ISO 2768-m unless otherwise specified.',
        f'3. Threads: 4x M3x0.5-6H, full thread depth {C["TAP_DEPTH"]:g} mm, '
        f'tap drill {C["TAP_DRILL"]:g} mm',
        f'    depth {C["DRILL_DEPTH"]:g} mm (STEP shows the tap drill only).',
        '    Threads must accept M3 screws after surface finishing.',
        '4. Internal corners are sharp in the STEP. Tool radius is acceptable:',
        '    cavity up to R6, bottom recess corners up to R1.',
        f'5. Large hole on the 45 deg face: dia {C["HOLE_D"]:g} (ISO 2768-m is OK).',
        '6. Break sharp external edges (standard deburr).',
        '7. Mating part: m5dial_cnc_lid.step (fits into the bottom recess).',
    ]
    fig.text(0.60, 0.40, '\n'.join(notes), fontsize=7.6, va='top', family='DejaVu Sans',
             linespacing=1.55)
    fig.text(0.60, 0.06, 'Units: mm    Projection: views as labelled    '
             'Part: m5dial_cnc_body    Qty: see order', fontsize=7, color='0.3')

    out = HERE / 'm5dial_cnc_body.pdf'
    fig.savefig(out)
    fig.savefig(HERE / 'cnc_drawing.png', dpi=110)
    print(f'wrote {out.name}, cnc_drawing.png')


if __name__ == '__main__':
    main()
