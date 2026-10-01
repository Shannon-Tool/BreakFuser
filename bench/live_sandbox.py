"""Disposable loopback-only targets for authorized black-box evaluation."""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def create_sandbox() -> FastAPI:
    app = FastAPI(title="BreakFuser authorized test sandbox")
    database = sqlite3.connect(":memory:", check_same_thread=False)
    database.execute("CREATE TABLE users (username TEXT, password TEXT)")
    database.execute("INSERT INTO users VALUES ('admin', 'admin123')")

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/login")
    async def login(request: Request) -> JSONResponse:
        payload = await request.json()
        username = str(payload.get("username", ""))
        password = str(payload.get("password", ""))
        query = f"SELECT username FROM users WHERE username='{username}' AND password='{password}'"  # noqa: S608 - intentional local sandbox vulnerability
        row = database.execute(query).fetchone()
        if row:
            return JSONResponse({"authenticated": True, "user": row[0]})
        return JSONResponse(status_code=401, content={"authenticated": False})

    @app.get("/users/{user_id}/records/{record_id}")
    async def record(user_id: int, record_id: int) -> JSONResponse:
        return JSONResponse(
            {
                "id": record_id,
                "owner": 2,
                "requested_by": user_id,
                "content": "synthetic-record",
            }
        )

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_sandbox(), host="127.0.0.1", port=8091, log_level="warning")


if __name__ == "__main__":
    main()
