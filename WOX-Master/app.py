from flask import Flask, jsonify, request, render_template_string
import time

app = Flask(__name__)
AGENTS = {}
START = time.time()
HTML='''<html><body style="background:#0f172a;color:white;font-family:Arial;padding:20px"><h1>WOX Master</h1><p>Nodes: {{count}}</p>{% for k,v in agents.items() %}<div style="margin:10px;padding:10px;background:#1e293b;border-radius:10px"><b>{{k}}</b><br>Status: online<br>Last Seen: {{v['ts']}}</div>{% endfor %}</body></html>'''
@app.route('/')
def home():
    return render_template_string(HTML,count=len(AGENTS),agents=AGENTS)
@app.route('/api/health')
def health():
    return jsonify({'ok':True,'role':'master','uptime':int(time.time()-START)})
@app.route('/api/agents/heartbeat',methods=['POST'])
def hb():
    data=request.get_json(force=True,silent=True) or {}
    name=data.get('node_name','unknown')
    AGENTS[name]={'data':data,'ts':int(time.time())}
    return jsonify({'ok':True,'registered':name})
@app.route('/api/agents')
def agents():
    return jsonify({'ok':True,'agents':AGENTS})
if __name__=='__main__':
    app.run(host='0.0.0.0',port=8000)
