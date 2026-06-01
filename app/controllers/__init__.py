"""
Controllers — the business-logic / use-case layer.

Intentionally empty for now. Today's endpoints are thin CRUD: the views
(`app/routers`) validate input and call straight into the persistence services
(`app/services`), so there's no business logic to hold yet.

When a use case appears that *isn't* just persistence — orchestrating several
services, enforcing a domain rule, computing a derived result — it lands here,
as stateless functions to match the services (e.g. `controllers/orders.py` with
`place_order(session, ...)` that checks inventory, writes the order, and emits
an event). The dependency direction stays one-way:

    views (routers)  ->  controllers  ->  services  ->  database
                         models are static data passed across all layers
"""
