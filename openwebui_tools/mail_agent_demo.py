"""SIMULATED Tool bridge for a portal running on the same host as the demo.

Import this file as an OpenWebUI Workspace Tool after starting the demo API.
All calls target loopback. Approval and delivery controls are deliberately not
exposed as model tools. OpenWebUI integration is optional, not required to run.
"""
import json

import httpx


class Tools:
    async def _post(self, path, payload, emitter=None):
        async def emit(description, done):
            if emitter:
                try:
                    await emitter({"type": "status", "data": {"description": description, "done": done}})
                except Exception:
                    pass  # UI transport is best-effort; never affects the mail result.
        await emit("Synthetic Mail Agent: working", False)
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8765", trust_env=False, timeout=10) as client:
                response = await client.post(path, json=payload)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPError, ValueError):
            return "Demo API unavailable or request rejected; start the loopback server and connect alice in /docs."
        finally:
            await emit("Synthetic Mail Agent: finished", True)

    async def mail_search(self, query_json: str, __event_emitter__=None) -> str:
        """Search synthetic metadata: pass JSON {query:{},page_size:5} or page an existing set."""
        try:
            payload = json.loads(query_json)
        except ValueError:
            return "Invalid JSON request"
        return await self._post("/portal/tools/mail/search", payload, __event_emitter__)

    async def mail_read(self, result_set_id: str, handles: list[str], detail: str = "preview", __event_emitter__=None) -> str:
        """Read synthetic handles m1, m2 using the original compact text projection."""
        return await self._post("/portal/tools/mail/read", {
            "result_set_id": result_set_id, "handles": handles, "detail": detail}, __event_emitter__)

    async def propose_action(self, proposal_json: str, __event_emitter__=None) -> str:
        """Propose a simulated mail/CRM action for a human to review; never executes it."""
        try:
            payload = json.loads(proposal_json)
        except ValueError:
            return "Invalid JSON proposal"
        return await self._post("/tools/actions/propose", payload, __event_emitter__)
