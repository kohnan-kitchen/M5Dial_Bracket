#!/usr/bin/env python3
"""M5Dial Bracket CNC 版（アルミ削り出し・底蓋タップ止め）— STEP / STL 生成スクリプト

    <venv>/bin/python m5dial_cnc.py              # 本体・底蓋の STEP / STL を出力
    <venv>/bin/python m5dial_cnc.py --assembly   # 確認用モック（Dial・USB-C）も STL 出力

要 build123d（STEP 出力）＋ trimesh + manifold3d + shapely（検証）。

■ v2（3D プリント版）からの変更点
  形は v2 と同じ（前面 45° スロープ・背面垂直・天面フラット、Dial はスロープの
  壁にパネルマウント）。3 軸マシニングで削れるように次を変えた。

  - 内側の空洞を「底から上へ掘るだけ」で届く形（z 方向の高さ場）にした。
    v2 のチェンバー（スロープに直交する円筒）や切妻天井はやめ、外形を壁厚
    T_WALL だけ内側へ寄せた単純な殻にする。スロープの内面はそのまま 45° の平面で、
    リングナットはこの内面に当たる。
  - 内側（組み立てると見えない面）の隅は R を付けず角のままモデル化する。
    加工で残る工具の R は工具半径 TOOL_R（φ12）まで許容: その形でも
    Dial・ナット・USB-C プラグと干渉しないことを検証する。
  - 壁厚 3mm（v2 は 1.5）。内隅の R6 がナットに掛からないよう、幅 70・奥行き 57・
    スロープ長 61 に広げ、Dial を 1.5mm 上げた（v2 は 60 × 53・58・30）。
  - 底蓋はスナップ爪をやめ、本体の底に彫った段（深さ 3、壁はこの高さだけ 1.5mm）に
    平板（厚 3）を落とし込み、本体の底面と面一にする。皿小ねじ M3×8 ×4 本で
    隅の柱（10×10・全高）に立てたタップ穴へ留める。
  - ケーブル出口は背面壁の下端の切り欠き（底蓋の上面から幅 8 × 高さ 6、上の角 R3）。
  - 外形の稜と角は R3 で丸める（底面の縁は角のまま）。

          ／▔▔▔│
       ／ ◎     │    ← スロープ（壁厚 3）に φ45 穴。Dial をリングナットで挟む
     │          │    ← 内側は底から掘った空洞（内隅は R6 以下で可）
     │▌        ▐⊓│    ← 隅の柱（M3 タップ）・背面下端のケーブル切り欠き
     ┗━━━━━━━━━┛    ← 底蓋（厚 3・本体の底の段に落とし込み、底面と面一。皿小ねじ M3 ×4）

■ 加工工程の想定（3 軸）
  OP1 底面側: 底面フライス → 空洞のポケット（φ12 フラットで荒・壁仕上げ、
       天井の 45° 面と天面裏は φ12 ボールで等高線/走査仕上げ）→ 底蓋の段
       （深さ 3・隅 R1 なので φ2 以下で隅を仕上げ）→ M3 下穴・タップ
       ※ ケーブル出口（上の角 R3）は背面を上にした段取りで φ6 以下の輪郭加工
  OP2 側面置き（x 軸を鉛直）: 外形の五角形を輪郭加工（2.5 次元。x 方向の稜の R3 は
       輪郭の円弧として出る）→ 側面の外周の稜の R3 はコーナー R カッターで左右から
  OP3 45° 傾斜治具（またはサインバイス）: スロープ面を水平にして φ45 穴を
       ヘリカル加工で貫通
  ※ 寸法・工程は推測を含む設計案。最終的な工程・公差は加工先と確認する。

■ 座標系（設置姿勢・本体）
    x : 左 → 右（幅）
    y : 前(0, スロープ側) → 奥（背面）
    z : 下(0, 本体の底面＝底蓋の下面) → 上

■ Dial の寸法出典
  m5dial_v2.py と同じ（M5Stack 公式 STL K130_Dial の実測値）。
  推測: L 字 USB-C プラグの外形（12×7、根元から 10mm で曲がる）と PORT.B の
  プラグ位置は一般的な製品・公式写真からの概算。必ず実機で確認する。
"""

import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon as SPolygon
from trimesh.creation import box as _box
from trimesh.creation import cylinder as _cylinder

