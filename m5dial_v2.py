#!/usr/bin/env python3
"""M5Dial Bracket v2（底蓋付き・小型）— STL 生成スクリプト

    ../.venv/bin/python m5dial_v2.py              # 本体・底蓋を出力
    ../.venv/bin/python m5dial_v2.py --assembly   # 組み付けイメージ用のモックも出力

要 trimesh + manifold3d + shapely。

■ 形
  前面が 45° スロープ、背面が一枚の垂直面、天面フラットの台形筐体。
  外形の稜と角は壁厚と同じ半径（1.5mm）で丸めてある（底面の縁のみ角のまま）。
  M5Dial はスロープの壁そのものをパネルとして取り付ける（φ45 穴＋
  Dial 純正のリングナット。ダイヤル面は垂直から 45° 後傾）。
  スロープ裏にはナットと Dial 背面のための面直チェンバー（φ54）を彫り、
  それを真下へ掃き出して底の開口とつないである（ナットに底から手が届く）。
  底は全面が開口で、組み付け後に底蓋（全面板・スナップ爪 4 本）で塞ぐ。
  電源ケーブルは本体背面壁の下端の U 字の切り欠きから出す（底蓋の底面は平ら）。
  v1（m5dial.scad、三角柱フレーム）の思想を m5dial-catm-gnss-stand の
  構造で作り直したもの。

          ／▔▔▔│              ← 天面フラット・背面は垂直一枚壁
       ／ ◎     │              ← スロープに M5Dial 直付け（裏はチェンバー→底へ抜ける）
     │  ╲        │              ← USB-C（L 字プラグ）は斜面の下向き、ケーブルは底へ
     │          ⊓│              ← 背面下端の U 字のケーブル切り欠き
    ▔▔▔▔▔▔▔▔▔▔▔▔            ← 底蓋（板厚 2・リップ＋爪 4 本で下からはめる）

■ 設計方針
  - 設置姿勢のまま印刷する（部品は本体と底蓋の 2 点。底蓋は板を下にして印刷）。
    45° なので、スロープの壁の裏（内天井）も外面と平行（壁厚 1.5）のまま自己支持する。
    背面側の内天井も 45° の切妻にしてある。
  - M5Dial はパネルマウント機器。ネジ筒(φ44)を壁の φ45 穴に通し、座(φ48)が
    スロープ外面に当たり、リングナット(φ50.8×5)を裏から手締めして挟む。
    挟まれるのは壁厚 1.5mm そのもの（締結範囲 1〜7.55mm の内側）。
  - 幅はチェンバー φ54 ＋壁で決まる最小値、奥行き・高さは Dial 背面の収まりで決まる。
  - USB-C は Dial の背面寄りの側面にある（公式 STL 実測）。Dial は穴の中で
    回して向きを決められるので、USB-C を斜面の下向きにして L 字プラグを挿し、
    ケーブルを底へ下ろす。ストレートのプラグは前壁に当たって入らない。
  - ボルト・ナットは使わない。底蓋はスナップ爪 4 本（左右妻面の小窓に掛かる。
    掛かり面は約 49° で、前面中央の溝からこじれば外れる）。

■ 座標系（設置姿勢）
    x : 左 → 右（幅）
    y : 前(0, スロープ側) → 奥（背面）
    z : 下(0, 机/造形プレート) → 上

■ Dial の寸法出典
  公式 STL (github.com/m5stack/M5_Hardware の Products/K130_Dial/Structures/Dial.stl)
  を解析した実測値。パネルマウント諸元（穴 φ45 / ネジ筒 φ44 / 座 φ48 /
  ナット φ50.8×5 / パネル厚 1〜7.55）は公式グラフィックの "Φ45mm INSTALLATION"
  表記とも一致する。USB-C の開口（11×5mm）は背面側の円筒の側面、座面から 11.5mm 奥。
  推測: L 字 USB-C プラグの外形（12×7、根元から 10mm で曲がる）と PORT.B の
  プラグ位置は一般的な製品・公式写真からの概算。必ず実機で確認する。
"""

import sys

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon
from trimesh.creation import cylinder as _cylinder
from trimesh.creation import box as _box
from trimesh.creation import extrude_polygon

