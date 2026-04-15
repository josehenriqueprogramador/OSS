from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
import random

app = FastAPI()

# Gerenciador de Conexões e Salas
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {} # {sala_id: [websocket1, websocket2]}
        self.game_states: dict = {} # {sala_id: estado_do_jogo}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
            # Inicializa o estado da sala
            self.game_states[room_id] = {
                "p1": {"nome": "Aguardando...", "pontos": 0, "stamina": 100, "pos": "Em pé"},
                "p2": {"nome": "Aguardando...", "pontos": 0, "stamina": 100, "pos": "Em pé"},
                "logs": ["Tatame criado. Aguardando oponente..."],
                "turno_de": 0, # 0 para P1, 1 para P2
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

# --- ROTAS HTML ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px 20px; }
                input { background: #111; border: 1px solid #0f0; color: #0f0; padding: 12px; width: 80%; margin: 10px; }
                button { background: #0f0; border: none; padding: 15px; font-weight: bold; width: 85%; border-radius: 5px; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>OSS ONLINE 🥋</h1>
            <p>SISTEMA DE CAMPEONATO REMOTO</p>
            <form onsubmit="event.preventDefault(); window.location.href='/luta/'+document.getElementById('sala').value+'?nome='+document.getElementById('nome').value;">
                <input type="text" id="nome" placeholder="SEU NOME" required><br>
                <input type="text" id="sala" placeholder="ID DA SALA (EX: 123)" required><br>
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
                .scoreboard {{ display: flex; justify-content: space-around; background: #222; padding: 10px; border: 2px solid #0f0; }}
                .log-box {{ background: #000; height: 100px; overflow: hidden; font-size: 0.8em; text-align: left; padding: 10px; margin: 10px 0; border-left: 3px solid #0f0; }}
                .btn {{ background: #222; color: #0f0; border: 1px solid #0f0; padding: 15px; width: 100%; display: block; margin: 5px 0; text-decoration: none; font-weight: bold; }}
                .btn.disabled {{ color: #444; border-color: #444; pointer-events: none; }}
                .st-bar {{ background: #333; height: 8px; width: 100%; }}
                .st-fill {{ background: #0f0; height: 100%; transition: 0.5s; }}
            </style>
        </head>
        <body>
            <div id="game-ui">
                <h2 id="status-luta">CONECTANDO...</h2>
                <div class="scoreboard">
                    <div id="p1-ui"><b>-</b><br><span id="p1-pts">0</span><br><div class="st-bar"><div id="p1-st" class="st-fill"></div></div></div>
                    <div style="color:#666">VS</div>
                    <div id="p2-ui"><b>-</b><br><span id="p2-pts">0</span><br><div class="st-bar"><div id="p2-st" class="st-fill"></div></div></div>
                </div>
                <div class="log-box" id="logs"></div>
                <p id="pos-info">📍 -</p>
                <div id="controles">
                    <button onclick="enviar('queda')" class="btn" id="btn-queda">QUEDA (+2)</button>
                    <button onclick="enviar('passar')" class="btn" id="btn-passar">PASSAR (+3)</button>
                    <button onclick="enviar('finalizar')" class="btn" id="btn-finalizar" style="color:#f0f; border-color:#f0f;">FINALIZAR</button>
                </div>
            </div>

            <script>
                const roomId = "{room_id}";
                const meuNome = "{nome}";
                let socket = new WebSocket((window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws/" + roomId + "/" + meuNome);
                let meuIndex = -1;

                socket.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    atualizarUI(data);
                }};

                function atualizarUI(data) {{
                    document.getElementById('p1-ui').querySelector('b').innerText = data.p1.nome;
                    document.getElementById('p2-ui').querySelector('b').innerText = data.p2.nome;
                    document.getElementById('p1-pts').innerText = data.p1.pontos;
                    document.getElementById('p2-pts').innerText = data.p2.pontos;
                    document.getElementById('p1-st').style.width = data.p1.stamina + "%";
                    document.getElementById('p2-st').style.width = data.p2.stamina + "%";
                    
                    if (meuIndex === -1) meuIndex = (data.p1.nome === meuNome) ? 0 : 1;
                    
                    const meuTurno = (data.turno_de === meuIndex);
                    document.getElementById('status-luta').innerText = meuTurno ? "SEU TURNO" : "TURNO DO ADVERSÁRIO";
                    document.getElementById('status-luta').style.color = meuTurno ? "#0f0" : "#f00";
                    
                    document.querySelectorAll('.btn').forEach(b => {{
                        b.classList.toggle('disabled', !meuTurno || data.vitoria);
                    }});

                    document.getElementById('logs').innerHTML = data.logs.slice(-4).map(l => "<p>• "+l+"</p>").join("");
                    document.getElementById('pos-info').innerText = "📍 " + (meuIndex === 0 ? data.p1.pos : data.p2.pos);
                    
                    if(data.vitoria) document.getElementById('status-luta').innerText = "FIM DE LUTA";
                }}

                function enviar(acao) {{
                    socket.send(acao);
                }}
            </script>
        </body>
    </html>
    """

# --- LOGICA DE WEBSOCKET ---

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    success = await manager.connect(websocket, room_id)
    if not success:
        await websocket.close()
        return

    state = manager.game_states[room_id]
    
    # Atribui nome ao slot vazio
    if state["p1"]["nome"] == "Aguardando...":
        state["p1"]["nome"] = player_name
    elif state["p2"]["nome"] == "Aguardando..." and state["p1"]["nome"] != player_name:
        state["p2"]["nome"] = player_name
    
    await manager.broadcast(room_id)

    try:
        while True:
            data = await websocket.receive_text() # Recebe a ação (queda, passar, etc)
            
            # Processa a luta
            p_idx = state["turno_de"]
            p_ataque = state["p1"] if p_idx == 0 else state["p2"]
            p_defesa = state["p2"] if p_idx == 0 else state["p1"]
            
            dado = random.randint(1, 6)
            msg = ""

            if data == "queda":
                if dado >= 4:
                    p_ataque["pontos"] += 2
                    p_ataque["pos"], p_defesa["pos"] = "Por cima", "Por baixo"
                    msg = f"{p_ataque['nome']} derrubou!"
                else:
                    msg = f"{p_defesa['nome']} defendeu a queda."
            
            elif data == "passar":
                if dado >= 5:
                    p_ataque["pontos"] += 3
                    msg = f"{p_ataque['nome']} passou a guarda!"
                else:
                    msg = f"A guarda de {p_defesa['nome']} segue impenetrável."

            elif data == "finalizar":
                if dado == 6:
                    state["vitoria"] = True
                    msg = f"OSS! {p_ataque['nome']} FINALIZOU A LUTA!"
                else:
                    msg = f"{p_ataque['nome']} tentou o bote e perdeu a posição!"
                    p_ataque["pos"], p_defesa["pos"] = "Em pé", "Em pé"

            p_ataque["stamina"] = max(0, p_ataque["stamina"] - 15)
            state["logs"].append(msg)
            state["turno_de"] = 1 - p_idx # Alterna turno
            
            await manager.broadcast(room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        state["logs"].append(f"{player_name} saiu do tatame.")
        await manager.broadcast(room_id)