import build123d as bd

# --------------------------------------------- M5Dial（パネルマウント・実測。v2 と同じ）
DIAL_SEAT_D = 48.0     # 座（固定フランジ＋ワッシャ）の外径。パネル前面に当たる
DIAL_THREAD_D = 44.0   # ネジ筒（オス）の外径
DIAL_THREAD_L = 12.55  # 座面からネジ筒の終わりまで
DIAL_LEAD_D = 44.6     # ネジ筒の根元の入口カラーの径
DIAL_NUT_D = 50.82     # リングナットの外径
DIAL_NUT_H = 5.0       # リングナットの高さ
DIAL_PANEL_MAX = DIAL_THREAD_L - DIAL_NUT_H   # 締められるパネル厚の上限 7.55
DIAL_PANEL_MIN = 1.0   # 同・下限
DIAL_KNOB_D = 49.83    # 回転ノブの外径
DIAL_KNOB_GAP = 0.8    # 座面とノブ後端の隙間
DIAL_FRONT = 14.62     # 座面からパネル前に出る量
DIAL_BACK = 15.70      # 座面からパネル後ろに出る量
DIAL_BACK_D = 42.0     # ネジ筒より奥（背面側）の最大径
DIAL_BEZEL_D = 45.03   # 前面ベゼルの外径
DIAL_MASS = 46.3       # g（公式仕様）
USB_T = 11.5           # USB-C 開口中心の座面からの奥行き
USB_R = 21.0           # USB-C 開口がある円筒の半径
USB_PLUG_W = 12.0      # 推測: L 字プラグの幅
USB_PLUG_T = 7.0       # 推測: 同・厚み
USB_PLUG_L = 10.0      # 推測: 円筒の表面から曲がりまで
USB_CABLE_D = 3.7      # ケーブル径

# ---------------------------------------------------------- 筐体の寸法
T_WALL = 3.0        # 壁厚（側面・前面・背面・天面・スロープ共通）。Dial の締結範囲 1〜7.55 の内側
SLOPE_DEG = 45.0    # 前面スロープの傾き（水平から）
PLINTH_H = 25.0     # スロープが始まるまでの垂直壁の高さ（v2 と同じ）
X_OUT = 70.0        # 幅。ナット φ50.8 が側壁・柱の内隅 R6 に掛からない幅（検証で確認）
Y_OUT = 57.0        # 奥行き。背面側の柱の上端の R6 がナットに掛からない奥行き
SLOPE_S_TOP = 61.0  # スロープの長さ。天井の稜の R6 がナット上端に掛からない長さ（v2 は 58）
SLOPE_TOP_Y = SLOPE_S_TOP * np.cos(np.radians(SLOPE_DEG))
TOP_Z = PLINTH_H + SLOPE_S_TOP * np.sin(np.radians(SLOPE_DEG))

TOOL_R = 6.0        # 空洞の加工工具の半径（φ12 フラット／ボール）。内隅はすべてこの R
EDGE_R = 3.0        # 外形の稜と角の R（底面の縁を除く）
PILLAR = 10.0       # 隅の柱の大きさ（外面から。壁を含む・全高）。M3 タップを立てる

# ------------------------------------------------- Dial のパネルマウント穴
POD_S = 31.5        # Dial 中心のスロープ上の位置（斜面下端から）。壁厚 3 で USB-C の
                    # L 字プラグが前壁に当たらないよう v2（30）より上げる
PANEL_T = T_WALL    # Dial を挟む厚み＝スロープの壁厚
HOLE_D = 45.0       # 貫通穴（公差 +0.1/0 を指示）。入口カラー φ44.6 が入る
FLAT_D = 52.0       # 穴まわりに平面が要る径（回転ノブ φ49.83 ＋逃げ）

N_POD = np.array([0.0, -np.sin(np.radians(SLOPE_DEG)), np.cos(np.radians(SLOPE_DEG))])
U_SLOPE = np.array([0.0, np.cos(np.radians(SLOPE_DEG)), np.sin(np.radians(SLOPE_DEG))])
X_HAT = np.array([1.0, 0.0, 0.0])
POD_C = np.array([X_OUT / 2, 0, PLINTH_H]) + POD_S * U_SLOPE   # Dial の座面中心

