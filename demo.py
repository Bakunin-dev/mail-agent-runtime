"""Executable walkthrough of real presentation code and simulated engines."""
import argparse
import json
import sys

from server.actions import ActionRequest
from server.app import Session
from server.mail_query.models import MailQuerySpecV2, MailReadRequest, MailSearchRequest
from server.mail_query.portal_projection import format_read_text, format_search_text


def run(scenario="tour", approve=False):
    session = Session(connected=True)
    owner = "alice"
    print("MAIL AGENT / SHOWCASE EDITION — synthetic data, no LLM, no external actions")
    if scenario in {"mail", "tour", "limits"}:
        result = session.query.search(owner, MailSearchRequest(query=MailQuerySpecV2(), page_size=5))
        print("\n1. Metadata search — original DTOs, simplified exact matcher")
        print(format_search_text(result))
        print("Body fetches after search:", session.mail.fetch_count)
        preview = session.query.read(owner, MailReadRequest(result_set_id=result.result_set_id,
            refs=[row.ref for row in result.items], detail="preview"))
        print("\n2. Selected preview — original bounded projection")
        print(format_read_text(preview, handle_by_ref={row.ref: f"m{i}" for i, row in enumerate(result.items, 1)}))
        page = session.query.search(owner, MailSearchRequest(result_set_id=result.result_set_id,
            cursor=result.next_cursor, page_size=2))
        print("\n3. Existing snapshot, next page")
        print(format_search_text(page, cursor=5))
        full = session.query.read(owner, MailReadRequest(result_set_id=result.result_set_id,
            refs=[result.items[0].ref], detail="full"))
        print("4. Full prepared body:", len(full.items[0].body), "characters; coverage:", full.coverage)
    if scenario in {"proactive", "tour"}:
        print("\n5. Synthetic delivery event -> deterministic agent policy -> CRM + reply proposals")
        event = session.agent.receive(owner, "arrival-001")
        print(" -> ".join(event["trace"]))
        for proposal in event["proposals"]:
            print(proposal["kind"], proposal["status"], proposal["payload"])
        print("Before review: outbox =", len(session.mail.outbox), "CRM tasks =", len(session.crm.tasks))
        if approve:
            for proposal in event["proposals"]:
                result = session.actions.decide(owner, proposal["id"], True)
                print("Explicit demo approval:", result["kind"], result["status"])
                session.actions.decide(owner, proposal["id"], True)
            print("After repeated approvals: outbox =", len(session.mail.outbox), "CRM tasks =", len(session.crm.tasks))
        print("Repeated delivery deduplicated:", session.agent.receive(owner, "arrival-001")["duplicate"])
    print("\nSIMULATED: matching, storage, transports, CRM, proactive policy.")
    print("REAL: selected original contracts, body/text projection and progress renderer.")


def interactive():
    session = Session(connected=True)
    while True:
        print("\n1 Search/read  2 Receive synthetic email  3 Review actions  4 State  0 Exit")
        choice = input("> ").strip()
        if choice == "0":
            return
        if choice == "1":
            result = session.query.search("alice", MailSearchRequest(query=MailQuerySpecV2(), page_size=5))
            print(format_search_text(result))
            selected = input("Read handle m1..m5 (Enter to skip): ").strip()
            if selected in [f"m{i}" for i in range(1, len(result.items) + 1)]:
                ref = result.items[int(selected[1:]) - 1].ref
                read = session.query.read("alice", MailReadRequest(result_set_id=result.result_set_id, refs=[ref]))
                print(format_read_text(read, handle_by_ref={ref: selected}))
        elif choice == "2":
            key = f"arrival-{len(session.agent.events) + 1}"
            print(json.dumps(session.agent.receive("alice", key), default=str, indent=2, ensure_ascii=False))
        elif choice == "3":
            for action_id in list(session.actions.records):
                item = session.actions.view("alice", action_id)
                if item["status"] in {"pending", "failed"}:
                    print(item["kind"], item["payload"])
                    answer = input("Simulate this action? [y=approve / n=reject / Enter=skip]: ").strip().lower()
                    if answer in {"y", "n"}:
                        print(session.actions.decide("alice", action_id, answer == "y")["status"])
        elif choice == "4":
            print("Outbox:", session.mail.outbox, "CRM:", session.crm.tasks)


if __name__ == "__main__":
    # Redirected Windows output may default to cp1252, which cannot encode mail text.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["tour", "mail", "limits", "proactive"], default="tour")
    parser.add_argument("--approve-demo", action="store_true", help="explicitly approve synthetic proposals")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    if args.interactive:
        interactive()
    else:
        run(args.scenario, args.approve_demo)
