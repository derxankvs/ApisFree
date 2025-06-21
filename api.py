# 📦 Imports
import os
import json
import asyncio
import httpx
import re
import uuid
import hashlib

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telethon import TelegramClient
from telethon.events import NewMessage

# 🔧 Carregar variáveis de ambiente
load_dotenv("config.env")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
API_LAYER_KEY = os.getenv("API_LAYER_KEY")

SESSION_V1 = "consultav2.session"
SESSION_V3 = "telegramv3.session"
GROUP_V1 = -1002821746685
GROUP_V3 = -1002821746685

client_v1 = TelegramClient(SESSION_V1, API_ID, API_HASH)
client_v3 = TelegramClient(SESSION_V3, API_ID, API_HASH)

# 🚀 Inicializar FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 📁 Banco de Dados
os.makedirs("db", exist_ok=True)

DB_PATH = "db/consultas.json"
if not os.path.exists(DB_PATH):
    with open(DB_PATH, "w") as f:
        json.dump([], f)

USUARIOS_PATH = "db/usuarios.json"
if not os.path.exists(USUARIOS_PATH):
    with open(USUARIOS_PATH, "w") as f:
        json.dump([], f)

# 📥 Funções de usuário
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_usuario(email, senha):
    try:
        with open(USUARIOS_PATH, "r") as f:
            usuarios = json.load(f)
    except:
        return False
    senha_hash = hash_senha(senha)
    return any(u["email"] == email and u["senha"] == senha_hash for u in usuarios)

def usuario_existe(email):
    try:
        with open(USUARIOS_PATH, "r") as f:
            usuarios = json.load(f)
        return any(u["email"] == email for u in usuarios)
    except:
        return False

def salvar_usuario(email, senha):
    try:
        with open(USUARIOS_PATH, "r") as f:
            usuarios = json.load(f)
    except:
        usuarios = []
    usuarios.append({"email": email, "senha": hash_senha(senha)})
    with open(USUARIOS_PATH, "w") as f:
        json.dump(usuarios, f, indent=2)

def salvar_consulta(ip, tipo, dado):
    try:
        with open(DB_PATH, "r") as f:
            dados = json.load(f)
    except:
        dados = []
    dados.append({"ip": ip, "tipo": tipo, "dado": dado})
    with open(DB_PATH, "w") as f:
        json.dump(dados, f, indent=2)

def limpar_resposta(texto):
    texto = re.sub(r'[^\w\s.,:;!?@/:\-_]', '', texto)
    texto = texto.replace("*", "").replace("_", "")
    texto = re.sub(r'@\w+', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

# 🌐 Autenticação Web
@app.get("/", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, email: str = Form(...), senha: str = Form(...)):
    if verificar_usuario(email, senha):
        response = RedirectResponse(url="/docs-api", status_code=302)
        response.set_cookie("user", email)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "erro": "Credenciais inválidas"})

@app.get("/cadastro", response_class=HTMLResponse)
async def cadastro_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/cadastro")
async def cadastro_post(request: Request, email: str = Form(...), senha: str = Form(...)):
    if usuario_existe(email):
        return templates.TemplateResponse("register.html", {"request": request, "erro": "Usuário já cadastrado"})
    salvar_usuario(email, senha)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/docs-api", response_class=HTMLResponse)
async def docs_api(request: Request):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("docs.html", {"request": request, "user": user})

# 🔐 Middleware de proteção
def autenticar(request: Request):
    return request.cookies.get("user") is not None

# 📡 API Interna
@app.get("/free/v1/{tipo}/{dado}")
async def consulta_v1(tipo: str, dado: str, request: Request):
    if not autenticar(request):
        return JSONResponse({"erro": "Acesso negado. Faça login."}, status_code=401)
    tipos = ["cnpj", "cep", "telefone", "ddd", "ip", "email", "whois"]
    if tipo in tipos:
        salvar_consulta(request.client.host, tipo, dado)
        return await enviar_para_telegram(client_v1, GROUP_V1, tipo, dado)
    return JSONResponse({"erro": "Tipo inválido"}, status_code=400)

@app.get("/free/v2/{tipo}/{dado}")
async def consulta_v2(tipo: str, dado: str, request: Request):
    if not autenticar(request):
        return JSONResponse({"erro": "Acesso negado. Faça login."}, status_code=401)
    tipos = ["cpf", "nome", "cnpj", "cep", "telefone", "ddd", "ip", "email", "rg", "whois"]
    if tipo in tipos:
        salvar_consulta(request.client.host, tipo, dado)
        return await enviar_para_telegram(client_v1, GROUP_V1, tipo, dado)
    return JSONResponse({"erro": "Tipo inválido"}, status_code=400)

# 📤 Envio para Telegram
async def enviar_para_telegram(client, group_id, tipo, dado):
    try:
        async with client:
            msg = await client.send_message(group_id, f"/{tipo} {dado}")
            resposta_final = None

            @client.on(NewMessage(chats=group_id))
            async def handler(event):
                nonlocal resposta_final
                texto = event.text.lower()
                if "aguarde" in texto or "carregando" in texto or "processando" in texto:
                    return
                if event.reply_to_msg_id == msg.id or dado in texto:
                    resposta_final = event.text

            for _ in range(20):
                if resposta_final:
                    break
                await asyncio.sleep(0.5)

            client.remove_event_handler(handler, NewMessage)

            if resposta_final:
                texto_limpo = limpar_resposta(resposta_final)
                return {
                    "tipo": tipo,
                    "dado": dado,
                    "resposta": texto_limpo,
                    "criador": "CenterApis - derxan.kvs",
                    "site": "https://centerseven7.netlify.app",
                    "telegram": "https://t.me/consultasblack01"
                }
            else:
                return JSONResponse({"erro": "Sem resposta final após aguardar"}, status_code=504)

    except Exception as e:
        return JSONResponse({"erro": f"Erro ao enviar consulta: {str(e)}"}, status_code=500)

# 🌍 API Externa
@app.get("/free/{tipo}/{valor}")
async def externo(tipo: str, valor: str, request: Request):
    if not autenticar(request):
        return JSONResponse({"erro": "Acesso negado. Faça login."}, status_code=401)
    salvar_consulta(request.client.host, tipo, valor)
    try:
        if tipo == "whois":
            url = f"https://api.apilayer.com/whois/query?domain={valor}"
            headers = {"apikey": API_LAYER_KEY}
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers)
                data = res.json()
        elif tipo == "ddd":
            url = f"https://brasilapi.com.br/api/ddd/v1/{valor}"
            async with httpx.AsyncClient() as client:
                res = await client.get(url)
                data = res.json()
        else:
            return JSONResponse({"erro": "Tipo externo inválido"}, status_code=400)

        return {
            "criador": "CenterApis - derxan.kvs",
            "site": "https://centerseven7.netlify.app",
            "resultado": data
        }

    except Exception as e:
        return JSONResponse({"erro": f"Erro externo: {str(e)}"}, status_code=500)