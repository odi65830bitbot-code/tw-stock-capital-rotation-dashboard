import os
from PIL import Image, ImageDraw

def process_image(src_path, dest_path):
    print(f"Processing {src_path} -> {dest_path}")
    img = Image.open(src_path).convert("RGBA")
    width, height = img.size
    
    # 建立一個與圖片同大小的遮罩，0代表非背景，255代表背景（透明）
    mask = Image.new("L", (width, height), 0)
    
    # 使用 flood fill 演算法，從四個角 (0,0), (width-1, 0), (0, height-1), (width-1, height-1) 開始填滿
    # 我們判斷與起始點顏色相近 (白色或極淺灰色) 的像素
    # 容差 (tolerance) 可以設在 20-30 左右，因為是 plain white
    pixels = img.load()
    
    # 我們把 border-connected 的淺色像素找出來
    # 用 PIL ImageDraw.floodfill
    # 淺色定義：R > 235 且 G > 235 且 B > 235
    # 我們可以自己實現一個簡易的 BFS/DFS floodfill，或是利用 ImageDraw.floodfill
    # 為了高精準度，我們自己寫一個簡單的 BFS 容差 flood fill
    
    visited = [[False for _ in range(height)] for _ in range(width)]
    queue = []
    
    # 將四個邊界的像素如果夠白就放入 queue
    for x in range(width):
        for y in [0, height - 1]:
            r, g, b, a = pixels[x, y]
            if r > 230 and g > 230 and b > 230 and not visited[x][y]:
                queue.append((x, y))
                visited[x][y] = True
                
    for y in range(height):
        for x in [0, width - 1]:
            r, g, b, a = pixels[x, y]
            if r > 230 and g > 230 and b > 230 and not visited[x][y]:
                queue.append((x, y))
                visited[x][y] = True
                
    # BFS
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while queue:
        cx, cy = queue.pop(0)
        mask.putpixel((cx, cy), 255) # 標記為背景
        
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height:
                if not visited[nx][ny]:
                    nr, ng, nb, na = pixels[nx, ny]
                    # 容差判斷：夠白就連通
                    if nr > 220 and ng > 220 and nb > 220:
                        visited[nx][ny] = True
                        queue.append((nx, ny))
                        
    # 套用遮罩，把遮罩為 255 的地方的 alpha 設為 0
    # 另外，為了邊緣平滑，我們可以對遮罩做些微的模糊或收縮，不過直接去背就很不錯
    # 我們把遮罩為 255 的像素 alpha 設為 0
    # 順便做一下邊緣的羽化 (feathering) 或是簡單的抗鋸齒
    # 如果一個像素的鄰居有背景有前景，我們可以稍微調低它的 alpha
    newData = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            is_bg = mask.getpixel((x, y)) == 255
            if is_bg:
                newData.append((r, g, b, 0))
            else:
                # 簡單抗鋸齒：如果它的鄰居有背景像素，可以給予半透明
                is_edge = False
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if mask.getpixel((nx, ny)) == 255:
                            is_edge = True
                            break
                if is_edge:
                    # 邊緣像素，如果是白色附近的就給更低alpha
                    if r > 200 and g > 200 and b > 200:
                        newData.append((r, g, b, int(a * 0.3)))
                    else:
                        newData.append((r, g, b, int(a * 0.7)))
                else:
                    newData.append((r, g, b, a))
                    
    img.putdata(newData)
    
    # 裁切多餘的透明邊界，讓圖片緊湊
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    # 縮放到合適的卡牌尺寸 (例如 512x512) 以提升網頁載入速度
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    
    # 儲存為 PNG
    img.save(dest_path, "PNG")
    print(f"Saved to {dest_path}")

if __name__ == "__main__":
    base_dir = "/Users/maxyu/.gemini/antigravity-ide/brain/52bc8f4e-6d03-443d-b899-49018ff9fe6c"
    output_dirs = [
        "/Users/maxyu/Documents/台股資金網站/web/public/creatures",
        "/Users/maxyu/Documents/台股資金網站/public/creatures"
    ]
    
    mapping = {
        "shiba_fortune_1781438506341.png": "shiba_fortune.png",
        "lucky_cat_1781438532430.png": "lucky_cat.png",
        "fortune_corgi_1781438546782.png": "fortune_corgi.png",
        "wealthy_orange_cat_1781438560848.png": "wealthy_orange_cat.png",
        "lucky_samoyed_new_1781439929283.png": "lucky_samoyed.png",
        "fortune_husky_1781438590104.png": "fortune_husky.png",
        "fortune_golden_retriever_1781438603686.png": "fortune_golden_retriever.png",
        "fortune_french_bulldog_1781438618823.png": "fortune_french_bulldog.png",
        "fortune_poodle_1781438633899.png": "fortune_poodle.png"
    }
    
    for src, dest in mapping.items():
        src_path = os.path.join(base_dir, src)
        if os.path.exists(src_path):
            for out_dir in output_dirs:
                dest_path = os.path.join(out_dir, dest)
                process_image(src_path, dest_path)
        else:
            print(f"Source file not found: {src_path}")