# ------------------------------------------------- 底蓋（タップ止め）
# 本体の底に段（ザグリ）を彫り、底蓋を落とし込んで底面と面一にする。
LID_T = 3.0         # 板厚（A5052 板 t3 を想定）＝段の深さ
REBATE_WALL = 1.5   # 段の部分の壁厚（外面から段の内面まで）
REBATE_R = 1.0      # 段の内隅に許す R の上限（モデルは角のまま）。底蓋の角はこれに合わせて丸める
LID_CLR = 0.1       # 底蓋の外周と段の内面の隙間（片側）
SCREW = 'M3×8 皿小ねじ（JIS B 1111 相当）'
SCREW_L = 8.0       # 首下長さ（皿頭を含む全長）
SCREW_XY = 6.0      # ねじ位置（外面からの距離）。柱 10□の中で、皿もみが蓋の縁から離れる位置
TAP_DRILL = 2.5     # M3 下穴
TAP_DEPTH = 7.0     # 有効ねじ深さ
DRILL_DEPTH = 9.0   # 下穴深さ
CLEAR_D = 3.4       # 底蓋の通し穴
CSK_D = 6.0         # 皿もみ径（90°）

# ------------------------------------------------- ケーブル出口
CABLE_W = 8.0       # 背面壁の下端の切り欠きの幅（USB-C ケーブル φ3.7）
CABLE_H = 6.0       # 同・高さ（底蓋の上面から。本体の底面からは LID_T + CABLE_H）
CABLE_R = EDGE_R    # 同・上の 2 つの角の R（外形と同じ R3。上辺の平らな部分は 8 − 2×3 = 2）


# ============================================================ 形状（build123d）
def outer_yz():
    """外形の y-z 断面（反時計回りの凸五角形）"""
    return [(0.0, 0.0), (Y_OUT, 0.0), (Y_OUT, TOP_Z), (SLOPE_TOP_Y, TOP_Z), (0.0, PLINTH_H)]


def inner_yz(off=T_WALL, z_bot=-1.0):
    """外形断面を各辺（底辺を除く）から off だけ内側へ寄せ、底を z_bot まで延ばす"""
    pts = outer_yz()
    poly = SPolygon([(-500, z_bot), (500, z_bot), (500, 500), (-500, 500)])
    for i, a in enumerate(pts):
        a = np.array(a, float)
        b = np.array(pts[(i + 1) % len(pts)], float)
        if abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9:
            continue                                   # 底辺は開放
        e = (b - a) / np.linalg.norm(b - a)
        n = np.array([-e[1], e[0]])                    # 内向き法線
        c = n @ a + off
        t = np.array([-n[1], n[0]])
        p0 = n * c
        poly = poly.intersection(SPolygon([p0 + t * 999, p0 - t * 999,
                                           p0 - t * 999 + n * 1998, p0 + t * 999 + n * 1998]))
    return [tuple(p) for p in list(poly.exterior.coords)[:-1]]


def prism_x(pts_yz, x0, x1):
    face = bd.Plane.YZ.offset(x0) * bd.Polygon(*pts_yz, align=None)
    return bd.extrude(face, amount=x1 - x0, dir=(1, 0, 0))


def cavity_xy(off=T_WALL):
    """空洞の平面形: 壁の内側の矩形から隅の柱を除いた 12 角形（角は尖ったまま）。
    off は外面からの距離（壁厚）。柱は外面から PILLAR、壁の内面から PILLAR-T_WALL"""
    t, p, X, Y = off, PILLAR + (off - T_WALL), X_OUT, Y_OUT
    pts = [(p, t), (X - p, t), (X - p, p), (X - t, p), (X - t, Y - p), (X - p, Y - p),
           (X - p, Y - t), (p, Y - t), (p, Y - p), (t, Y - p), (t, p), (p, p)]
    return bd.Polygon(*pts, align=None)


