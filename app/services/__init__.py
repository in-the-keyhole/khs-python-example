"""
Services — the data-access layer the views (routers) depend on.

Two shapes live here, by design:

  - `items` exposes a *stateful singleton* (`ItemStore`) — it owns the
    in-memory data, so it has to be one long-lived instance.
  - `orders` is a set of *stateless functions* that each take a request-scoped
    DB `Session` — there's no state to hold, so there's no class.

Both are reached from the routers through FastAPI's `Depends(...)` seam, never
imported and called ad hoc. Business logic (when there is any) lives one layer
up in `app.controllers`; services only touch storage.
"""
