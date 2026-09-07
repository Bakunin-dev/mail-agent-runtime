"""Loopback API for a synthetic showcase; no credentials or live adapters."""
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict

from bitrix_connector.synthetic import SyntheticBitrix
from mail_connector.synthetic import SyntheticMailbox
from server.actions import ActionRequest, Actions, Decision
from server.errors import DemoError
from server.integrations.mail_progress import MailProgress, render_mail_progress
from server.mail_query.models import MailReadRequest, MailSearchRequest, MailSearchResult, MailReadResult
from server.mail_query.portal_projection import MailPortalReadRequest, format_read_text, format_search_text, handle_to_position
from server.mail_query.service import QueryService
from server.proactive import DeliveryEvent, ProactiveAgent


@dataclass
class Session:
    mail: SyntheticMailbox = field(default_factory=SyntheticMailbox)
    crm: SyntheticBitrix = field(default_factory=SyntheticBitrix)
    connected: bool = False

    def __post_init__(self):
        self.query = QueryService(self.mail)
        self.actions = Actions(self.query, self.mail, self.crm)
        self.agent = ProactiveAgent(self.query, self.mail, self.actions)


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["connected", "cancelled", "rejected"] = "connected"


class Fault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["fetch_failure", "clear", "expire_sets", "generation_change", "crm_failure", "candidate_limit"]


def create_app():
    app = FastAPI(title="Mail Agent · Showcase Edition", version="0.1.0",
                  description="REAL contracts/projections + SIMULATED engines. All data is synthetic. "
                  "Bitrix24 and proactive actions are new demo extensions, not production claims.")
    sessions = {name: Session() for name in ("alice", "bob")}
    lock = Lock()
    app.state.sessions = sessions
    app.state.lock = lock

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Showcase-Mode"] = "synthetic-only"
        return response

    @app.exception_handler(DemoError)
    async def error(request: Request, exc: DemoError):
        return JSONResponse(status_code=exc.status, content={"error": exc.code,
            "request_id": request.state.request_id, "simulated": True})

    def context(x_demo_session: Annotated[Literal["alice", "bob"], Header()] = "alice"):
        if not lock.acquire(blocking=False):
            raise DemoError("capacity_busy", 503)
        try:
            yield x_demo_session, sessions[x_demo_session]
        finally:
            lock.release()

    def connected(ctx=Depends(context)):
        if not ctx[1].connected:
            raise DemoError("demo_mailbox_not_connected", 409)
        return ctx

    @app.get("/health")
    def health():
        return {"status": "ready", "mode": "synthetic-only", "live_connectors": False,
                "authentication": "none; named demo sessions", "deletion": False}

    @app.post("/demo/connect")
    def connect(body: Connection, ctx=Depends(context)):
        ctx[1].connected = body.outcome == "connected"
        return {"status": body.outcome, "simulated": True, "session": ctx[0]}

    @app.post("/tools/mail/search", response_model=MailSearchResult)
    def search(body: MailSearchRequest, ctx=Depends(connected)):
        return ctx[1].query.search(ctx[0], body)

    @app.post("/tools/mail/read", response_model=MailReadResult)
    def read(body: MailReadRequest, ctx=Depends(connected)):
        return ctx[1].query.read(ctx[0], body)

    @app.post("/portal/tools/mail/search", response_class=PlainTextResponse)
    def portal_search(body: MailSearchRequest, ctx=Depends(connected)):
        return format_search_text(ctx[1].query.search(ctx[0], body), cursor=body.cursor)

    @app.post("/portal/tools/mail/read", response_class=PlainTextResponse)
    def portal_read(body: MailPortalReadRequest, ctx=Depends(connected)):
        snapshot = ctx[1].query.owned(ctx[0], body.result_set_id)
        positions = [handle_to_position(handle) for handle in body.handles]
        if any(position >= len(snapshot.items) for position in positions):
            raise DemoError("message_ref_not_found", 404)
        refs = [snapshot.items[position].ref for position in positions]
        result = ctx[1].query.read(ctx[0], MailReadRequest(result_set_id=body.result_set_id,
                                                        refs=refs, detail=body.detail))
        return format_read_text(result, handle_by_ref=dict(zip(refs, body.handles)))

    @app.post("/tools/actions/propose")
    def propose(body: ActionRequest, ctx=Depends(connected)):
        return ctx[1].actions.propose(ctx[0], body)

    @app.get("/tools/actions/{action_id}")
    def action_status(action_id: str, ctx=Depends(connected)):
        return ctx[1].actions.view(ctx[0], action_id)

    @app.post("/demo/actions/{action_id}/decision")
    def decision(action_id: str, body: Decision, ctx=Depends(connected)):
        return ctx[1].actions.decide(ctx[0], action_id, body.approve)

    @app.post("/demo/events/mail-received")
    def receive(body: DeliveryEvent, ctx=Depends(connected)):
        return ctx[1].agent.receive(ctx[0], body.event_key)

    @app.get("/tools/bitrix/contact")
    def contact(email: str = "alex@north.example.test", ctx=Depends(connected)):
        return {"contact": ctx[1].crm.find_contact(email), "simulated": True}

    @app.get("/demo/state")
    def state(ctx=Depends(connected)):
        session = ctx[1]
        return {"simulated": True, "outbox": session.mail.outbox, "drafts": session.mail.drafts,
                "tasks": session.crm.tasks, "folders": session.mail.folders,
                "fetch_count": session.mail.fetch_count,
                "actions": [session.actions.view(ctx[0], key) for key in session.actions.records]}

    @app.post("/demo/fault")
    def fault(body: Fault, ctx=Depends(connected)):
        from datetime import datetime, timezone
        session = ctx[1]
        if body.kind == "fetch_failure":
            session.mail.fail_fetch = True
        elif body.kind == "clear":
            session.mail.fail_fetch = False
            session.crm.fail_next = False
            session.query.scan_limit = 100
        elif body.kind == "expire_sets":
            for snapshot in session.query.sets.values():
                snapshot.expires = datetime(2000, 1, 1, tzinfo=timezone.utc)
        elif body.kind == "generation_change":
            session.mail.generation += 1
        elif body.kind == "crm_failure":
            session.crm.fail_next = True
        elif body.kind == "candidate_limit":
            session.query.scan_limit = 2
        return {"fault": body.kind, "simulated": True}

    @app.get("/demo/progress", response_class=HTMLResponse)
    def progress(ctx=Depends(connected)):
        return render_mail_progress(MailProgress(phase="Synthetic demo ready", progress=100,
            scanned=len(ctx[1].mail.messages), detail="Original presentation renderer; fixture metrics.", done=True))

    return app


app = create_app()