def build_cavity(tool_r=0.0):
    """底から掘る空洞。

    tool_r=0 は出力用（内隅は角のまま。組み立てると見えないので R は指示しない）。
    tool_r>0 は検証用の「工具 R で削った場合」の形: 工具中心（ボール中心／フラットの側面の中心線）が動ける範囲 core を、
    設計上の空洞を TOOL_R だけ内側へ寄せて作り、それを TOOL_R だけ膨らませる。
    これで部品の内隅（鉛直の隅・天井と壁の境・天井どうしの境）がすべて R6 になり、
    柱の出隅（空洞側に凹の角）は尖ったまま残る。実際の削り跡と同じ形になる。"""
    if tool_r <= 0:
        cav = bd.Pos(0, 0, -1) * bd.extrude(cavity_xy(), amount=TOP_Z + 2)
        return cav & prism_x(inner_yz(), -1, X_OUT + 1)
    off = T_WALL + tool_r
    core = bd.Pos(0, 0, -20) * bd.extrude(cavity_xy(off), amount=TOP_Z + 20)
    core = core & prism_x(inner_yz(off, -20.0), -1, X_OUT + 1)
    cav = bd.offset(core, amount=tool_r, kind=bd.Kind.ARC)
    clip = bd.Pos(X_OUT / 2, Y_OUT / 2, (TOP_Z - 1) / 2) * bd.Box(X_OUT + 10, Y_OUT + 10,
                                                                     TOP_Z + 1)
    return cav & clip


