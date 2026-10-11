import os
from flask import Flask, render_template, request, send_file, jsonify, url_for
import pymupdf
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
STATIC_IMG_FOLDER = 'static/pages'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMG_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    doc = pymupdf.open(file_path)
    pages_info = []
    zoom = 2.0  # High res render zoom
    mat = pymupdf.Matrix(zoom, zoom)
    
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_filename = f"{file.filename}_page_{i}.png"
        img_path = os.path.join(STATIC_IMG_FOLDER, img_filename)
        pix.save(img_path)
        
        image_url = url_for('static', filename=f'pages/{img_filename}')
        pages_info.append({
            'pageIndex': i,
            'imageUrl': image_url,
            'origWidth': pix.width,
            'origHeight': pix.height
        })
        
    doc.close()
    
    return jsonify({
        'success': True, 
        'filename': file.filename, 
        'pages': pages_info,
        'zoomFactor': zoom
    })

@app.route('/save_pdf', methods=['POST'])
def save_pdf():
    data = request.json
    filename = data.get('filename')
    all_pages_edits = data.get('pages', [])
    zoom_factor = float(data.get('zoomFactor', 2.0))
    
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'PDF not found'}), 404
        
    doc = pymupdf.open(input_path)
    
    font_file = "NotoSerifDevanagari-Regular.ttf"
    if not os.path.exists(font_file):
        font_file = "NotoSansDevanagari-Regular.ttf"

    for page_edit in all_pages_edits:
        p_idx = page_edit.get('pageIndex', 0)
        elements = page_edit.get('elements', [])
        rectangles = page_edit.get('rectangles', [])
        
        img_filename = f"{filename}_page_{p_idx}.png"
        img_path = os.path.join(STATIC_IMG_FOLDER, img_filename)
        
        if os.path.exists(img_path) and p_idx < len(doc):
            base_img = Image.open(img_path).convert("RGB")
            draw = ImageDraw.Draw(base_img)
            
            # Since frontend coordinates are already mapped to original image pixels, use directly or scale if ratio applied
            for rect in rectangles:
                rx = float(rect.get('x', 0))
                ry = float(rect.get('y', 0))
                rw = float(rect.get('width', 50))
                rh = float(rect.get('height', 20))
                color_hex = rect.get('color', '#ffffff')
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=color_hex)
                
            for el in elements:
                text = el.get('text', '')
                x = float(el.get('x', 50))
                y = float(el.get('y', 50))
                font_size = float(el.get('fontSize', 14)) * (zoom_factor / 1.5) # Scale font size with zoom
                color_hex = el.get('color', '#000000')
                
                try:
                    if os.path.exists(font_file):
                        font = ImageFont.truetype(font_file, int(font_size))
                    else:
                        font = ImageFont.load_default()
                except:
                    font = ImageFont.load_default()
                    
                draw.text((x, y), text, fill=color_hex, font=font)
                
            modified_img_path = os.path.join(UPLOAD_FOLDER, f"modified_p{p_idx}_{filename}")
            base_img.save(modified_img_path, "PNG")
            
    output_filename = "edited_" + filename
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    
    images_to_pdf = []
    for i in range(len(doc)):
        mod_path = os.path.join(UPLOAD_FOLDER, f"modified_p{i}_{filename}")
        if os.path.exists(mod_path):
            images_to_pdf.append(Image.open(mod_path).convert('RGB'))
        else:
            orig_img_path = os.path.join(STATIC_IMG_FOLDER, f"{filename}_page_{i}.png")
            if os.path.exists(orig_img_path):
                images_to_pdf.append(Image.open(orig_img_path).convert('RGB'))
                
    doc.close()
    
    if images_to_pdf:
        images_to_pdf[0].save(
            output_path, "PDF", resolution=300.0, quality=95,
            save_all=True, append_images=images_to_pdf[1:]
        )
        
    return jsonify({'success': True, 'download_url': f'/download/{output_filename}'})

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)