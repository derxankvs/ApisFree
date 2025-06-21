#!/data/data/com.termux/files/usr/bin/bash

echo "🔄 Iniciando servidor FastAPI com Uvicorn..."
uvicorn api:app --host 0.0.0.0 --port 8000 &

sleep 3

echo "🚀 Iniciando túnel Ngrok..."
ngrok http 8000 > /dev/null &

sleep 3

echo "🌐 Aguardando link público do Ngrok..."
sleep 5

# Extrair o link público do ngrok via API local
link=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o 'https://[a-zA-Z0-9.-]*\.ngrok\.io' | head -n 1)

if [ -n "$link" ]; then
    echo "✅ Sua API está online em:"
    echo "$link"
else
    echo "❌ Não foi possível obter o link do ngrok. Verifique se ele iniciou corretamente."
fi