def build_body(tool_r=0.0):
    """本体。tool_r=0 は出力用（内隅は角のまま）、tool_r>0 は内隅を工具 R で
    削った場合の検証用（空洞は tool_r、底蓋の段は REBATE_R）"""
    outer = prism_x(outer_yz(), 0, X_OUT)
    # 外形の稜と角を EDGE_R で丸める（底面の縁は角のまま。底蓋の段と面一の底面を保つ）
    outer = bd.fillet([e for e in outer.edges() if e.bounding_box().max.Z > 1e-6], EDGE_R)
    body = outer - build_cavity(tool_r)
    # Dial の貫通穴（スロープに直交）
    c0 = POD_C + 2 * N_POD
    hole = bd.Cylinder(HOLE_D / 2, PANEL_T + 4,
                       align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX))
    hole = bd.Location(bd.Plane(origin=tuple(c0), z_dir=tuple(N_POD))) * hole
    body -= hole
    # 底蓋を落とし込む段（深さ LID_T）
    body -= bd.Pos(0, 0, -1) * bd.extrude(
        rebate_xy(0.0, REBATE_R if tool_r > 0 else 0.0), amount=LID_T + 1)
    # 底蓋の M3 タップ下穴（隅の柱。段の底面 z=LID_T から DRILL_DEPTH）
    for x, y in screw_xy():
        body -= bd.Pos(x, y, -1) * bd.Cylinder(
            TAP_DRILL / 2, LID_T + DRILL_DEPTH + 1,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    # ケーブル出口（背面壁の下端の切り欠き。底蓋の上面から CABLE_H、上の角は CABLE_R）
    body -= cable_cut()
    return body


def cable_cut():
    """背面壁を貫くケーブル出口。背面から見て幅 CABLE_W・本体の底面から高さ
    LID_T + CABLE_H の矩形で、上の 2 つの角を CABLE_R で丸める"""
    h, cx, w = LID_T + CABLE_H, X_OUT / 2, CABLE_W / 2
    y0 = Y_OUT - T_WALL - 1.0
    pl = bd.Plane(origin=(0, y0, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))   # 局所 (x, z)
    face = pl * bd.Polygon((cx - w, -1), (cx + w, -1), (cx + w, h), (cx - w, h), align=None)
    face = bd.fillet([v for v in face.vertices() if abs(v.Z - h) < 1e-6], CABLE_R)
    return bd.extrude(face, amount=T_WALL + 2, dir=(0, 1, 0))


def rebate_xy(clr=0.0, r=REBATE_R):
    """底蓋の段の平面形（clr だけ内側へ寄せると底蓋の外形）。r は段の内隅の R"""
    w = REBATE_WALL + clr
    face = bd.Pos(X_OUT / 2, Y_OUT / 2) * bd.Rectangle(X_OUT - 2 * w, Y_OUT - 2 * w)
    return bd.fillet(face.vertices(), r - clr) if r - clr > 0 else face


def screw_xy():
    return [(x, y) for x in (SCREW_XY, X_OUT - SCREW_XY)
            for y in (SCREW_XY, Y_OUT - SCREW_XY)]


def build_lid():
    """底蓋（組み付け状態の座標。本体の段に収まり、下面が z=0 で本体の底面と面一）。
    皿もみは下面側"""
    lid = bd.extrude(rebate_xy(LID_CLR), amount=LID_T)
    csk_h = (CSK_D - CLEAR_D) / 2                    # 90° 皿もみの深さ
    for x, y in screw_xy():
        lid -= bd.Pos(x, y, -1) * bd.Cylinder(
            CLEAR_D / 2, LID_T + 2, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        lid -= bd.Pos(x, y, 0) * bd.Cone(
            CSK_D / 2, CLEAR_D / 2, csk_h,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        lid -= bd.Pos(x, y, -1) * bd.Cylinder(
            CSK_D / 2, 1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    return lid


# ============================================================ 検証用（trimesh）
def cyl(p0, p1, r, sections=128):
    return _cylinder(radius=r, segment=[np.asarray(p0, float), np.asarray(p1, float)],
                     sections=sections)


def oriented_box(center, ax, ay, az, ex, ey, ez):
    b = _box(extents=[ex, ey, ez])
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2] = ax, ay, az
    T[:3, 3] = center
    b.apply_transform(T)
    return b


def tm_union(parts):
    return trimesh.boolean.union(parts, engine='manifold')


def tm_intersect(a, b):
    return trimesh.boolean.intersection([a, b], engine='manifold')


def to_mesh(part, path):
    bd.export_stl(part, path, tolerance=0.01, angular_tolerance=0.1)
    m = trimesh.load(path)
    # 外形の R と壁厚が同じため、側面の平らな面の頂点で長さゼロの辺が出る。
    # 頂点を統合して縮退した三角形を落とす（形状は変わらない）
    m.merge_vertices(digits_vertex=4)
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    m.export(path)
    return m


def mock_dial():
    """M5Dial の簡易モデル（同軸円筒の積層）＋PORT.B のプラグ空間（v2 と同じ）"""
    seat = POD_C
    segs = [(DIAL_SEAT_D / 2, 0.0, 2.35),
            (DIAL_KNOB_D / 2, DIAL_KNOB_GAP + 0.85, DIAL_FRONT - 0.4),
            (DIAL_BEZEL_D / 2, DIAL_FRONT - 6.1, DIAL_FRONT),
            (DIAL_THREAD_D / 2, -DIAL_THREAD_L, 0.0),
            (DIAL_BACK_D / 2, -DIAL_BACK, -DIAL_THREAD_L),
            (DIAL_NUT_D / 2, -PANEL_T - DIAL_NUT_H, -PANEL_T)]
    parts = [cyl(seat + a * N_POD, seat + b * N_POD, r) for r, a, b in segs]
    # 推測: PORT.B は軸から約 17mm、プラグ＋ケーブル曲げで背面から 14mm 見込む
    parts.append(oriented_box(seat - (DIAL_BACK + 7.0) * N_POD - 17.0 * U_SLOPE,
                              X_HAT, U_SLOPE, -N_POD, 12.0, 8.0, 14.0))
    return tm_union(parts)


def mock_usb():
    """USB-C の L 字プラグ（斜面の下向きに挿す）＋底へ下ろすケーブル（v2 と同じ）"""
    d = -U_SLOPE
    port = POD_C - USB_T * N_POD
    body = oriented_box(port + (USB_R + USB_PLUG_L / 2 + USB_PLUG_T / 4) * d,
                        X_HAT, d, N_POD, USB_PLUG_W, USB_PLUG_L + USB_PLUG_T / 2, USB_PLUG_T)
    bend = port + (USB_R + USB_PLUG_L) * d
    s = (bend[2] - USB_CABLE_D / 2 - LID_T - 0.5) / N_POD[2]   # 底蓋の上面まで
    cable = cyl(bend, bend - s * N_POD, USB_CABLE_D / 2, sections=24)
    return tm_union([body, cable])


def check_machinable_from_bottom(mesh):
    """底から 3 軸で掘れるか: 各 (x, y) の鉛直線上で、本体の肉が 1 区間だけ
    （＝底から天井まで空洞が途切れず、肉の下に空洞がない）であることを調べる。
    Dial の穴（OP3 で加工）の投影範囲は除く"""
    bad, n = [], 0
    hole_ry = HOLE_D / 2 * abs(N_POD[2])              # 穴の xy 投影（楕円）の y 半径
    for x in np.arange(0.37, X_OUT, 1.0):            # 面と一致しない格子
        for y in np.arange(0.41, Y_OUT, 1.0):
            if ((x - POD_C[0]) / (HOLE_D / 2 + 1)) ** 2 + \
               ((y - POD_C[1]) / (hole_ry + 1)) ** 2 < 1:
                continue
            o = np.array([[x, y, -5.0]])
            locs, _, _ = mesh.ray.intersects_location(o, [[0, 0, 1]], multiple_hits=True)
            zs = np.unique(np.round(np.sort(locs[:, 2]), 4)) if len(locs) else []
            n += 1
            if len(zs) > 2:
                bad.append((x, y, list(zs)))
    return n, bad


def main():
    do_assembly = '--assembly' in sys.argv

    print('本体・底蓋を生成中...')
    body = build_body()
    lid = build_lid()
    for part, name in ((body, 'm5dial_cnc_body'), (lid, 'm5dial_cnc_lid')):
        assert part.is_valid, f'{name} が不正な形状'
        assert len(part.solids()) == 1, f'{name} が 1 部品になっていない'
        bd.export_step(part, f'{name}.step')
    body_m = to_mesh(body, 'm5dial_cnc_body.stl')
    lid_m = to_mesh(lid, 'm5dial_cnc_lid.stl')
    rho = 2.68e-3                                     # A5052 g/mm3
    for m, n in ((body_m, 'm5dial_cnc_body'), (lid_m, 'm5dial_cnc_lid')):
        assert m.is_watertight, f'{n}.stl が watertight ではない'
        b = m.bounds
        print(f'  {n}.step / .stl 出力  {(b[1] - b[0]).round(1)} mm'
              f'  体積 {m.volume / 1000:.1f} cm3  質量 {m.volume * rho:.0f} g（A5052）')

    # --- Dial のパネルマウント
    assert DIAL_PANEL_MIN <= PANEL_T <= DIAL_PANEL_MAX, 'パネル厚がナットの締結範囲外'
    assert HOLE_D > DIAL_LEAD_D + 0.2 and HOLE_D < DIAL_SEAT_D - 1.6
    assert POD_S - FLAT_D / 2 > 0 and POD_S + FLAT_D / 2 < SLOPE_S_TOP, \
        'ノブの平面領域がスロープからはみ出す'
    assert X_OUT / 2 - FLAT_D / 2 > EDGE_R, 'ノブの平面領域が側面の R にかかる'
    t135 = EDGE_R * np.tan(np.radians((180 - 135) / 2))   # 135° の稜の R が斜面を食う長さ
    assert POD_S - FLAT_D / 2 > t135 and SLOPE_S_TOP - POD_S - FLAT_D / 2 > t135, \
        'ノブの平面領域がスロープ上下の稜の R にかかる'
    assert EDGE_R <= T_WALL, '外形の R が壁厚より大きい'

    # --- 検証用: 内隅を工具 R（空洞 R6・段 R1）で削った場合の本体。
    #     出力モデルは内隅が角のままなので、加工後の形はこれと出力モデルの間に入る。
    #     肉が一番多いこちらで干渉・手の届き・加工可否を見る
    import tempfile
    worst = build_body(TOOL_R)
    assert worst.is_valid and len(worst.solids()) == 1
    with tempfile.TemporaryDirectory() as td:
        worst_m = to_mesh(worst, f'{td}/worst.stl')
    assert worst_m.is_watertight

    # --- 部品間の干渉（交差体積＝0）
    lid_asm = lid_m                                  # 組み付け位置（段に収まった状態）
    dial, usb = mock_dial(), mock_usb()
    for bm, label in ((body_m, '出力モデル'), (worst_m, f'内隅 R{TOOL_R:g} で削った場合')):
        for a, b, name in ((bm, dial, '本体×Dial（ナット含む）'),
                           (bm, usb, '本体×USB-C プラグ'),
                           (lid_asm, bm, '底蓋×本体'), (lid_asm, dial, '底蓋×Dial'),
                           (lid_asm, usb, '底蓋×USB-C プラグ')):
            inter = tm_intersect(a, b)
            v = inter.volume if inter is not None and len(inter.faces) else 0.0
            assert v < 0.01, f'[{label}] {name} が干渉（交差体積 {v:.3f} mm3）'
    print(f'  干渉チェック OK（出力モデル・内隅 R{TOOL_R:g} で削った場合とも、'
          '本体/底蓋/Dial・ナット/USB-C プラグの交差体積 = 0）')

    # --- リングナットに底から手が届く（ナット外周の下半分から真下に肉が無い）
    nut_c = POD_C - (PANEL_T + DIAL_NUT_H / 2) * N_POD
    blocked = []
    for th in np.radians(np.arange(180, 361, 15)):
        p = nut_c + (DIAL_NUT_D / 2) * (np.cos(th) * X_HAT + np.sin(th) * U_SLOPE)
        hit = worst_m.ray.intersects_location([p - [0, 0, 0.5]], [[0, 0, -1]])[0]
        if len(hit) and (hit[:, 2] > LID_T + 0.1).any():
            blocked.append(round(float(np.degrees(th))))
    assert not blocked, f'リングナットの下に本体の肉がある（角度 {blocked}）'

    # --- 3 軸で底から掘れるか
    for bm in (body_m, worst_m):
        n, bad = check_machinable_from_bottom(bm)
        assert not bad, f'底から届かない（アンダーカット）箇所: {bad[:5]} ...'
    depth = body_m.bounds[1][2] - T_WALL
    print(f'  底からの加工: {n} 点でアンダーカットなし / 最深部 約 {depth:.0f} mm'
          f'（φ{2 * TOOL_R:g} 突き出し {depth + 5:.0f} mm 以上の工具。'
          f'内隅は R{TOOL_R:g} 以下なら可）')

    # --- ねじ
    engage = SCREW_L - LID_T
    assert engage <= TAP_DEPTH, 'ねじがタップ深さより長い'
    assert engage >= 1.5 * 3, f'ねじのかかり {engage}mm が短い'
    assert SCREW_XY - TAP_DRILL / 2 >= 2.0, 'タップ穴の外側の肉が薄い'
    edge = SCREW_XY - REBATE_WALL - LID_CLR - CSK_D / 2
    corner = (np.hypot(SCREW_XY - REBATE_WALL - REBATE_R, SCREW_XY - REBATE_WALL - REBATE_R)
              - (REBATE_R - LID_CLR) - CSK_D / 2)
    assert min(edge, corner) >= 0.8, f'皿もみから底蓋の縁までが狭い（{min(edge, corner):.2f}mm）'
    assert REBATE_WALL >= 1.0 and LID_CLR < REBATE_R
    assert (PILLAR - SCREW_XY) - TAP_DRILL / 2 >= 2.0, 'タップ穴の内側の肉が薄い'
    assert CABLE_W > USB_CABLE_D + 2 and CABLE_H > USB_CABLE_D + 1.5
    #     丸めた角の下でもケーブル（底蓋の上に載る φ3.7）の上に隙間が残ること
    dx = max(USB_CABLE_D / 2 - (CABLE_W / 2 - CABLE_R), 0.0)
    clear_top = CABLE_H - CABLE_R + np.sqrt(CABLE_R ** 2 - dx ** 2) - USB_CABLE_D
    assert 2 * CABLE_R <= CABLE_W and clear_top > 1.5, f'ケーブル上の隙間 {clear_top:.1f}mm'
    print(f'  底蓋: {SCREW} ×4 / タップ M3 深さ {TAP_DEPTH:g}（下穴 φ{TAP_DRILL} 深さ'
          f' {DRILL_DEPTH:g}）/ ねじのかかり {engage:g} mm'
          f' / 皿もみから蓋の縁まで {edge:.1f} mm（角 {corner:.1f} mm）')

    total = (body_m.volume + lid_m.volume) * rho + DIAL_MASS
    print(f'  総質量 約 {total:.0f} g（Dial 込み）/ 据え置き高さ {TOP_Z:.1f} mm（底蓋は本体内に収まる）')

    if do_assembly:
        dial.export('mock_dial.stl')
        usb.export('mock_usb.stl')
        lid_asm.export('mock_lid.stl')
        half = trimesh.boolean.difference(
            [body_m, _box(extents=[X_OUT, Y_OUT + 2, TOP_Z + 2]).apply_translation(
                [X_OUT / 4 - 0.5, Y_OUT / 2, TOP_Z / 2])], engine='manifold')
        half.export('body_half.stl')
        print('  mock_dial.stl / mock_usb.stl / mock_lid.stl / body_half.stl 出力')


if __name__ == '__main__':
    main()
