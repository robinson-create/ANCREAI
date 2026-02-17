#!/usr/bin/env bash
# Démarre l'API FastAPI et le frontend Vite pour le dev.
# Garder ce terminal ouvert. Ctrl+C pour tout arrêter.

set -e
cd "$(dirname "$0")"

echo "▶ Démarrage de l'API (port 8000) et du frontend (port 3000)..."
echo ""

# Activer le venv si présent
if [ -d .venv ]; then
  source .venv/bin/activate
fi

# Arrêter les enfants à la sortie
cleanup() {
  echo ""
  echo "▶ Arrêt des serveurs..."
  kill $API_PID $FRONT_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

# Lancer l'API en arrière-plan
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# Laisser l'API démarrer
sleep 2

# Lancer le frontend en arrière-plan
(cd frontend && npm run dev) &
FRONT_PID=$!

echo "  API:      http://localhost:8000  (docs: http://localhost:8000/docs)"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Appuyez sur Ctrl+C pour tout arrêter."
echo ""

wait
