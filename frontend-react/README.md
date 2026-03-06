# Frontend React (Vite)

## Libraries
From `package.json`:
- `react`
- `react-dom`
- `react-router-dom`
- `vite` (dev/build tool)

## Environment
Frontend reads root `.env` via `vite.config.js` (`envDir: ".."`).

Required keys:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ENABLE_MOCK_AUTH_FALLBACK=false
```

## Run
```bash
cd "/Users/kayra/Developer/DESD Group Project/frontend-react"
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:
- `http://127.0.0.1:5173`

## Build Check
```bash
npm run build
```

## Backend Dependency
Backend must be running at:
- `http://127.0.0.1:8000`
