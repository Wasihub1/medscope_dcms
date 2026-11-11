# DCMS Final Scope and Module Logic Specification (V1)
**Date:** Oct 30, 2026 | **Context:** Web-based Diagnostic Center Management System (DCMS) for medium centers in BD. Living document; source of truth for Claude Code schema/UI.

## 0. Principles & Workflow
* **Core:** Linked chain (patient->visit->bill->test->sample->result->report->stock->commission->ledger).
* **Rules:** Money is append-only. Catch anomalies (log them), don't block them. Offline support via queue. Owner sees all; staff sees limited. Text: Bangla/English support (SMS English only).
* **Process:** Quote rule numbers (D15, 3.3-4) in commits/tests. Update this doc for any changes.

## 1. Scope Status
* **Inputs:** 68 Board Decisions (D#) > Chat decisions > Checklist comments (M#).
* **Modules 1-26:** Defined. **Modules 27-31:** Provisional (pending Part B).

## 2. Items to Confirm (Defaults Applied)
| # | Topic | Default Applied |
|---|---|---|
| 1 | Part B missing | Provisional specs used (Sec 9). Replace when Part B arrives. |
| 2 | Offline scope (D64) | Search/Reg/Bill/Pay/Print/Sample/Offline Result Entry (for cached orders) allowed via Temp IDs. Day close/payouts/stock/approvals blocked till sync. |
| 3 | Doctor approval, no login (D22/D59)| Staff checks attestation box. Report prints Dr's name/reg. Logged. |
| 4 | Imaging lock timing (D13) | Cancel after start = wastage logged, needs admin/owner approval. |
| 5 | Owner unlock (D14) | Reopen locked line same day: Owner only + reason. Wastage kept, commission reverses, report Cancelled. |
| 6 | Refund after sample (D15) | *Not Performed* outcome only (admin/owner). Refunded, stock wasted, comm reversed. New sample = new bill. |
| 7 | Discount control (D3/M6.2) | Over-limit needs admin/owner override (logs to anomaly report). |
| 8 | Package mode (D4) | Configured as *Fixed Bundle* OR *Discount Rule* (counts as the 1 allowed bill discount). |
| 9 | Price list precedence (D5) | 1. Patient List -> 2. Referred-by List -> 3. General. |
| 10| Two referrers (D39) | Comm pool based on *Referred-by* rate. Split via owner % (up to 2 refs). |
| 11| Payables lacking vendor mod | Generic party ledger (accrued/paid/balance) for Dr/Ref/Lab. Cash expenses via simple entry. |
| 12| Sample time (D20/M10.1) | System time recorded on click. Report shows it ONLY if scanned/edited/confirmed. |
| 13| Result checks (D25/M13.4) | Impossible-value limits only (V1). Previous comparison deferred. |
| 14| Report flags (M13.1/13.2) | Auto-flags/critical alerts dropped (V1). Ref ranges print; manual flagging used. |
| 15| Vendor access (D60/61) | Read-only, logged, IDs masked, no export. Toggleable. |
| 16| Backups in V1 (D65) | DB-level auto-backup (hosting). No app-level drills. |
| 17| Language (D62) | SMS: English. UI/Reports/Names: Bangla + English. |
| 18| Unset numbers | Settings for limits/tolerances editable by owner. |
| 19| Advance payment | Dropped (D9). No overpay/credit. |
| 20| Amend vs Supp (D2) | Amend only if NO line locked. Once 1 lock exists -> Supplementary bill. |

## 3. Cross-Cutting Rules
* **3.1 Money:** Integer taka (no paisa). Bill discount rounded half-up, splits to lines pro-rata (largest-remainder). One discount type per bill (line OR bill level). Due is derived. Payments append-only; errors fixed via reversal (owner). Refunds via original channel (admin/owner).
* **3.2 Immutability:** Bill line freezes price/list/comm at billing (D36). Result freezes ref range. Audits/Ledgers/Stock append-only.
* **3.3 Locks & Cancellation:** Lock is per line. *Sample tests:* lock at `Sample taken`. *No-sample tests:* lock at `Completed` (D13). Stock deducted at lock (never restored). Post-lock, no cancel/refund (exceptions: item 4, 5, 6 above). Re-run needs new bill.
* **3.4 IDs:** Patient (perm), Visit (1/arrival), Bill (gapless via lock transaction), Sample (barcode), Report (new ID per correct).
* **3.5 Age/Identity:** Years/months/days based on visit date. Bangla/Eng names. Soft merge (D53).
* **3.6 Roles:** Multi-role supported (M1.1). SOD (Segregation of Duties) configurable; *Small Center Mode* clears SOD. Acting role logged.
* **3.7 Offline:** Fallback device logic. Cached IDs format: `T + DeviceCode + Counter`. Sync processes by device timestamp. Sync replaces Temp IDs with Permanent IDs. Day close blocks if unsynced items exist. Overrides need cached PIN. Offline results allowed only for orders physically on that device.
* **3.8 Audit:** Append-only (who, role, when, action, before, after). Cannot delete.

## 4. Modules 1-4 (Access, Dashboard, Patient, Referrer)
* **M1 Access:** PIN-switch (D58). Visiting Drs no login (name/reg only, D59). Vendor masked (D60).
* **M2 Dashboard:** Owner (finances, center view), Tech (worklist). Alerts (day open >24h, stock <0). 
* **M3 Patient:** Search mobile/name. Soft merge. After reports exist, demographic edit creates `Clerical Correction` report version.
* **M4 Referrers:** Ordered By + Referred By (max 2 for comm). Rates: fixed/%. Cap % per test. Name visible, money hidden (D41). Ledger tracks balance.

## 5. Modules 5-9 (Tests, Bill, Pay, Print)
* **M5 Catalog:** Ref ranges versioned by sex/age in days (D24). 4 report templates (D28). Approval rules per test (Tech/Dr/Both). Price lists auto-apply.
* **M6 Billing:** Confirm -> gapless ID. Dr. Fee = separate line (liability, no comm). Override discount -> anomaly report. Unlocked lines can be cancelled.
* **M7 Payment:** Exact matched Tx numbers. Allocates Dr Fee -> Tests. No advance/overpay (D9). Reversals (D10). Mobile matching manual + CSV.
* **M8 Numbers:** Gapless counter on confirm. Patient & Bill #s independent.
* **M9 Print:** Patient+Office (1 page), Owner (shows comm). Reprints logged. Offline shows Temp ID.

## 6. Modules 10-16 (Lab & Stock)
* **M10 Workflow:** Route to Tech/Dr. Real-time scanner OR 1-click `Sample taken` (locks line, starts lab clock).
* **M11 Tech List:** Worklist only. No money visible. Urgent/Late flags.
* **M12 In-Progress:** Barcodes print. Invalid sample -> `Not Performed` -> refund, new bill needed. 
* **M13 Results:** Impossible-value blocks. Flags typed manually. QR codes added. Signatures by approval rule.
* **M14 Finalize:** Draft (auto-save) -> Final (locks report, triggers SMS). 
* **M15 Corrections:** Clerical / Result. Needs Admin (+Dr if Dr-required test). Old version -> `Superseded`. Generates new ID (D26).
* **M16 Stock:** Deducted strictly at Lock (D30). May go negative (flags owner). Wastage needs reason/user. Batch table exists but deferred (V1).

## 7. Modules 17-20 (Handover, Dues, Comm, Payout)
* **M17 Handover:** Admin/Owner can "Hold" report if test unpaid. Logs who handed over.
* **M18 Dues:** Patient Due vs Dr Ledger (Liability vs Receivable). Write-offs to bad debt (D11).
* **M19 Comm:** Based on line price *before* discount. Accrues at billing. Dr Fee excluded. Line cancel = negative accrual. Owner only (D41).
* **M20 Payout:** Commission/fees payout reduces ledger balance. Dr fee refund allowed before handover.

## 8. Modules 21-26 (Accounting, Day Close, Audit, Reports)
* **M21 Acct:** Double-entry (Journal/Line). Cash book, Income/Exp. No fiscal year (date filters).
* **M22 Day Close:** 1 business day open at a time (D46). Expected Cash formula. Shortage -> Variance entry. Closed days locked (Owner reopen for adjust only).
* **M23 Audit:** Immutable. Export needs owner perm. View report logs.
* **M24 Search:** Unified search.
* **M25 Extras:** SMS at Final. Scannable QR shows validity.
* **M26 Reports:** Profit = Price - Cost - Comm. Gap-catching report (overrides, prints, voids).

## 9. Modules 27-31 (Provisional)
* **M27 Queue:** Daily serial reset.
* **M28 Dr Fees/Wholesale:** Dr collects -> pays center later on wholesale price list. 
* **M29 Refunds:** Unlocked = yes. Locked = no (except exceptions). Not performed = refund only. Refund = original channel.
* **M30 Home Col:** Mobile sample taken.
* **M31 Outside Lab:** Status: Sent -> Received. Cost accrues to outside lab ledger.

## 10. State Machines
* **Bill:** Draft -> Confirmed -> Cancelled (if no lock).
* **Line:** Ordered -> Sample taken (LOCK/STOCK) -> In progress -> Completed. Exits: Cancelled (before lock), Not Performed (refund only). Imaging locks at Completed.
* **Report:** Draft -> Final -> Superseded (on correct) / Cancelled (on owner unlock).
* **Day:** Open -> Closed -> Reopened.

## 11. Permission Matrix Summary
* **Owner:** Overrides all, sees money/comm, reopens days, edits catalogs, manages users.
* **Admin:** Overrides standard rules, approves corrections/refunds, writes-off limits.
* **Receptionist/Cashier:** Bills, discounts (within limits), takes pay, hands reports, opens/closes day.
* **Tech/Dr:** Only own tests. Enters results, finalizes (per rule). Sees NO money/comm.
* **Vendor:** Masked read-only.

## 12. Data Model Constraints
* IDs: gapless counter in transaction lock.
* Relational logs: Audit, Payment, Journal, Stock are insert-only.
* Temporary IDs map 1:1 to Final IDs on sync.
* Settings tables handle configs (D68 multi-tenant prep).

## 13. Master Decision Log (1-68 Mapping)
| Rule | Summary | Rule | Summary |
|---|---|---|---|
| 1 | States: Draft, Conf, Cancel | 35 | Adjust stock = any admin, log |
| 2 | Amend unlocked, else Supp | 36 | Comm snapshot at billing |
| 3 | Discount limits/overrides | 37 | Ledger: accrued/paid/bal |
| 4 | Package = Bundle or Disc | 38 | Line cancel reverses comm |
| 5 | Price list auto-cascade | 39 | Config split (2 referrers max) |
| 6 | Round whole taka at bill | 40 | Comm max % cap per test |
| 7 | Minimal walk-in reg | 41 | Comm rate/amt Owner-only |
| 8 | Pay visits fee first | 42 | Visit fee = liability |
| 9 | No overpay/adv/credit | 43 | Dr: 2 ledger balances |
| 10| Pay errors = reversal | 44 | Consultant payout via ledger |
| 11| Due write-off limit | 45 | Expected cash formula |
| 12| Mobile matching (CSV/Man) | 46 | Day open till closed |
| 13| No-sample lock at Complete| 47 | Owner reopen day (adjusts) |
| 14| Owner unlock same day | 48 | Cash variance limits |
| 15| Invalid sample = no re-run | 49 | Expenses = simple entry |
| 16| Lock covers lines only | 50 | Basic acct reports (V1) |
| 17| Lock is per line | 51 | IDs: Pat, Vis, Bill, Sam, Rep |
| 18| Refund orig channel + Admin | 52 | Gapless counter via lock |
| 19| Test states (extensions) | 53 | Soft merge patients |
| 20| Sample event/time | 54 | Pat edit -> Clerical correction |
| 21| Two turn clocks (pat/lab) | 55 | Age structure (Y/M/D) |
| 22| Approval rules per test | 56 | Configurable SOD list |
| 23| No auto-alerts (V1) | 57 | Audit logs Acting Role |
| 24| Ref ranges versioned | 58 | 4-6 digit PIN switch |
| 25| Limits (impossible vals) | 59 | Visiting Drs: NO login |
| 26| Report V-IDs immutable | 60 | Vendor read-only masked |
| 27| Corrections (Clerical/Res) | 61 | Audit kept forever |
| 28| 4 fixed templates | 62 | SMS English only |
| 29| Outside lab workflow | 63 | SMS at Final state |
| 30| Stock deducted per type/test| 64 | Offline device queue / Temp IDs |
| 31| Wastage needs user/reason | 65 | DB-level backups |
| 32| Negative stock warned | 66 | A4/A5/80mm print formats |
| 33| Base units & factors | 67 | Migration via CSV |
| 34| Batch/Expiry deferred | 68 | Multi-tenant db rule prep |

## 14. Build Order & Exclusions
* **Excluded V1:** Auto-machine imports, delta checks, patient portal, Bangla SMS, inventory valuation/batches, full balance sheets.
* **Phases:** 0(Stack) -> 1(Core/Users) -> 2(Frontdesk/Bill) -> 3(Lab/Report) -> 4(Money/Acct) -> 5(Owner/Dash) -> 6(Offline) -> 7(Pilot).
* **Hard Tests:** Exact cash match, lock strictness, offline parallel sync conflict resolution.