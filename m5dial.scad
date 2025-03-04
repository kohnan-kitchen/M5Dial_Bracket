// 元の穴位置に戻した三角柱
// パラメータ
base_length = 120;      // 底辺の長さ (mm)
prism_height = 100;     // 三角柱の高さ (mm)
corner_radius = 5;      // 角の丸みの半径 (mm)
side_wall_thickness = 5;  // 側面の壁の厚さ (mm)
base_wall_thickness = 5; // 底辺の壁の厚さ (mm)
hole_diameter = 45;     // 穴の直径 (mm)
$fn = 50;               // 丸みの解像度

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

// 内側三角形（調整済み）
module inner_triangle() {
    // 内側の三角形の寸法を計算
    // 底辺の壁厚を考慮
    inner_base = base_length - (2 * side_wall_thickness);
    // 高さは角度30度を保つために調整
    inner_height = inner_base * tan(30);
    // 内側三角形の位置調整（底部から上に、左端から右に）
    x_offset = side_wall_thickness;
    y_offset = base_wall_thickness;
    
    translate([x_offset, y_offset, 0])
        polygon(points=[
            [0, 0],                  // 左下（直角の点）
            [inner_base-15, 0],         // 右下（60度の角）
            [0, inner_height-10]        // 左上（30度の角）
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
    
    // 内側の三角柱（完全くり抜き）
    translate([0, 0, -5])
        linear_extrude(height=prism_height + 10)
            inner_triangle();
    
    // 斜面に穴をあける（元の中央位置）
    // 三角形の斜辺の長さと角度を計算
    hypotenuse_length = sqrt(pow(base_length, 2) + pow(triangle_height, 2));
    hypotenuse_angle = atan2(triangle_height, base_length);
    
    // 斜面の中央に穴を配置
    translate([base_length/2, triangle_height/2, prism_height/2])
        // 斜面に対して垂直になるよう回転
        rotate([0, 0, -hypotenuse_angle])
        rotate([90, 0, 0])
        translate([-10,-5,-60])
        cylinder(h=hypotenuse_length, d=hole_diameter, center=true);
}