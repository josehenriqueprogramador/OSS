from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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
            "turnos_restantes": 10,
            "vitoria": False,
            "vencedor": None
        }

    async def connect(self, websocket: WebSocket, room_id: str, name: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {"connections": [], "queue": [], "state": self.get_initial_state()}
        
        sid = str(id(websocket))
        state = self.rooms[room_id]["state"]

        # Limpeza de clones
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
            try: await conn["ws"].send_text(json.dumps(data))
            except: pass

manager = ArenaManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px 20px; }
            input { background: #111; border: 1px solid #0f0; color: #0f0; padding: 15px; width: 85%; margin: 10px; font-size: 1.1em; }
            button { background: #0f0; border: none; padding: 20px; font-weight: bold; width: 90%; cursor: pointer; font-size: 1.2em; }
        </style></head>
        <body>
            <h1>OSS ARENA 🥋</h1>
            <input type="text" id="nome" placeholder="SEU NOME"><br>
            <input type="text" id="sala" placeholder="NÚMERO DA SALA"><br>
            <button onclick="entrar()">ENTRAR NO TATAME</button>
            <script>
                function entrar() {
                    const n = document.getElementById('nome').value;
                    const s = document.getElementById('sala').value;
                    if(n && s) location.href = `/luta/${s}?nome=${encodeURIComponent(n)}`;
                }
            </script>
        </body>
    </html>
    """

@app.get("/luta/{room_id}", response_class=HTMLResponse)
async def arena_page(room_id: str, nome: str):
    return f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #111; color: #eee; font-family: monospace; text-align: center; padding: 10px; margin: 0; }}
            .scoreboard {{ display: flex; justify-content: space-around; background: #000; padding: 15px; border-bottom: 2px solid #0f0; }}
            .btn {{ background: #222; color: #0f0; border: 1px solid #0f0; padding: 20px; width: 100%; display: none; margin: 8px 0; font-weight: bold; font-size: 1.1em; }}
            .log-box {{ background: #000; height: 120px; font-size: 0.8em; text-align: left; padding: 10px; border-left: 3px solid #0f0; overflow: hidden; }}
        </style></head>
        <body>
            <div style="font-size:0.8em; padding:10px;">SALA: {room_id} | MOVIMENTOS: <span id="m-count">10</span></div>
            <div class="scoreboard">
                <div><b id="n1">...</b><br><span id="p1" style="font-size:2em">0</span></div>
                <div style="align-self:center; color:#444">X</div>
                <div><b id="n2">...</b><br><span id="p2" style="font-size:2em">0</span></div>
            </div>
            <div id="status" style="font-weight:bold; color:#0f0; padding:15px; background:#222;">CONECTANDO...</div>
            <div class="log-box" id="logs"></div>
            <div id="controles" style="padding:10px;">
                <button id="btn-queda" onclick="enviar('queda')" class="btn">QUEDA (+2)</button>
                <button id="btn-passar" onclick="enviar('passar')" class="btn">PASSAR/RASPAR (+3)</button>
                <button id="btn-finalizar" onclick="enviar('finalizar')" class="btn" style="color:#f0f; border-color:#f0f;">FINALIZAR</button>
                <button id="btn-reset" onclick="enviar('reset')" class="btn" style="background:#0f0; color:#000;">NOVA LUTA</button>
            </div>
            <a href="/" style="color:#666; font-size:0.9em;">SAIR DA ARENA</a>

            <script>
                let mySid = null;
                // Lógica de Reconexão e Protocolo Seguro (WSS)
                const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
                const socket = new WebSocket(protocol + location.host + "/ws/{room_id}/{nome}");

                socket.onmessage = function(e) {{
                    const data = JSON.parse(e.data);
                    const state = data.state;
                    if(!mySid) mySid = data.your_sid;

                    document.getElementById('n1').innerText = state.p1.nome || "---";
                    document.getElementById('n2').innerText = state.p2.nome || "---";
                    document.getElementById('p1').innerText = state.p1.pts;
                    document.getElementById('p2').innerText = state.p2.pts;
                    document.getElementById('m-count').innerText = state.turnos_restantes;
                    document.getElementById('logs').innerHTML = state.logs.slice(-4).reverse().map(l=>`<p style="margin:4px 0; border-bottom:1px solid #111;">• ${{l}}</p>`).join("");

                    const isP1 = state.p1.sid === mySid;
                    const isP2 = state.p2.sid === mySid;
                    const meuTurno = (state.turno_de === 0 && isP1) || (state.turno_de === 1 && isP2);

                    document.querySelectorAll('.btn').forEach(b => b.style.display = 'none');

                    if (state.vitoria) {{
                        document.getElementById('status').innerText = "FIM: " + (state.vencedor || "EMPATE");
                        if(isP1 || isP2) document.getElementById('btn-reset').style.display = 'block';
                    }} else if (isP1 || isP2) {{
                        document.getElementById('status').innerText = meuTurno ? "SUA VEZ DE ATACAR!" : "DEFENDA!";
                        document.getElementById('status').style.background = meuTurno ? "#040" : "#400";
                        if(meuTurno) {{
                            document.getElementById('btn-finalizar').style.display = 'block';
                            if(isP1 ? state.p1.pos === "Em pé" : state.p2.pos === "Em pé") document.getElementById('btn-queda').style.display = 'block';
                            else document.getElementById('btn-passar').style.display = 'block';
                        }}
                    }} else {{
                        document.getElementById('status').innerText = "ASSISTINDO DA ARQUIBANCADA";
                    }}
                }};
                function enviar(a) {{ if(socket.readyState === 1) socket.send(a); }}
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

            if data == "reset" and state["vitoria"]:
                p1_old, p2_old = state["p1"], state["p2"]
                room["state"] = manager.get_initial_state()
                room["state"]["p1"].update({"nome": p1_old["nome"], "sid": p1_old["sid"]})
                room["state"]["p2"].update({"nome": p2_old["nome"], "sid": p2_old["sid"]})
                await manager.broadcast(room_id)
                continue

            p_idx = state["turno_de"]
            if sid == (state["p1"]["sid"] if p_idx == 0 else state["p2"]["sid"]) and not state["vitoria"]:
                p_atk, p_def = (state["p1"], state["p2"]) if p_idx == 0 else (state["p2"], state["p1"])
                dado = random.randint(1, 6)
                msg = ""

                if data == "queda":
                    if dado >= 3: p_atk["pts"] += 2; p_atk["pos"] = p_def["pos"] = "Chão"; msg = f"{p_atk['nome']} quedou!"
                    else: msg = f"{p_def['nome']} defendeu a queda."
                elif data == "passar":
                    if dado >= 4: p_atk["pts"] += 3; msg = f"{p_atk['nome']} progrediu no chão!"
                    else: msg = f"{p_def['nome']} travou a progressão."
                elif data == "finalizar":
                    if dado >= 5: state["vitoria"] = True; state["vencedor"] = p_atk["nome"]; msg = f"🔥 {p_atk['nome']} FINALIZOU!"
                    else: p_atk["pos"] = p_def["pos"] = "Em pé"; msg = "Perdeu a posição! Luta em pé."

                state["logs"].append(msg)
                state["turnos_restantes"] -= 1
                
                if state["turnos_restantes"] <= 0 and not state["vitoria"]:
                    state["vitoria"] = True
                    p1, p2 = state["p1"], state["p2"]
                    state["vencedor"] = p1["nome"] if p1["pts"] > p2["pts"] else p2["nome"] if p2["pts"] > p1["pts"] else "Empate"
                    state["logs"].append("⏰ ACABOU O TEMPO!")

                state["turno_de"] = 1 - p_idx
                await manager.broadcast(room_id)
    except Exception:
        room = manager.rooms[room_id]
        room["connections"] = [c for c in room["connections"] if c["sid"] != sid]
        if room["state"]["p1"]["sid"] == sid: room["state"]["p1"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}
        if room["state"]["p2"]["sid"] == sid: room["state"]["p2"] = {"nome": None, "pts": 0, "pos": "Em pé", "sid": None}
        await manager.broadcast(room_id)
