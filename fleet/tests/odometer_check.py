"""What happens when the operator types the odometer and presses Enter - and after it.

The real app against the mock FleetCard site (see app_harness). After a card has been
swiped and the rego is back, the odometer is typed and Enter pressed, exactly as at the
till. Then everything the confirm sets off is checked, in the browser the operator sees,
in the window, and in what would be written to the database:

    odo_submit           the odometer lands in the form and the check box is ticked
    re_enter_products    nothing to re-categorise, so it passes
    get_exp_month_year   the card's expiry is read off the form
    form_submit          the 2nd Submit is clicked, the receipt page comes up, the PDF
                         link is read (the download itself needs the real site)
    then                 'Processed!', the window hides itself, the card screen is
                         rebuilt for the next customer, one record per line goes to Mongo

A second sale follows straight away, because that is where anything left over from the
first one shows up. A third has the database gone away: the sale is done at FleetCard by
then, so it must still finish, with the failure in the log rather than a dead thread.

    fleet\\.venv\\Scripts\\python.exe tests\\odometer_check.py
    set SCENARIO=timeout && ...           a transaction FleetCard does not accept
"""
import builtins
import json

from app_harness import (LINES, SCENARIO, SESSION_STEPS, app, buttons, check, check_form, entries,
                         notices, on_worker, run, state, status_text, swipe_card, wait_for_rego)
import fleet  # the module the app star-imports; its path_data is already pointed at fixtures

ODO = "123456"


def submit_button():
    found = [b for b in buttons() if b.cget("text") == "Submit"]
    return found[0] if found else None


# ---- the odometer step ------------------------------------------------------------------
def type_odometer_and_press_enter():
    print("\n--- odometer: type %s and press Enter ---" % ODO)
    odo = entries()[0]
    check("the caret is in the odometer box, so what is typed goes there",
          app.root.focus_lastfor() is odo, "caret on %s" % (app.root.focus_lastfor(),))
    check("Enter is bound to this screen's Submit, and the reader's Tab to nothing",
          bool(app.root.bind("<Return>")) and not app.root.bind("<Tab>"))
    check("Submit is enabled, because the rego came back", str(submit_button().cget("state")) == "normal")
    odo.insert(0, ODO)
    state.pop("outcome", None)  # this sale's, not the last one's
    state["inserts_before"] = len(app.db.inserts)
    state["processing_seen"] = False
    watch_for_processing()
    app.root.event_generate("<Return>", when="now")
    # Enter again while the first is in flight: odo_submit_command must ignore it, or the
    # sale would be sent twice. Seen later as exactly one record per line in the database.
    app.root.event_generate("<Return>", when="now")


def sale_over():
    return app.root.state() == "withdrawn" or "Error: timeout" in notices()


def watch_for_processing():
    """Look for the notice every 10 ms: against the mock site a whole sale can be over
    in a tenth of a second, before the next step gets its tick."""
    if any(str(t).startswith("processing") for t in notices()):
        state["processing_seen"] = True
    elif not sale_over():
        app.root.after(10, watch_for_processing)


def check_processing_notice():
    if not state["processing_seen"] and not sale_over():
        return True  # submit_task packs it first thing, from the worker thread
    check("a 'processing' notice appears under the form while the sale is sent",
          state["processing_seen"], "" if state["processing_seen"] else "the sale ended without it")


def wait_for_outcome():
    if app.root.state() == "withdrawn":
        state["outcome"] = "success"
        return
    if "Error: timeout" in notices():
        state["outcome"] = "error"
        return
    return True


# ---- after a successful confirm -----------------------------------------------------------
def check_after_confirmed():
    print("\n--- after the odometer is confirmed ---")
    check("the sale went through: the window hid itself for the POS to take over",
          state.get("outcome") == "success", "outcome %s, window %s" % (state.get("outcome"), app.root.state()))
    written = app.db.inserts[state["inserts_before"]:]
    check("one record per line went to the database, and one only (the second Enter was ignored)",
          len(written) == len(LINES), "%d records for %d lines" % (len(written), len(LINES)))
    for line, record in zip(LINES, written):
        check("  %s: card, category, amount, status, rego and expiry" % line["description"],
              record["card_number"] == state["card"] and record["fuel_type"] == line["description"]
              and record["price"] == line["subaftertax"] and record["type"] == "complete"
              and record["rego"].strip() == "MOCK123"
              and (record["exp_month"], record["exp_year"]) == ("12", "2027"),
              json.dumps({k: v for k, v in record.items() if k != "datetime"}, default=str))
    if written and written[0]["rego"] != written[0]["rego"].strip():
        print("  NOTE  the rego is written as %r - with the space that follows 'Rego is:'" % written[0]["rego"])
    pdfs = fleet.path_format(fleet.path_data["pdfDir"])
    print("  NOTE  the PDF receipt is fetched from the receipt link with requests; a file:// mock"
          " cannot serve it, so nothing landed in %s - that part needs the real site" % pdfs)
    on_worker("receipt", lambda d: {"url": d.current_url,
                                    "submitted": json.loads(d.execute_script("return window.submitted()"))})
    app.root.deiconify()  # the POS re-shows the window for the next sale


