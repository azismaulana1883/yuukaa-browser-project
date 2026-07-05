from PIL import Image, ImageDraw, ImageFont

def create_icon():
    # Buat image berukuran 256x256 dengan background transparan
    size = 256
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Gambar lingkaran ungu/pink sebagai background
    d.ellipse([(10, 10), (size-10, size-10)], fill=(124, 77, 255)) # Warna #7c4dff
    
    # Coba pakai font default, jika gagal pakai font dasar
    try:
        font = ImageFont.truetype("arialbd.ttf", 160)
    except IOError:
        font = ImageFont.load_default()
    
    # Tulis huruf "Y" putih di tengah
    text = "Y"
    # Dapatkan ukuran teks
    left, top, right, bottom = d.textbbox((0,0), text, font=font)
    text_w = right - left
    text_h = bottom - top
    
    # Gambar teks di tengah
    x = (size - text_w) / 2
    y = (size - text_h) / 2 - 20 # Geser sedikit ke atas agar simetris
    d.text((x, y), text, font=font, fill=(255, 255, 255))
    
    # Simpan sebagai ICO
    img.save('icon.ico', format='ICO', sizes=[(256, 256), (128,128), (64,64), (32,32)])
    print("icon.ico berhasil dibuat!")

if __name__ == "__main__":
    create_icon()
