from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
import threading
import time
import socket

app = Flask(__name__)

CONFIG_FILE = "stream_config.json"

default_config = {
    "bitrate": 6000000,
    "denoise": "auto",
    "codec": "libav",
    "libav_format": "mpegts",
    "profile": "high",
    "hdr": "off",
    "level": "4.1",
    "framerate": 30,
    "width": 1920,
    "height": 1080,
    "intra": 15,
    "av_sync": 0,
    "awb": "indoor",
    "rtsp_host": "",
    "rtsp_port": 8554,
    "rtsp_path": "kali1080",
    "nice": -11,
    "sharpness": 1.0,
    "contrast": 1.0,
    "brightness": 0.0,
    "saturation": 1.0,
    "exposure": "normal"
}

def get_lan_ip():
    """Get the primary LAN IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(('10.254.254.254', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    except:
        return '127.0.0.1'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return default_config.copy()

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_rtsp_url(config):
    """Get RTSP URL, using LAN IP if not explicitly configured"""
    host = config.get('rtsp_host', '')
    if not host or host == '127.0.0.1':
        host = get_lan_ip()
    return f"rtsp://{host}:{config['rtsp_port']}/{config['rtsp_path']}"

def is_stream_running():
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'pi_camera_stream'],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == 'active'
    except:
        return False

def get_cpu_stats():
    """Get CPU stats for total and individual cores"""
    stats = {"total": 0, "cores": []}
    
    try:
        # Read first sample
        with open('/proc/stat', 'r') as f:
            lines1 = f.readlines()
        
        # Parse cpu lines (total + individual cores)
        cpu_lines1 = {}
        for line in lines1:
            if line.startswith('cpu'):
                parts = line.split()
                cpu_name = parts[0]
                values = list(map(int, parts[1:]))
                idle = values[3]
                total = sum(values)
                cpu_lines1[cpu_name] = {'idle': idle, 'total': total}
        
        time.sleep(0.3)
        
        # Read second sample
        with open('/proc/stat', 'r') as f:
            lines2 = f.readlines()
        
        cpu_lines2 = {}
        for line in lines2:
            if line.startswith('cpu'):
                parts = line.split()
                cpu_name = parts[0]
                values = list(map(int, parts[1:]))
                idle = values[3]
                total = sum(values)
                cpu_lines2[cpu_name] = {'idle': idle, 'total': total}
        
        # Calculate total CPU
        if 'cpu' in cpu_lines1 and 'cpu' in cpu_lines2:
            idle_diff = cpu_lines2['cpu']['idle'] - cpu_lines1['cpu']['idle']
            total_diff = cpu_lines2['cpu']['total'] - cpu_lines1['cpu']['total']
            if total_diff > 0:
                stats['total'] = round(100 * (1 - idle_diff / total_diff), 1)
        
        # Calculate individual cores
        core_num = 0
        while f'cpu{core_num}' in cpu_lines1:
            core_name = f'cpu{core_num}'
            if core_name in cpu_lines2:
                idle_diff = cpu_lines2[core_name]['idle'] - cpu_lines1[core_name]['idle']
                total_diff = cpu_lines2[core_name]['total'] - cpu_lines1[core_name]['total']
                if total_diff > 0:
                    core_percent = round(100 * (1 - idle_diff / total_diff), 1)
                    stats['cores'].append(core_percent)
                else:
                    stats['cores'].append(0)
            core_num += 1
            
    except Exception as e:
        print(f"CPU stats error: {e}")
    
    return stats

def get_system_stats():
    stats = {"cpu_percent": 0, "cpu_cores": [], "ram_percent": 0, "temperature": 0}
    
    # CPU usage - total and individual cores
    cpu_stats = get_cpu_stats()
    stats['cpu_percent'] = cpu_stats['total']
    stats['cpu_cores'] = cpu_stats['cores']
    
    # RAM usage
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            total = int(lines[0].split()[1])
            available = int(lines[2].split()[1])
            ram_used = total - available
            stats['ram_percent'] = round(100 * ram_used / total, 1) if total > 0 else 0
    except:
        pass
    
    # Temperature (Raspberry Pi specific)
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_milli = int(f.read().strip())
            stats['temperature'] = round(temp_milli / 1000.0, 1)
    except:
        pass
    
    return stats

@app.route('/')
def index():
    config = load_config()
    rtsp_url = get_rtsp_url(config)
    running = is_stream_running()
    stats = get_system_stats()
    current_ip = get_lan_ip()
    return render_template('index.html', config=config, rtsp_url=rtsp_url, running=running, stats=stats, current_ip=current_ip)

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

@app.route('/api/config', methods=['POST'])
def update_config():
    config = load_config()
    new_config = request.json
    
    for field in ['bitrate', 'framerate', 'width', 'height', 'intra', 'av_sync', 'rtsp_port', 'nice']:
        if field in new_config:
            config[field] = int(new_config[field])
    
    for field in ['sharpness', 'contrast', 'brightness', 'saturation']:
        if field in new_config:
            config[field] = float(new_config[field])
    
    for field in ['denoise', 'codec', 'libav_format', 'profile', 'hdr', 'level', 'awb', 'rtsp_host', 'rtsp_path']:
        if field in new_config:
            config[field] = new_config[field]
    
    save_config(config)
    return jsonify({"status": "ok", "config": config})

@app.route('/api/stream/start', methods=['POST'])
def start_stream():
    try:
        subprocess.run(['systemctl', 'start', 'pi_camera_stream'], check=True)
        return jsonify({"status": "started"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/stream/stop', methods=['POST'])
def stop_stream_endpoint():
    try:
        subprocess.run(['systemctl', 'stop', 'pi_camera_stream'], check=True)
        return jsonify({"status": "stopped"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/stream/restart', methods=['POST'])
def restart_stream():
    try:
        subprocess.run(['systemctl', 'restart', 'pi_camera_stream'], check=True)
        return jsonify({"status": "restarted"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/stream/status', methods=['GET'])
def stream_status():
    return jsonify({"running": is_stream_running()})

@app.route('/api/system/reboot', methods=['POST'])
def reboot_system():
    def do_reboot():
        time.sleep(2)
        subprocess.run(['reboot'])
    
    threading.Thread(target=do_reboot).start()
    return jsonify({"status": "rebooting", "message": "System wird in 2 Sekunden neu gestartet"})

@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    return jsonify(get_system_stats())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