def check_what_was_submitted():
    if "receipt" not in state:
        return True
    receipt = state["receipt"]
    if "error" in receipt:
        check("the receipt page could be read back", False, receipt["error"].strip().splitlines()[-1])
        return
    print("--- what the form held when the 2nd Submit was clicked, from the receipt page ---")
    check("the browser is on the receipt page, with a transaction id in the URL",
          "uni_txn_id=MOCK-TXN-" in receipt["url"], receipt["url"])
    sent = receipt["submitted"]
    check("the odometer that was typed was in the form", sent["text"]["odometer"] == ODO, repr(sent["text"]["odometer"]))
    check("the check box was ticked (odo_submit ticks it again before submitting)", sent["ticked"] is True)
    check("the card, sales number and rego were still in the form",
          sent["text"]["cardNumber"] == state["card"] and sent["text"]["salesNumber"] == "0320330"
          and sent["text"]["Rego"] == "MOCK123",
          json.dumps(sent["text"]))
    check("every line was still in the form", len(sent["rows"]) == len(LINES), "%d rows" % len(sent["rows"]))


def check_card_screen_is_back():
    if len(entries()) != 1 or [b.cget("text") for b in buttons()] != ["Submit"]:
        return True  # redo_command rebuilds it on the Tk thread; the window was just re-shown
    print("--- the card screen, ready for the next customer ---")
    check("the card screen is back with one empty card box", entries()[0].get() == "")
    check("the caret is in the card box", app.root.focus_lastfor() is entries()[0],
          "caret on %s" % (app.root.focus_lastfor(),))
    check("the reader's trailing Tab submits again", bool(app.root.bind("<Tab>")))
    check("the odometer screen's 'processing' notice is gone", not notices(), str(notices()))


# ---- a second sale, straight after -------------------------------------------------------
def check_second_sale_writes_only_its_own_lines():
    print("\n--- the second sale's records ---")
    written = app.db.inserts[state["inserts_before"]:]
    check("the second sale wrote one record per line - and nothing left over from the first sale",
          len(written) == len(LINES),
          "%d records for %d lines; cards written: %s" % (
              len(written), len(LINES), sorted({r["card_number"] for r in written})))
    check("all of them carry the second card", all(r["card_number"] == state["card"] for r in written),
          str(sorted({r["card_number"] for r in written})))


# ---- a third sale, with the database gone away --------------------------------------------
def mark_database_down():
    print("\n--- a third sale, with the database gone away ---")
    app.db.down = True
    state["printed"] = []
    real_print = builtins.print

    def recording_print(*args, **kwargs):
        state["printed"].append(" ".join(str(a) for a in args))
        real_print(*args, **kwargs)

    builtins.print = recording_print


def check_after_database_down():
    print("\n--- after the odometer is confirmed with the database down ---")
    app.db.down = False
    check("the sale still went through: the window hid itself for the POS to take over",
          state.get("outcome") == "success", "outcome %s, window %s" % (state.get("outcome"), app.root.state()))
    check("nothing was written to the database", len(app.db.inserts) == state["inserts_before"],
          "%d records" % (len(app.db.inserts) - state["inserts_before"]))
    check("the log says the record could not be made, instead of the thread dying quietly",
          any(line.startswith("Could not record the sale in the database") for line in state["printed"]),
          "; ".join(line for line in state["printed"] if "database" in line)[:200])


# ---- a transaction FleetCard does not accept ----------------------------------------------
def check_after_timeout():
    """form_submit waits 20 s for the receipt page; this looks at the screen after 25 s."""
    if getattr(check_after_timeout, "tries", 0) < 250:
        return True
    print("\n--- 25 s after Enter, with FleetCard not accepting the transaction ---")
    print("  SEEN  window %s, status %r, notices %s, Submit %s" % (
        app.root.state(), status_text(), notices(),
        submit_button().cget("state") if submit_button() else "gone"))
    check("nothing was written to the database", len(app.db.inserts) == state["inserts_before"],
          "%d records" % (len(app.db.inserts) - state["inserts_before"]))
    check("the window is still up, on the odometer screen", app.root.state() != "withdrawn"
          and submit_button() is not None)
    check("Submit can be pressed again", str(submit_button().cget("state")) == "normal")
    check("the operator is told something went wrong",
          any("Error" in str(t) for t in notices()) or status_text().startswith("Err"),
          "notices %s, status %r" % (notices(), status_text()))


if SCENARIO == "timeout":
    run(SESSION_STEPS + [type_odometer_and_press_enter, check_processing_notice, check_after_timeout])
else:
    run(SESSION_STEPS + [
        type_odometer_and_press_enter, check_processing_notice, wait_for_outcome,
        check_after_confirmed, check_what_was_submitted, check_card_screen_is_back,
        swipe_card("70343059876543210"), wait_for_rego, check_form,
        type_odometer_and_press_enter, check_processing_notice, wait_for_outcome,
        check_after_confirmed, check_second_sale_writes_only_its_own_lines,
        mark_database_down, check_card_screen_is_back,
        swipe_card("70343051111222233"), wait_for_rego, check_form,
        type_odometer_and_press_enter, check_processing_notice, wait_for_outcome,
        check_after_database_down,
    ])
