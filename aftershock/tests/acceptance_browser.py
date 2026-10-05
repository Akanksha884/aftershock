from playwright.sync_api import sync_playwright
B="http://localhost:8080/app/"
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); errs=[]
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto(B); pg.get_by_role("button",name="Start an Incident").first.click()
    pg.get_by_label("Password").fill("x-pass-1"); pg.get_by_role("button",name="Sign in").click()
    pg.get_by_role("button",name="New incident").click()
    pg.get_by_label("Incident description").fill("My phone was stolen yesterday while I was travelling. I am worried about my accounts, banking apps and SIM.")
    pg.get_by_role("button",name="Analyze Incident").click()
    pg.get_by_text("ACTION REQUIRES YOUR APPROVAL").first.wait_for(timeout=15000); print("S9 approval card shown")
    for n in ["SIM","FINANCE","INSURANCE"]: assert pg.get_by_label(f"{n}: ",exact=False).count()>=1
    print("S7 graph nodes ok")
    pg.get_by_role("heading",name="Block your SIM card").wait_for()
    pg.get_by_role("button",name="Approve Action").first.click()
    pg.get_by_text("COMPLETED (simulated)").wait_for(timeout=8000); print("S10 approved->completed")
    pg.reload(); pg.get_by_role("button",name="Dashboard").click()
    assert pg.get_by_text("PHONE STOLEN").count()>=1; print("S16/17 persists after refresh")
    pg.get_by_role("button",name="Documents").click()
    pg.get_by_label("Upload document").set_input_files({"name":"p.txt","mimeType":"text/plain","buffer":b"Policy number: AB-12345"})
    pg.get_by_text("p.txt").wait_for(); print("S18 doc persisted")
    pg.get_by_role("button",name="Assets").click(); pg.get_by_label("Asset name").fill("MacBook Pro"); pg.get_by_role("button",name="Add",exact=True).click()
    pg.get_by_text("MacBook Pro").wait_for(); print("S19 asset persisted")
    pg.get_by_role("button",name="Settings").click(); pg.get_by_text("Human approval required").wait_for(); print("S20 settings ok")
    pg.get_by_role("button",name="Dashboard").click(); pg.get_by_text("PHONE STOLEN").first.click()
    pg.get_by_role("button",name="Reject").first.click(); pg.get_by_text("Rejected").first.wait_for(timeout=8000); print("S15 reject+replan")
    print("page errors:",errs); b.close()
