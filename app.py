from flask import Flask, request, Response
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import xml.dom.minidom
from urllib.parse import urlparse
import urllib3

# --- DISABLE SSL WARNINGS ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- CONFIGURATION ---
ALLOWED_DOMAINS = [
    "api.toonamiaftermath.com",  # Added your specific domain
    "toonamiaftermath.com"
]

def is_url_allowed(url):
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if not hostname: return False
        for allowed in ALLOWED_DOMAINS:
            if hostname == allowed or hostname.endswith("." + allowed):
                return True
        return False
    except Exception:
        return False

# --- Conversion Logic ---
def parse_iso_date(date_str):
    try:
        return datetime.strptime(date_str.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        try:
            return datetime.strptime(date_str.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
             return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")

def format_xmltv_date(dt_obj):
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

def generate_channel_id(name):
    clean_name = "".join(c for c in name if c.isalnum())
    return f"{clean_name}.us"

def json_to_xmltv(json_data):
    tv = ET.Element("tv", {
        "generator-info-name": "JSON to XMLTV Web Converter",
        "generator-info-url": "https://your-domain.com"
    })

    # The JSON structure seems to be a list of channels
    for channel_obj in json_data:
        channel_name = channel_obj.get("name", "Unknown Channel")
        channel_id = generate_channel_id(channel_name)

        chan_elem = ET.SubElement(tv, "channel", {"id": channel_id})
        ET.SubElement(chan_elem, "display-name").text = channel_name

        media_list = channel_obj.get("media", [])
        
        for i, media in enumerate(media_list):
            try:
                start_dt = parse_iso_date(media["startDate"])
                
                if i + 1 < len(media_list):
                    next_media = media_list[i+1]
                    stop_dt = parse_iso_date(next_media["startDate"])
                else:
                    stop_dt = start_dt + timedelta(minutes=30)

                prog_elem = ET.SubElement(tv, "programme", {
                    "start": format_xmltv_date(start_dt),
                    "stop": format_xmltv_date(stop_dt),
                    "channel": channel_id
                })

                info = media.get("info", {})
                title_text = info.get("fullname", media.get("name"))
                ET.SubElement(prog_elem, "title").text = title_text

                episode_title = info.get("episode")
                if episode_title:
                    ET.SubElement(prog_elem, "sub-title").text = episode_title
            
            except Exception:
                continue

    return ET.tostring(tv, encoding='utf-8')

# --- API Endpoint ---
@app.route('/translate')
def translate():
    source_url = request.args.get('url')

    if not source_url:
        return Response("Error: Missing 'url' parameter.", status=400)

    if not is_url_allowed(source_url):
        return Response(f"Error: Domain not allowed. Please verify '{source_url}' is in the whitelist.", status=403)

    try:
        # verify=False bypasses the SSL error
        response = requests.get(source_url, timeout=10, verify=False)
        response.raise_for_status()
        
        json_data = response.json()
        raw_xml = json_to_xmltv(json_data)
        
        parsed_xml = xml.dom.minidom.parseString(raw_xml)
        pretty_xml = parsed_xml.toprettyxml(indent="  ")

        return Response(pretty_xml, mimetype='text/xml')

    except requests.exceptions.RequestException as e:
        return Response(f"Error fetching JSON source: {e}", status=500)
    except Exception as e:
        return Response(f"Error converting data: {e}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
