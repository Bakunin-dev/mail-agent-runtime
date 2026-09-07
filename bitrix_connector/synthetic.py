"""SIMULATED / NEW: no REST methods, webhook URLs, tokens or Bitrix SDK.

The public port demonstrates a CRM lookup and task creation. It is not a
statement that production Bitrix24 integration has been implemented or tested.
"""
from typing import Protocol


class CrmPort(Protocol):
    def find_contact(self, email: str) -> dict | None: ...
    def create_task(self, title: str, contact_id: str) -> dict: ...


class SyntheticBitrix:
    def __init__(self):
        self.tasks: list[dict] = []
        self.fail_next = False

    def find_contact(self, email):
        if email.casefold() == "alex@north.example.test":
            return {"id": "contact-demo-1", "name": "Alex North", "company": "North Example",
                    "simulated": True}
        return None

    def create_task(self, title, contact_id):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("synthetic CRM failure before write")
        task = {"id": f"task-{len(self.tasks) + 1}", "title": title,
                "contact_id": contact_id, "status": "open", "simulated": True}
        self.tasks.append(task)
        return task.copy()