# --------------------------------------------- M5Dial（パネルマウント・実測）
# 座面（ワッシャ後面＝パネル前面に当たる面）を基準 t=0 として:
DIAL_SEAT_D = 48.0     # 座（固定フランジ＋ワッシャ）の外径。パネル前面に当たる
DIAL_THREAD_D = 44.0   # ネジ筒（オス）の外径。谷径 φ42。これがパネル穴を通る
DIAL_THREAD_L = 12.55  # 座面からネジ筒の終わりまで
DIAL_LEAD_D = 44.6     # ネジ筒の根元にある入口カラーの径（座面から 0.15〜0.9mm）
DIAL_LEAD_T1 = 0.9     # 同・座面から見た終わり。ここより奥はネジ山 φ44.0
DIAL_NUT_D = 50.82     # リングナットの外径（縦溝・手締め）
DIAL_NUT_H = 5.0       # リングナットの高さ
DIAL_PANEL_MAX = DIAL_THREAD_L - DIAL_NUT_H   # 締められるパネル厚の上限 7.55
DIAL_PANEL_MIN = 1.0   # 同・下限（これ以下だとナットが座に当たる）
DIAL_KNOB_D = 49.83    # 回転ノブの外径（縦溝）。触れてはいけない
DIAL_KNOB_GAP = 0.8    # 座面とノブ後端の隙間（ワッシャが潰れた時の最小値）
DIAL_FRONT = 14.62     # 座面からパネル前に出る量（ノブ＋前面ベゼル）
DIAL_BACK = 15.70      # 座面からパネル後ろに出る量（ネジ筒＋背面）
DIAL_BACK_D = 42.0     # ネジ筒より奥（背面側）の最大径
DIAL_BEZEL_D = 45.03   # 前面ベゼルの外径（画面開口は φ35）
DIAL_MASS = 46.3       # g（公式仕様）
USB_T = 11.5           # USB-C 開口中心の座面からの奥行き（開口 11×5mm、実測）
USB_R = 21.0           # USB-C 開口がある円筒の半径（実測）
# 推測: L 字 USB-C プラグ（一般的な製品の概算）
USB_PLUG_W = 12.0      # 幅（Dial の周方向）
USB_PLUG_T = 7.0       # 厚み（Dial の軸方向）
USB_PLUG_L = 10.0      # 円筒の表面から曲がり（ケーブル中心）まで
USB_CABLE_D = 3.7      # ケーブル径（使用するケーブルの実測）

# ---------------------------------------------------------- 筐体の寸法
T_WALL = 1.5        # 壁厚（垂直壁・スロープとも）。0.4mm ノズルで外周3〜4本
SLOPE_DEG = 45.0    # 前面スロープの傾き（水平から。45° は垂直からも 45°）
PLINTH_H = 25.0     # スロープが始まるまでの垂直壁の高さ（指定値）。下限を決めるのは Dial 裏の
                    # PORT.B プラグ空間の最下点（18 で底蓋の上面から 3.4mm）
X_OUT = 60.0        # 幅。チェンバー φ54 ＋壁 1.5×2 ＝ 57 に余裕をみて 60
Y_OUT = 53.0        # 奥行き。Dial 背面がチェンバークリップ（Y_OUT−3.5）より
                    # 1mm 以上手前に来る下限に余裕をみて決める

TAN = np.tan(np.radians(SLOPE_DEG))
SLOPE_S_TOP = 58.0  # 前面スロープの長さ（Dial 中心 30 ＋平面領域の半径 26 ＋上の余白 2）
SLOPE_TOP_Y = SLOPE_S_TOP * np.cos(np.radians(SLOPE_DEG))
TOP_Z = PLINTH_H + SLOPE_S_TOP * np.sin(np.radians(SLOPE_DEG))

# ------------------------------------------------- Dial のパネルマウント穴
POD_S = 30.0        # Dial 中心のスロープ上の位置（斜面下端から）。ノブの平面 φ52 が
                    # 取れる下限は 26 だが、USB-C の L 字プラグが前壁に当たらないよう上げる
PANEL_T = T_WALL    # Dial を挟む厚み＝壁厚そのもの（ベゼル肉付けなし）
HOLE_D = 45.0       # 受け径（公式指定）。入口カラー φ44.6 がここに収まる
HOLE_SEAT_T = 1.0   # φ45 で受ける深さ（入口カラー 0.9mm ぶんを確保）
HOLE_RELIEF_D = 46.0  # それより奥（壁の残り 0.5mm）の逃げ径。穴上縁の垂れ対策
FLAT_D = 52.0       # 穴まわりに平面が要る径（回転ノブ φ49.83 ＋ 逃げ 2mm）
CHAM_D = 54.0       # チェンバー径（ナット φ50.8 ＋ 手回しの逃げ）
CHAM_T = DIAL_BACK + 1.7   # 座面からのチェンバー深さ 17.4
CHAM_CLIP_Y = Y_OUT - T_WALL - 2.0   # チェンバー後端のクリップ位置

