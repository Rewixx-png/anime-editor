#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== Anime Editor Worker — Termux Setup ==="

pkg update -y
pkg install -y python ffmpeg git

pip install --upgrade pip
pip install httpx python-dotenv pydantic yt-dlp

PROJ_DIR="$HOME/anime-editor"
if [ ! -d "$PROJ_DIR" ]; then
    mkdir -p "$PROJ_DIR"
    echo "Created $PROJ_DIR"
fi

mkdir -p "$PROJ_DIR/data/worker" "$PROJ_DIR/data/results"

if [ ! -f "$PROJ_DIR/.env" ]; then
    cp "$PROJ_DIR/.env.example" "$PROJ_DIR/.env" 2>/dev/null || cat > "$PROJ_DIR/.env" << 'EOF'
TELEGRAM_TOKEN=your_bot_token
WORKER_API_KEY=your_api_key
VPS_API_URL=http://YOUR_VPS_IP:8080
EOF
    echo "Создан .env — заполни его!"
fi

echo ""
echo "=== Готово ==="
echo "Заполни $PROJ_DIR/.env и запусти:"
echo "  cd $PROJ_DIR && python -m worker.main"
