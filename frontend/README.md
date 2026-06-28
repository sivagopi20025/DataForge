# DataForge UI

Phase 1 Next.js frontend for DataForge.

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` if the FastAPI backend is not running on `http://127.0.0.1:8010`.

If the UI appears as unstyled raw HTML/blue links, stop the dev server and clear
the Next.js cache:

```bash
npm run dev:clean -- --hostname 127.0.0.1 --port 3000
```

This can happen when `npm run build` is executed while a dev server is still
running.