N_POD = np.array([0.0, -np.sin(np.radians(SLOPE_DEG)), np.cos(np.radians(SLOPE_DEG))])
U_SLOPE = np.array([0.0, np.cos(np.radians(SLOPE_DEG)), np.sin(np.radians(SLOPE_DEG))])
X_HAT = np.array([1.0, 0.0, 0.0])
POD_C = np.array([X_OUT / 2, 0, PLINTH_H]) + POD_S * U_SLOPE   # Dial の座面中心

# ------------------------------------------------- 底蓋（スナップ爪）
# 本体の下に敷く全面板（外形と同じ平面形・角 R1.5）で、上面から開口の内周に
# 沿うリップが立ち、4 本のスナップ爪が左右の妻面の小窓に掛かる。
# 座標は本体と同じ（組み付け状態で板の上面が z=0、板は z<0）。
# 印刷は板を下にした姿勢（STL は +LID_T だけ持ち上げて出力）。
LID_T = 2.0         # 板厚（＝据え置き時の高さの増分）
LID_CLR = 0.2       # リップ・爪の外面と本体内面の隙間
LIP_W = 1.2         # リップの厚み
LIP_H = 3.5         # リップの高さ（板の上面から）
SNAP_W = 8.0        # 爪の幅
SNAP_T = 1.0        # 爪の腕の厚み（片持ち梁。ひずみ ≒1.5·t·δ/L² ≒ 1.7%）
SNAP_SLIT = 1.0     # 爪の両脇でリップを切り離すすき間
SNAP_P = 0.7        # 爪の出っ張り（隙間 0.2 を引いた掛かり代 0.5）
SNAP_Z = (3.9, 4.7, 5.2, 6.6)   # 爪の輪郭の高さ: 掛かり面の下端／上端（約 49°）、
                    # 平坦部の上端、導入斜面の上端＝腕の先端
SNAP_WIN_Z = (4.05, 6.4)        # 本体側の窓の z 範囲
SNAP_Y = (10.0, Y_OUT - 10.0)   # 左右妻面の爪の y 位置（各面 2 本、前後の壁から 10mm）
PRY_W = 12.0        # 前面中央のこじ開け溝（板の上面に幅 12・深さ 0.8）
PRY_D = 0.8
# ケーブルの出口: 背面壁の下端の U 字の切り欠き（直線部 CABLE_STRAIGHT の上に
# 半円 CABLE_R）。底蓋の板には切り欠きを設けない（底面は平ら）。ケーブルは
# 底蓋の上面を這って出るので、その位置だけ底蓋のリップを切っておく。
CABLE_R = 3.5       # 半円の半径（幅 7）
CABLE_STRAIGHT = 2.0  # 半円の下の直線部（高さ 2 ＋ 3.5 ＝ 5.5。ケーブル φ3.7 に約 1.8mm の余裕）
CABLE_IN = 6.0      # リップを切る範囲の、背面壁内面からの奥行き

SEG = 128           # 円の分割数
EDGE_R = T_WALL     # 角丸の半径。壁厚と同じにすると 90°の角でも肉厚が保たれる
EDGE_SEG = 3        # 丸めに使う球の分割（icosphere subdivisions）


# ============================================================ ヘルパー
def cyl(p0, p1, r, sections=SEG):
    return _cylinder(radius=r, segment=[np.asarray(p0, float), np.asarray(p1, float)],
                     sections=sections)


def bx(x0, x1, y0, y1, z0, z1):
    b = _box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def oriented_box(center, ax, ay, az, ex, ey, ez):
    """center を中心に、単位ベクトル ax/ay/az 方向へ ex/ey/ez の長さを持つ直方体"""
    b = _box(extents=[ex, ey, ez])
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2] = ax, ay, az
    T[:3, 3] = center
    b.apply_transform(T)
    return b


def prism_x(points_yz, x0, x1):
    """y-z 平面の多角形を x 方向に押し出す"""
    m = extrude_polygon(Polygon(points_yz), height=x1 - x0)   # (u,v,w)=(y,z,x-x0)
    m.apply_transform(np.array([[0., 0., 1., x0],
                                [1., 0., 0., 0.],
                                [0., 1., 0., 0.],
                                [0., 0., 0., 1.]]))
    return m


def extrude_xy(poly, z0, z1):
    m = extrude_polygon(poly, height=z1 - z0)
    m.apply_translation([0, 0, z0])
    return m


def union(parts):
    return trimesh.boolean.union(parts, engine='manifold')


def diff(base, cuts):
    return trimesh.boolean.difference([base] + cuts, engine='manifold')


def intersect(a, b):
    return trimesh.boolean.intersection([a, b], engine='manifold')


# ============================================================ 外形
def outer_yz():
    """外形の y-z 断面（反時計回りの凸五角形）"""
    return [(0.0, 0.0), (Y_OUT, 0.0), (Y_OUT, TOP_Z),
            (SLOPE_TOP_Y, TOP_Z), (0.0, PLINTH_H)]


