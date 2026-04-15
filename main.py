from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
import json
import random

app = FastAPI()

class ArenaManager:
    def __init__(self):
        self.rooms: dict = {}

    def get_initial_state(self):
        return {
            "p1": {"nome": None, "pts": 0, "pos": "Em pé", "sid": None},
            "p2": {"nome": None, "pts": 0, "pos": "Em pé", "sid": None},
            "logs": ["Tatame pronto. Oss!"],
            "turno_de": 0,
            "vitoria": False,
            "vencedor": None
        }

    async def connect(self, websocket: WebSocket, room_id: str, name: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {"connections": [], "queue": [], "state": self.get_initial_state()}
        
        sid = str(id(websocket))
        state = self.rooms[room_id]["state"]

        # Se o mesmo nome entrar, removemos o registro anterior dele para evitar bugs
        if state["p1"]["nome"] == name: state["p1"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}
        if state["p2"]["nome"] == name: state["p2"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}

        conn_data = {"ws": websocket, "name": name, "sid": sid}
        self.rooms[room_id]["connections"].append(conn_data)
        
        if not state["p1"]["sid"]:
            state["p1"].update({"nome": name, "sid": sid})
        elif not state["p2"]["sid"]:
            state["p2"].update({"nome": name, "sid": sid})
        else:
            self.rooms[room_id]["queue"].append(conn_data)
        
        return sid

    async def broadcast(self, room_id: str):
        if room_id not in self.rooms: return
        room = self.rooms[room_id]
        data = {
            "state": room["state"],
            "queue": [p["name"] for p in room["queue"]],
            "spectators": len(room["connections"]) - (2 if room["state"]["p2"]["sid"] else 1 if room["state"]["p1"]["sid"] else 0)
        }
        for conn in room["connections"]:
            data["your_sid"] = conn["sid"]
            try:
                await conn["ws"].send_text(json.dumps(data))
            except: pass

manager = ArenaManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px 20px; }
            input { background: #111; border: 1px solid #0f0; color: #0f0; padding: 12px; width: 80%; margin: 10px; font-family: monospace; }
            button { background: #0f0; border: none; padding: 15px; font-weight: bold; width: 85%; border-radius: 5px; cursor: pointer; }
        </style></head>
        <body>
            <h1>OSS ARENA 🥋</h1>
            <form onsubmit="event.preventDefault(); window.location.href='/luta/'+document.getElementById('sala').value+'?nome='+document.getElementById('nome').value;">
                <input type="text" id="nome" placeholder="SEU NOME" required><br>
                <input type="text" id="sala" placeholder="CÓDIGO DA SALA" required><br>
                <button type="submit">ENTRAR NO TATAME</button>
            </form>
        </body>
    </html>
    """

@app.get("/luta/{room_id}", response_class=HTMLResponse)
async def arena_page(room_id: str, nome: str):
    return f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #111; color: #eee; font-family: monospace; text-align: center; padding: 10px; }}
            .scoreboard {{ display: flex; justify-content: space-around; background: #000; padding: 10px; border: 2px solid #0f0; margin-bottom: 10px; }}
            .btn {{ background: #222; color: #0f0; border: 1px solid #0f0; padding: 15px; width: 100%; display: none; margin: 5px 0; font-weight: bold; border-radius: 5px; }}
            .btn-exit {{ background: transparent; color: #f44; border: 1px solid #f44; padding: 5px 10px; font-size: 0.7em; margin-top: 20px; text-decoration: none; display: inline-block; }}
            .log-box {{ background: #000; height: 100px; font-size: 0.7em; text-align: left; padding: 10px; margin: 10px 0; border-left: 2px solid #0f0; overflow: hidden; }}
        </style></head>
        <body>
            <div style="font-size: 0.7em; color: #555;">SALA: {room_id} | <span id="specs">0</span> ASSISTINDO</div>
            <div class="scoreboard">
                <div><b id="n1">-</b><br><span id="p1" style="font-size:1.5em">0</span></div>
                <div style="align-self:center">VS</div>
                <div><b id="n2">-</b><br><span id="p2" style="font-size:1.5em">0</span></div>
            </div>

            <div id="status" style="font-weight:bold; color:#0f0; margin-bottom:10px;">CONECTANDO...</div>
            <div class="log-box" id="logs"></div>

            <div id="controles">
                <button id="btn-queda" onclick="enviar('queda')" class="btn">QUEDA (+2)</button>
                <button id="btn-passar" onclick="enviar('passar')" class="btn">PASSAR (+3)</button>
                <button id="btn-raspar" onclick="enviar('raspar')" class="btn">RASPAGEM (+2)</button>
                <button id="btn-finalizar" onclick="enviar('finalizar')" class="btn" style="color:#f0f; border-color:#f0f;">FINALIZAR</button>
            </div>

            <a href="/" class="btn-exit">ABANDONAR ARENA</a>

            <script>
                let mySid = null;
                const socket = new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws/{room_id}/{nome}");

                socket.onmessage = function(e) {{
                    const data = JSON.parse(e.data);
                    const state = data.state;
                    if(!mySid) mySid = data.your_sid;

                    document.getElementById('n1').innerText = state.p1.nome || "AGUARDANDO...";
                    document.getElementById('n2').innerText = state.p2.nome || "AGUARDANDO...";
                    document.getElementById('p1').innerText = state.p1.pts;
                    document.getElementById('p2').innerText = state.p2.pts;
                    document.getElementById('specs').innerText = data.spectators;
                    document.getElementById('logs').innerHTML = state.logs.slice(-4).reverse().map(l=>"<p>• "+l+"</p>").join("");

                    const isP1 = state.p1.sid === mySid;
                    const isP2 = state.p2.sid === mySid;
                    const meuTurno = (state.turno_de === 0 && isP1) || (state.turno_de === 1 && isP2);

                    document.querySelectorAll('.btn').forEach(b => b.style.display = 'none');

                    if (state.vitoria) {{
                        document.getElementById('status').innerText = "FIM DE LUTA: " + state.vencedor;
                    }} else if (isP1 || isP2) {{
                        document.getElementById('status').innerText = meuTurno ? "SUA VEZ!" : "AGUARDE...";
                        if(meuTurno) {{
                            document.getElementById('btn-finalizar').style.display = 'block';
                            if(isP1 ? state.p1.pos === "Em pé" : state.p2.pos === "Em pé") {{
                                document.getElementById('btn-queda').style.display = 'block';
                            }} else {{
                                document.getElementById('btn-passar').style.display = 'block';
                                document.getElementById('btn-raspar').style.display = 'block';
                            }}
                        }}
                    }} else {{
                        document.getElementById('status').innerText = "VOCÊ ESTÁ NA ARQUIBANCADA";
                    }}
                }};
                function enviar(a) {{ socket.send(a); }}
            </script>
        </body>
    </html>
    """

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    sid = await manager.connect(websocket, room_id, player_name)
    await manager.broadcast(room_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            room = manager.rooms[room_id]
            state = room["state"]
            p_idx = state["turno_de"]
            current_sid = state["p1"]["sid"] if p_idx == 0 else state["p2"]["sid"]
            
            if sid == current_sid and not state["vitoria"]:
                p_atk = state["p1"] if p_idx == 0 else state["p2"]
                p_def = state["p2"] if p_idx == 0 else state["p1"]
                dado = random.randint(1, 6)
                msg = ""
                
                if data == "queda":
                    if dado >= 3: 
                        p_atk["pts"] += 2; p_atk["pos"], p_def["pos"] = "Chão", "Chão"; msg = f"{p_atk['nome']} derrubou!"
                    else: msg = f"{p_def['nome']} defendeu a queda."
                elif data == "passar" or data == "raspar":
                    if dado >= 4: p_atk["pts"] += 2; msg = f"{p_atk['nome']} progrediu!"
                    else: msg = f"{p_def['nome']} travou a luta."
                elif data == "finalizar":
                    if dado >= 5: state["vitoria"] = True; state["vencedor"] = p_atk["nome"]; msg = f"🔥 {p_atk['nome']} FINALIZOU!"
                    else: p_atk["pos"] = p_def["pos"] = "Em pé"; msg = f"Finalização falhou! Luta volta em pé."

                state["logs"].append(msg)
                state["turno_de"] = 1 - p_idx
                await manager.broadcast(room_id)

    except WebSocketDisconnect:
        room = manager.rooms[room_id]
        room["connections"] = [c for c in room["connections"] if c["sid"] != sid]
        state = room["state"]
        # Se o lutador desconectar, liberamos o slot dele
        if state["p1"]["sid"] == sid: state["p1"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}
        if state["p2"]["sid"] == sid: state["p2"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}
        await manager.broadcast(room_id)
