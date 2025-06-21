# arquivo: gerar_sessao.py

from telethon.sync import TelegramClient

api_id = 20418970
api_hash = '7f743090fb2971a1bbbe42c507672501'

with TelegramClient('consultav2', api_id, api_hash) as client:
    print("Sessão criada com sucesso!")