def _halfplane(n, c, big=600.0):
    """n·p >= c の半平面を表す大きな多角形"""
    n = np.asarray(n, float)
    t = np.array([-n[1], n[0]])
    p0 = n * c
    return Polygon([p0 + t * big, p0 - t * big,
                    p0 - t * big + n * 2 * big, p0 + t * big + n * 2 * big])


def eroded_yz(r):
    """外形断面を各辺から r だけ内側へ寄せる（底辺 z=0 は動かさない）"""
    pts = outer_yz()
    poly = Polygon([(-500, -500), (500, -500), (500, 500), (-500, 500)])
    for i, a in enumerate(pts):
        a = np.array(a, float)
        b = np.array(pts[(i + 1) % len(pts)], float)
        e = (b - a) / np.linalg.norm(b - a)
        n = np.array([-e[1], e[0]])               # 反時計回り → 内向き法線
        on_floor = abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9
        poly = poly.intersection(_halfplane(n, n @ a + (0.0 if on_floor else r)))
    return list(poly.exterior.coords)[:-1]


def rounded_outer(r=EDGE_R):
    """角を半径 r で丸めた外形（底面はフラットのまま）"""
    ball = trimesh.creation.icosphere(subdivisions=EDGE_SEG, radius=r)
    centers = [np.array([x, y, z]) for x in (r, X_OUT - r) for (y, z) in eroded_yz(r)]
    hull = trimesh.convex.convex_hull(np.vstack([ball.vertices + c for c in centers]))
    return intersect(hull, bx(-10, X_OUT + 10, -10, Y_OUT + 10, 0, TOP_Z + 10))


# ============================================================ 本体
# 内キャビティの y-z 断面。底は開放、背面は垂直壁を z=BACK_IN_Z まで、そこから
# 45° の内天井（切妻）で前面側へ下る。前面側の内天井は外スロープと平行（壁厚
# T_WALL）。外スロープが 45° より寝る場合は平行な内天井が自己支持しないので、
# 45° の切妻のまま上げて外スロープとの間を中実（インフィル）にする。
BACK_IN_Z = 40.0    # 背面内壁の垂直部分の高さ
ROOF_TAN = 1.0      # 内天井の傾き 45°（これより寝ると自己支持しない）


def _ridge(z0):
    """前内スロープの y=T_WALL での高さ z0 から、前後の内スロープの交点（稜）を返す"""
    yb = Y_OUT - T_WALL
    y_r = (BACK_IN_Z + ROOF_TAN * yb - z0 + ROOF_TAN * T_WALL) / (2 * ROOF_TAN)
    return y_r, BACK_IN_Z + ROOF_TAN * (yb - y_r)


def cavity_yz():
    yb = Y_OUT - T_WALL
    if SLOPE_DEG >= 45.0:
        # 前内スロープは外スロープに平行（壁厚 T_WALL）
        off = T_WALL / np.sin(np.radians(SLOPE_DEG))  # 前内スロープの水平オフセット
        z0 = PLINTH_H - off * TAN + TAN * T_WALL
    else:
        # 稜が外形から T_WALL 内側に収まる最高位置まで 45° の切妻を上げる
        inner = Polygon(eroded_yz(T_WALL))
        lo, hi = 0.0, PLINTH_H
        for _ in range(60):
            z0 = (lo + hi) / 2
            if inner.covers(Point(_ridge(z0))):
                lo = z0
            else:
                hi = z0
        z0 = lo
    assert z0 > 0.5, '内天井が外形に収まらない（BACK_IN_Z が高すぎる）'
    y_r, z_r = _ridge(z0)
    assert Polygon(eroded_yz(T_WALL)).buffer(1e-6).covers(Point(y_r, z_r)), \
        '内天井の稜が外形の壁厚の内側に収まらない'
    return [(T_WALL, 0), (yb, 0), (yb, BACK_IN_Z), (y_r, z_r), (T_WALL, z0)]


def chamber():
    """チェンバー（ナットの回転空間＋Dial 背面）。後端は背面壁の手前で平面クリップ"""
    cham = cyl(POD_C - PANEL_T * N_POD, POD_C - CHAM_T * N_POD, CHAM_D / 2)
    return intersect(cham, bx(-10, X_OUT + 10, -10, CHAM_CLIP_Y, -10, TOP_Z + 10))


