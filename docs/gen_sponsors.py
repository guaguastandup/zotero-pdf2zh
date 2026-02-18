import urllib.parse

# ================= 配置区域 =================

# 基础配色 (对应你喜欢的绿色小清新风格)
STYLE_CONFIG = {
    "style": "flat-square",
    "color": "e8f5e0",       # 右侧背景色 (浅绿)
    "labelColor": "ffffff",  # 左侧背景色 (白色)
    # 如果你想让左侧文字(名字)是深绿，Shields.io默认很难改文字颜色，
    # 但我们可以通过把名字放在 message (右侧) 来通过 color 控制背景，
    # 下面的脚本采用最稳妥的 label=名字 方案。
}

# 赞助者名单列表
# 格式 1: 简单名字 -> "名字"
# 格式 2: 带备注 -> ("名字", "备注")
# 格式 3: 带链接 -> ("名字", "备注", "链接")
SPONSORS = [
    # --- 贡献者 (带链接/Logo) ---
    ("awwaawwa", "GitHub x8", "https://github.com/awwaawwa"),
    ("htyxyt", "GitHub", "https://github.com/htyxyt"),
    ("jiajia", "Bilibili", "https://space.bilibili.com/347580558"),
    # --- 赞助者 ---
    "bibiu77",
    "*琰",
    "*冬萍",
    ("阿赟", "x3"),  # 带备注
    "*声",
    "h*u",
    ("爱发电用户", "96598"),
    "soooda",
    ("泪花花", "x2"),
    "狐狸",
    "山间火",
    "Angus",
    "研究所",
    "Henrietta",
    "匿名",
    "柿十",
    "*川",
    "Milse",
    "n*r",
    "*糖",
    "小马",
    "**龙",
    "*u",
    "prprprprpprpr",
    "Lstar",
    "*头",
    "YoungEmperorCaesar",
    "Yuriart",
    "J*h",
    "GeorgeXiaobinRen",
    "Keeptg",
    "h*o",
    "C*u",
    "莫林",
    "*萌",
    "*川",
    "*博",
    "Sine璇"
]

# ================= 核心逻辑 =================

def generate_html():
    print('<div align="center">')
    print('  <h3>赞助者名单</h3>')
    print('  <p>感谢您的支持! 您的支持是我开发的动力~</p>')
    print('  <br>')
    print('  <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 4px;">')

    for entry in SPONSORS:
        name = ""
        msg = "Sponsor" # 默认备注
        link = None
        
        # 解析输入数据格式
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, tuple):
            if len(entry) == 2:
                name, msg = entry
            elif len(entry) == 3:
                name, msg, link = entry

        # URL 编码关键步骤 (解决中文乱码问题)
        safe_name = urllib.parse.quote(name)
        safe_msg = urllib.parse.quote(msg)
        
        # 针对特殊 Logo 的颜色处理 (可选)
        current_color = "fb7299" if "Bilibili" in msg else "2d5a27" if "GitHub" in msg else STYLE_CONFIG["color"]
        logo_part = ""
        
        # 如果是 GitHub 或 B站，加个 Logo 参数
        if "GitHub" in msg:
            logo_part = "&logo=github&logoColor=2d5a27"
            # 特殊高亮配色
            shield_url = f"https://img.shields.io/static/v1?label={safe_name}&message={safe_msg}&color=2d5a27&labelColor=f5fbf0&style={STYLE_CONFIG['style']}{logo_part}"
        elif "Bilibili" in msg:
            logo_part = "&logo=bilibili&logoColor=fb7299"
            shield_url = f"https://img.shields.io/static/v1?label={safe_name}&message={safe_msg}&color=fb7299&labelColor=f5fbf0&style={STYLE_CONFIG['style']}{logo_part}"
        else:
            # 普通赞助者配色
            shield_url = f"https://img.shields.io/static/v1?label={safe_name}&message={safe_msg}&color={STYLE_CONFIG['color']}&labelColor={STYLE_CONFIG['labelColor']}&style={STYLE_CONFIG['style']}"

        # 生成 HTML 标签
        img_tag = f'<img src="{shield_url}" alt="{name}">'
        
        if link:
            print(f'    <a href="{link}">{img_tag}</a>')
        else:
            print(f'    {img_tag}')

    print('  </div>')
    print('  <div style="margin-top: 20px;">')
    print('    <img src="../images/chii.jpg" alt="感谢" width="150" style="border-radius: 10px;" />')
    print('  </div>')
    print('</div>')

if __name__ == "__main__":
    generate_html()