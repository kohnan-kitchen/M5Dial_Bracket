// 三角柱の内側コーナーに円柱状の切り欠きによる補強を追加
// パラメータ
base_length = 128;      // 底辺の長さ (mm)
prism_height = 70;      // 三角柱の高さ (mm)
corner_radius = 3;      // 角の丸みの半径 (mm)
side_wall_thickness = 3;  // 側面の壁の厚さ (mm)
base_wall_thickness = 3; // 底辺の壁の厚さ (mm)
hole_diameter = 45;     // 穴の直径 (mm)
fillet_radius = 8;      // 内側の角の補強用円柱の半径 (mm)
$fn = 64;               // 丸みの解像度（補強部分をきれいに表示するため高めの値に設定）

// 三角形の高さを計算（底辺×tan(30°)）
triangle_height = base_length * tan(30);

// 外側三角形
module outer_triangle() {
    polygon(points=[
        [0, 0],               // 左下（直角の点）
        [base_length, 0],     // 右下（60度の角）
        [0, triangle_height]  // 左上（30度の角）
    ]);
}

// 内側三角形（調整済み）- これは表示用
module inner_triangle_visual() {
    // 内側の三角形の寸法を計算
    // 底辺の壁厚を考慮
    inner_base = base_length - (2 * side_wall_thickness);
    // 高さは角度30度を保つために調整
    inner_height = inner_base * tan(30);
    // 内側三角形の位置調整（底部から上に、左端から右に）
    x_offset = side_wall_thickness + 2;
    y_offset = base_wall_thickness + 2;
    
    translate([x_offset, y_offset, 0])
        polygon(points=[
            [0, 0],                  // 左下（直角の点）
            [inner_base-15, 0],      // 右下（60度の角）
            [0, inner_height-10]     // 左上（30度の角）
        ]);
}

// 内側三角形（円柱による切り欠きなし）- くり抜き用の基本形状
module inner_triangle_base() {
    // 内側の三角形の寸法を計算
    inner_base = base_length - (2 * side_wall_thickness);
    inner_height = inner_base * tan(30);
    x_offset = side_wall_thickness + 2;
    y_offset = base_wall_thickness + 2;
    
    // 角の位置を計算
    corner1 = [x_offset, y_offset]; // 左下の角（直角）
    corner2 = [x_offset + inner_base - 15, y_offset]; // 右下の角（60度）
    corner3 = [x_offset, y_offset + inner_height - 10]; // 左上の角（30度の鋭角）
    
    translate([0, 0, 0])
        polygon(points=[
            corner1,
            corner2,
            corner3
        ]);
}

// 角の丸い三角柱モジュール
module rounded_triangular_prism(depth, radius) {
    minkowski() {
        // 縮小した三角形
        linear_extrude(height=depth-radius*2)
            offset(r=-radius)
                outer_triangle();
        
        // 球との合成で角を丸める
        sphere(r=radius);
    }
}

// メイン処理
difference() {
    // 外側の角丸三角柱
    rounded_triangular_prism(prism_height, corner_radius);
    
    // 内側空間をくり抜く
    difference() {
        // 基本の内側三角柱（完全くり抜き）
        translate([0, 0, -5])
            linear_extrude(height=prism_height + 10)
                inner_triangle_base();
        
        // 左下の角（直角）に円柱状の切り欠き
        x_offset = side_wall_thickness + 2;
        y_offset = base_wall_thickness + 2;
        translate([x_offset, y_offset, -5])
            cylinder(r=fillet_radius, h=prism_height + 10);
        
        // 右下の角（60度）に円柱状の切り欠き
        inner_base = base_length - (2 * side_wall_thickness);
        translate([x_offset + inner_base - 15, y_offset, -5])
            cylinder(r=fillet_radius + 10, h=prism_height + 10);
        
        // 左上の角（30度の鋭角）に円柱状の切り欠き
        inner_height = inner_base * tan(30);
        translate([x_offset, y_offset + inner_height - 10, -5])
            cylinder(r=fillet_radius, h=prism_height + 10000);
    }
    
    // 斜面に穴をあける（元の中央位置）
    // 三角形の斜辺の長さと角度を計算
    hypotenuse_length = sqrt(pow(base_length, 2) + pow(triangle_height, 2));
    hypotenuse_angle = atan2(triangle_height, base_length);
    
    // 斜面の中央に穴を配置
    translate([base_length/2, triangle_height/2, prism_height/2])
        // 斜面に対して垂直になるよう回転
        rotate([0, 0, -hypotenuse_angle])
        rotate([90, 0, 0])
        translate([-10, -corner_radius, -60])
        cylinder(h=hypotenuse_length, d=hole_diameter, center=true);
}