def build_body():
    outer = rounded_outer()
    inner = prism_x(cavity_yz(), T_WALL, X_OUT - T_WALL)
    solid = diff(outer, [inner])

    # --- Dial のパネル穴（φ45 で受け、奥は φ46 に逃がす）＋チェンバー。
    #     各切削は奥側の大径区間へ 0.05 食い込ませる（厚みゼロの膜を残さないため）
    EPS = 0.05
    cham = chamber()
    cuts = [cyl(POD_C + 2 * N_POD, POD_C - (HOLE_SEAT_T + EPS) * N_POD, HOLE_D / 2),
            cyl(POD_C - HOLE_SEAT_T * N_POD, POD_C - (PANEL_T + EPS) * N_POD,
                HOLE_RELIEF_D / 2),
            cham]
    # ナットに手が届くよう、チェンバーを真下へ掃き出して底の開口とつなぐ
    # （背面側の内天井の肉がナットの回りに残らないように）。
    # 真下への掃引なので新たな下向き面は生じない。前壁・背面壁は削らない。
    sweep = trimesh.convex.convex_hull(np.vstack([
        cham.vertices, cham.vertices - [0.0, 0.0, TOP_Z + 10]]))
    cuts.append(intersect(sweep, bx(T_WALL, X_OUT - T_WALL, T_WALL, CHAM_CLIP_Y,
                                    -1.0, TOP_Z + 10)))

    # --- 底蓋のスナップ爪の受け: 左右妻面の貫通窓（上縁はブリッジ）
    hw = SNAP_W / 2 + 0.3
    for x0, x1 in ((-1.0, T_WALL + 0.5), (X_OUT - T_WALL - 0.5, X_OUT + 1.0)):
        for sy in SNAP_Y:
            cuts.append(bx(x0, x1, sy - hw, sy + hw, *SNAP_WIN_Z))

    # --- ケーブルの出口: 背面壁の下端の U 字の切り欠き（直線部＋半円）
    y0, y1 = Y_OUT - T_WALL - 1.0, Y_OUT + 1.0
    cuts.append(bx(X_OUT / 2 - CABLE_R, X_OUT / 2 + CABLE_R, y0, y1, -1.0, CABLE_STRAIGHT))
    cuts.append(cyl([X_OUT / 2, y0, CABLE_STRAIGHT], [X_OUT / 2, y1, CABLE_STRAIGHT],
                    CABLE_R, sections=64))
    return diff(solid, cuts)


# ============================================================ 底蓋
def lid_snaps():
    """爪 4 本の (外面上の基点 xy, 外向き法線 xy)"""
    c = T_WALL + LID_CLR
    return ([((c, sy), (-1.0, 0.0)) for sy in SNAP_Y]
            + [((X_OUT - c, sy), (1.0, 0.0)) for sy in SNAP_Y])


def opening_xy():
    """底の開口の平面形（内キャビティの矩形）"""
    return Polygon([(T_WALL, T_WALL), (X_OUT - T_WALL, T_WALL),
                    (X_OUT - T_WALL, Y_OUT - T_WALL), (T_WALL, Y_OUT - T_WALL)])


def build_lid():
    """底蓋（組み付け状態の座標。板の上面が z=0）"""
    plate = Polygon([(0, 0), (X_OUT, 0), (X_OUT, Y_OUT), (0, Y_OUT)]) \
        .buffer(-EDGE_R, join_style=2).buffer(EDGE_R, quad_segs=8)
    op = opening_xy()
    ring = op.buffer(-LID_CLR, join_style=2).difference(
        op.buffer(-LID_CLR - LIP_W, join_style=2))
    parts = [extrude_xy(plate, -LID_T, 0.0)]
    z_lo, z_cu, z_fl, z_top = SNAP_Z
    for (bx_, by_), (nx, ny) in lid_snaps():
        n = np.array([nx, ny, 0.0])
        t = np.array([-ny, nx, 0.0])
        b = np.array([bx_, by_, 0.0])
        # 爪の両脇でリップを切り離す
        g = SNAP_W / 2 + SNAP_SLIT
        gap = [b + sn * n + st * t for sn, st in ((-3, -g), (1, -g), (1, g), (-3, g))]
        ring = ring.difference(Polygon([p[:2] for p in gap]))
        # 腕（外面＝基点の面から内側へ SNAP_T）
        pts = [b + dn * n + s * t + [0, 0, z]
               for dn in (-SNAP_T, 0.0) for s in (-SNAP_W / 2, SNAP_W / 2)
               for z in (-0.5, z_top)]
        parts.append(trimesh.convex.convex_hull(np.array(pts)))
        # 爪（下面＝掛かり面は約 49°、上面＝導入斜面）
        prof = [(-0.1, z_lo), (SNAP_P, z_cu), (SNAP_P, z_fl), (-0.1, z_top)]
        pts = [b + dn * n + s * t + [0, 0, z]
               for dn, z in prof for s in (-SNAP_W / 2, SNAP_W / 2)]
        parts.append(trimesh.convex.convex_hull(np.array(pts)))
    parts += [extrude_xy(g, -0.5, LIP_H) for g in getattr(ring, 'geoms', [ring])]
    lid = union(parts)
    return diff(lid, [
        # 前面中央のこじ開け溝（コインや爪を差し込んで前側から外す）。
        # 前壁の真下だけを彫り、リップの下は削らない（削るとリップが宙に浮く）
        bx(X_OUT / 2 - PRY_W / 2, X_OUT / 2 + PRY_W / 2, -1.0, T_WALL + 0.1, -PRY_D, 0.5),
        # ケーブルが通る位置のリップを切る（板は切らない＝底面は平ら）
        bx(X_OUT / 2 - CABLE_R, X_OUT / 2 + CABLE_R,
           Y_OUT - T_WALL - CABLE_IN, Y_OUT + 1.0, 0.0, LIP_H + 1.0)])


