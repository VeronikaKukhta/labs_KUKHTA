
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, send_file, Response, jsonify

app = Flask(__name__)


STORAGE_DIR = Path("./storage").resolve()

def get_full_path(path):
    if path.startswith('/'):
        path = path[1:]
    path = path.replace('\\', '/')
    full_path = STORAGE_DIR / path
    full_path = full_path.resolve()
    
    if STORAGE_DIR not in full_path.parents and full_path != STORAGE_DIR:
        return None
    
    return full_path

def get_file_info(file_path):
   
    try:
        stat = file_path.stat()
        return {
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    except Exception as e:
        print(f"Error getting file info: {e}")
        return {'size': 0, 'modified': ''}

def list_directory(dir_path):
   
    items = []
    
    try:
        for item in dir_path.iterdir():
            
            if not item.is_file() and not item.is_dir():
                continue
             
            try:
                rel_path = str(item.relative_to(STORAGE_DIR)).replace('\\', '/')
            except:
                rel_path = item.name
            
            item_info = {
                'name': item.name,
                'type': 'directory' if item.is_dir() else 'file',
                'path': rel_path
            }
            
            if item.is_file():
                try:
                    info = get_file_info(item)
                    item_info['size'] = info['size']
                    item_info['modified'] = info['modified']
                except:
                    item_info['size'] = 0
                    item_info['modified'] = ''
            
            items.append(item_info)
    except Exception as e:
        print(f"Error listing directory: {e}")
        raise
    
    return items

@app.route('/', defaults={'path': ''}, methods=['GET', 'PUT', 'DELETE', 'HEAD'])
@app.route('/<path:path>', methods=['GET', 'PUT', 'DELETE', 'HEAD'])
def handle_storage(path):
    
    full_path = get_full_path(path)
    
    if full_path is None:
        return jsonify({'error': 'Invalid path'}), 400
    
    if request.method == 'PUT':
        return handle_put(full_path, path)
    elif request.method == 'GET':
        return handle_get(full_path, path)
    elif request.method == 'DELETE':
        return handle_delete(full_path)
    elif request.method == 'HEAD':
        return handle_head(full_path)

def handle_put(full_path, original_path):
   
    
    copy_from = request.headers.get('X-Copy-From')
    
    if copy_from:
       
        if copy_from.startswith('/'):
            copy_from = copy_from[1:]
        
        source_path = get_full_path(copy_from)
        
        if source_path is None:
            return jsonify({'error': 'Invalid source path'}), 400
        
        if not source_path.exists():
            return jsonify({'error': 'Source file not found'}), 404
        
        if not source_path.is_file():
            return jsonify({'error': 'Source is not a file'}), 400
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, full_path)
            return jsonify({'message': 'File copied successfully'}), 201
        except Exception as e:
            return jsonify({'error': f'Failed to copy: {str(e)}'}), 500
    
   
    file_data = request.get_data()
    
    if not file_data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
       
        with open(full_path, 'wb') as f:
            f.write(file_data)
        
        return jsonify({'message': 'File uploaded successfully', 'size': len(file_data)}), 201
    except Exception as e:
        return jsonify({'error': f'Failed to upload: {str(e)}'}), 500

def handle_get(full_path, original_path):
    
    if not full_path.exists():
        return jsonify({'error': 'File or directory not found'}), 404
    
    if full_path.is_dir():
        try:
            items = list_directory(full_path)
            return jsonify({
                'path': original_path or '/',
                'contents': items
            }), 200
        except Exception as e:
            return jsonify({'error': f'Failed to list directory: {str(e)}'}), 500
    
    try:
        return send_file(
            full_path,
            as_attachment=False,
            download_name=full_path.name
        )
    except Exception as e:
        return jsonify({'error': f'Failed to send file: {str(e)}'}), 500

def handle_delete(full_path):
    
    if not full_path.exists():
        return jsonify({'error': 'File or directory not found'}), 404
    
    try:
        if full_path.is_file():
            full_path.unlink()
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            shutil.rmtree(full_path)
            return jsonify({'message': 'Directory deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to delete: {str(e)}'}), 500

def handle_head(full_path):
  
    if not full_path.exists():
        return Response(status=404)
    
    if full_path.is_dir():
        return Response(status=400, headers={'X-Error': 'Cannot HEAD a directory'})
    
    try:
        info = get_file_info(full_path)
        
        headers = {
            'X-File-Size': str(info['size']),
            'X-File-Modified': info['modified'],
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(info['size'])
        }
        
        return Response(status=200, headers=headers)
    except Exception as e:
        return Response(status=500)

if __name__ == '__main__':
    
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
 
    app.run(host='0.0.0.0', port=5000, debug=False)