from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import random

app = FastAPI()

class RoomManager:
    def __init__(self):
        self.rooms: dict = {} # {room_id: {"connections": [], "queue": [], "state": {}}}

    def get_initial_state(self):
        return {
            "p1": {"nome": None, "pts": 0, "st": 100, "pos": "Em pé", "sid": None},
            "p2": {"nome": None, "pts": 0, "st": 100, "pos": "Em pé", "sid": None},
            "logs": ["Tatame pronto. Entrem na fila!"],
            "turno_de": 0,
            "vitoria": False
        }

    async def connect(self, websocket: WebSocket, room_id: str, name: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {"connections": [], "queue": [], "state": self.get_initial_state()}
        
        sid = str(id(websocket))
        conn_data = {"ws": websocket, "name": name, "sid": sid}
        self.rooms[room_id]["connections"].append(conn_data)
        
        # Se não houver lutadores, ocupa o posto. Se não, vai para a fila.
        state = self.rooms[room_id]["state"]
        if not state["p1"]["sid"]:
            state["p1"].update({"nome": name, "sid": sid})
        elif not state["p2"]["sid"]:
            state["p2"].update({"nome": name, "sid": sid})
        else:
            self.rooms[room_id]["queue"].append(conn_data)
        
        return sid

    async def broadcast(self, room_id: str):
        room = self.rooms[room_id]
        data = {
            "state": room["state"],
            "queue": [p["name"] for p in room["queue"]],
            "spectators": len(room["connections"]) - (2 if room["state"]["p2"]["sid"] else 1)
        }
        for conn in room["connections"]:
            await conn["ws"].send_text(json.dumps(data))

    async def next_match(self, room_id: str, loser_sid: str):
        room = self.rooms[room_id]
        state = room["state"]
        
        # Reset de pontos e stamina para a nova luta
        state["p1"]["pts"] = state["p2"]["pts"] = 0
        state["p1"]["st"] = state["p2"]["st"] = 100
        state["p1"]["pos"] = state["p2"]["pos"] = "Em pé"
        state["vitoria"] = False
        
        # Se o perdedor for P1, ele vai para o fim da fila e o P2 espera o próximo
        # Se houver gente na fila, o próximo entra no lugar do perdedor
        if room["queue"]:
            next_p = room["queue"].pop(0)
            if state["p1"]["sid"] == loser_sid:
                # Adiciona quem perdeu ao fim da fila
                old_p = next(c for c in room["connections"] if c["sid"] == loser_sid)
                room["queue"].append(old_p)
                state["p1"].update({"nome": next_p["name"], "sid": next_p["sid"]})
            else:
                old_p = next(c for c in room["connections"] if c["sid"] == loser_sid)
                room["queue"].append(old_p)
                state["p2"].update({"nome": next_p["name"], "sid": next_p["sid"]})
            
            state["logs"] = [f"NOVA LUTA: {state['p1']['nome']} vs {state['p2']['nome']}"]

manager = RoomManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px 20px; }
                input { background: #111; border: 1px solid #0f0; color: #0f0; padding: 12px; width: 80%; margin: 10px; font-family: monospace; }
                button { background: #0f0; border: none; padding: 15px; font-weight: bold; width: 85%; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>OSS ARENA 🥋</h1>
            <form onsubmit="event.preventDefault(); window.location.href='/luta/'+document.getElementById('sala').value+'?nome='+document.getElementById('nome').value;">
                <input type="text" id="nome" placeholder="SEU NOME" required><br>
                <input type="text" id="sala" placeholder="CÓDIGO DA ARENA" required><br>
                <button type="submit">ENTRAR NA ARENA</button>
            </form>
        </body>
    </html>
    """

@app.get("/luta/{room_id}", response_class=HTMLResponse)
async def arena(room_id: str, nome: str):
    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ background: #111; color: #eee; font-family: monospace; text-align: center; padding: 10px; }}
                .arena-info {{ background: #222; padding: 5px; font-size: 0.8em; margin-bottom: 5px; color: #888; }}
                .scoreboard {{ display: flex; justify-content: space-around; background: #000; padding: 10px; border: 2px solid #0f0; }}
                .btn {{ background: #222; color: #0f0; border: 1px solid #0f0; padding: 12px; width: 100%; display: none; margin: 5px 0; font-weight: bold; }}
                .queue-box {{ background: #1a1a1a; padding: 10px; margin-top: 10px; border: 1px dashed #444; font-size: 0.8em; text-align: left; }}
                .log-box {{ background: #000; height: 100px; font-size: 0.7em; text-align: left; padding: 10px; margin: 10px 0; overflow: hidden; }}
            </style>
        </head>
        <body>
            <div class="arena-info">ARENA: {room_id} | ESPECTADORES: <span id="spec-count">0</span></div>
            <div class="scoreboard">
                <div id="p1-ui"><b id="p1-name">-</b><br><span id="p1-pts">0</span></div>
                <div style="color:#555">X</div>
                <div id="p2-ui"><b id="p2-name">-</b><br><span id="p2-pts">0</span></div>
            </div>
            
            <div id="status" style="margin: 10px; font-weight: bold;">CONECTANDO...</div>
            <div class="log-box" id="logs"></div>

            <div id="controles">
                <button onclick="enviar('queda')" class="btn" id="btn-queda">QUEDA (+2)</button>
                <button onclick="enviar('passar')" class="btn" id="btn-passar">PASSAR (+3)</button>
                <button onclick="enviar('finalizar')" class="btn" id="btn-finalizar" style="color:#f0f;">FINALIZAR</button>
                <button onclick="enviar('proxima')" class="btn" id="btn-proxima" style="background:#0f0; color:#000; display:none;">PRÓXIMA LUTA</button>
            </div>

            <div class="queue-box"><b>FILA DE DESAFIANTES:</b><br><span id="queue-list">Vazia</span></div>

            <script>
                const nome = "{nome}";
                let mySid = "";
                let socket = new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws/{room_id}/"+nome);

                socket.onmessage = function(e) {{
                    const data = JSON.parse(e.data);
                    const state = data.state;
                    if(!mySid) mySid = data.state.current_sid_check; // Ajustado no server

                    document.getElementById('p1-name').innerText = state.p1.nome || "---";
                    document.getElementById('p2-name').innerText = state.p2.nome || "---";
                    document.getElementById('p1-pts').innerText = state.p1.pts;
                    document.getElementById('p2-pts').innerText = state.p2.pts;
                    document.getElementById('spec-count').innerText = data.spectators;
                    document.getElementById('queue-list').innerText = data.queue.join(", ") || "Vazia";
                    document.getElementById('logs').innerHTML = state.logs.slice(-4).reverse().map(l=>"<p>• "+l+"</p>").join("");

                    const isP1 = (state.p1.sid === mySid);
                    const isP2 = (state.p2.sid === mySid);
                    const meuTurno = (state.turno_de === 0 && isP1) || (state.turno_de === 1 && isP2);

                    document.querySelectorAll('.btn').forEach(b=>b.style.display='none');
                    
                    if(state.vitoria) {{
                        document.getElementById('status').innerText = "FIM DE LUTA";
                        if(isP1 || isP2) document.getElementById('btn-proxima').style.display='block';
                    }} else if(isP1 || isP2) {{
                        document.getElementById('status').innerText = meuTurno ? "SEU ATAQUE!" : "AGUARDE...";
                        if(meuTurno) {{
                            document.getElementById('btn-queda').style.display='block';
                            document.getElementById('btn-passar').style.display='block';
                            document.getElementById('btn-finalizar').style.display='block';
                        }}
                    }} else {{
                        document.getElementById('status').innerText = "ASSISTINDO ARQUIBANCADA";
                    }}
                }};
                function enviar(a){{ socket.send(a); }}
            </script>
        </body>
    </html>
    """

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    sid = await manager.connect(websocket, room_id, player_name)
    await manager.broadcast(room_id)
    
    room = manager.rooms[room_id]
    state = room["state"]

    try:
        while True:
            data = await websocket.receive_text()
            
            # Ação de Próxima Luta (chama a fila)
            if data == "proxima" and state["vitoria"]:
                # Descobre quem perdeu
                loser_sid = state["p2"]["sid"] if state["vencedor"] == state["p1"]["nome"] else state["p1"]["sid"]
                await manager.next_match(room_id, loser_sid)
                await manager.broadcast(room_id)
                continue

            # Lógica de combate (apenas se for o turno do lutador)
            p_idx = state["turno_de"]
            current_p_sid = state["p1"]["sid"] if p_idx == 0 else state["p2"]["sid"]
            
            if sid == current_p_sid and not state["vitoria"]:
                p_atk = state["p1"] if p_idx == 0 else state["p2"]
                p_def = state["p2"] if p_idx == 0 else state["p1"]
                dado = random.randint(1, 6)
                
                if data == "queda":
                    if dado >= 3: p_atk["pts"] += 2; msg = f"{p_atk['nome']} pontuou!"
                    else: msg = f"{p_def['nome']} defendeu!"
                elif data == "finalizar":
                    if dado == 6: 
                        state["vitoria"] = True; state["vencedor"] = p_atk["nome"]
                        msg = f"🔥 {p_atk['nome']} FINALIZOU!"
                    else: msg = f"Tentativa falha de {p_atk['nome']}"
                
                state["logs"].append(msg)
                state["turno_de"] = 1 - p_idx
                await manager.broadcast(room_id)
                
    except WebSocketDisconnect:
        manager.rooms[room_id]["connections"] = [c for c in room["connections"] if c["sid"] != sid]
        await manager.broadcast(room_id)