# ============================================================ モック（確認用）
def mock_dial():
    """M5Dial の簡易モデル（同軸円筒の積層）＋PORT.B のプラグ空間。

    座面（＝スロープ外面）を t=0 とし、+t が前（手前）、-t が筐体内側。
    リングナットは壁厚 PANEL_T の位置から奥へ DIAL_NUT_H。
    """
    seat = POD_C
    segs = [(DIAL_SEAT_D / 2, 0.0, 2.35),            # 固定フランジ＋ワッシャ
            (DIAL_KNOB_D / 2, DIAL_KNOB_GAP + 0.85, DIAL_FRONT - 0.4),  # 回転ノブ
            (DIAL_BEZEL_D / 2, DIAL_FRONT - 6.1, DIAL_FRONT),           # 前面ベゼル
            (DIAL_THREAD_D / 2, -DIAL_THREAD_L, 0.0),                   # ネジ筒
            (DIAL_BACK_D / 2, -DIAL_BACK, -DIAL_THREAD_L),              # 背面側
            (DIAL_NUT_D / 2, -PANEL_T - DIAL_NUT_H, -PANEL_T)]          # リングナット
    parts = [cyl(seat + a * N_POD, seat + b * N_POD, r) for r, a, b in segs]
    # PORT.B に挿さる Grove プラグ＋ケーブル曲げの空間（使わなくても空けておく）。
    # 推測: ポート位置は背面プレート上で軸から約 17mm（公式写真からの概算）、
    #       HY2.0 プラグとケーブルの曲げで背面から軸方向に 14mm 見込む。
    parts.append(oriented_box(seat - (DIAL_BACK + 7.0) * N_POD - 17.0 * U_SLOPE,
                              X_HAT, U_SLOPE, -N_POD, 12.0, 8.0, 14.0))
    return union(parts)


def mock_usb():
    """USB-C の L 字プラグ（斜面の下向きに挿す）＋底へ下ろすケーブル"""
    d = -U_SLOPE                                     # 挿す向き（Dial の半径方向・斜面の下向き）
    port = POD_C - USB_T * N_POD
    body = oriented_box(port + (USB_R + USB_PLUG_L / 2 + USB_PLUG_T / 4) * d,
                        X_HAT, d, N_POD, USB_PLUG_W, USB_PLUG_L + USB_PLUG_T / 2, USB_PLUG_T)
    bend = port + (USB_R + USB_PLUG_L) * d
    # ケーブル: 曲がりから Dial の奥向き（-N_POD）に出て、底蓋の上面（z=0.5）まで下る
    s = (bend[2] - USB_CABLE_D / 2 - 0.5) / N_POD[2]
    cable = cyl(bend, bend - s * N_POD, USB_CABLE_D / 2, sections=24)
    return union([body, cable])


# ============================================================ 検証
def audit_overhangs(mesh, name, allow):
    """45°より寝た下向き面を検出。allow=[(説明, 判定関数)] は許容ブリッジ。"""
    nz = mesh.face_normals[:, 2]
    ang = np.degrees(np.arccos(np.clip(np.abs(nz), 0, 1)))
    ctr = mesh.triangles_center
    bad = (nz < -0.05) & (ang < 44.0) & (ctr[:, 2] > 0.4)   # 45° までは自己支持
    report, rest = {}, 0.0
    for i in np.where(bad)[0]:
        for label, fn in allow:
            if fn(ctr[i]):
                report[label] = report.get(label, 0) + mesh.area_faces[i]
                break
        else:
            rest += mesh.area_faces[i]
    print(f'  [{name}] 45°より寝た下向き面:')
    for k, v in sorted(report.items()):
        print(f'    許容ブリッジ {k}: {v:.0f} mm2')
    print(f'    未分類: {rest:.0f} mm2 {"⚠️ 要確認" if rest > 60 else "(微小・OK)"}')
    return rest


