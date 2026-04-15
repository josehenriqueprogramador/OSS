from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import random

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {} 
        self.game_states: dict = {} 

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
            self.game_states[room_id] = {
                "p1": {"nome": "Aguardando...", "pontos": 0, "stamina": 100, "pos": "Em pé"},
                "p2": {"nome": "Aguardando...", "pontos": 0, "stamina": 100, "pos": "Em pé"},
                "logs": ["Tatame liberado. Oss!"],
                "turno_de": 0,
                "vitoria": False
            }
        
        if len(self.active_connections[room_id]) < 2:
            self.active_connections[room_id].append(websocket)
            return True
        return False

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, room_id: str):
        if room_id in self.active_connections:
            state = json.dumps(self.game_states[room_id])
            for connection in self.active_connections[room_id]:
                await connection.send_text(state)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px 20px; }
                input { background: #111; border: 1px solid #0f0; color: #0f0; padding: 12px; width: 80%; margin: 10px; font-family: monospace; }
                button { background: #0f0; border: none; padding: 15px; font-weight: bold; width: 85%; border-radius: 5px; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>OSS ONLINE 🥋</h1>
            <p>SISTEMA DE CAMPEONATO</p>
            <form onsubmit="event.preventDefault(); window.location.href='/luta/'+document.getElementById('sala').value+'?nome='+document.getElementById('nome').value;">
                <input type="text" id="nome" placeholder="NOME DO LUTADOR" required><br>
                <input type="text" id="sala" placeholder="ID DA SALA (EX: 10)" required><br>
                <button type="submit">ENTRAR NO TATAME</button>
            </form>
        </body>
    </html>
    """

@app.get("/luta/{room_id}", response_class=HTMLResponse)
async def game_page(room_id: str, nome: str):
    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ background: #111; color: #eee; font-family: monospace; text-align: center; margin: 0; padding: 10px; }}
                .scoreboard {{ display: flex; justify-content: space-around; background: #222; padding: 10px; border: 2px solid #0f0; border-radius: 8px; }}
                .log-box {{ background: #000; height: 120px; font-size: 0.75em; text-align: left; padding: 10px; margin: 10px 0; border-left: 3px solid #0f0; overflow-y: hidden; }}
                .btn {{ background: #222; color: #0f0; border: 1px solid #0f0; padding: 14px; width: 100%; display: none; margin: 5px 0; font-weight: bold; border-radius: 5px; }}
                .st-bar {{ background: #333; height: 8px; width: 100%; border-radius: 4px; margin-top: 5px; }}
                .st-fill {{ background: #0f0; height: 100%; transition: 0.5s; }}
                #status-luta {{ font-size: 1.2em; margin: 10px 0; text-transform: uppercase; }}
            </style>
        </head>
        <body>
            <div id="game-ui">
                <h2 id="status-luta">CONECTANDO...</h2>
                <div class="scoreboard">
                    <div id="p1-ui"><b>-</b><br><span style="font-size:1.5em" id="p1-pts">0</span><div class="st-bar"><div id="p1-st" class="st-fill"></div></div></div>
                    <div style="align-self: center; color: #555;">VS</div>
                    <div id="p2-ui"><b>-</b><br><span style="font-size:1.5em" id="p2-pts">0</span><div class="st-bar"><div id="p2-st" class="st-fill"></div></div></div>
                </div>
                <div class="log-box" id="logs"></div>
                <p id="pos-info" style="color:#0f0">📍 POSIÇÃO: -</p>
                
                <div id="controles">
                    <button onclick="enviar('queda')" class="btn" id="btn-queda">QUEDA (+2)</button>
                    <button onclick="enviar('passar')" class="btn" id="btn-passar">PASSAR GUARDA (+3)</button>
                    <button onclick="enviar('raspar')" class="btn" id="btn-raspar">RASPAGEM (+2)</button>
                    <button onclick="enviar('costas')" class="btn" id="btn-costas">PEGAR COSTAS (+4)</button>
                    <button onclick="enviar('montar')" class="btn" id="btn-montar">MONTAR (+4)</button>
                    <button onclick="enviar('finalizar')" class="btn" id="btn-finalizar" style="color:#f0f; border-color:#f0f;">FINALIZAR</button>
                </div>
            </div>

            <script>
                const roomId = "{room_id}";
                const meuNome = "{nome}";
                let protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
                let socket = new WebSocket(protocol + window.location.host + "/ws/" + roomId + "/" + meuNome);
                let meuIndex = -1;

                socket.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    if (meuIndex === -1) meuIndex = (data.p1.nome === meuNome) ? 0 : 1;
                    atualizarUI(data);
                }};

                function atualizarUI(data) {{
                    document.getElementById('p1-ui').querySelector('b').innerText = data.p1.nome;
                    document.getElementById('p2-ui').querySelector('b').innerText = data.p2.nome;
                    document.getElementById('p1-pts').innerText = data.p1.pontos;
                    document.getElementById('p2-pts').innerText = data.p2.pontos;
                    document.getElementById('p1-st').style.width = data.p1.stamina + "%";
                    document.getElementById('p2-st').style.width = data.p2.stamina + "%";
                    
                    const meuTurno = (data.turno_de === meuIndex);
                    const minhaPos = meuIndex === 0 ? data.p1.pos : data.p2.pos;
                    
                    document.getElementById('status-luta').innerText = data.vitoria ? "FIM DE LUTA" : (meuTurno ? "SEU ATAQUE" : "DEFENDENDO...");
                    document.getElementById('status-luta').style.color = meuTurno ? "#0f0" : "#f66";
                    document.getElementById('pos-info').innerText = "📍 ESTADO: " + minhaPos;
                    document.getElementById('logs').innerHTML = data.logs.slice(-4).reverse().map(l => "<p style='margin:5px 0; border-bottom:1px solid #222;'>• "+l+"</p>").join("");

                    // LÓGICA DE BOTÕES DINÂMICOS
                    document.querySelectorAll('.btn').forEach(b => b.style.display = 'none');
                    if (meuTurno && !data.vitoria) {{
                        if (minhaPos === "Em pé") {{
                            document.getElementById('btn-queda').style.display = 'block';
                            document.getElementById('btn-finalizar').style.display = 'block';
                        }} else if (minhaPos === "Por baixo") {{
                            document.getElementById('btn-raspar').style.display = 'block';
                            document.getElementById('btn-finalizar').style.display = 'block';
                        }} else if (minhaPos === "Por cima") {{
                            document.getElementById('btn-passar').style.display = 'block';
                            document.getElementById('btn-costas').style.display = 'block';
                            document.getElementById('btn-finalizar').style.display = 'block';
                        }} else if (minhaPos === "Dominando") {{
                            document.getElementById('btn-montar').style.display = 'block';
                            document.getElementById('btn-finalizar').style.display = 'block';
                        }}
                    }}
                }}

                function enviar(acao) {{ socket.send(acao); }}
            </script>
        </body>
    </html>
    """

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    success = await manager.connect(websocket, room_id)
    if not success:
        await websocket.close()
        return

    state = manager.game_states[room_id]
    if state["p1"]["nome"] == "Aguardando...": state["p1"]["nome"] = player_name
    elif state["p2"]["nome"] == "Aguardando..." and state["p1"]["nome"] != player_name: state["p2"]["nome"] = player_name
    
    await manager.broadcast(room_id)

    try:
        while True:
            data = await websocket.receive_text()
            p_idx = state["turno_de"]
            p_atk = state["p1"] if p_idx == 0 else state["p2"]
            p_def = state["p2"] if p_idx == 0 else state["p1"]
            dado = random.randint(1, 6)
            msg = ""

            if data == "queda":
                if dado >= 3:
                    p_atk["pontos"] += 2
                    p_atk["pos"], p_def["pos"] = "Por cima", "Por baixo"
                    msg = f"{p_atk['nome']} derrubou com estilo!"
                else: msg = f"{p_def['nome']} defendeu a queda."

            elif data == "raspar":
                if dado >= 4:
                    p_atk["pontos"] += 2
                    p_atk["pos"], p_def["pos"] = "Por cima", "Por baixo"
                    msg = f"{p_atk['nome']} raspou e inverteu!"
                else: msg = f"{p_def['nome']} pesou o quadril e evitou a raspagem."

            elif data == "passar":
                if dado >= 4:
                    p_atk["pontos"] += 3
                    p_atk["pos"] = "Dominando"
                    msg = f"{p_atk['nome']} passou a guarda!"
                else: msg = f"{p_def['nome']} repôs a guarda."

            elif data == "costas" or data == "montar":
                if dado >= 5:
                    p_atk["pontos"] += 4
                    msg = f"{p_atk['nome']} conquistou os 4 pontos!"
                else: msg = f"{p_def['nome']} escapou do domínio."

            elif data == "finalizar":
                chance = 6 if p_atk["pos"] == "Em pé" else 5
                if dado >= chance:
                    state["vitoria"] = True
                    msg = f"🔥 OSS! {p_atk['nome']} FINALIZOU A LUTA!"
                else:
                    p_atk["pos"], p_def["pos"] = "Em pé", "Em pé"
                    msg = f"{p_atk['nome']} perdeu o ajuste e a luta voltou em pé."

            p_atk["stamina"] = max(0, p_atk["stamina"] - 12)
            state["logs"].append(msg)
            state["turno_de"] = 1 - p_idx
            await manager.broadcast(room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