def main():
    do_assembly = '--assembly' in sys.argv

    print('本体・底蓋を生成中...')
    body = build_body()
    lid = build_lid()
    lid_print = lid.copy()
    lid_print.apply_translation([0, 0, LID_T])          # 印刷姿勢（板が下）

    for m, n in ((body, 'm5dial_v2_body'), (lid_print, 'm5dial_v2_lid')):
        assert m.is_watertight, f'{n} が watertight ではない'
        assert m.is_winding_consistent
        assert len(m.split(only_watertight=False)) == 1, f'{n} が 1 部品になっていない'
        m.export(f'{n}.stl')
        b = m.bounds
        print(f'  {n}.stl 出力  {(b[1]-b[0]).round(1)} mm  体積 {m.volume/1000:.0f} cm3')

    # --- 印刷可否の検証
    def near(c, p, r):
        return np.linalg.norm(np.asarray(c) - np.asarray(p)) < r
    allow_body = [
        # 半円の頂部（水平に近い幅 3.5mm 程度）。径が小さいのでブリッジで刷れる。
        # Dial の判定範囲にも入るので先に見る
        ('ケーブル切り欠き(半円)頂部', lambda c: c[1] > Y_OUT - T_WALL - 1.1
         and abs(np.hypot(c[0] - X_OUT / 2, c[2] - CABLE_STRAIGHT) - CABLE_R) < 0.1),
        # パネル穴の上縁・チェンバー天井。Dial とナットに隠れる
        ('Dial穴・チェンバー内(隠れる)',
         lambda c: near(c, POD_C - (CHAM_T / 2) * N_POD, CHAM_D / 2 + 12)),
        ('スナップ窓上縁', lambda c: (c[0] < T_WALL + 0.6 or c[0] > X_OUT - T_WALL - 0.6)
         and min(abs(c[1] - sy) for sy in SNAP_Y) < SNAP_W / 2 + 0.4
         and abs(c[2] - SNAP_WIN_Z[1]) < 0.1),
    ]
    rest_b = audit_overhangs(body, 'm5dial_v2_body', allow_body)
    rest_l = audit_overhangs(lid_print, 'm5dial_v2_lid(印刷姿勢)', [])
    assert rest_b < 1.0 and rest_l < 1.0, '未分類の下向き面がある'

    # --- Dial のパネルマウントが成立するかの検証
    assert HOLE_D > DIAL_LEAD_D + 0.2
    assert HOLE_SEAT_T > DIAL_LEAD_T1
    assert HOLE_RELIEF_D > HOLE_D and HOLE_RELIEF_D < DIAL_SEAT_D - 1.0
    assert DIAL_PANEL_MIN <= PANEL_T <= DIAL_PANEL_MAX, \
        f'パネル厚 {PANEL_T} がナットの締結範囲 {DIAL_PANEL_MIN}〜{DIAL_PANEL_MAX} の外'
    assert CHAM_D > DIAL_NUT_D + 1.5, 'チェンバーでリングナットが回らない'
    assert CHAM_T > DIAL_BACK + 1.0, 'チェンバーが Dial 背面の深さに足りない'
    assert X_OUT - 2 * T_WALL > CHAM_D + 1.0, 'チェンバーが妻面にかかる'
    seat_ring = (DIAL_SEAT_D - HOLE_D) / 2
    assert seat_ring > 0.8
    nut_ring_w = (CHAM_D - HOLE_RELIEF_D) / 2
    assert nut_ring_w >= 3.0, f'ナットが締め付ける座の幅 {nut_ring_w}mm が狭い'
    assert POD_S - FLAT_D / 2 > 0 and POD_S + FLAT_D / 2 < SLOPE_S_TOP, \
        'ノブの平面領域がスロープからはみ出す'
    assert X_OUT / 2 - FLAT_D / 2 > T_WALL, 'ノブの平面領域が妻面にかかる'

    # --- Dial まわりの空間チェック
    assert CHAM_CLIP_Y <= Y_OUT - T_WALL - 0.5, 'チェンバークリップが背面壁に近すぎる'
    dial_back_y = (POD_C - DIAL_BACK * N_POD)[1] + (DIAL_BACK_D / 2) * U_SLOPE[1]
    assert dial_back_y < CHAM_CLIP_Y - 1.0, \
        f'Dial 背面 y={dial_back_y:.1f} がチェンバークリップ {CHAM_CLIP_Y} を越える'
    #     リングナットに底から手が届くこと: ナット外周（下半分）の各点から
    #     真下に、机まで本体の肉が無いこと
    nut_c = POD_C - (PANEL_T + DIAL_NUT_H / 2) * N_POD
    blocked = []
    for th in np.radians(np.arange(180, 361, 15)):
        p = nut_c + (DIAL_NUT_D / 2) * (np.cos(th) * X_HAT + np.sin(th) * U_SLOPE)
        hit = body.ray.intersects_location([p - [0, 0, 0.5]], [[0, 0, -1]])[0]
        if len(hit) and (hit[:, 2] > 0.1).any():
            blocked.append(round(float(np.degrees(th))))
    assert not blocked, f'リングナットの下に本体の肉がある（角度 {blocked}）'
    dial, usb = mock_dial(), mock_usb()
    dial_low = dial.bounds[0][2]
    assert dial_low > LIP_H - 1.5, f'Dial の最下点 z={dial_low:.1f} が底蓋に近すぎる'
    #     底蓋: 爪が窓に掛かること（壁内面の位置で、掛かり面が窓の下縁より上、
    #     爪の上側が窓の上縁より下）と、腕のひずみ
    zc = SNAP_Z[0] + (SNAP_Z[1] - SNAP_Z[0]) * LID_CLR / SNAP_P
    zt = SNAP_Z[2] + (SNAP_Z[3] - SNAP_Z[2]) * (SNAP_P - LID_CLR) / SNAP_P
    assert SNAP_WIN_Z[0] < zc and zt < SNAP_WIN_Z[1], '爪が窓に収まらない'
    assert SNAP_WIN_Z[0] - 1.0 > 0, '窓の下の壁が薄い'
    strain = 1.5 * SNAP_T * (SNAP_P - LID_CLR) / SNAP_Z[3] ** 2
    assert strain < 0.025, f'爪の腕のひずみ {strain:.1%} が大きい'
    #     ケーブル: 出口の高さがケーブル径より大きいこと
    assert CABLE_STRAIGHT + CABLE_R > USB_CABLE_D + 1.5, 'ケーブルの出口が低い'
    assert 2 * CABLE_R > USB_CABLE_D + 2.5, 'ケーブルの出口が狭い'
    print(f'  Dial: 受け径 φ{HOLE_D}×{HOLE_SEAT_T}mm（奥は φ{HOLE_RELIEF_D} に逃がす）'
          f' / パネル厚 {PANEL_T}mm（締結範囲 {DIAL_PANEL_MIN}〜{DIAL_PANEL_MAX:.2f}）'
          f' / 座の当たり幅 {seat_ring:.2f}mm / ナット座の幅 {nut_ring_w:.1f}mm')
    print(f'  Dial: 最下点 z={dial_low:.1f} / Dial 背面 y={dial_back_y:.1f}'
          f'（チェンバークリップ {CHAM_CLIP_Y}）')

    # --- 質量と重心（据え置きの安定の目安）
    rho = 1.24e-3                                    # PLA g/mm3
    parts = [(body.volume * rho, body.center_mass[2]),
             (DIAL_MASS, POD_C[2]),
             (lid.volume * rho, lid.center_mass[2])]
    mass = sum(m for m, _ in parts)
    com_z = sum(m * z for m, z in parts) / mass
    print(f'  質量・重心: 総質量 {mass:.0f} g（本体 {body.volume * rho:.0f} g・'
          f'底蓋 {lid.volume * rho:.0f} g・Dial {DIAL_MASS} g）,'
          f' 重心 机から {com_z + LID_T:.0f} mm / 据え置き高さ {TOP_Z + LID_T:.1f} mm'
          f' / 爪のひずみ {strain:.1%}')

    # --- 部品間の干渉（ブーリアン交差＝0）
    for a, b, name in ((body, dial, '本体×Dial'), (body, usb, '本体×USB-C プラグ'),
                       (lid, body, '底蓋×本体'), (lid, dial, '底蓋×Dial'),
                       (lid, usb, '底蓋×USB-C プラグ')):
        inter = intersect(a, b)
        v = inter.volume if inter is not None and len(inter.faces) else 0.0
        assert v < 0.01, f'{name} が干渉（交差体積 {v:.2f} mm3）'
    print('  干渉チェック OK（本体/底蓋/Dial/USB-C プラグの交差体積 = 0）')

    if do_assembly:
        print('組み付けイメージを生成中...')
        dial.export('mock_dial.stl')
        usb.export('mock_usb.stl')
        lid.export('mock_lid.stl')                   # 組み付け位置の底蓋
        half = diff(body, [bx(-1, X_OUT / 2, -1, Y_OUT + 1, -1, TOP_Z + 1)])
        half.export('body_half.stl')
        print('  mock_dial.stl / mock_usb.stl / mock_lid.stl / body_half.stl 出力')


if __name__ == '__main__':
    main()
